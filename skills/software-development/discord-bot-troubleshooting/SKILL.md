---
name: discord-bot-troubleshooting
description: Systematic approach to diagnose and fix Discord bot connectivity and responsiveness issues in Hermes agent environment
category: software-development
---

# Discord Bot Troubleshooting Skill

## When to Use
When a Discord bot appears to be offline, not responding, or not working properly despite being configured.

## Prerequisites
- Access to Hermes agent environment
- Discord bot token configured in `~/.hermes/.env`
- Basic familiarity with Linux command line

## Step-by-Step Approach

### 1. Verify Environment Variables Are Loaded
The most common issue: Discord bot token not being loaded from `.env` file.

```bash
# Check if .env file exists and contains token
cat ~/.hermes/.env | grep DISCORD

# Load environment variables properly
export $(grep -v '^#' ~/.hermes/.env | xargs)

# Verify the token is loaded
echo $DISCORD_BOT_TOKEN | head -c 10  # Should show first 10 chars
```

### 2. Start Gateway with Proper Environment
Ensure the gateway starts with loaded environment variables:

```bash
# Method 1: Source venv and export then run
cd /home/alca/.hermes
source hermes-agent/venv/bin/activate
export $(grep -v '^#' .env | xargs)
hermes gateway run --replace

# Method 2: Direct path with explicit python
cd /home/alca/.hermes/hermes-agent
source ../hermes-agent/venv/bin/activate
export $(grep -v '^#' ../../.env | xargs)
python hermes_cli/main.py gateway run --replace
```

### 3. Verify Bot Connection in Logs
Watch for these key indicators in `~/.hermes/logs/gateway.log`:

✅ **Successful connection signs:**
- `Connecting to discord...`
- `logging in using static token`
- `Shard ID None has connected to Gateway`
- `[Discord] Connected as [BotName]#[Tag]`
- `[Discord] Synced X slash command(s)`
- `✓ discord connected`
- `Gateway running with 2 platform(s)`

### 4. Test Bot Responsiveness
During the gateway runtime (typically ~60 seconds due to built-in timeout):

**In Discord:**
- Send a **direct message** to the bot (often required first)
- Use the exact bot name/tag as shown in logs
- Try **slash commands** by typing `/` in a server where bot is present
- If `require_mention: true` in config, you must `@mention` the bot in servers

**Expected responses:**
- Bot shows "thinking..." status
- Executes commands like `/help`, `/status`, `/reset`, `/sethome`
- Returns appropriate feedback messages

### 5. Common Configuration Checks
Verify these in `~/.hermes/config.yaml` under `discord:` section:
- `require_mention: true` (bot won't respond to unmentioned messages in servers)
- `auto_thread: true` (creates threads for conversations)
- `free_response_channels: ''` (leave empty unless specific channels)

Environment variables to verify in `~/.hermes/.env`:
- `DISCORD_BOT_TOKEN=your_token_here`
- `DISCORD_HOME_CHANNEL=channel_id_here` (optional)
- `DISCORD_ALLOWED_USERS=user_id_here` (optional)

### 6. Permission Requirements
Ensure bot has these Discord permissions:
- Read Messages/View Channels
- Send Messages
- Use Application Commands (for slash commands)
- Read Message History (if reading past messages)
- If bot appears offline: Check application not reset/reinvited needed

### 7. Troubleshooting Flow
If bot still not responding:

1. **Check logs immediately after startup** for auth/connection errors
2. **Verify exact bot name/tag** - case sensitive, include discriminator (`#3295`)
3. **Test in DM first** - many bots require DM initiation
4. **Check server permissions** - bot may lack needed permissions
5. **Look for rate limiting** in logs if spamming commands
6. **Verify intents** - bot may not be subscribed to message events

## Key Learnings from Experience
- Environment variables from `.env` **must be explicitly loaded** - they don't auto-load
- Gateway has built-in timeout (~60 seconds) - not a malfunction
- Bot connection and command syncing in logs **proves** it's working
- Lack of visible response often means **incorrect interaction method** (wrong channel, not DMing first, not using exact name, missing mention)
- Successful connection logs show: connected → synced commands → ✓ discord connected
- The **most valuable diagnostic** is watching the gateway logs in real-time during startup

### Cloudflare WAF Blocking (error code 1010)
**Symptom:** REST API calls to `discord.com/api/v10/` return 403 with body `error code: 1010`. Gateway WebSocket connection works (messages received) but `send_message` to Discord fails.

**Cause:** Cloudflare's WAF blocks datacenter IPs on Discord's REST API endpoints. The machine's IP is classified as a datacenter/cloud IP and is rejected at the Cloudflare layer before reaching Discord's servers.

**Diagnosis:**
```python
import os, json, urllib.request
env_text = open(os.path.expanduser("~/.hermes/.env")).read()
token = env_text.split("DISCORD_BOT_TOKEN=")[1].split("\n")[0]
req = urllib.request.Request(
    "https://discord.com/api/v10/users/@me",
    headers={"Authorization": f"Bot {token}"}
)
try:
    resp = urllib.request.urlopen(req)
    print("REST API works:", json.loads(resp.read()))
except Exception as e:
    print(f"REST API blocked: {e}")  # 403 + error code: 1010 = Cloudflare block
```

**Why WebSocket works but REST doesn't:**
- Gateway connects to `gateway.discord.gg` (WebSocket) — different Cloudflare endpoint, not IP-blocked
- `_send_discord()` in `tools/send_message_tool.py:489` makes direct REST POST to `discord.com/api/v10/channels/{id}/messages` — blocked by Cloudflare

**Impact:**
- `send_message(target="discord:...")` always fails from datacenter IPs
- Cron jobs writing to `discord-outbox/` as fallback — but **gateway does NOT process the outbox** (no outbox pickup code exists in gateway). Files pile up undelivered.

**Workaround:** Route Discord sends through the gateway adapter's `discord.py` client (WebSocket) instead of REST API. Or use a residential proxy. Or accept that cron jobs can't send to Discord from this IP.

### discord-outbox is a dead end
The `discord-outbox/` directory in `~/.hermes/` is written to by agents as a fallback when `send_message` fails, but the gateway has **zero code** that reads or processes files from this directory. It's not a delivery mechanism — it's a silent data graveyard.

## Verification Checklist
When troubleshooting, confirm:
- [ ] .env file contains `DISCORD_BOT_TOKEN`
- [ ] Environment variables loaded before starting gateway
- [ ] Gateway starts without import/module errors
- [ ] Logs show: connecting → logged in → gateway connected → synced commands
- [ ] Gateway shows "running with 2 platform(s)" (Telegram + Discord)
- [ ] You interact with bot using correct method during runtime window
- [ ] Bot shows "thinking..." when processing requests

## Recovery Procedure
If bot appears stuck or unresponsive:
1. Check logs for graceful shutdown indications
2. Restart with proper environment loading
3. Wait for "✓ discord connected" in logs
4. Immediately test interaction in Discord
5. Remember: Runtime limited to ~60 seconds by design