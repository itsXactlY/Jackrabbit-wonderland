# Integration Guide

## Hermes Agent Plugin

### Option A: Copy Plugin

```bash
cp ~/projects/hermes-crypto/crypto_plugin.py ~/.hermes/plugins/
```

### Option B: Symlink

```bash
ln -s ~/projects/hermes-crypto/crypto_plugin.py ~/.hermes/plugins/crypto_plugin.py
```

### How It Works

1. On session start: `on_session_start()` generates key, stores in DLM, injects header
2. Before each tool result: `on_tool_result()` encrypts (except whitelisted tools)
3. Before Neural Memory store: `on_neural_store()` encrypts content
4. After Neural Memory recall: `on_neural_recall()` decrypts content
5. On session end: `on_session_end()` destroys key

### Whitelisted Tools (not encrypted)

These tools must remain readable by the LLM:
- `neural_remember`, `neural_recall`, `neural_think`, `neural_graph`
- `skill_view`, `skills_list`
- `read_file`, `search_files`, `browser_snapshot`

---

## PULSE Integration

Run PULSE searches through the encrypted gateway:

```bash
# Via gateway
curl -X POST http://192.168.0.2:8080/command \
  -d '{"cmd":"pulse","args":"AI regulation 2026"}'

# PULSE results are returned through the encrypted channel
```

The gateway calls `python3 ~/projects/pulse/scripts/pulse.py` with `--depth quick --emit json`.

---

## Neural Memory Integration

### Encrypt on Store

```python
from remember_protocol import RememberProtocol

rp = RememberProtocol()

# Before storing
content = "User is looking for freistehende Häuser in Brandenburg"
encrypted = rp.store_encrypted(content)
# Store `encrypted` in Neural Memory database
```

### Decrypt on Recall

```python
# After recalling
stored = "AES:base64(nonce+tag+ciphertext)"
plaintext = rp.recall_encrypted(stored)
```

### Via Plugin

```python
plugin = CryptoPlugin()

# Automatic — plugin hooks handle encryption
encrypted = plugin.on_neural_store(content)
decrypted = plugin.on_neural_recall(encrypted)
```

---

## iOS Shortcuts

### Quick Hermes Query

1. Open Shortcuts app
2. Create new shortcut
3. Add "Get Contents of URL" action:
   - URL: `http://192.168.0.2:8080/command`
   - Method: POST
   - Headers: `Content-Type: application/json`
   - Body: `{"cmd":"hermes","args":"ask what is 2+2"}`
4. Add "Get Dictionary from Input"
5. Add "Get Dictionary Value" → key: `stdout`
6. Add "Speak" or "Show Result"

### Voice Control

"Hey Siri, ask Hermes [your question]"

---

## Tasker (Android)

```yaml
Profile: Hermes Query
  Event: AutoVoice Recognized
  Task:
    1. HTTP Post
       Server: http://192.168.0.2:8080/command
       Data: {"cmd":"hermes","args":"%avmessage"}
    2. JavaScriptlet
       var result = JSON.parse(global('HTTPD'));
       setGlobal('HERMES_RESULT', result.stdout);
    3. Say %HERMES_RESULT
```

---

## Programmatic Usage

### Basic Encryption

```python
import sys
sys.path.insert(0, "~/projects/hermes-crypto")
from crypto_middleware import CryptoMiddleware

cm = CryptoMiddleware()
header = cm.session_start()

# Encrypt
blob, chaff = cm.encrypt_outbound("My secret query")

# Decrypt
plaintext = cm.decrypt(blob)
```

### Full DLM Session

```python
from dlm_vault import create_encrypted_session, end_encrypted_session

session = create_encrypted_session(session_ttl=7200)
cm = session["middleware"]

# Use...
blob = cm.encrypt("data")

# Cleanup
end_encrypted_session(session)
```

### Remember Protocol

```python
from remember_protocol import RememberProtocol

rp = RememberProtocol()

# Transport (for LLM)
wire = rp.encode("Find houses in Brandenburg")
plaintext = rp.decode(wire)

# Storage (for local persistence)
stored = rp.store_encrypted("sensitive data")
recalled = rp.recall_encrypted(stored)
```

---

## External System Integration

### Home Assistant

```yaml
rest_command:
  hermes_query:
    url: "http://192.168.0.2:8080/command"
    method: POST
    headers:
      Content-Type: "application/json"
    payload: '{"cmd":"hermes","args":"{{ command }}"}'
```

### Grafana / Monitoring

```bash
# DLM health endpoint (via gateway)
curl http://192.168.0.2:8080/status | jq '.dlm'

# Systemd status
systemctl is-active jackrabbit-dlm@$USER
systemctl is-active hermes-gateway@$USER
```
