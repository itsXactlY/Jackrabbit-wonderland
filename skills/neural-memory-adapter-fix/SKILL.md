---
name: neural-memory-adapter-fix
category: devops
description: Fix and configure neural-memory-adapter for 100% Hermes Agent compatibility
triggers:
  - neural memory not loading
  - tool_error missing
  - plugin compatibility issues
  - memory provider not available
---

# Neural Memory Adapter Fix

## Problem Symptoms
- Neural memory plugin fails to load
- Error: `cannot import name 'tool_error' from 'tools.registry'`
- Memory provider shows `available=False` despite correct config
- Plugin loads but `register()` fails silently

## Root Causes
1. **Missing `tool_error` function**: Both neural and honcho plugins import `from tools.registry import tool_error` but the function doesn't exist in `tools/registry.py`
2. **Outdated plugin files**: `hermes-plugin/memory_client.py` was older than `python/memory_client.py` (missing conflict detection)
3. **Broken installer**: `install.sh` had bugs (missing banner pth file, inconsistent numbering)

## Fix Steps

### 1. Add `tool_error` to `tools/registry.py`
```python
def tool_error(message: str) -> str:
    """Return a JSON error string for tool responses."""
    return json.dumps({"error": message})
```

### 2. Sync plugin files
```bash
# Copy newer python/memory_client.py to hermes-plugin/
cp ~/projects/neural-memory-adapter/python/memory_client.py \
   ~/projects/neural-memory-adapter/hermes-plugin/

# Copy to deployed plugin
cp ~/projects/neural-memory-adapter/hermes-plugin/memory_client.py \
   ~/.hermes/hermes-agent/plugins/memory/neural/
```

### 3. Fix install.sh
- Remove reference to non-existent `neural_memory_banner.pth`
- Fix inconsistent step numbering ([4/6] vs [5/5])
- Check if dependencies already installed before installing
- Copy all required plugin files (neural_memory.py, cpp_bridge.py, mssql_store.py)

### 4. Restart gateway
```bash
hermes gateway restart
```

## Related Skill
For the full Honcho-equivalent integration in run_agent.py (system prompt, sync/prefetch, memory mirroring), see: `devops/neural-memory-run-agent-integration`

## Verification
```bash
# Test plugin loads
cd ~/.hermes/hermes-agent
python3 -c "from plugins.memory import load_memory_provider; p = load_memory_provider('neural'); print(f'Available: {p.is_available()}')"

# Test operations
python3 -c "
from plugins.memory import load_memory_provider
p = load_memory_provider('neural')
p.initialize('test')
result = p.handle_tool_call('neural_remember', {'content': 'test'})
print(result)
"
```

## File Locations
- Plugin source: `~/projects/neural-memory-adapter/hermes-plugin/`
- Deployed plugin: `~/.hermes/hermes-agent/plugins/memory/neural/`
- Config: `~/.hermes/config.yaml` (section: `memory.neural`)
- Database: `~/.neural_memory/memory.db`

## Critical: Tool Registration

The neural memory plugin loads but its tools are NOT visible to the agent unless properly registered. The plugin's `get_tool_schemas()` and `handle_tool_call()` methods are only used through the MemoryManager, but the agent doesn't use MemoryManager directly.

### Create `tools/neural_tools.py`

Create `~/.hermes/hermes-agent/tools/neural_tools.py` that:
1. Imports the neural provider
2. Registers 4 tools: `neural_remember`, `neural_recall`, `neural_think`, `neural_graph`
3. Uses `registry.register()` like other tools (see `tools/honcho_tools.py` for reference)

### Add to tool discovery in `model_tools.py`

Add `"tools.neural_tools"` to the `_modules` list in `~/.hermes/hermes-agent/model_tools.py` (around line 159, after `"tools.honcho_tools"`).

### Initialize provider in `run_agent.py`

Add neural memory initialization after honcho initialization (around line 2376):
```python
# Initialize neural memory provider if configured
try:
    from tools.neural_tools import set_neural_provider
    from plugins.memory import load_memory_provider
    neural_provider = load_memory_provider("neural")
    if neural_provider and neural_provider.is_available():
        neural_provider.initialize(self.session_id or "default")
        set_neural_provider(neural_provider)
except Exception as e:
    logger.debug("Neural memory initialization failed (non-fatal): %s", e)
```

## Common Issues
1. **Plugin not loading**: Check `tool_error` exists in `tools/registry.py`
2. **Dependencies missing**: `pip install sentence-transformers numpy`
3. **Database errors**: Delete `~/.neural_memory/memory.db` to reset
4. **CUDA not detected**: Check `nvidia-smi` works
5. **Tools not visible to agent**: Check `tools/neural_tools.py` exists and is in `model_tools.py` discovery list
6. **Provider not initialized**: Check `run_agent.py` has neural initialization code
7. **Gateway needs restart**: After any changes, run `hermes gateway restart` AND clear Python cache (delete `__pycache__` dirs)
8. **Session required**: Tools only load when an agent session starts (when user sends a message). Gateway itself is just a router - it doesn't load tools at startup.

## Architecture Notes

**Gateway vs Agent Session:**
- Gateway: Routes messages, manages platforms (Telegram, Discord, etc.)
- Agent Session: Created when user sends a message, loads tools, initializes providers
- Neural memory initialization happens in `run_agent.py` during session start, NOT at gateway startup

**Tool Registration Pattern:**
Memory provider plugins (neural, honcho) need TWO things:
1. Plugin in `plugins/memory/<name>/` - implements MemoryProvider ABC
2. Tool file in `tools/<name>_tools.py` - registers tools with `registry.register()`

The plugin alone is NOT sufficient. Without the tool file, the agent cannot see or call the memory tools.
