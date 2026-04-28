# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**hermes-crypto** is a zero-knowledge AES256-GCM encryption layer that sits between [Hermes Agent](https://github.com/NousResearch/hermes-agent) and its AI provider. The provider sees base64 blobs and chaff noise — not plaintext queries. Keys live exclusively in volatile memory via JackrabbitDLM and are auto-destroyed on TTL expiry or crash.

The sole external Python dependency is `pycryptodome`. Everything else is stdlib.

## Commands

### Tests

```bash
# Full suite (114 tests)
python3 tests/run_all.py

# Individual suites
python3 tests/run_all.py crypto    # 51 tests — AES256-GCM, nonce, tamper, rotation, memory
python3 tests/run_all.py gateway   # 22 tests — HTTP API, concurrent sessions, session bomb
python3 tests/run_all.py dlm       # 18 tests — key lifecycle, TTL, locking, identity isolation
python3 tests/run_all.py plugin    # 23 tests — plugin lifecycle, tool encryption, neural memory
```

Gateway and DLM tests require a running JackrabbitDLM server on `:37373`. Crypto and plugin tests are standalone.

### Running Components Directly

```bash
# Check if JackrabbitDLM is reachable
python3 dlm_vault.py health

# Create an encrypted session end-to-end
python3 dlm_vault.py session

# Crypto middleware CLI
python3 crypto_middleware.py demo
python3 crypto_middleware.py encrypt "my secret query"
python3 crypto_middleware.py chaff

# Start the LAN gateway
python3 lan_gateway.py                  # default :8080 HTTP, :37374 TCP
python3 lan_gateway.py --port 9090
python3 lan_gateway.py --no-crypto      # debug mode
```

### Deployment

```bash
# Podman (recommended)
container/run-podman.sh build
container/run-podman.sh start
container/run-podman.sh status
container/run-podman.sh configure-hermes   # sync host Hermes CLI to Wonderland

# Native systemd
sudo bash install.sh
sudo bash install.sh --check
sudo bash install.sh --uninstall
sudo bash install.sh --no-firewall

# Service management (native)
systemctl status jackrabbit-dlm@$USER
systemctl status hermes-gateway@$USER
journalctl -u hermes-gateway@$USER -f
```

### Environment Variables

Key env vars recognized across all components:

| Variable | Default | Purpose |
|---|---|---|
| `JACKRABBITDLM_HOME` / `DLM_DIR` | `/home/JackrabbitDLM` | Path to JackrabbitDLM install |
| `DLM_HOST` | `127.0.0.1` | DLM server address |
| `DLM_PORT` | `37373` | DLM server port |
| `GATEWAY_PORT` | `8080` | HTTP gateway port |
| `RAW_TCP_PORT` | `37374` | Raw TCP (netcat) port |
| `SESSION_TTL` | `3000` | Key TTL in seconds (max safe: 3543) |
| `HERMES_BIN` | `hermes` | Path to Hermes CLI |
| `WONDERLAND_UPSTREAM_PROVIDER` | `openrouter` | Upstream AI provider |
| `WONDERLAND_UPSTREAM_BASE_URL` | — | Provider base URL |
| `WONDERLAND_UPSTREAM_API_KEY` | — | Provider API key |

## Architecture

### Component Map

```
crypto_middleware.py   — AES256-GCM core: encrypt/decrypt, key rotation, chaff
remember_protocol.py   — Base64 transport layer for LLM wire format (LLMs can't do AES256)
dlm_vault.py           — Bridge to JackrabbitDLM: volatile key storage, session locking
crypto_plugin.py       — Hermes-agent plugin: hooks into session start/end/tool results
lan_gateway.py         — HTTP :8080 + raw TCP :37374 control interface, Web UI, proxy
```

### Data Flow

1. `CryptoMiddleware.session_start()` generates a random AES256 key and returns a crypto header string injected into the Hermes system prompt (looks like "developer testing encryption").
2. `DLMVault.store_key()` puts the key into JackrabbitDLM's volatile memory with a TTL. Key never touches disk.
3. Outbound messages are AES256-GCM encrypted → base64 → sent to provider wrapped in `ENC_MSG: <blob>` format. Every 3–5 messages a chaff query fires. Every 20 messages the key rotates (old key kept in `_key_history` for decrypting prior messages, max history depth 5).
4. `CryptoPlugin` wires the above into Hermes agent hooks: `on_session_start`, `on_tool_result`, `on_session_end`.
5. `lan_gateway.py` exposes all of this to LAN devices: browser Web UI, JSON API (`POST /command`), and raw TCP for netcat/iOS Shortcuts.

### Two Layers — Hard Separation

- **Provider transport** (`remember_protocol.py`): base64 with `remember::` prefix. This is the **only** thing that goes to real LLM endpoints. LLMs can decode base64 natively. The system prompt is `RememberProtocol.system_prompt_header()` — a persona that instructs the model to decode `remember::` messages. No AES, no AES keys, ever.
- **Local storage** (`crypto_middleware.py`): AES256-GCM with `pycryptodome`. Used only for Neural Memory, tool results, PULSE cache on the local machine. The DLM vault stores only these local AES keys — they never leave the pod.

**The rule:** `remember_openai_messages()` in `lan_gateway.py` is the only code path that produces messages for upstream providers. It calls `rp.encode(text)` (base64) and `rp.system_prompt_header()` — nothing from `CryptoMiddleware`. The blocklist `AES_UPSTREAM_BLOCKLIST` strips any AES markers that might appear in user-provided content before encoding.

### Blob Format

AES256-GCM blobs are `base64(nonce[16] + tag[16] + ciphertext)`. The `decrypt()` method tries the current session key first, then falls back through `_key_history` to handle post-rotation messages.

### JackrabbitDLM Dependency

JackrabbitDLM is an external single-file Python server (not in this repo) that must be running on `:37373`. It is not bundled — the installer clones it, or Podman includes it in the image. `DLMLocker.py` (its client library) is imported at runtime from `DLM_DIR`.

DLM locker names follow a consistent scheme:
- `vault-key-{session_id}` — AES256 session keys
- `vault-msg-{msg_id}` — encrypted messages
- `lock-{session_id}` — session mutex locks

### Podman/Container Layout

`container/podman-compose.yml` runs two services:
- `dlm` container: runs JackrabbitDLM on internal port 37373, exposed as `WONDERLAND_DLM_PORT` (default 17373)
- `gateway` container: runs `lan_gateway.py`, talks to `dlm` container via DNS name `dlm`

`container/wonderland.env` is the single source of truth for downstream projects (`OPENAI_BASE_URL=http://127.0.0.1:18080/v1`, `OPENAI_MODEL=wonderland`). Copy from `gateway.env.example` to `gateway.env` for upstream provider config.

## Design Constraints

- **Zero-knowledge server**: The gateway and DLM vault never decrypt user queries. `CryptoMiddleware.decrypt()` is for client-side use only — this is enforced by design, not just convention.
- **Volatile keys only**: Keys must never be written to disk. The DLM's in-memory TTL is the only storage. Crash = key destroyed = encrypted data cryptographically shredded.
- **DLMLocker ownership**: Each DLM locker name must be unique per session. Reusing a locker name across sessions causes `NotOwner` errors. The `identity` parameter on `DLMVault` defaults to `"hermes-crypto-vault"` — all lockers under one vault instance share this identity.
- **Printable-only DLM values**: JackrabbitDLM's `DataStore` field requires printable strings. Binary keys must be base64-encoded before storage.
- **TTL cap**: Maximum anonymous DLM TTL is 3543 seconds. `SESSION_TTL` defaults to 3000 for safety margin.
