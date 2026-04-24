---
name: discord-system-reporting
category: software-development
description: Send system health reports to Discord channels via Hermes outbox system
version: 1.0.0
---

# Discord System Reporting

Send automated system health reports to Discord channels using the Hermes outbox mechanism.

## When to Use
- Sending automated system monitoring reports
- Reporting health checks to operational Discord channels
- Integrating system monitoring with Discord-based ops workflows
- Regular status reporting to dev/ops channels

## Procedure

### 1. Load Context Awareness
Always load discord-context-awareness skill first to understand channel semantics and reporting destinations.

### 2. Gather System Metrics
Collect essential system health data:
- **Disk Usage**: `df -h / | awk 'NR==2 {print \"Disk Usage: \"$3\" used / \"$2\" total (\"$5\" used)\"}'`
- **CPU Usage** (primary): `grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5+$6+$7+$8); printf(\"CPU Usage: %.1f%% user, %.1f%% system, %.1f%% idle\\n\", usage, ($3+$5)*100/($2+$3+$4+$5+$6+$7+$8), ($6+$7+$8)*100/($2+$3+$4+$5+$6+$7+$8))}'`
  - **Fallback**: `top -bn1 | grep \"Cpu(s)\" | awk '{print \"CPU Usage: \"$2\"% user, \"$4\"% system, \"$8\"% idle\"}'`
- **Memory Usage**: `free -h`
- **Service Status**: 
  - Hermes gateway: `systemctl status hermes-gateway` + `ps aux | grep hermes`
  - Ollama: `curl -s http://localhost:11434/api/tags`

### 3. Format Report
Create a markdown-formatted report with clear sections:
```markdown
**Hermes Agent System Health Check**
⏰ Timestamp: [current timestamp]
🖥️ Host: [hostname]

**System Resources:**
• Disk Usage: [used]/[total] ([percent] used) [status emoji]
• CPU Load: [1min], [5min], [15min] [status emoji]
• Memory: [used]/[total] ([percent] used) [status emoji]

**Services Status:**
• Hermes Gateway: [status]
• Ollama: [status] 
• Hermes Agent: [status]

**Notes:**
- [Any observations or recommendations]
- [Trend warnings if applicable]

**Next Check:** [time for next report]
```

### 4. Send via Discord Outbox
Place the formatted report in the Discord outbox:
```
~/.hermes/discord-outbox/{channel-name}_{channel-id}.md
```

Key channels from discord-context-awareness:
- `dev-control-room_1485340236316807278.md` (Development reports)
- `ops-control-room_1485339988215337192.md` (Operational alerts)
- `trading-command_[id].md` (Trading operations)
- `research-requests_[id].md` (Research task results)

### 5. Verification
- Confirm file was created in outbox
- Check that content is properly formatted
- Verify gateway processes the outbox (check gateway logs)
- Ensure message appears in correct Discord channel

## Tips
- Use consistent emoji for visual scanning (⚠️ for warnings, ✅ for normal)
- Include timestamps for trend analysis
- Monitor disk usage trends over time
- Keep reports concise but informative
- Consider automating with cron jobs for regular reporting

## Error Handling
- If outbox write fails, check permissions on ~/.hermes/discord-outbox/
- If message doesn't appear in Discord, check gateway status and logs
- Format validation: ensure no malformed markdown that could break Discord rendering