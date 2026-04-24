---
name: neural-memory-first
category: devops
description: Verify and use neural memory as the primary recall source. Check health before other search methods.
version: 1.0.0
---

# Neural Memory First — MANDATORY RULE

**BEFORE ANY ACTION: Call neural_recall(query). If results found, answer from them. DONE. Do NOT search filesystem. Do NOT use terminal find/grep. Do NOT read README files. Neural memory FIRST, ALWAYS.**

If neural_recall returns NOTHING relevant (similarity < 0.3), THEN AND ONLY THEN explore the filesystem.

**NEVER loop through reasoning → terminal → reasoning → terminal. ONE neural_recall call. ONE answer.**

When the user asks about past conversations, decisions, or context, ALWAYS check neural memory first.

## Step 1: Check if neural memory is functional

```bash
# Check config
grep -A5 "memory" ~/.hermes/config.yaml

# Check plugin exists
ls ~/.hermes/plugins/memory/neural/

# Check DB exists
ls ~/.neural_memory/memory.db 2>/dev/null || echo "DB MISSING"
```

If `~/.neural_memory/memory.db` is missing or the plugin dir is empty:
- Plugin source: `~/projects/neural-memory-adapter/hermes-plugin/`
- Copy/link into: `~/.hermes/plugins/memory/neural/`
- Or use the Python API directly (see below)

## Step 2: Query via Python API (fallback if plugin broken)

```python
import sys
sys.path.insert(0, '/home/alca/projects/neural-memory-adapter/python')

from neural_memory import NeuralMemory
nm = NeuralMemory()

results = nm.recall("search query", k=5)
for r in results:
    print(r.get('content', '')[:200])
```

**NOTE:** The `k` parameter is `k`, NOT `top_k`.

## Step 3: Check stats before searching

```python
nm = NeuralMemory()
print(nm.stats())  # {'memories': 0, 'connections': 0, ...}
```

If memories == 0, the system is empty — don't waste time querying it. Tell the user directly.

## Verification: Trust the Source Code, Not the Config

The config.yaml `db_path` may be WRONG. The actual default comes from the source code:

```bash
grep "neural_memory" ~/projects/neural-memory-adapter/python/neural_memory.py | grep -i "\.db"
# Expected: self._db_path = db_path or str(Path.home() / ".neural_memory" / "memory.db")
```

If config says `hermes.db` but code says `memory.db`, the code wins. Always verify with:

```bash
ls -la ~/.neural_memory/*.db
```

The DB filename is `memory.db` (NOT `hermes.db`). Config was wrong historically — fixed 2026-04-10.

## CRITICAL: Remove built-in memory + session_search from toolsets

Having BOTH the built-in `memory` tool (2200 char limit) AND neural memory tools causes the agent to use the wrong one. When the small memory fills up, the agent gets stuck in a retry loop ("Memory is full" → retry → retry...).

**Fix in `~/.hermes/config.yaml`** — remove `- memory` and `- session_search` from ALL platform_toolsets (cli, discord, telegram):

```yaml
platform_toolsets:
  cli:
  - browser
  - clarify
  - code_execution
  - cronjob
  - delegation
  - file
  - image_gen
  # - memory        # REMOVED - use neural_remember instead
  # - session_search # REMOVED - use neural_recall instead
  - skills
  - terminal
  - todo
  - tts
  - vision
  - web
```

This forces the agent to use `neural_remember`/`neural_recall` exclusively.

## Unlimited DB growth

Set in `~/.hermes/config.yaml` under `memory.neural`:
```yaml
max_episodic: 0           # 0 = unlimited
consolidation_interval: 0 # 0 = no pruning
```

Also update plugin defaults in `~/.hermes/plugins/memory/neural/config.py`:
```python
DEFAULT_CONSOLIDATION_INTERVAL = 0
DEFAULT_MAX_EPISODIC = 0
```

And in `__init__.py`, ensure `_run_consolidation()` returns early when `max_episodic <= 0`.

## ROOT CAUSE: Neural memory tools NEVER injected into agent (investigated 2026-04-10)

The `neural_remember`, `neural_recall`, `neural_think`, `neural_graph` tools are
**defined** in the plugin but **never registered** in the Hermes tool registry.
The agent literally cannot call them. Here's why:

### The broken chain

```
model_tools.py  →  _discover_tools()  →  imports tools/*.py modules
                                        →  each calls registry.register() ✅
                                        →  imports plugins via discover_plugins()
                                           →  PluginContext.register_tool() ✅
                                           →  PluginContext.register_memory_provider() ❌ MISSING

plugins/memory/__init__.py  →  load_memory_provider("neural")
                             →  _ProviderCollector.register_memory_provider(provider) ✅
                             →  _ProviderCollector.register_tool() → pass NO-OP ❌
                             →  provider.get_tool_schemas() → never called ❌
                             →  provider.handle_tool_call() → never called ❌
```

**Two separate plugin systems exist:**
1. `hermes_cli/plugins.py` → `PluginContext` → `register_tool()` calls `registry.register()` ✅
   BUT: only scans immediate children of `plugins/` (misses `memory/neural/`)
   AND: no `register_memory_provider()` method

2. `plugins/memory/__init__.py` → `_ProviderCollector` → loads memory providers
   BUT: `register_tool()` is a no-op `pass` — tools never enter registry

**The neural plugin calls `ctx.register_memory_provider(provider)` which is ONLY
supported by system #2. But system #2's `_ProviderCollector.register_tool()` is a
no-op, so the provider's `get_tool_schemas()` are never bridged to the registry.**

### What used to work

A module `agent/memory_manager.py` previously existed that:
1. Called `load_memory_provider("neural")`
2. Called `provider.get_tool_schemas()` to get the 4 tool schemas
3. Registered them with the tool registry

Log evidence (2026-04-10 03:37):
```
INFO agent.memory_manager: Memory provider 'neural' registered (4 tools)
```

This module may have been removed in a recent update or exists on a different branch.

### Workaround: Use Python API directly

Until the bridge is fixed, call the neural memory Python API directly:

```python
import sys
sys.path.insert(0, '$HOME/.hermes/plugins/memory/neural')
# OR: sys.path.insert(0, '/home/alca/projects/neural-memory-adapter/python')
from memory_client import NeuralMemory

nm = NeuralMemory()
# Recall
results = nm.recall("search query", k=5)
# Remember
mid = nm.remember("fact to store", label="category")
# Stats
print(nm.stats())
nm.close()
```

### Fix options

**Option A: Fix `_ProviderCollector.register_tool()`**
In `~/.hermes/hermes-agent/plugins/memory/__init__.py`, change the `_ProviderCollector`
to actually register tools. After `load_memory_provider("neural")` returns, call
`provider.get_tool_schemas()` and register each via `from tools.registry import registry`.

**Option B: Restore `agent/memory_manager.py`**
Check git history (`git log --all -- agent/memory_manager.py`) and restore from
the commit before removal.

**Option C: Register tools manually in `_discover_tools()`**
Add a new module like `tools/neural_memory_tool.py` that imports the neural plugin
and registers its tools with `registry.register()`.

## Pitfalls

- **Plugin not installed**: Config says `provider: neural` but `~/.hermes/plugins/memory/neural/` may be missing. Fix: `cp -r ~/projects/neural-memory-adapter/hermes-plugin ~/.hermes/plugins/memory/neural`
- `~/.neural_memory/` may not exist after migrations — check backup at `~/hermes-neural-backup-*/`
- The embedding model (all-MiniLM-L6-v2) downloads on first use (~80MB, cached to `~/.neural_memory/models/`)
- If DB is empty, no recall source available — agent must ask user directly
- DB filename is `memory.db` (confirmed correct in config as of 2026-04-10)
- **Agent loop bug**: If `memory` tool is still in toolsets AND memory is full, agent will loop endlessly trying to save. ALWAYS remove `memory` and `session_search` from toolsets when using neural provider.
- **NEURAL TOOLS ARE BROKEN**: `neural_remember`/`neural_recall`/`neural_think`/`neural_graph` are NOT in the agent's tool list. Use Python API directly as workaround.
