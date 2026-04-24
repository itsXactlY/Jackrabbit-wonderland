---
name: neural-memory-run-agent-integration
category: devops
description: First-class Neural Memory integration in run_agent.py — Honcho-equivalent pattern for system prompt, sync/prefetch, memory mirroring, tool management
triggers:
  - neural memory not appearing in system prompt
  - neural memory not syncing after turns
  - neural tools not stripped when inactive
  - integrate memory provider like honcho
  - add new memory provider to run_agent
---

# Neural Memory — First-Class run_agent.py Integration

## Problem
Neural memory was only loaded as a generic plugin via `load_memory_provider("neural")` inside `_activate_honcho`. This meant:
- Neural only worked when Honcho was active
- No system prompt block showing neural stats
- No sync/prefetch hooks in the conversation loop
- No memory write mirroring from built-in memory
- Tools weren't stripped when provider was unavailable

## Solution: Honcho-Equivalent Integration Pattern

The pattern mirrors how Honcho is wired into `run_agent.py`. Any new memory provider should follow the same structure.

### 1. Tool Name Constant (top of file, near HONCHO_TOOL_NAMES)
```python
NEURAL_TOOL_NAMES = {
    "neural_remember",
    "neural_recall",
    "neural_think",
    "neural_graph",
}
```

### 2. State Variables in `__init__` (independent of Honcho)
```python
# Neural Memory — standalone, not inside _activate_honcho
self._neural = None  # NeuralMemoryProvider | None
self._neural_available = False
if not skip_memory:
    try:
        from plugins.memory import load_memory_provider
        neural_provider = load_memory_provider("neural")
        if neural_provider and neural_provider.is_available():
            neural_provider.initialize(self.session_id or "default")
            self._neural = neural_provider
            self._neural_available = True
            try:
                from tools.neural_tools import set_neural_provider
                set_neural_provider(neural_provider)
            except Exception:
                pass
            if not self.quiet_mode:
                print(f"  Neural memory active")
    except Exception as e:
        logger.debug("Neural memory init failed (non-fatal): %s", e)

if not self._neural:
    self._strip_neural_tools_from_surface()
```

### 3. Integration Methods (alongside Honcho methods)
```python
def _strip_neural_tools_from_surface(self) -> None:
    if not self.tools:
        self.valid_tool_names = set()
        return
    self.tools = [t for t in self.tools
                  if t.get("function", {}).get("name") not in NEURAL_TOOL_NAMES]
    self.valid_tool_names = {t["function"]["name"] for t in self.tools} if self.tools else set()

def _neural_sync(self, user_content: str, assistant_content: str) -> None:
    if not self._neural:
        return
    try:
        self._neural.sync_turn(user_content, assistant_content, session_id=self.session_id or "")
    except Exception as e:
        logger.debug("Neural sync failed (non-fatal): %s", e)

def _neural_prefetch(self, user_message: str) -> str:
    if not self._neural:
        return ""
    try:
        return self._neural.prefetch(user_message, session_id=self.session_id or "") or ""
    except Exception:
        return ""

def _queue_neural_prefetch(self, user_message: str) -> None:
    if not self._neural:
        return
    try:
        self._neural.queue_prefetch(user_message, session_id=self.session_id or "")
    except Exception:
        pass
```

### 4. System Prompt Block (in `_build_system_prompt`, after Honcho block)
```python
if self._neural:
    try:
        neural_block = self._neural.system_prompt_block()
        if neural_block:
            neural_block += "\nNeural memory tools:\n  ...\n"
            prompt_parts.append(neural_block)
    except Exception:
        pass
```

### 5. Conversation Loop Prefetch (after Honcho prefetch section)
```python
if self._neural:
    try:
        neural_context = self._neural_prefetch(original_user_message)
        if neural_context:
            if not conversation_history:
                self._honcho_context = (... + neural_context).strip()
            else:
                self._honcho_turn_context = (... + neural_context).strip()
    except Exception:
        pass
```

### 6. Conversation Loop Sync (after Honcho sync)
```python
if final_response and not interrupted:
    self._neural_sync(original_user_message, final_response)
    self._queue_neural_prefetch(original_user_message)
```

### 7. Memory Write Mirroring (3 locations where Honcho mirrors)
```python
if self._neural:
    try:
        self._neural.on_memory_write(
            args.get("action", "add"),
            args.get("target", "memory"),
            args.get("content", ""),
        )
    except Exception:
        pass
```

### 8. Session End Hook (before plugin on_session_end)
```python
if self._neural:
    try:
        self._neural.on_session_end(messages)
    except Exception:
        pass
```

## Pitfalls

1. **Don't nest neural init inside `_activate_honcho`** — it must be independent
2. **Import chain issues in tests** — `plugins/memory/neural/__init__.py` imports `tools.registry` which triggers `tools/__init__.py` which imports optional deps (firecrawl, fal_client). Mock them in root `tests/conftest.py`:
   ```python
   for _mod in ["firecrawl", "firecrawl.firecrawl", "fal_client", "fal_client.client"]:
       if _mod not in sys.modules:
           sys.modules[_mod] = _MagicMock()
   ```
3. **Neural prefetch reuses `_honcho_context` / `_honcho_turn_context`** — these are the injection channels. Append neural context to existing honcho context rather than creating separate channels.
4. **Plugin `__init__.py` must implement `MemoryProvider` ABC** — including `on_session_end` and `on_memory_write` hooks.

## Verification
```bash
# Compile check
python -c "import py_compile; py_compile.compile('run_agent.py', doraise=True)"

# Test suite
cd hermes-agent && python -m pytest tests/plugins/memory/ -v -o addopts=

# Live check — provider loads and has correct stats
python -c "
from plugins.memory import load_memory_provider
p = load_memory_provider('neural')
print(f'Available: {p.is_available()}')
p.initialize('test')
print(p.system_prompt_block())
p.shutdown()
"
```
