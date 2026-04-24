---
name: discord-context-awareness
category: software-development
description: Enables the Hermes agent to understand Discord channel semantics, route actions appropriately, and operate autonomously within the backup server infrastructure.
version: 1.1.0
---

# Discord Context Awareness

Enables the Hermes agent to understand Discord channel semantics, route actions appropriately, and operate autonomously within the backup server infrastructure.

## When to Use
- When you need to know where to report results
- When planning actions based on channel purpose
- When integrating with Discord as an operational environment
- Before spawning agents or executing tasks that require channel context

## Channel Reference (from backup server)

### Administrative Control
- `admin-control` (1485339913430896883) - Primary admin command center ⭐ CURRENT LOCATION
- `admin-approvals` - Approvals workflow
- `admin-audit-log` - Audit trail
- `admin-bot-debug` - Bot debugging
- `admin-config` - Admin configuration

### Operations
- `ops-control-room` (1485339988215337192) - **Discord home channel** - Main ops hub
- `ops-status` - System status
- `ops-incidents` - Incident management
- `ops-approvals` - Operational approvals
- `ops-daily-briefing` - Daily summaries
- `ops-jobs` - Job tracking

### Trading & Finance
- `trading-command` - Trading command center
- `trading-signals` - Signals & alerts
- `trading-analysis` - Market analysis & research
- `trading-risk` - Risk management
- `trading-news` - Financial news
- `trading-results` - Performance tracking
- `trading-backtests` - Strategy backtesting
- `trading-war-room` - Live trading operations

### Research & Analysis
- `research-requests` - Task requests
- `research-output` - Results & findings
- `research-watchers` - Monitoring & watchlists
- `research-summaries` - Summary reports

### Development (CRITICAL FOR REPORTING)
- `dev-control-room` (1485340236316807278) - **Development control center** - **WHERE ALL REPORTS SHOULD BE MADE**
- `dev-agent-jobs` - Agent job tracking
- `dev-code-review` - Code reviews
- `dev-debugging` - Development debugging
- `dev-deployments` - Deployment coordination
- `dev-test-runs` - Test execution
- `dev-planning` - Planning & roadmap

### Feeds & Monitoring
- `feed-system-health` - System health
- `feed-market-data` - Market data feeds
- `feed-external-alerts` - External alerts
- `feed-cron-reports` - Cron job logs
- `feed-ingest-log` - Ingestion logs
- `feed-agent-events` - Agent activity logs

## Free Response Channels (Hermes can reply without @mention)
- `admin-control` - current
- `ops-control-room` - Discord home
- `trading-command`
- `trading-analysis`
- `trading-war-room`
- `dev-control-room` ← REPORTING DESTINATION
- `dev-debugging`
- `research-requests`

## Configuration
- Hermes config: `~/.hermes/config.yaml`
- Channel directory: `~/.hermes/channel_directory.json`
- Docs: `~/discord-backup.md`, `~/discord-setup-quickref.md`

## Sending Reports to Discord

**ALWAYS use the `send_message` tool** to post to Discord channels. Example:

```
send_message(target="discord:1485340236316807278", message="Your report content here")
```

**DO NOT** write files to `~/.hermes/discord-outbox/` — that directory is deprecated and messages written there are never delivered.

**DO NOT** make raw HTTP calls to the Discord API via terminal/urllib/curl — use `send_message` instead.

### Routing Logic
- Development/code/status → `send_message(target="discord:1485340236316807278")` (dev-control-room)
- Trading ops/signals → `send_message(target="discord:<trading-channel-id>")`
- System alerts/incidents → `send_message(target="discord:1485339988215337192")` (ops-control-room)
- Research tasks → `send_message(target="discord:<research-channel-id>")`
- When in doubt, default to `dev-control-room` (1485340236316807278)

## Usage
1. Load this skill before acting in Discord context
2. Use `where_should_i_report(task_type)` logic to pick the right channel
3. Use `send_message(target="discord:<channel_id>")` to post
4. Always verify channel ID matches current server (backup)

## Verification
- After action, confirm output was sent to correct channel
- Check `session_search` for similar past routing
- Update mental model if channel purpose changes
