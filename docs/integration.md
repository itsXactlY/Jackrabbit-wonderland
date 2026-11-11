# Integration Guide

## Ariadne

Point Ariadne's model at Wonderland, so every provider call is Remember-Protocol encoded:

```bash
container/run-podman.sh configure-ariadne   # rewrites model: in ~/ariadne/config.yaml
```

LAN clients run an agent turn through the gateway with `cmd:ariadne`
(`ariadne-agent --home $ARIADNE_HOME -- <message>`; set `ARIADNE_BIN` if it is not on PATH).

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
content = "User is looking for ਮਕਾਨ ਖੋਜ in ਕੈਮਰੂਨ"
encrypted = rp.store_encrypted(content)
# Store `encrypted` in Neural Memory database
```

### Decrypt on Recall

```python
# After recalling
stored = "AES:base64(nonce+tag+ciphertext)"
plaintext = rp.recall_encrypted(stored)
```

---

## iOS Shortcuts

### Quick Ariadne Query

1. Open Shortcuts app
2. Create new shortcut
3. Add "Get Contents of URL" action:
   - URL: `http://192.168.0.2:8080/command`
   - Method: POST
   - Headers: `Content-Type: application/json`
   - Body: `{"cmd":"ariadne","args":"what is 2+2"}`
4. Add "Get Dictionary from Input"
5. Add "Get Dictionary Value" → key: `final`
6. Add "Speak" or "Show Result"

### Voice Control

"Hey Siri, ask Ariadne [your question]"

---

## Tasker (Android)

```yaml
Profile: Ariadne Query
  Event: AutoVoice Recognized
  Task:
    1. HTTP Post
       Server: http://192.168.0.2:8080/command
       Data: {"cmd":"ariadne","args":"%avmessage"}
    2. JavaScriptlet
       var result = JSON.parse(global('HTTPD'));
       setGlobal('ARIADNE_RESULT', result.final);
    3. Say %ARIADNE_RESULT
```

---

## Programmatic Usage

### Basic Encryption

```python
import sys
sys.path.insert(0, "~/projects/mazemaker-stack/gateway")
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

session = create_encrypted_session(session_ttl=3000)
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
wire = rp.encode("Find houses in ਕੈਮਰੂਨ")
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
  ariadne_query:
    url: "http://192.168.0.2:8080/command"
    method: POST
    headers:
      Content-Type: "application/json"
    payload: '{"cmd":"ariadne","args":"{{ command }}"}'
```

### Grafana / Monitoring

```bash
# DLM health endpoint (via gateway)
curl http://192.168.0.2:8080/status | jq '.dlm'

# Systemd status
systemctl is-active jackrabbit-dlm@$USER
systemctl is-active mazemaker-gateway@$USER
```
