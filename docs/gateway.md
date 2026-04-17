# Gateway API

## Endpoints

### GET /

Returns the Web UI (HTML). Mobile-friendly dark theme.

### GET /status

Gateway + DLM status.

```bash
curl http://192.168.0.2:8080/status
```

```json
{
    "status": "ok",
    "gateway": "running",
    "dlm": "online",
    "dlm_version": "JackrabbitDLM v1.0",
    "crypto": "AES256-GCM",
    "sessions": 1,
    "time": "2026-04-17T14:30:00"
}
```

### GET /sessions

List active sessions.

```json
{
    "sessions": [
        {"id": "abc123def4", "created": "2026-04-17T14:00:00", "last_active": "2026-04-17T14:30:00", "dlm": true}
    ]
}
```

### POST /command

Main command interface.

**Request:**
```json
{
    "cmd": "hermes",
    "args": "ask what is 2+2",
    "session_id": "abc123def4",
    "encrypted": false
}
```

**Response:** varies by command.

---

## Commands

### status

No args. Returns gateway + DLM status.

```bash
curl -X POST http://192.168.0.2:8080/command -d '{"cmd":"status"}'
```

### sessions

No args. Lists active sessions.

### session

Creates new encrypted session.

```json
{"created": {"session_id": "abc123", "crypto_header": "...", "dlm_vault": true, "key_suffix": "...xyz"}}
```

### kill

Destroy a session.

```json
{"cmd":"kill","args":"abc123def4"}
```

### hermes

Run hermes CLI command.

```bash
curl -X POST http://192.168.0.2:8080/command \
  -d '{"cmd":"hermes","args":"ask what is 2+2"}'
```

### pulse

Run PULSE search.

```bash
curl -X POST http://192.168.0.2:8080/command \
  -d '{"cmd":"pulse","args":"AI regulation 2026"}'
```

### shell

Run shell command. Some dangerous commands blocked (`rm -rf`, `mkfs`, `dd if=`, fork bombs, `chmod 777`).

```bash
curl -X POST http://192.168.0.2:8080/command \
  -d '{"cmd":"shell","args":"uptime"}'
```

### encrypt

Encrypt a message.

```bash
curl -X POST http://192.168.0.2:8080/command \
  -d '{"cmd":"encrypt","args":"secret message"}'
```

```json
{"wire": "remember::c2VjcmV0IG1lc3NhZ2U=", "decoded_check": "secret message"}
```

### decrypt

Decrypt a message.

```bash
curl -X POST http://192.168.0.2:8080/command \
  -d '{"cmd":"decrypt","args":"c2VjcmV0IG1lc3NhZ2U="}'
```

### chaff

Generate chaff (cover traffic).

```json
{"chaff": "What's the current price of Bitcoin?", "wire": "remember::V2hhdCdzIHRoZQ=="}
```

### key

Rotate session key.

```json
{"rotated": true, "new_key_suffix": "...abc123def4", "keys_in_history": 1}
```

---

## Raw TCP Protocol

Port 37374. Netcat compatible.

```bash
# Send JSON, get JSON back
echo '{"cmd":"status"}' | nc 192.168.0.2 37374

# Plain text treated as shell command
echo "uptime" | nc 192.168.0.2 37374
```

Response is always JSON + newline.

---

## Web UI

### Quick Actions

- **Status** — Gateway + DLM status
- **Sessions** — List active sessions
- **New Session** — Create encrypted session
- **Chaff** — Generate cover traffic
- **PULSE** — Prompt for topic, run search
- **Hermes** — Prompt for command, run hermes

### Command Selector

Dropdown with all commands. Args input field. Execute button.

### Session Indicator

Header shows `session:abc123` when a session is active. Auto-updates on session creation.
