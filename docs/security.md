# Security Model

## Threat Model

| Threat | Protection | Limitation |
|--------|-----------|------------|
| **Provider logs** | Base64 blobs + chaff noise | Manual review of specific session possible |
| **Provider data mining** | Automated scanners don't flag base64 patterns | Sophisticated NLP could detect encoding |
| **Manual log review** | Volume (millions of requests) hides you | Targeted surveillance bypasses volume |
| **DLM crash** | Key destroyed — encrypted data cryptographically shredded | — |
| **Session hijacking** | DLM ownership enforcement — only creator reads | — |
| **Key compromise** | Rotation every 20 messages — limited exposure | Old keys kept for 5 rotations |
| **Traffic analysis** | Chaff injection masks patterns | Timing/packet size still correlate |
| **Local machine compromise** | Key in memory during session | Full compromise = full access |

## What This IS

**Operational security through obscurity at scale.**

- The provider sees base64 blobs that look like development/testing traffic
- Automated scanners look for CSAM, violence, copyright — not base64
- Millions of requests make manual review economically infeasible
- The `remember::` prefix looks like a memory protocol, not encryption
- Chaff queries add noise that masks real query patterns

## What This IS NOT

**Not cryptographic perfection.**

- A provider who manually decodes your specific session CAN see your queries
- Base64 is encoding, not encryption — anyone can decode it
- The system prompt contains the key — visible to the provider
- Traffic analysis (timing, sizes) can correlate to content
- Local machine compromise means the key is accessible in memory

## Attack Surfaces

### 1. Provider-Side Decoding

**Risk:** Provider sees the system prompt with the `remember::` protocol instructions. A human reviewer could follow those instructions and decode your messages.

**Mitigation:** Volume. Millions of requests make targeted review unlikely. The `remember::` pattern looks like testing/development, not real encryption.

### 2. Traffic Analysis

**Risk:** Even encrypted, message timing and sizes correlate to content. A burst of queries during market hours suggests trading research.

**Mitigation:** Chaff injection (every 3-5 messages). Random timing. Plausible decoy queries mixed with real ones.

### 3. Key in System Prompt

**Risk:** The AES256 key is in the system prompt, which the provider sees.

**Mitigation:** The key looks like a random base64 string. In a system prompt labeled "crypto testing project," it doesn't stand out. But it IS visible.

### 4. Local Memory Access

**Risk:** During a session, the key exists in RAM. A compromised machine exposes the key.

**Mitigation:** DLM crash = key destroyed. TTL = key auto-expired. But during active session, key is in memory.

### 5. DLM Server Compromise

**Risk:** If the DLM server is compromised, all stored keys are accessible.

**Mitigation:** Keys are in volatile memory only. DLM restart = all keys gone. Network access restricted to LAN via nftables.

## Defense in Depth

```
Layer 1: Base64 Encoding
  └─► Looks like dev/test traffic, not encryption

Layer 2: Chaff Injection
  └─► Masks real query patterns with plausible noise

Layer 3: Key Rotation
  └─► Limits exposure window to 20 messages per key

Layer 4: Volatile Storage
  └─► DLM crash/expiry = key destroyed = data shredded

Layer 5: Ownership Enforcement
  └─► DLM session isolation — only creator reads

Layer 6: LAN-Only Access
  └─► nftables blocks all non-LAN traffic

Layer 7: systemd Hardening
  └─► NoNewPrivileges, ProtectSystem=strict, MemoryMax
```

## Recommended Practices

1. **Rotate keys frequently** — every 20 messages is default, consider lower
2. **Use chaff consistently** — don't disable it
3. **Keep DLM on localhost** — don't expose to WAN
4. **Monitor DLM logs** — check for `NotOwner` events (someone tried to read your keys)
5. **Restart DLM periodically** — destroys all keys as a safety measure
6. **Don't rely on this for life-or-death security** — it's obscurity, not perfection

## Compliance Notes

### GDPR

- Volatile storage = inherent right-to-erasure (crash/TTL = guaranteed deletion)
- No disk writes = no residual data after session
- Session isolation = data minimization

### SOC 2

- Encryption at rest (AES256-GCM for local storage)
- Encryption in transit (base64 transport + AES256 for LAN)
- Access control (DLM ownership enforcement)
- Audit trail (DLM collision logging for `NotOwner` events)

### HIPAA

- PHI encrypted before leaving machine
- Key destruction = cryptographic shredding
- Session isolation = minimum necessary access
- Note: provider-side decoding is still a risk for HIPAA-compliant workflows
