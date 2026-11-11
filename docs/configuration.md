# Configuration

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PULSE_SCRIPT` | `~/projects/pulse/scripts/pulse.py` | PULSE script path |
| `GATEWAY_PORT` | `8080` | HTTP/OpenAI-compatible gateway port |
| `RAW_TCP_PORT` | `37374` | Raw TCP gateway port |
| `DLM_HOST` | `127.0.0.1` | DLM server host |
| `DLM_PORT` | `37373` | DLM server port |
| `DLM_RETRY` | `1` | DLMLocker retry count per vault operation |
| `DLM_RETRY_SLEEP` | `0.2` | Seconds between DLMLocker retries |
| `DLM_TIMEOUT` | `2` | Socket timeout for each DLM attempt |
| `SESSION_TTL` | `3000` | Gateway session key TTL, in seconds |
| `JACKRABBITDLM_HOME` | `/home/JackrabbitDLM` | Location of `DLMLocker.py` and `JackrabbitDLM` |
| `PROXY_MODEL_ALIASES` | `wonderland,ariadne,proxy,default` | Model names that mean "this gateway", rewritten to the configured upstream model |
| `WONDERLAND_UPSTREAM_PROVIDER` | `openrouter` | Upstream OpenAI-compatible provider preset |
| `WONDERLAND_UPSTREAM_BASE_URL` | provider default | Upstream OpenAI-compatible base URL |
| `WONDERLAND_UPSTREAM_MODEL` | unset | Real upstream model used behind the `wonderland` alias |
| `WONDERLAND_UPSTREAM_API_KEY` | unset | Upstream provider API key |

## Wonderland Client Source

Projects that should use the local Wonderland gateway should load this file
instead of duplicating endpoint/model settings:

```bash
set -a
. /home/alca/projects/mazemaker-stack/gateway/container/wonderland.env
set +a
```

It defines:

| Variable | Value |
|----------|-------|
| `OPENAI_BASE_URL` | `http://127.0.0.1:18080/v1` |
| `OPENAI_API_BASE` | `http://127.0.0.1:18080/v1` |
| `OPENAI_MODEL` | `wonderland` |
| `MODEL` | `wonderland` |
| `WONDERLAND_BASE_URL` | `http://127.0.0.1:18080/v1` |
| `WONDERLAND_MODEL` | `wonderland` |

Ariadne reads its model from `~/ariadne/config.yaml` (`model.base_url`, `model.name`,
`model.api_key`). Sync it from the same file:

```bash
container/run-podman.sh configure-ariadne
```

After this, Ariadne runs on model `wonderland` at base URL `http://127.0.0.1:18080/v1`.

## Gateway Configuration

Set environment variables or edit constants at top of `lan_gateway.py`:

```python
GATEWAY_PORT = 8080          # HTTP port
RAW_TCP_PORT = 37374         # Raw TCP port
DLM_HOST = "127.0.0.1"      # DLM server
DLM_PORT = 37373             # DLM port
SESSION_TTL = 3000           # Session key TTL (seconds)
```

## Middleware Configuration

```python
cm = CryptoMiddleware(master_key=None)  # Auto-generates key

# Adjust intervals
cm.chaff_interval = 3       # Chaff every 3 messages (default: 3)
cm.rotation_interval = 20   # Rotate key every 20 messages (default: 20)
```

## DLM Vault Configuration

```python
vault = DLMVault(
    host="127.0.0.1",          # DLM server
    port=37373,                 # DLM port
    identity="mazemaker-gateway-vault"  # Ownership identity
)
```

## TTL Guidelines

| TTL | Use Case |
|-----|----------|
| 300s (5min) | Short session, quick query |
| 1800s (30min) | Standard research session |
| 3600s (1h) | Extended work session |
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
