# Hermes-Jackrabbit-wonderland-crypto-layer

> Zero-knowledge AES256 encryption for [Hermes Agent](https://github.com/NousResearch/hermes-agent).
> Your data stays yours. The provider sees noise.

## Documentation

Full production documentation in [`docs/`](docs/):

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design, data flow, DLM integration |
| [Components](docs/components.md) | Deep-dive into all 6 modules |
| [API Reference](docs/api.md) | Every class, method, and CLI command |
| [Deployment](docs/deployment.md) | Install, systemd, firewall, verification |
| [Configuration](docs/configuration.md) | All config options and environment variables |
| [Security Model](docs/security.md) | Threat model, attack surface, limitations |
| [Integration](docs/integration.md) | Hermes plugin, PULSE, Neural Memory, iOS, Tasker |
| [Gateway](docs/gateway.md) | HTTP/TCP API, Web UI, device access |
| [Troubleshooting](docs/troubleshooting.md) | 12 common issues with solutions |
| [Use Cases](USECASES.md) | 10 primary + 32 application areas |

## Quick Start

### Podman

```bash
git clone https://github.com/itsXactlY/hermes-crypto.git
cd hermes-crypto

# Build once, then run the DLM + gateway pod.
container/run-podman.sh build
container/run-podman.sh start

# Point any OpenAI-compatible project at the Wonderland proxy.
set -a
. "$PWD/container/wonderland.env"
set +a

# Make the host Hermes CLI use the same Wonderland gateway by default.
container/run-podman.sh configure-hermes
```

The Podman gateway exposes `http://127.0.0.1:18080/v1` and the local model alias
`wonderland`. Keep `container/wonderland.env` as the single source of truth for
projects that should use this gateway. Hermes Agent is configured from that same
file through `container/run-podman.sh configure-hermes`.

When Wonderland calls a real LLM endpoint, it uses the Remember Protocol only:
`remember::<base64>` payloads plus the Remember Protocol system header. AES
headers, AES ciphertext, and AES key material are never sent upstream.

### Native systemd

```bash
git clone https://github.com/itsXactlY/hermes-crypto.git
cd hermes-crypto
sudo bash install.sh
```

## Testing

117 tests across 4 suites — crypto, gateway, DLM vault, plugin.

```bash
# Run everything
python3 tests/run_all.py

# Run specific suite
python3 tests/run_all.py crypto     # 51 tests — AES256-GCM, nonce, tamper, rotation, memory
python3 tests/run_all.py gateway    # 25 tests — HTTP API, Remember Protocol upstream, concurrency
python3 tests/run_all.py dlm        # 18 tests — key lifecycle, TTL, locking, identity isolation
python3 tests/run_all.py plugin     # 23 tests — plugin lifecycle, tool encryption, neural memory
```

**What's tested:**
- Round-trip: ASCII, Unicode (äöüß, emoji, arabic, CJK), empty, NUL bytes, 1MB payloads
- Security: nonce uniqueness (1000 iterations), tamper detection (bit-flip), truncated blobs, garbage input
- Key management: rotation chain, history eviction, auto-rotation, master key vs session key isolation
- Concurrency: 20 parallel sessions, 50 threads on same session, 500 session bomb, 1000 DLM key bomb
- Memory: tracemalloc plateau verification, 10k encrypt baseline, 50-cycle warmup comparison
- DLM: TTL expiry, lock/unlock, identity isolation, overwrite, 5KB payload limit detection
- Gateway: all API commands, response format, kill via args, roundtrip built-in, 100KB payloads

## What This Is
```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   The provider logs everything.                               ║
║   But logs full of base64 blobs are just... logs.             ║
║   Nobody reviews them. Nobody flags them.                     ║
║   Your house search. Your trades. Your thoughts.              ║
║   Hidden in plain sight.                                      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

## What This Is

A four-component encryption layer for Hermes Agent:

| Component | Role |
|-----------|------|
| **JackrabbitDLM** | Volatile key vault — keys in memory only, TTL-bound, auto-destroy on crash |
| **crypto_middleware** | AES256-GCM encrypt/decrypt, key rotation, chaff injection |
| **crypto_plugin** | Hermes-agent plugin — injects crypto header into system prompt |
| **lan_gateway** | HTTP + raw TCP server — control from any LAN device (browser, curl, netcat, iOS Shortcuts) |

## The Foundation: JackrabbitDLM

> *This project stands on the shoulders of a rabbit.*
> — Not Newton, but close enough.

### What It Is

[JackrabbitDLM](https://github.com/rapmd73/JackrabbitDLM) is a **Distributed Lock Manager** — a single-file Python server (1,003 lines) that manages locks and volatile key-value state across a network. Think Redis, ZooKeeper, or Etcd, but:

- **Zero dependencies** (stdlib only — `socket`, `select`, `json`)
- **Language-agnostic** — JSON-over-TCP, any device that speaks TCP can talk to it
- **Single file** — no install, no config, no cluster. `python3 JackrabbitDLM 0.0.0.0 37373` and it runs

Written by Robert APM Darin. Copyright 2021.

### The Blind Vault

Here's where it gets interesting. Robert's own words from the source:

```python
# This is NOT security. It is a ZERO effort obfuscation that foccuses on the
# protocol and data at the binary level, making it deliberately unstable,
# forcing full parsing instead of shortcut analysis.
```

The server has a built-in **table-based byte encoder** — every byte gets mapped to a 2-character alphabetic pair before transmission. JSON keys are randomly shuffled on the wire. The result: raw TCP traffic looks like alphabet soup. Not encrypted. Not secure. But *invisible to casual inspection*.

Robert calls this "ZERO effort security that is effective in a large number of cases that really shouldn't ever happen." He's right. And he left the door wide open:

```python
# If you want REAL security, CHANGE the en(de)coder here and in the DLMLocker.py
```

The client library (`DLMLocker.py`, 314 lines) accepts **custom Encoder and Decoder functions**:

```python
Locker(filename, ..., Encoder=None, Decoder=None, ...)
#               ↑                    ↑
#         Your AES256          Your AES256
#         encrypt function     decrypt function
```

Two lines of code. That's the gap between "obfuscation" and "AES256-GCM encryption." Robert built the scaffold. We injected the cipher.

### Why It's Perfect for Crypto

| Property | Why It Matters |
|----------|----------------|
| **Volatile by default** | Data lives in memory. Server crash = data gone. For crypto keys, this is a *feature* — crash = key destroyed = cryptographically shredded. |
| **TTL-bound** | Every key has mandatory Time-To-Live. Session ends, TTL expires, key auto-destroys. No cleanup code needed. |
| **Ownership enforcement** | Only the `ID` that stored a value can retrieve it. Session isolation is built into the protocol, not bolted on. |
| **Printable strings only** | Robert's design choice: `DataStore` must be printable, no escaped chars. Forces base64 encoding of binary data. Sounds limiting — actually perfect for our threat model (base64 blobs look like dev code, not secrets). |
| **Any framework, any language** | The protocol is JSON. You can control DLM from Python, Go, a shell script, a browser fetch, or an iOS Shortcut. No client library required (though DLMLocker makes it nicer). |
| **select.poll() event loop** | Non-blocking I/O. Handles 1,024+ concurrent connections. The gateway doesn't bottleneck. |
| **Memory exhaustion protection** | Configurable payload limits (default 10MB). A rogue client can't crash the vault. |
| **Collision logging** | `NotOwner` events are tracked — if someone tries to read your keys, you know. |

### The Philosophy

Robert designed JackrabbitDLM as infrastructure glue — something that sits between distributed processes and keeps them from stepping on each other. Locks for shared resources. Volatile state for coordination. TTL for self-healing (crashed processes auto-free their locks).

He deliberately made the wire format "deliberately unstable" — not to be secure, but to force proper parsing. He added the encoder/decoder injection point because he knew: *the server shouldn't decide what security means. The client should.*

That philosophy is why hermes-crypto exists. The DLM doesn't know it's holding AES256 keys. It doesn't care. It's a volatile key-value store with ownership and TTL. We just told it the keys are strings and the values are base64. It treats them like any other data.

**The Blind Vault doesn't see what's inside. It just holds the door shut.**

### What We Built On Top

```
JackrabbitDLM (Robert's foundation)
    │
    ├── Volatile key-value store     →  we store AES256 session keys here
    ├── Ownership enforcement        →  only our identity reads our keys
    ├── TTL auto-expiry              →  keys self-destruct when their DLM TTL expires
    ├── Custom Encoder/Decoder API   →  we inject AES256-GCM here
    ├── JSON-over-TCP protocol       →  we build HTTP/TCP gateways on top
    └── select.poll() event loop     →  handles concurrent LAN connections
```

Everything in this repo — the middleware, the plugin, the gateway, the installer — is possible because Robert left the door open. The `Encoder`/`Decoder` parameters in `DLMLocker.__init__()` are the single integration point that makes the entire crypto layer work.

```
hermes-crypto adds:
    │
    ├── crypto_middleware.py    →  AES256-GCM (the "real security" Robert invited)
    ├── dlm_vault.py            →  Bridge to DLM via DLMLocker with consistent identity
    ├── crypto_plugin.py        →  Hermes system prompt injection
    ├── lan_gateway.py          →  HTTP + TCP control interface
    └── install.sh              →  One-command deployment
```

## Architecture

```
┌──────────────┐  HTTP/TCP   ┌──────────────────┐
│ Any Device   │ ──────────► │  LAN Gateway     │
│ (phone,      │             │  :8080 / :37374  │
│  laptop,     │             └────────┬─────────┘
│  tablet)     │                      │
└──────────────┘              ┌───────┴────────┐
                              │                │
                       ┌──────▼──────┐  ┌──────▼──────┐
                       │ Jackrabbit  │  │   Hermes    │
                       │ DLM         │  │   Agent     │
                       │ :37373      │  │             │
                       │             │  │ ┌─────────┐ │
                       │ Key Vault   │  │ │AES256   │ │
                       │ (volatile)  │  │ │encrypt/ │ │
                       │             │  │ │decrypt  │ │
                       └─────────────┘  │ └────┬────┘ │
                                        │      │      │
                                        │  ┌───▼────┐ │
                                        │  │Provider│ │
                                        │  │sees:   │ │
                                        │  │base64  │ │
                                        │  │blobs   │ │
                                        │  └────────┘ │
                                        └─────────────┘
```

## How It Works

1. **Client config**: Projects point to `http://127.0.0.1:18080/v1` with model `wonderland`.
2. **Provider transport**: Wonderland prepends the Remember Protocol system header.
3. **Messages**: User/tool payloads are sent upstream as `remember::<base64>`.
4. **Guardrail**: AES headers, AES ciphertext, and key material are stripped before upstream dispatch.
5. **Local state**: DLM/session state stays inside the Wonderland pod.
6. **Session end**: Local state is destroyed explicitly or by TTL expiry.

**What the provider sees:**
- A Remember Protocol system prompt
- `remember::<base64>` payloads in user/tool messages
- Periodic normal queries (chaff)
- **Nobody reviews this.** Automated scanners look for CSAM/violence/copyright, not base64.

**What the provider does NOT see:**
- AES headers, AES ciphertext, AES keys, or DLM key material
- Your actual queries (house search, trading analysis, PULSE research)
- Neural Memory contents (encrypted at rest with master key)
- Tool results (optionally encrypted before entering context)

## Install

### Podman

```bash
container/run-podman.sh build
container/run-podman.sh start
container/run-podman.sh status
```

For projects that should use Wonderland:

```bash
set -a
. /home/alca/projects/hermes-crypto/container/wonderland.env
set +a
```

This exports `OPENAI_BASE_URL=http://127.0.0.1:18080/v1` and
`OPENAI_MODEL=wonderland` for any OpenAI-compatible client.

For the host Hermes CLI, sync the named custom provider and default model from
the same file:

```bash
container/run-podman.sh configure-hermes
```

The Podman image is Wonderland-only: JackrabbitDLM plus the gateway/encryption
proxy. It does not install or run a second `hermes-agent` inside the pod.

### Native systemd

```bash
git clone https://github.com/itsXactlY/hermes-crypto.git
cd hermes-crypto
sudo bash install.sh
```

**What the installer does:**
1. Checks for existing JackrabbitDLM (clones if missing)
2. Installs `pycryptodome` (only pip dependency)
3. Copies files to `/opt/hermes-crypto/`
4. Installs systemd services (auto-start on boot)
5. Adds nftables rules (LAN-only access)
6. Starts both services
7. Verifies everything works

**Flags:**
```bash
bash install.sh              # Full install
bash install.sh --check      # Verify only
bash install.sh --uninstall  # Remove everything
bash install.sh --no-firewall # Skip nftables
```

## Access

After install, control from any device on your LAN:

```bash
# Browser (any device)
http://192.168.0.2:8080

# curl
curl -X POST http://192.168.0.2:8080/command \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"status"}'

# netcat
echo '{"cmd":"chaff"}' | nc 192.168.0.2 37374

# iOS Shortcuts
HTTP POST to http://192.168.0.2:8080/command
Body: {"cmd":"hermes","args":"ask what is 2+2"}
```

### Gateway Commands

| Command | Args | Description |
|---------|------|-------------|
| `status` | — | Gateway + DLM status |
| `sessions` | — | List active sessions |
| `session` | — | Create new encrypted session |
| `kill` | session_id | Destroy a session |
| `hermes` | command | Run hermes CLI (e.g. `"ask what is 2+2"`) |
| `pulse` | topic | Run PULSE research |
| `shell` | command | Run shell command (LAN only, some blocked) |
| `encrypt` | text | Encrypt a message |
| `decrypt` | blob | Decrypt a message |
| `chaff` | — | Generate cover traffic message |
| `key` | — | Rotate session key |

## Hermes Integration

### Option A: Wonderland Provider (recommended)

```bash
container/run-podman.sh configure-hermes
```

Hermes uses the OpenAI-compatible Wonderland gateway. Real LLM endpoints receive
Remember Protocol payloads only.

### Option B: Legacy Direct Plugin

```bash
cp /opt/hermes-crypto/crypto_plugin.py ~/.hermes/plugins/
```

The plugin automatically:
- Generates a session key on new sessions
- Injects the crypto header into the system prompt for direct-plugin mode
- Encrypts tool results before they enter context
- Encrypts Neural Memory entries at rest

Do not use the legacy direct plugin as the upstream transport for Wonderland.

### Option C: Manual Local Crypto

```python
import sys
sys.path.insert(0, "/opt/hermes-crypto")
from crypto_middleware import CryptoMiddleware

cm = CryptoMiddleware()
header = cm.session_start()  # Add this to your system prompt

# Encrypt before sending
blob, chaff = cm.encrypt_outbound("my secret query")

# Decrypt after receiving
plaintext = cm.decrypt(response_blob)
```

## Services

```bash
# Status
systemctl status jackrabbit-dlm@$USER
systemctl status hermes-gateway@$USER

# Logs
journalctl -u jackrabbit-dlm@$USER -f
journalctl -u hermes-gateway@$USER -f

# Restart
sudo systemctl restart jackrabbit-dlm@$USER
sudo systemctl restart hermes-gateway@$USER
```

## nftables

The installer adds these rules (LAN-only):

```nft
# Hermes Crypto Gateway - LAN only
# JackrabbitDLM :37373, HTTP gateway :8080, Raw TCP :37374
ip saddr 192.168.0.0/24 tcp dport { 8080, 37373, 37374 } accept
```

If you skipped `--no-firewall`, add manually to `/etc/nftables.conf` and run:
```bash
sudo nft -f /etc/nftables.conf
```

## Threat Model

| Attack | Protection |
|--------|-----------|
| Provider logs | Base64 blobs + chaff noise — looks like crypto dev work |
| Provider data mining | Automated scanners don't flag base64 patterns |
| Manual log review | Volume (millions of requests) hides you |
| DLM crash | Key destroyed — encrypted data becomes cryptographically shredded |
| Session hijacking | DLM ownership enforcement — only creator can read |
| Key compromise | Key rotation every 20 messages — old keys limited exposure |

**What this does NOT protect against:**
- Provider who manually decrypts your specific session (unlikely but possible)
- Local machine compromise (key is in memory during session)
- Traffic analysis (timing, packet sizes correlate to encrypted content)

**The protection is obscurity, not cryptographic perfection.**
For most use cases, obscurity is enough.

## Requirements

- Python 3.8+
- `pycryptodome` (auto-installed)
- JackrabbitDLM (auto-cloned if missing)
- Linux with systemd + nftables
- sudo access (for services + firewall)

## Uninstall

```bash
sudo bash install.sh --uninstall
```

Removes services, files, and firewall rules. JackrabbitDLM is preserved (shared resource).

## Credits

- [JackrabbitDLM](https://github.com/rapmd73/JackrabbitDLM) by Robert APM Darin — the Blind Vault
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research — the agent
- [PULSE](https://github.com/itsXactlY/pulse-hermes) — multi-source research engine

## License

MIT — see [LICENSE](LICENSE).
