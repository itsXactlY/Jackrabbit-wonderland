# Components

## 1. crypto_middleware.py (283 lines)

AES256-GCM encryption core. The foundation of all encryption operations.

### Class: CryptoMiddleware

```python
from crypto_middleware import CryptoMiddleware

cm = CryptoMiddleware(master_key=None)  # auto-generates if None
```

### Key Methods

#### session_start() → str
Generate a new AES256 session key and return the system prompt header.

```python
header = cm.session_start()
# Returns:
# ## SESSION_CRYPTO ##
# ## KEY: <base64_key> ##
# ## MODE: AES256-GCM ##
# ## Hermes encrypted research session. ##
# ## All messages and responses are AES256 encrypted. ##
# ## This is a privacy research project. ##
# ## END CRYPTO HEADER ##
```

#### encrypt(plaintext, key=None) → str
AES256-GCM encrypt. Returns base64 blob (nonce + tag + ciphertext).

```python
blob = cm.encrypt("secret message")
# blob = base64(nonce[16] + tag[16] + ciphertext[n])
```

#### decrypt(ciphertext_b64, key=None) → str
Decrypt. Tries current key first, then key history (for rotated keys).

```python
plaintext = cm.decrypt(blob)
# Raises ValueError if all keys fail
```

#### encrypt_outbound(message) → Tuple[str, bool]
Encrypt + increment message counter. Returns (encrypted_blob, should_chaff).

```python
blob, needs_chaff = cm.encrypt_outbound("Find houses in Brandenburg")
if needs_chaff:
    chaff = cm.chaff_message()
```

#### format_for_provider(encrypted_blob) → str
Format encrypted blob for the provider — includes decode instruction.

```python
wire = cm.format_for_provider(blob)
# "ENC_MSG: <blob>\n\nDecode the above message..."
```

#### rotate_key() → str
Generate new key, archive old key (max 5 in history). Returns encrypted rotation metadata.

```python
rotation_blob = cm.rotate_key()
# Old key added to _key_history
# decrypt() will try old keys if new key fails
```

#### encrypt_for_storage(data) / decrypt_from_storage(data)
Encrypt/decrypt with master key (for persistent storage like Neural Memory).

```python
encrypted = cm.encrypt_for_storage("Neural memory content")
plaintext = cm.decrypt_from_storage(encrypted)
```

### Chaff Pool

20 plausible decoy queries. Selected randomly via `secrets.choice()`.

```
"What's the current price of Bitcoin?"
"How do I make sourdough starter?"
"Explain Docker networking basics."
"How does a CPU cache work?"
"Best budget mechanical keyboard 2026?"
...
```

### CLI

```bash
python3 crypto_middleware.py init       # Generate session, print header
python3 crypto_middleware.py encrypt "text"  # Encrypt a message
python3 crypto_middleware.py decrypt "blob"  # Decrypt a blob
python3 crypto_middleware.py chaff      # Generate chaff message
python3 crypto_middleware.py demo       # Full demo
```

---

## 2. remember_protocol.py (408 lines)

Base64 transport layer for LLM communication. LLMs can decode base64 natively — they can't do AES256.

### Class: RememberProtocol

```python
from remember_protocol import RememberProtocol

rp = RememberProtocol(master_key=None, chaff_interval=5)
```

### Transport Layer (Base64)

#### encode(plaintext) → str
Encode for LLM transport. Prefixes with `remember::`.

```python
wire = rp.encode("Find houses in Brandenburg")
# "remember::RmluZCBob3VzZXMgaW4gQnJhbmRlbmJ1cmc="
```

#### decode(wire_msg) → Optional[str]
Decode from wire. Handles `remember::`, `MSG:`, `ENC_MSG:` prefixes.

```python
plaintext = rp.decode(wire)
# "Find houses in Brandenburg"
```

#### decode_response(llm_response) → str
Extract decoded content from LLM response. Scans for base64 blocks (20+ chars), decodes valid ones, returns plaintext if none found.

```python
# LLM might respond with base64 back
decoded = rp.decode_response(llm_response)
```

#### format_conversation(messages) → list
Encode a list of user messages in OpenAI format with `remember::` encoding.

```python
formatted = rp.format_conversation([
    "What is quantum computing?",
    {"role": "user", "content": "Explain Docker networking"}
])
# Returns list of dicts with encoded content
```

### System Prompt

#### system_prompt_header(extra_context="") → str
Returns "The Architect's Anomaly" persona. Looks like character AI to the provider.

The persona instructs the LLM to:
- Decode `remember::<base64>` messages internally
- Respond naturally to decoded content
- Never mention the encoding

### Storage Layer (AES256-GCM)

#### store_encrypted(data, key=None) → str
Encrypt for local persistence. Prefixed with `AES:` or `B64:` (fallback).

```python
stored = rp.store_encrypted("sensitive data")
# "AES:base64(nonce+tag+ciphertext)"
```

#### recall_encrypted(stored, key=None) → str
Decrypt from local storage. Auto-detects `AES:` vs `B64:` prefix.

```python
plaintext = rp.recall_encrypted(stored)
```

### Backward Compatibility

```python
CryptoMiddleware = RememberProtocol  # alias
```

### CLI

```bash
python3 remember_protocol.py encode "text"   # Encode for LLM
python3 remember_protocol.py decode "b64"    # Decode from wire
python3 remember_protocol.py header          # Print system prompt
python3 remember_protocol.py chaff           # Generate chaff
python3 remember_protocol.py store "text"    # Encrypt for storage
python3 remember_protocol.py recall "blob"   # Decrypt from storage
python3 remember_protocol.py demo            # Full demo
```

---

## 3. dlm_vault.py (340 lines)

Bridge to JackrabbitDLM via Robert's DLMLocker client library.

### Class: DLMVault

```python
from dlm_vault import DLMVault

vault = DLMVault(
    host="127.0.0.1",
    port=37373,
    identity="hermes-crypto-vault"
)
```

### Key Storage

#### store_key(session_id, key_b64, ttl=3000) → bool
Store AES256 key in DLM volatile memory.

```python
ok = vault.store_key("abc123", cm.session_key, ttl=7200)
# Key stored as: vault-key-abc123
# Only identity "hermes-crypto-vault" can read it
```

#### retrieve_key(session_id) → Optional[str]
Retrieve key. Returns `None` if not found or not owner.

#### destroy_key(session_id) → bool
Explicitly destroy key (don't wait for TTL).

### Session Locking

#### lock_session(session_id, ttl=300) → bool
Acquire distributed lock. Prevents concurrent agent runs on same session.

#### unlock_session(session_id) → bool
Release lock.

#### is_session_locked(session_id) → bool
Check lock status.

### Message Storage

#### store_message(msg_id, encrypted_blob, ttl=3000) → bool
Store encrypted message blob in DLM.

#### retrieve_message(msg_id) → Optional[str]
Retrieve message blob.

#### destroy_message(msg_id) → bool
Destroy stored message.

### Full Session Integration

```python
from dlm_vault import create_encrypted_session, end_encrypted_session

# Create (health check → generate key → store in DLM → acquire lock)
session = create_encrypted_session(dlm_host="127.0.0.1", dlm_port=37373, session_ttl=3000)
# Returns: {session_id, system_prompt_header, middleware, vault, key_location, key_ttl, verified}

# Use
cm = session["middleware"]
blob = cm.encrypt("secret")

# End (destroy key → release lock)
end_encrypted_session(session)
```

### CLI

```bash
python3 dlm_vault.py health    # Check DLM server
python3 dlm_vault.py session   # Create encrypted session
python3 dlm_vault.py demo      # Full integration test (9 steps)
```

---

## 4. crypto_plugin.py (237 lines)

Drop-in plugin for hermes-agent. Injects encryption into the session pipeline.

### Class: CryptoPlugin

```python
from crypto_plugin import CryptoPlugin

plugin = CryptoPlugin(config={
    "enabled": True,
    "dlm_host": "127.0.0.1",
    "dlm_port": 37373,
    "session_ttl": 7200,
    "encrypt_tools": True,
    "encrypt_memory": True,
    "chaff_interval": 5,
})
```

### Integration Hooks

#### on_session_start(system_prompt) → str
Called when session starts. Generates key, stores in DLM, injects crypto header into system prompt.

```python
modified_prompt = plugin.on_session_start(original_prompt)
# Crypto preamble injected at TOP
```

#### on_tool_result(tool_name, result) → str
Called after tool execution. Encrypts result before it enters context.

Skips encryption for tools that need to be readable by the LLM:
- `neural_remember`, `neural_recall`, `neural_think`, `neural_graph`
- `skill_view`, `skills_list`
- `read_file`, `search_files`, `browser_snapshot`

#### on_neural_store(content, label=None) → str
Called before storing in Neural Memory. Returns AES256-encrypted content.

#### on_neural_recall(encrypted_content) → str
Called after recalling from Neural Memory. Returns decrypted content.

#### on_session_end()
Called when session ends. Destroys key in DLM vault.

### Installation

```bash
# Option A: Copy
cp /opt/hermes-crypto/crypto_plugin.py ~/.hermes/plugins/

# Option B: Symlink
ln -s /opt/hermes-crypto/crypto_plugin.py ~/.hermes/plugins/crypto_plugin.py

# Option C: Config
# Add to ~/.hermes/config.yaml:
plugins:
  - crypto_plugin
```

---

## 5. lan_gateway.py (584 lines)

HTTP + TCP server for controlling Hermes from any LAN device.

### Components

#### SessionManager
Manages encrypted sessions with DLM vault fallback.

#### GatewayHandler (HTTP)
Serves Web UI on `/` and JSON API on `/command` (POST).

#### raw_tcp_server
Netcat-compatible TCP server on port 37374. Accepts JSON, returns JSON.

### Commands

| Command | Args | Description |
|---------|------|-------------|
| `status` | — | Gateway + DLM status |
| `sessions` | — | List active sessions |
| `session` | — | Create new encrypted session |
| `kill` | session_id | Destroy a session |
| `hermes` | command | Run hermes CLI (e.g. `"ask what is 2+2"`) |
| `pulse` | topic | Run PULSE search |
| `shell` | command | Run shell command (LAN only, some blocked) |
| `encrypt` | text | Encrypt a message |
| `decrypt` | blob | Decrypt a message |
| `chaff` | — | Generate cover traffic message |
| `key` | — | Rotate session key |

### Web UI

Mobile-friendly dark theme (amber #f5b731 on dark #1a1a24). Quick actions, command selector, session indicator.

### Access Methods

```bash
# Browser
http://192.168.0.2:8080

# curl
curl -X POST http://192.168.0.2:8080/command \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"status"}'

# netcat
echo '{"cmd":"chaff"}' | nc 192.168.0.2 37374

# iOS Shortcuts
HTTP POST → http://192.168.0.2:8080/command
Body: {"cmd":"hermes","args":"ask what is 2+2"}
```

### CLI

```bash
python3 lan_gateway.py                    # Start on 0.0.0.0:8080
python3 lan_gateway.py --port 9090        # Custom port
python3 lan_gateway.py --tcp-port 37375   # Custom TCP port
python3 lan_gateway.py --bind 192.168.0.2 # Bind to specific IP
python3 lan_gateway.py --no-crypto        # Disable encryption (debug)
```

---

## 6. install.sh (11,347 bytes)

One-command deployment script.

### What It Does

1. Checks for existing JackrabbitDLM (clones to `/home/JackrabbitDLM` if missing)
2. Installs `pycryptodome` (only pip dependency)
3. Copies files to `/opt/hermes-crypto/`
4. Installs systemd services (`jackrabbit-dlm@$USER`, `hermes-gateway@$USER`)
5. Adds nftables rules (LAN-only access)
6. Starts both services
7. Verifies everything works

### Flags

```bash
sudo bash install.sh              # Full install
sudo bash install.sh --check      # Verify only
sudo bash install.sh --uninstall  # Remove everything
sudo bash install.sh --no-firewall # Skip nftables
```

### Systemd Services

```ini
# jackrabbit-dlm@.service
# Volatile crypto vault. MemoryMax=256M. NoNewPrivileges.
ExecStart=/usr/bin/python3 /home/JackrabbitDLM/JackrabbitDLM 0.0.0.0 37373

# hermes-gateway@.service
# HTTP :8080 + TCP :37374. MemoryMax=128M. Depends on jackrabbit-dlm.
ExecStart=/usr/bin/python3 /opt/hermes-crypto/lan_gateway.py --port 8080 --tcp-port 37374
```

### nftables Rules

```nft
# LAN only — 192.168.0.0/24
ip saddr 192.168.0.0/24 tcp dport { 8080, 37373, 37374 } accept
```
