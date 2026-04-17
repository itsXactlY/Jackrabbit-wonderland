# API Reference

## crypto_middleware.CryptoMiddleware

### Constructor

```python
CryptoMiddleware(master_key: Optional[str] = None)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `master_key` | `str` | `None` | Base64-encoded AES256 key for storage encryption. Auto-generated if `None`. |

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `session_start` | `() → str` | System prompt header | Generate session key, reset counters |
| `session_start_from_dlm` | `(dlm_client, session_id) → str` | Header | Generate key + store in DLM |
| `encrypt` | `(plaintext, key=None) → str` | Base64 blob | AES256-GCM encrypt |
| `decrypt` | `(ciphertext_b64, key=None) → str` | Plaintext | Decrypt (tries key history) |
| `encrypt_outbound` | `(message) → Tuple[str, bool]` | `(blob, should_chaff)` | Encrypt + counter + chaff check |
| `format_for_provider` | `(encrypted_blob) → str` | Wire format | Format with decode instruction |
| `decrypt_inbound` | `(response) → Optional[str]` | Plaintext | Extract + decrypt from response |
| `chaff_message` | `() → str` | Decoy query | Random from CHAFF_POOL |
| `chaff_formatted` | `() → str` | Decoy query | Same as chaff_message |
| `rotate_key` | `() → str` | Encrypted rotation | Generate new key, archive old |
| `encrypt_for_storage` | `(data) → str` | Base64 blob | Encrypt with master key |
| `decrypt_from_storage` | `(data) → str` | Plaintext | Decrypt with master key |
| `status` | `() → dict` | Status dict | Session state |

### Status Dict

```python
{
    "session_active": bool,
    "session_key_suffix": str,      # "...last12chars"
    "message_count": int,
    "chaff_interval": int,
    "rotation_interval": int,
    "keys_in_history": int,
    "master_key_suffix": str,
}
```

### Wire Format

```
Encrypted blob structure (after base64 decode):
  Bytes 0-15:   Nonce (16 bytes, random per message)
  Bytes 16-31:  GCM Tag (16 bytes, authentication)
  Bytes 32+:    Ciphertext (variable length)
```

---

## remember_protocol.RememberProtocol

### Constructor

```python
RememberProtocol(master_key: Optional[str] = None, chaff_interval: int = 5)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `master_key` | `str` | `None` | AES256 key for storage. Auto-generated if `None`. |
| `chaff_interval` | `int` | `5` | Send chaff every N real messages |

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `encode` | `(plaintext) → str` | `remember::<base64>` | Encode for LLM transport |
| `decode` | `(wire_msg) → Optional[str]` | Plaintext | Decode from wire |
| `decode_response` | `(llm_response) → str` | Extracted text | Extract base64 from LLM output |
| `format_conversation` | `(messages) → list` | OpenAI format | Encode message list |
| `system_prompt_header` | `(extra_context="") → str` | Persona header | System prompt injection |
| `should_chaff` | `() → bool` | Boolean | Check if chaff needed |
| `chaff_message` | `() → str` | Decoy query | Random plaintext chaff |
| `chaff_encoded` | `() → str` | Encoded chaff | Chaff as remember:: protocol |
| `store_encrypted` | `(data, key=None) → str` | `AES:<blob>` or `B64:<blob>` | Encrypt for local storage |
| `recall_encrypted` | `(stored, key=None) → str` | Plaintext | Decrypt from local storage |
| `rotate_storage_key` | `() → str` | New key | Rotate master key |
| `store_key_in_dlm` | `(dlm_client, session_id, ttl=7200) → bool` | Success | Store master key in DLM |
| `status` | `() → dict` | Status dict | Protocol state |

### Backward Compatibility

```python
CryptoMiddleware = RememberProtocol  # Line 316
```

---

## dlm_vault.DLMVault

### Constructor

```python
DLMVault(host: str = "127.0.0.1", port: int = 37373, identity: str = "hermes-crypto-vault")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"127.0.0.1"` | DLM server host |
| `port` | `int` | `37373` | DLM server port |
| `identity` | `str` | `"hermes-crypto-vault"` | DLM identity (ownership) |

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `health_check` | `() → bool` | Online status | Check DLM connectivity |
| `store_key` | `(session_id, key_b64, ttl=3000) → bool` | Success | Store AES256 key |
| `retrieve_key` | `(session_id) → Optional[str]` | Key or None | Retrieve key |
| `destroy_key` | `(session_id) → bool` | Success | Destroy key explicitly |
| `lock_session` | `(session_id, ttl=300) → bool` | Locked | Acquire distributed lock |
| `unlock_session` | `(session_id) → bool` | Unlocked | Release lock |
| `is_session_locked` | `(session_id) → bool` | Locked status | Check lock |
| `store_message` | `(msg_id, encrypted_blob, ttl=3000) → bool` | Success | Store encrypted message |
| `retrieve_message` | `(msg_id) → Optional[str]` | Blob or None | Retrieve message |
| `destroy_message` | `(msg_id) → bool` | Success | Destroy message |

### Free Functions

```python
create_encrypted_session(dlm_host, dlm_port, session_ttl) → dict
end_encrypted_session(session: dict) → bool
```

---

## crypto_plugin.CryptoPlugin

### Constructor

```python
CryptoPlugin(config: dict = None)
```

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable/disable plugin |
| `dlm_host` | `str` | `"127.0.0.1"` | DLM server host |
| `dlm_port` | `int` | `37373` | DLM server port |
| `session_ttl` | `int` | `7200` | Key TTL in seconds |
| `encrypt_tools` | `bool` | `True` | Encrypt tool results |
| `encrypt_memory` | `bool` | `True` | Encrypt Neural Memory |
| `chaff_interval` | `int` | `5` | Chaff every N messages |

### Methods

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `on_session_start` | `(system_prompt) → str` | Modified prompt | Inject crypto header |
| `on_tool_result` | `(tool_name, result) → str` | Encrypted result | Encrypt tool output |
| `on_neural_store` | `(content, label=None) → str` | Encrypted | Encrypt for memory storage |
| `on_neural_recall` | `(encrypted_content) → str` | Decrypted | Decrypt from memory |
| `on_session_end` | `() → None` | — | Destroy key, cleanup |
| `get_status` | `() → dict` | Status | Plugin state |

### Factory Function

```python
create_plugin_instance(config=None) → CryptoPlugin
```

### Standalone Injection

```python
inject_into_system_prompt(system_prompt, config=None) → str
```

---

## lan_gateway

### CLI Flags

```bash
python3 lan_gateway.py [--port PORT] [--tcp-port PORT] [--bind ADDR] [--no-crypto]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `8080` | HTTP port |
| `--tcp-port` | `37374` | Raw TCP port |
| `--bind` | `0.0.0.0` | Bind address |
| `--no-crypto` | off | Disable encryption |

### HTTP API

#### GET /

Returns Web UI (HTML).

#### GET /status

```json
{
    "status": "ok",
    "gateway": "running",
    "dlm": "online",
    "dlm_version": "JackrabbitDLM v...",
    "crypto": "AES256-GCM",
    "sessions": 1,
    "time": "2026-04-17T14:30:00"
}
```

#### GET /sessions

```json
{
    "sessions": [
        {"id": "abc123", "created": "...", "last_active": "...", "dlm": true}
    ]
}
```

#### POST /command

Request:
```json
{"cmd": "status", "args": "", "session_id": null, "encrypted": false}
```

Response: varies by command (see Commands table above).
