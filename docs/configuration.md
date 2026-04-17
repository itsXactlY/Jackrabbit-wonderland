# Configuration

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PULSE_SCRIPT` | `~/projects/pulse/scripts/pulse.py` | PULSE script path |
| `HERMES_BIN` | `hermes` (on PATH) | Hermes CLI binary |
| `DLM_HOST` | `127.0.0.1` | DLM server host |
| `DLM_PORT` | `37373` | DLM server port |

## Gateway Configuration

Edit constants at top of `lan_gateway.py`:

```python
GATEWAY_PORT = 8080          # HTTP port
RAW_TCP_PORT = 37374         # Raw TCP port
DLM_HOST = "127.0.0.1"      # DLM server
DLM_PORT = 37373             # DLM port
SESSION_TTL = 7200           # Session key TTL (seconds)
```

## Middleware Configuration

```python
cm = CryptoMiddleware(master_key=None)  # Auto-generates key

# Adjust intervals
cm.chaff_interval = 3       # Chaff every 3 messages (default: 3)
cm.rotation_interval = 20   # Rotate key every 20 messages (default: 20)
```

## Plugin Configuration

```python
plugin = CryptoPlugin(config={
    "enabled": True,          # Enable/disable
    "dlm_host": "127.0.0.1", # DLM host
    "dlm_port": 37373,       # DLM port
    "session_ttl": 7200,     # Key TTL (2 hours)
    "encrypt_tools": True,    # Encrypt tool results
    "encrypt_memory": True,   # Encrypt Neural Memory
    "chaff_interval": 5,      # Chaff every 5 messages
})
```

## DLM Vault Configuration

```python
vault = DLMVault(
    host="127.0.0.1",          # DLM server
    port=37373,                 # DLM port
    identity="hermes-crypto-vault"  # Ownership identity
)
```

## TTL Guidelines

| TTL | Use Case |
|-----|----------|
| 300s (5min) | Short session, quick query |
| 1800s (30min) | Standard research session |
| 3600s (1h) | Extended work session |
| 7200s (2h) | Default — full work session |
| 3543s | Maximum anonymous DLM TTL |

## Chaff Pool Customization

Edit `CHAFF_POOL` in `crypto_middleware.py` or `remember_protocol.py`:

```python
CHAFF_POOL = [
    "Your custom decoy query 1",
    "Your custom decoy query 2",
    # ... add more for better traffic masking
]
```

The pool should contain queries that:
- Are plausible for your usage pattern
- Are unrelated to your actual research
- Cover different topics (don't all be tech/finance)
