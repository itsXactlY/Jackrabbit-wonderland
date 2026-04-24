---
name: existing-infra-integration
description: When building a new system that must integrate with existing infrastructure, explore the existing codebase FIRST before building anything. Creates adapter/mixin patterns to bridge new code with existing systems.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [integration, infrastructure, adapter, exploration, legacy]
    related_skills: [subagent-driven-development, writing-plans]
---

# Existing Infrastructure Integration

## When to Use

- User says "fit the existing X infrastructure" or mentions "existing/current/reuse/integrate"
- Building an add-on/extension to an existing system
- Integrating with legacy code, existing databases, or running services
- Spec references components that already exist somewhere

**Critical lesson:** NEVER build standalone first then discover must integrate. EXPLORE EXISTING INFRA BEFORE WRITING CODE.

## Process

### 1. Explore Existing Infrastructure (BEFORE building anything)

```bash
# Find project root and structure
find /path/to/existing -maxdepth 2 -type f \( -name "*.py" -o -name "*.json" -o -name "*.yaml" \) | head -50

# Find credential/config files (dontcommit, .env, config, secrets)
find /path/to/existing -maxdepth 3 \( -name "*config*" -o -name "*secret*" -o -name "*dontcommit*" -o -name ".env*" \)

# Find database connections
grep -r "connection_string\|DATABASE_URL\|server.*database\|sqlalchemy" /path/to/existing --include="*.py" -l

# Find API/webhook endpoints
grep -r "webhook_url\|api_url\|endpoint\|base_url" /path/to/existing --include="*.py" -l

# Find external integrations
grep -r "ccxt\|redis\|rabbitmq\|kafka\|websocket" /path/to/existing --include="*.py" -l
```

Document findings:
- Database: server, port, credentials, existing databases
- APIs: URLs, auth methods, data formats
- Shared memory/IPC: paths, data structures
- Config files: where credentials live
- Existing data formats: signal formats, struct layouts

### 2. Map Integration Points

| Existing Component | How New System Integrates |
|---|---|
| Database server | Reuse same server, new database/schema |
| Exchange API keys | Load via adapter, don't duplicate |
| Shared memory | Read via ctypes/ffi bridge |
| Webhook endpoints | Forward signals, add auth layer |
| Strategy framework | Intercept via mixin pattern |

### 3. Build Adapters (Not Replacements)

**Adapter pattern** - bridges data formats:
```python
class ExistingSystemBridge:
    def convert_signal(self, existing_format) -> NewFormat: ...
    def load_credentials(self) -> dict: ...  # From existing store
```

**Mixin pattern** - hooks into existing framework:
```python
class CopyTradingMixin:
    def notify_order(self, order):
        super().notify_order(order)           # Preserve existing
        if order.status == order.Completed:
            self._publish_to_new_platform()   # Add new
```

### 4. Configure New System to Reference Existing Infra

```python
# DON'T spin up new infrastructure
database_url = "postgresql://localhost/new_db"

# DO reuse existing
database_url = "mssql+pyodbc://existing_user@existing_host/existing_server"
```

### 5. Validate Integration

Test: read existing DB, load existing creds, parse existing formats, send to existing endpoints, coexist without conflicts.

## Anti-Patterns

- ❌ Build standalone → user says "must fit existing" → refactor everything
- ✅ Explore first → build adapters from start → fits naturally

- ❌ Duplicate credentials/API key management
- ✅ Load from existing config locations

- ❌ Replace existing database/message queue
- ✅ Add to existing server, reuse connections

## Checklist

- [ ] Explored existing project structure
- [ ] Found credential/config file locations
- [ ] Identified database connection details
- [ ] Mapped existing data formats/signals
- [ ] Found existing API/webhook endpoints
- [ ] Created adapter modules (not replacements)
- [ ] Used mixin pattern for framework hooks
- [ ] Configured new system to reference existing infra
- [ ] Tested integration end-to-end
