# Agent Failure Recovery Patterns

## Pattern 1: "Completed" but no changes made
**Symptom:** Agent reports "completed" but grep shows no new symbols/code.
**Cause:** Agent spent all iterations reading files and never got to writing.
**Fix:** Re-spawn with EXPLICIT diffs:
```
In file X, after line Y, add EXACTLY this code:
[paste exact code]
Do NOT read any files. Just make this edit.
```

## Pattern 2: Max iterations hit
**Symptom:** `exit_reason: max_iterations`
**Cause:** Task too broad — agent tried to read 2000-line files + make complex edits.
**Fix:** Break into 2-3 smaller tasks. First task: "Read file X and report what you found." Second: "Make these specific changes."

## Pattern 3: Wrong namespace/type used
**Symptom:** Code references wrong type (e.g., `TradeData` from wrong namespace).
**Cause:** Multiple types with same name in codebase.
**Fix:** In task, explicitly list ALL types with same name and their locations:
```
WARNING: There are TWO TradeData types:
1. BTQuant::Data::TradeData in include/data/TradeData.h (use this one)
2. BTQuant::RenderEngine::TradeData in include/market_data_processor.hpp (NOT this one)
```

## Pattern 4: Agent rewrites instead of patches
**Symptom:** 2000-line file completely replaced instead of targeted edits.
**Cause:** Task said "implement X" instead of "add X to existing Y".
**Fix:** Always say "READ the existing file first, then ADD/MODIFY these specific sections."

## Verification Commands
```bash
# Check if agent actually modified files
git diff --stat
# Check for expected new symbols
grep -rn "new_function_name" include/ src/
# Quick syntax check
g++ -std=c++23 -fsyntax-only -I include modified.hpp
```
