---
name: memory-plugin-debugging
description: Debug and fix memory provider plugin loading issues in Hermes agent — missing imports, broken dependencies, and configuration problems.
category: software-development
---

# Memory Plugin Debugging

## When to Use
When a memory provider (neural, honcho, etc.) fails to load, shows "available=False" unexpectedly, or logs "loaded but no provider instance found".

## How Memory Plugins Load

The loading chain in `plugins/memory/__init__.py`:

1. `discover_memory_providers()` scans `plugins/memory/<name>/` directories
2. `_load_provider_from_dir()` imports the plugin's `__init__.py`
3. Tries `register(ctx)` pattern first — uses `_ProviderCollector` to capture the provider
4. Falls back to finding a `MemoryProvider` subclass
5. Calls `provider.is_available()` to check if dependencies are present

## Step-by-Step Debugging

### 1. Test Import Chain Directly
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / ".hermes" / "hermes-agent"))

# Try importing the plugin module directly
from plugins.memory.neural import NeuralMemoryProvider
provider = NeuralMemoryProvider()
print(f"Available: {provider.is_available()}")
```

If this fails, the error message tells you exactly which import is broken.

### 2. Common Import Failures

**Missing `tool_error` in `tools/registry.py`:**
Both neural and honcho plugins do `from tools.registry import tool_error`. If this function is missing, the module import fails silently during `_load_provider_from_dir()`.

Fix — add to `tools/registry.py`:
```python
def tool_error(message: str) -> str:
    """Return a JSON error string for tool responses."""
    return json.dumps({"error": message})
```

**Missing `memory_provider.py` ABC:**
Plugins import `from agent.memory_provider import MemoryProvider`. The file must exist at:
- `/home/alca/.hermes/hermes-agent/agent/memory_provider.py`

If missing, copy from `/home/alca/.hermes/agent/memory_provider.py`.

**Broken transitive imports in plugin dependencies:**
The neural plugin's `is_available()` tries to import `memory_client` from the project directory. Check:
```python
import importlib.util
spec = importlib.util.find_spec("memory_client")
print(spec)  # None = not found
```

Fix: ensure `~/projects/neural-memory-adapter/python/` is on sys.path (the plugin does this in `initialize()`).

### 3. Check Plugin Discovery Output
```python
from plugins.memory import discover_memory_providers
for name, desc, available in discover_memory_providers():
    print(f"{name}: available={available}")
```

### 4. Verify Config
```python
import yaml
config = yaml.safe_load(open(Path.home() / ".hermes" / "config.yaml"))
print(config.get("memory", {}))
```

Key fields: `provider`, `memory_enabled`, and provider-specific config under `memory.<provider>`.

### 5. Check Gateway Logs
```bash
journalctl --user -u hermes-gateway --since "5 min ago" --no-pager
```

Look for:
- `Memory provider 'X' loaded but no provider instance found` — register() failed
- Import errors — missing dependency
- `X init failed:` — initialize() threw

### 6. After Fixing — Restart Gateway
```bash
hermes gateway restart
```

Memory providers are loaded per-session, not at gateway startup. A restart ensures the next session picks up fixes.

## Verification Checklist
- [ ] Plugin module imports without errors
- [ ] `discover_memory_providers()` shows provider as available=True
- [ ] `load_memory_provider("name")` returns a provider instance
- [ ] `provider.initialize("test")` succeeds
- [ ] `provider.handle_tool_call(...)` works for at least one tool
- [ ] Gateway restarts without errors
- [ ] Gateway logs show no "no provider instance found" warnings

## Key Architecture Notes
- Only ONE memory provider active at a time (set via `memory.provider` in config)
- `_ProviderCollector` is a fake context that captures `register_memory_provider()` calls
- Plugin submodules (config.py, memory_client.py, etc.) are pre-registered in `sys.modules` before the main module loads
- The honcho plugin also uses `tool_error` — fixing it fixes both plugins
