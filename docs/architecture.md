# Architecture

## System Overview

```
┌──────────────┐          ┌──────────────────┐
│ Any Device   │  HTTP    │  LAN Gateway     │
│ (phone,      │─────────►│  :8080           │
│  laptop,     │  TCP     │  :37374          │
│  tablet)     │─────────►│                  │
└──────────────┘          └────────┬─────────┘
                                   │
                          ┌────────┴────────┐
                          │                 │
                   ┌──────▼──────┐   ┌──────▼──────┐
                   │ Jackrabbit  │   │   Hermes    │
                   │ DLM         │   │   Agent     │
                   │ :37373      │   │             │
                   │             │   │ ┌─────────┐ │
                   │ Key Vault   │   │ │Plugin   │ │
                   │ (volatile)  │   │ │         │ │
                   │             │   │ │Remember │ │
                   │ • Keys      │   │ │Protocol │ │
                   │ • Locks     │   │ │         │ │
                   │ • Messages  │   │ │AES256   │ │
                   │             │   │ │GCM      │ │
                   └─────────────┘   │ └────┬────┘ │
                                     │      │      │
                                     │  ┌───▼────┐ │
                                     │  │Provider│ │
                                     │  │sees:   │ │
                                     │  │base64  │ │
                                     │  │blobs   │ │
                                     │  └────────┘ │
                                     └─────────────┘
```

## Component Stack

```
┌─────────────────────────────────────────────────────┐
│                    Access Layer                      │
│  Browser │ curl │ netcat │ iOS Shortcuts │ Tasker   │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│                  LAN Gateway                         │
│  lan_gateway.py (584 lines)                         │
│  HTTP :8080  │  Raw TCP :37374  │  Web UI           │
│  SessionManager │ CommandExecutor │ GatewayHandler   │
└───────────────────────┬─────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│   Remember   │ │  DLM Vault  │ │   Crypto    │
│   Protocol   │ │  dlm_vault  │ │   Plugin    │
│              │ │             │ │             │
│ Transport:   │ │ Key Storage │ │ Hermes      │
│ Base64       │ │ Session Lock│ │ Integration │
│              │ │ Msg Storage │ │             │
│ Storage:     │ │             │ │ Hooks:      │
│ AES256-GCM   │ │ DLMLocker   │ │ on_start    │
│              │ │ bridge      │ │ on_tool     │
│ Chaff        │ │             │ │ on_store    │
│ Key Rotation │ │             │ │ on_end      │
└───────┬──────┘ └──────┬──────┘ └─────────────┘
        │               │
┌───────▼───────────────▼────────────────────────────┐
│              JackrabbitDLM Server                   │
│  JackrabbitDLM (1003 lines, Robert APM Darin)      │
│                                                     │
│  • Volatile key-value store (memory only)           │
│  • Distributed lock manager                         │
│  • TTL-bound entries (auto-expiry)                  │
│  • Ownership enforcement (session isolation)        │
│  • select.poll() event loop (1024+ concurrent)      │
│  • Custom Encoder/Decoder injection                 │
│  • JSON-over-TCP protocol                           │
└─────────────────────────────────────────────────────┘
```

## Data Flow

### Session Lifecycle

```
1. SESSION START
   └─► Generate AES256 key (os.urandom(32) → base64)
   └─► Store key in DLM vault (volatile, 2h TTL)
   └─► Inject crypto header into system prompt
   └─► Acquire session lock (prevent concurrent runs)

2. MESSAGE LOOP
   └─► User message → AES256-GCM encrypt → base64
   └─► Every 3-5 messages: inject chaff (decoy query)
   └─► Every 20 messages: rotate key (old key kept for decrypt)
   └─► Provider receives: base64 blob + "decode and respond" instruction

3. SESSION END
   └─► Destroy key in DLM vault (explicit)
   └─► Release session lock
   └─► OR: TTL expires → key auto-destroyed
   └─► OR: DLM crash → key destroyed (volatile memory gone)
```

### Encryption Flow

```
Plaintext: "ਕਿੰਨੀਆਂ ਭਾਸ਼ਾਵਾਂ ਕੈਮਰੂਨ ਵਿੱਚ ਬੋਲੀਆਂ ਜਾਂਦੀਆਂ ਹਨ"
    │
    ▼
AES256-GCM Encrypt
    │  Key: 32 bytes (from DLM vault)
    │  Nonce: 16 bytes (random per message)
    │  Tag: 16 bytes (GCM authentication)
    │
    ▼
Blob = Nonce (16) + Tag (16) + Ciphertext (variable)
    │
    ▼
Base64 Encode
    │
    ▼
Wire: "remember::Tm9uY2UxNjE2VGFnMTYxNkNpcGhlcnRleHQ..."
    │
    ▼
Provider Log: [looks like a memory protocol with base64 payload]
```

### Key Rotation Flow

```
Message 20:
    │
    ├─► Generate new AES256 key
    ├─► Append old key to _key_history (max 5)
    ├─► Encrypt rotation metadata with old key
    ├─► Switch to new key for outbound
    └─► decrypt() tries current key first, then history

Why keep old keys?
    └─► Provider might respond to a message encrypted with the old key
    └─► History limited to 5 keys = bounded exposure window
```

## JackrabbitDLM Integration

### Why JackrabbitDLM

| Property | Benefit |
|----------|---------|
| **Volatile by default** | Data lives in RAM. Crash = gone. For crypto keys, this is a *feature*. |
| **TTL-bound** | Mandatory Time-To-Live. Session ends → TTL expires → key auto-destroys. |
| **Ownership enforcement** | Only the `ID` that stored a value can retrieve it. Session isolation built-in. |
| **Custom Encoder/Decoder** | `Locker(..., Encoder=your_aes, Decoder=your_aes)` — the integration point. |
| **Zero dependencies** | stdlib only (`socket`, `select`, `json`). No pip, no config, no cluster. |
| **Language agnostic** | JSON-over-TCP. Python, Go, shell, browser, iOS — anything that speaks TCP. |

### The Blind Vault Concept

Robert's original design: the server is deliberately "blind" to data semantics.

```python
# From JackrabbitDLM source:
# "This is NOT security. It is a ZERO effort obfuscation that focuses on the
#  protocol and data at the binary level, making it deliberately unstable,
#  forcing full parsing instead of shortcut analysis."
```

The server maps every byte to a 2-character alphabetic pair before transmission. JSON keys are randomly shuffled on the wire. Raw traffic looks like alphabet soup.

We inject real AES256-GCM via the `Encoder`/`Decoder` parameters:

```python
Locker(filename, ..., Encoder=aes256_encrypt, Decoder=aes256_decrypt)
```

**The Blind Vault doesn't see what's inside. It just holds the door shut.**

### DLM Namespace Convention

| Locker Name | Purpose | TTL |
|-------------|---------|-----|
| `vault-key-{session_id}` | AES256 session key | 3000s (default) |
| `vault-msg-{msg_id}` | Encrypted message blob | 3000s |
| `lock-{session_id}` | Session lock (concurrency) | 300s |
| `health-check` | DLM connectivity test | 10s |

All lockers use identity `hermes-crypto-vault` — only this identity can read/write.
