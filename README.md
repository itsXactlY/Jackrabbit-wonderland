# Hermes-Jackrabbit-wonderland-crypto-layer

> Zero-knowledge AES256 encryption for [Hermes Agent](https://github.com/NousResearch/hermes-agent).
> Your data stays yours. The provider sees noise.

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

1. **Session start**: Generate random AES256 key, store in DLM (volatile memory, 2h TTL)
2. **System prompt**: Inject `## KEY: <base64> ##` header — looks like dev config
3. **Messages**: Hermes encrypts before sending to provider, decrypts responses
4. **Chaff**: Every 3-5 messages, a plausible decoy query is sent ("What's the price of Bitcoin?")
5. **Key rotation**: Every 20 messages, new key generated, old key kept for decrypting history
6. **Session end**: Key destroyed (explicitly or TTL expiry)

**What the provider sees:**
- A system prompt with a key string (looks like "crypto testing project")
- Base64 encrypted blobs in user messages
- The LLM's confused attempts at decoding them
- Periodic normal queries (chaff)
- **Nobody reviews this.** Automated scanners look for CSAM/violence/copyright, not base64.

**What the provider does NOT see:**
- Your actual queries (house search, trading analysis, PULSE research)
- Neural Memory contents (encrypted at rest with master key)
- Tool results (optionally encrypted before entering context)

## Install

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

### Option A: Plugin (recommended)

```bash
cp /opt/hermes-crypto/crypto_plugin.py ~/.hermes/plugins/
```

The plugin automatically:
- Generates a session key on new sessions
- Injects the crypto header into the system prompt
- Encrypts tool results before they enter context
- Encrypts Neural Memory entries at rest

### Option B: Manual

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
