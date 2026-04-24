---
name: btquant-maintenance-routine
description: Reusable approach for maintaining BTQuant trading infrastructure projects with dependency, linting, type checking, and test validation
category: devops
---

# BTQuant Maintenance Routine

## Overview
Reusable approach for maintaining BTQuant (trading infrastructure) projects with dependency checking, linting, type checking, and test execution. Handles common issues with externally managed environments and complex project structures.

## Trigger Conditions
- Scheduled maintenance of BTQuant/PubBTQuant projects
- Pre-deployment checks
- Post-update verification
- Regular system health monitoring for trading infrastructure

## Prerequisites
- Access to /home/alca/projects/PubBTQuant/
- Existing virtual environment at venv/
- Basic understanding of BTQuant project structure
- write_file and memory tool access

## Procedure

### 1. Environment Setup
```bash
cd /home/alca/projects/PubBTQuant/
source venv/bin/activate  # Use existing venv to avoid externally-managed-environment errors
```

### 2. Dependency Verification
```bash
# Check current package state and count
pip list --format=json | wc -l  # Get package count

# Output package list for documentation
pip list --format=json > pip-list.json  # Save for reporting

# Verify requirements are met (installs to venv, not system)
pip install -r requirements-dev.txt  # Safe to run even if already installed
```

### 3. Linting Analysis (flake8)
```bash
# Run with appropriate exclusions for BTQuant structure
flake8 . --count \
  --exclude=.git,__pycache__,venv,.benchmarks,.btq_cache,.mypy_cache,.ruff_cache,.pytest_cache,.claude \
  --max-line-length=120 \
  --statistics
```

### 4. Type Checking (mypy)
```bash
# Handle duplicate module issues by excluding problematic directories
# NOTE: mypy --exclude uses regex with | separator, NOT comma-separated
mypy . --exclude='\.git|__pycache__|venv|\.benchmarks|\.btq_cache|\.mypy_cache|\.ruff_cache|\.pytest_cache|\.claude|dependencies' --ignore-missing-imports

# Alternative: Check specific modules (still useful when root-level syntax errors block full pass)
mypy hotspine/ --ignore-missing-imports --exclude='\.git|__pycache__|venv|\.benchmarks|\.btq_cache|\.mypy_cache|\.ruff_cache|\.pytest_cache|\.claude|dependencies'
```

### 5. Test Execution
```bash
# Run HotSpine-specific tests
python -m pytest hotspine/ -v

# Run MS SQL hotswap tests
python -m pytest test_ms_sql_hotswap.py -v

# For examples/tests in test/new structure:
cd tests/new/examples  # Or relevant subdirectory
python -m pytest . -v
```

### 6. Results Documentation
Create structured session state report:
```markdown
# BTQuant Maintenance Routine - Session State
**Last Updated:** [CURRENT TIMESTAMP]
**Executed By:** [Agent/User Name]

## Summary
[Brief overview of maintenance outcome]

## Dependency Check [✅/⚠️/❌]
- Virtual environment status
- Package count and key dependencies
- Any installation issues

## Linting Check [✅/⚠️/❌]
- Key issue categories and counts
- Notable patterns (examples vs core)
- Severity assessment

## Type Checking [✅/⚠️/❌]
- Module-specific results
- Critical type mismatches
- Exclusions needed

## Test Results [✅/⚠️/❌]
- HotSpine integration status
- MS SQL hotswap results
- Any failing tests and impact

## System Status
- Overall framework health
- Critical issues requiring attention
- Recommendations

## Next Maintenance
[Schedule or trigger for next check]
```

### 7. Memory Management
Proactively manage agent memory before saving significant updates:
- Check current memory usage
- Remove oldest/redundant entries if nearing limit
- Add maintenance summary as new memory entry

## Common Issues & Solutions

### Externally Managed Environment
**Problem:** `error: externally-managed-environment` when using system pip
**Solution:** Always use project virtual environment (`source venv/bin/activate`)

### Duplicate Module Detection (mypy)
**Problem:** `Duplicate module named "setup"` 
**Solution:** Exclude conflicting directories:
```
--exclude=dependencies,dependencies/MsSQL
```

### Test Collection Errors
**Problem:** Import errors in test configuration
**Solution:** Run tests from specific directories rather than project root when dealing with complex import structures

### HotSpine sys.exit() Crash (all test files)
**Problem:** ALL hotspine test files contain `sys.exit()` at module level — not just test_hotspine_basic.py
**Affected files (verified 2026-03-31):** test_hotspine_basic.py:89, test_hotspine_reader.py:22, test_hotspine_comprehensive.py, test_hotspine_core.py, test_hotspine_integration.py, test_hotspine_simple.py, test_hotspine_system.py, test_hotspine_sql_architecture.py
**Workaround:** `python -m pytest hotspine/ --ignore=hotspine/test_hotspine_basic.py` still crashes on other files. Use `test_ms_sql_hotswap.py` (9/9 passing) as the only currently runnable test suite.
**Fix:** Wrap all `sys.exit()` calls in `if __name__ == "__main__":` guards

### test_hotspine_reader.py Stale Import
**Problem:** `ImportError: cannot import name 'HotSpineRuntime' from 'backtrader.hotspine.reader' (test_hotspine_reader.py:18)`
**Cause:** `HotSpineRuntime` class was removed/renamed — test import is stale
**Fix:** Remove `HotSpineRuntime` from the import line: `from backtrader.hotspine.reader import HotSpineReader, HotTrade`

### test_configuration.py Stale Import
**Problem:** `ImportError: cannot import name 'HotSpineRuntime' from 'backtrader.hotspine.reader'`
**Cause:** `HotSpineRuntime` class was removed/renamed — test import is stale
**Fix:** Update import to current class name or remove test

### pip install -r requirements-dev.txt may succeed but pip list JSON has trailing noise
**Problem:** `pip list --format=json` sometimes appends non-JSON text after the array, causing `JSONDecodeError: Extra data`
**Fix:** Find last `]` in output and slice: `pkgs = json.loads(text[:text.rfind(']')+1])`

### Memory Limits
**Problem:** Exceeding agent memory capacity
**Solution:** Proactively remove older entries before adding new ones, prioritizing recent operational data

## Verification Steps
- [ ] Virtual environment activated successfully
- [ ] Dependency check completed without blocking errors
- [ ] Linting run completed (informational - failures don't halt process)
- [ ] Type checking completed with appropriate exclusions
- [ ] Critical test suites passing (HotSpine, MS SQL hotswap)
- [ ] Session state documentation created
- [ ] Memory entry added successfully

## Reporting
- Primary output: Session state markdown file at `/home/alca/proactivity/session-state.md`
- Secondary: Agent memory entry for cross-session awareness
- Optional: Discord/webhook notifications if configured

## Time Estimation
- Quick check (deps + basic tests): 5-10 minutes
- Full routine (linting + type + comprehensive tests): 15-25 minutes
- Factors: Test suite size, network speed for downloads, issue resolution time

## Notes
- BTQuant prioritizes existing infrastructure reuse over rebuilding
- Focus on HotSpine integration and MS SQL hotswap as critical paths
- Example files often have linting issues - core framework quality is priority
- Regular maintenance prevents accumulation of technical debt in trading systems