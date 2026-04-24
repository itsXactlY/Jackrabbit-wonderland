---
name: discord-outbox-messaging
category: software-development
description: Send messages to Discord channels using the Hermes gateway outbox directory when direct messaging tools are unavailable or unclear.
version: 1.0.0
---

# Discord Outbox Messaging

Send messages to Discord channels using the Hermes gateway outbox directory mechanism. This approach is useful when direct messaging commands are not available or when you need to leverage the gateway's automatic file processing.

## When to Use
- When direct Hermes messaging commands fail or are unavailable
- When you need to send formatted reports or multi-line content to Discord
- When working in environments where the gateway is running but messaging tools are unclear
- As a reliable fallback for Discord messaging via Hermes

## Method Overview
The Hermes gateway monitors `~/.hermes/discord-outbox/` for files named with the pattern `{channel-name}_{channel-id}.md`. When it detects new or updated files, it automatically sends their contents to the corresponding Discord channel.

## Procedure

### 1. Prepare Your Message
Create or obtain the message content you wish to send. Markdown formatting is supported.

```bash
# Example: Create a system health report
cat > /tmp/my_report.md << 'EOF'
**SYSTEM HEALTH REPORT**
- Status: All systems operational
- Timestamp: $(date)
EOF
```

### 2. Identify Target Channel
You need both the channel name and channel ID. Find these in:
- `~/.hermes/channel_directory.json`
- Existing files in `~/.hermes/discord-outbox/`
- Discord context awareness skills or documentation

Common channel IDs from backup server:
- `dev-control-room`: 1485340236316807278
- `ops-control-room`: 1485339988215337192
- `trading-command`: 1485340062387404910
- `admin-control`: 1485339913430896883

### 3. Place File in Outbox
Copy your message file to the outbox with the correct naming convention:

```bash
cp /tmp/my_report.md ~/.hermes/discord-outbox/{channel-name}_{channel-id}.md
```

**Example**:
```bash
cp /tmp/system_report.md ~/.hermes/discord-outbox/dev-control-room_1485340236316807278.md
```

### 4. Verify Delivery
Check that:
- The file exists in the outbox with correct permissions
- The gateway service is running (`hermes gateway status`)
- Optionally, check Discord to confirm message arrival

## Verification
- Confirm file appears in outbox: `ls -la ~/.hermes/discord-outbox/`
- Check gateway status: `hermes gateway status`
- Monitor logs if needed: `journalctl --user -u hermes-gateway.service -f`

## Tips
- Use `.md` extension for markdown formatting support
- Channel names should match those used in existing outbox files
- The gateway processes files automatically - no manual triggering needed
- Files can be updated - gateway will detect changes and resend
- Remove files from outbox to prevent resending (optional)

## Troubleshooting
- **File not processed**: Verify gateway is running with `hermes gateway status`
- **Wrong channel**: Double-check channel ID matches name
- **Formatting issues**: Ensure proper markdown syntax if using .md extension
- **Permissions**: Files should be readable by the gateway service

## Example: System Health Report
```bash
# Generate report
echo "**SYSTEM HEALTH CHECK**" > /tmp/health.md
echo "- Disk: $(df -h / | awk 'NR==2 {print $5}') used" >> /tmp/health.md
echo "- CPU: $(top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | sed 's/,//')%" >> /tmp/health.md
echo "- Memory: $(free -h | awk 'NR==2 {printf \"%.1f%%\", $3*100/$2 }')" >> /tmp/health.md

# Send to dev-control-room
cp /tmp/health.md ~/.hermes/discord-outbox/dev-control-room_1485340236316807278.md
```