---
name: self-improvement-audit
version: 1.0.0
category: autonomous-ai-agents
description: Systematic self-improvement audit for Hermes Agent — analyze skills, memory, config, tool usage, errors, and communication patterns using parallel subagents.
author: hermes
tags: [meta, self-improvement, audit, quality]
---

# Self-Improvement Audit

Systematic audit of agent health across 6 dimensions using parallel subagents.

## When to Use
- After major config changes or migrations
- Periodically (monthly) to catch drift
- When user asks "how can you improve?"
- After accumulating 1000+ error log lines

## Audit Dimensions (6 parallel subagents)

### 1. Skills Analysis
- Scan ~/.hermes/skills/ for duplicates, overlaps, quality
- Check for: identical files, overlapping content, excessive length, missing metadata
- Flag hardcoded paths, domain bloat

### 2. Memory System
- Check MEMORY.md and USER.md capacity (warn at 80%)
- Look for: stale entries, duplicated content, misplaced entries
- Verify config.yaml drift (reasoning_effort, compression, providers)

### 3. Behavioral Patterns
- Analyze errors.log for top error categories
- Check cron job execution status
- Look for: auth failures, connection errors, rate limiting
- Check plugin/provider health

### 4. Tool Usage Patterns
- Analyze which tools are used vs available
- Find tools with 100% failure rate (disable or fix)
- Identify underutilized tools (session_search, delegate_task, execute_code)
- Check for sequential calls that could be parallel

### 5. MemPalace Data Quality
- Check KG entity types (should NOT be "unknown")
- Verify temporal bounds on facts
- Look for duplicate KG databases
- Check wing/room organization (not flat)
- Count noise vs signal in embeddings

### 6. Communication Patterns
- Verbosity consistency (too terse vs too verbose)
- Formatting (markdown in CLI = bad)
- Language consistency with user
- MemPalace citation compliance
- Duplicate responses across sessions

## Execution Pattern

```
1. session_search() → find recent sessions
2. delegate_task × 6 (parallel) → one per dimension
3. Synthesize findings
4. Execute safe fixes (memory consolidation, skill dedup, config corrections)
5. Report + save to memory
```

## Safe Fixes (do automatically)
- Memory consolidation (merge duplicates, right-size entries)
- Skill deduplication (delete identical files)
- Config corrections (remove dead providers, fix reasoning_effort)

## Unsafe Fixes (ask user first)
- Deleting skills with overlap (may have unique content)
- Changing compression settings
- Modifying personality/system_prompt
- Pruning custom_providers

## Pitfalls
- Don't auto-delete skills without verifying content is merged elsewhere
- Don't change config without user confirmation for impactful settings
- MEMORY.md edits must use exact string matching (replace mode)
- Cron jobs may look unexecuted because scheduler needs gateway running
