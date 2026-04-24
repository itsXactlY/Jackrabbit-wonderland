---
name: multi-agent-codebase-modification
description: Parallel sub-agent workflow for large-scale codebase modifications across many files and phases
triggers:
  - multi-phase implementation tasks (5+ files, 3+ phases)
  - "implement spec across codebase"
  - "adapt existing codebase to new design"
  - tasks with clear phase dependencies that can be parallelized
---

# Multi-Agent Codebase Modification

Use when implementing a large spec (8+ phases, 20+ files) across an existing codebase.

## Setup

1. **Audit the codebase FIRST** — read key files to understand what exists vs what the spec assumes
2. **Write a plan file** (`PLAN.md`) with phase status, file lists, known conflicts
3. **Group phases by dependency** — independent phases go to separate agents
4. **Spawn agents in waves** if hard dependencies exist (Phase 1 depends on Phase 0)

## Agent Task Specification Rules

**DO:**
- Give exact file paths and describe what to ADD (not rewrite)
- Say "READ `file.hpp` first, then add X after line Y"
- Specify namespace conflicts explicitly (e.g., "There are TWO TradeData types: BTQuant::Data::TradeData in TradeData.h AND BTQuant::RenderEngine::TradeData in market_data_processor.hpp")
- For NEW files, give the full API signature
- For modifications, show the exact diff you want

**DON'T:**
- Say "implement the spec" — agents will over-engineer or hallucinate paths
- Assume agents will discover namespace conflicts on their own
- Give a single agent 5+ complex tasks — they'll hit iteration limits
- Trust "completed" from an agent that only read files — verify with grep

## Failure Recovery

- **Agent only reads, doesn't modify**: Re-spawn with "Make EXACTLY these changes: [diff]. Do NOT just read."
- **Agent hits max iterations**: Break the task into smaller pieces, spawn again
- **Agent creates wrong namespace**: Add explicit namespace context to task

## Verification After Each Wave

```bash
# Check new files exist
find . -name "*.hpp" -newer PLAN.md
# Check for expected symbols
grep -rn "new_symbol" include/ src/
# Syntax check modified files
g++ -std=c++23 -fsyntax-only -I include modified_file.hpp
```

## SPIR-V Shader Compilation

When compute shaders need compilation:
```bash
glslc --target-env=vulkan1.3 -o /tmp/shader.comp.spv shaders/shader.comp
# Convert to C array and append to shader_spirv.hpp
python3 -c "
import struct
with open('/tmp/shader.comp.spv','rb') as f: data=f.read()
words = struct.unpack(f'<{len(data)//4}I', data)
# Generate static const uint32_t array
"
```

## Lessons Learned

- **Incremental patches > rewrites** when existing code is 500+ lines
- **Re-spawn failed agents immediately** — don't try to fix in same session
- **Phase 0 (foundation) should complete before spawning Phase 1+** agents
- **Two agents CAN work on the same file** if their changes don't overlap (verified: both modified cluster_engine.hpp in different sections)
