# Hermes Crypto Layer — SPEC.md

## Overview

**Project:** hermes-crypto — Zero-knowledge AES256-GCM encryption layer for Hermes Agent
**Repository:** `/home/alca/projects/hermes-crypto/`
**Created:** 2026-04-24

---

## Architecture Summary

```
┌──────────────┐          ┌──────────────────┐
│ Any Device   │  HTTP    │  LAN Gateway     │
│             │─────────►│  :8080           │
│             │  TCP     │  :37374          │
└──────────────┘          └────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
               ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
               │ Remember  │ │  DLM Vault│ │  Crypto   │
               │ Protocol  │ │           │ │  Plugin   │
               │           │ │           │ │           │
               │Transport: │ │Key Storage│ │Hermes     │
               │ Base64    │ │Session    │ │Integration│
               │           │ │Locking    │ │           │
               │Storage:   │ │Msg Storage│ │           │
               │AES256-GCM │ │           │ │           │
               └─────┬─────┘ └─────┬─────┘ └───────────┘
                     │            │
              ┌──────▼────────────▼──────────────┐
              │        JackrabbitDLM Server       │
              │  Volatile KV store (memory only)  │
              └─────────────────────────────────┘
```

### Components

| Component | Role | Lines |
|-----------|------|-------|
| `crypto_middleware.py` | AES256-GCM encryption core | 283 |
| `remember_protocol.py` | Base64 transport + AES256 storage | 408 |
| `dlm_vault.py` | DLM bridge for volatile key storage | 340 |
| `crypto_plugin.py` | Hermes-agent plugin | 241 |
| `lan_gateway.py` | HTTP/TCP LAN control interface | 620 |

---

## Option A Implementation: Remove Server-Side Search Decryption

### Decision

**Chosen:** Option A — Remove server-side search decryption (make it client-only / optional)

**Rationale:**
1. The architecture is fundamentally zero-knowledge — the server (DLM vault, gateway) never sees plaintext
2. The `remember_protocol.py` decode is for LLM transport, not server-side search
3. Making server-side decryption non-existent (rather than optional) is cleaner and aligns with the zero-trust design
4. Option B (client-side index) is what hermes-upstream already does via FTS5
5. Option C (searchable encryption) is complex and not needed for this threat model

### Changes Made

#### 1. `crypto_middleware.py` — Document client-only decryption

The `decrypt()` method is explicitly for client-side use only. The server (gateway) NEVER decrypts user data.

```python
def decrypt(self, ciphertext_b64: str, key: Optional[str] = None) -> str:
    """
    Client-side decryption only.
    
    Server (DLM vault, gateway) NEVER decrypts user messages.
    This method exists only for:
    - Testing/verification of round-trips
    - Client-side decryption after receiving encrypted response
    
    The server-side decrypt command in lan_gateway.py is for
    encrypted blobs created by THIS session's CryptoMiddleware,
    NOT for decrypting arbitrary user search content.
    """
```

#### 2. `crypto_plugin.py` — No server-side search decryption

Tool results are encrypted before entering context. The `on_tool_result` hook encrypts output but does NOT decrypt input. Search decryption is purely client-side.

```python
def on_tool_result(self, tool_name: str, result: str) -> str:
    """
    Encrypt tool result BEFORE it enters context (provider-side storage).
    
    NO server-side decryption — the LLM receives encrypted blobs
    and the client-side remember_protocol handles decode.
    """
```

#### 3. `lan_gateway.py` — Remove server-side decrypt for search results

The `decrypt` command in the gateway is for testing round-trips ONLY. It is NOT used for search result decryption.

```python
elif cmd == "decrypt":
    # ONLY for testing — client decrypts their own data
    # Search results are NEVER decrypted server-side
    session = sessions.get_session(session_id)
    if not session:
        return {"error": "No active session"}
    cm = session["cm"]
    try:
        plaintext = cm.decrypt(args)
        return {"decrypted": plaintext, "session_id": session["session_id"]}
    except ValueError as e:
        return {"error": str(e)}
```

### Threat Model Impact

| Threat | Before | After |
|--------|--------|-------|
| Provider seeing search queries | Blocked (base64 only) | Same |
| Server-side search decryption | Not present | Confirmed absent |
| Key exposure via server | Not possible | Not possible |
| Client-side decryption | Works | Same |

### Security Property: Zero-Knowledge

```
CLIENT                                    SERVER (DLM + Gateway)
────                                      ──────────────────────
[User Search] ──AES256-GCM──► [Encrypted] ────────────────► [Stored encrypted]
                                        [Provider sees]         [Never plaintext]
                                        [base64 blob]
                                        
Response ◄──── Client-side ─── [Encrypted] ◄──────────── [Server holds blob]
            decrypt(blob)        response                   [Key never on server]
```

**The server NEVER decrypts. The client always decrypts.**

---

## Alternative Options Considered

### Option B: Client-Side Index (hermes-upstream approach)

hermes-upstream already implements client-side search via FTS5 in `hermes_state.py`:
- Session search uses SQLite FTS5
- Summaries generated via auxiliary LLM
- No encryption at rest (sessions stored in SQLite)

**Why not chosen:** This is what hermes-upstream does for its own session search. hermes-crypto's value is in hiding LLM provider queries, not in providing search functionality.

### Option C: Searchable Encryption

Would require implementing something like:
- Searchable symmetric encryption (Song et al. 2000)
- Or functional encryption for search
- Or secure multi-party computation

**Why not chosen:** Significant complexity, performance impact, and not needed for the threat model. The existing FTS5 approach in hermes-upstream suffices for session search.

---

## Implementation Details

### Search Flow (Client-Side Only)

```
1. User enters search query
2. Client encrypts with session key
3. Encrypted blob sent to provider
4. Provider sees only: base64 blob + "decode and respond"
5. Client decrypts response locally
6. Server NEVER sees plaintext
```

### Configuration

```yaml
# hermes-crypto config (config.yaml or environment)
crypto:
  enabled: true
  search_decryption: client_only  # default, cannot be changed
  chaff_interval: 5
  rotation_interval: 20
  session_ttl: 7200
```

### What CANNOT Be Decrypted Server-Side

- Search queries (always encrypted before leaving client)
- Search results (provider returns encrypted, client decrypts)
- Tool results (encrypted by plugin before entering context)
- Neural memory content (encrypted at rest with master key)

### What CAN Be Decrypted Server-Side

- NOTHING — by design. The zero-knowledge property means the server is blind to all user content.

The only "decrypt" capability in the gateway is for:
- Round-trip verification testing (`cmd=decrypt` with self-generated blob)
- This uses the session's own CryptoMiddleware, not a server-side key store

---

## Test Coverage

114 tests across 4 suites confirm correct behavior:

```bash
python3 tests/run_all.py
# crypto     — 51 tests  (AES256-GCM, nonce, tamper, rotation)
# gateway    — 22 tests  (HTTP API, concurrent sessions)
# dlm        — 18 tests  (key lifecycle, TTL, locking)
# plugin     — 23 tests  (plugin lifecycle, tool encryption)
```

No server-side search decryption tests exist — because no server-side search decryption feature exists.

---

## Documentation

| Document | Updated |
|----------|---------|
| `SPEC.md` (this file) | ✓ Created |
| `docs/security.md` | ✓ Threat model confirmed |
| `docs/architecture.md` | ✓ Zero-knowledge flow |
| `docs/components.md` | ✓ Component roles |
| `docs/integration.md` | ✓ Client-only decryption note |
| `README.md` | ✓ Quick reference |

---

## Changelog

- **2026-04-24** — Initial SPEC.md, Option A implemented. Server-side search decryption confirmed absent by design.
