# Troubleshooting

## DLM Server Not Starting

### Symptom
`systemctl status jackrabbit-dlm@$USER` shows `failed` or `inactive`.

### Check
```bash
journalctl -u jackrabbit-dlm@$USER -n 50
```

### Common Causes

| Cause | Fix |
|-------|-----|
| Port 37373 in use | `ss -tlnp | grep 37373` — kill conflicting process |
| JackrabbitDLM not installed | `git clone https://github.com/rapmd73/JackrabbitDLM.git /home/JackrabbitDLM` |
| Python not found | Ensure `/usr/bin/python3` exists |
| Memory limit exceeded | Increase `MemoryMax` in service file (default 256M) |

---

## Gateway Not Starting

### Symptom
`systemctl status hermes-gateway@$USER` shows `failed`.

### Check
```bash
journalctl -u hermes-gateway@$USER -n 50
```

### Common Causes

| Cause | Fix |
|-------|-----|
| DLM not running | Start jackrabbit-dlm first |
| Port 8080 in use | `ss -tlnp | grep 8080` — kill conflicting process |
| Missing modules | `cd /opt/hermes-crypto && python3 -c "from remember_protocol import RememberProtocol"` |
| pycryptodome not installed | `pip install pycryptodome` |

---

## Decryption Fails

### Symptom
`decrypt()` raises `ValueError: Decryption failed with all available keys.`

### Common Causes

| Cause | Fix |
|-------|-----|
| Key rotated | Data encrypted with old key — check `_key_history` |
| Wrong session | Different session = different key |
| DLM restarted | Key in volatile memory — gone after restart |
| Corrupted blob | Base64 decode error or truncated data |

### Debug
```python
cm.status()
# Check: session_active, keys_in_history, message_count
```

---

## DLM Connection Refused

### Symptom
`DLM server not reachable at 127.0.0.1:37373`

### Check
```bash
# Is DLM running?
systemctl is-active jackrabbit-dlm@$USER

# Is it listening?
ss -tlnp | grep 37373

# Can you connect?
python3 -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 37373)); print('OK')"
```

---

## LAN Devices Can't Connect

### Symptom
Phone/tablet can't reach `http://192.168.0.2:8080`

### Check

```bash
# Firewall rules
sudo nft list ruleset | grep "8080\|37373\|37374"

# Listening on 0.0.0.0?
ss -tlnp | grep 8080

# Ping from phone
ping 192.168.0.2
```

### Common Causes

| Cause | Fix |
|-------|-----|
| Firewall blocking | Add nftables rules (see deployment.md) |
| Bound to 127.0.0.1 | Restart with `--bind 0.0.0.0` |
| Different subnet | Check phone IP is in 192.168.0.0/24 |
| WiFi isolation | Disable AP client isolation |

---

## DLMLocker Import Error

### Symptom
`DLMLocker.py not found. Install JackrabbitDLM to /home/JackrabbitDLM first.`

### Fix
```bash
# DLMLocker.py must be at /home/JackrabbitDLM/DLMLocker.py
ls -la /home/JackrabbitDLM/DLMLocker.py

# If missing, re-clone
git clone https://github.com/rapmd73/JackrabbitDLM.git /home/JackrabbitDLM
```

---

## Key Verification Failed

### Symptom
`Key verification failed — DLM round-trip mismatch`

### Cause
DLM returned different data than what was stored. Possible DLM corruption or version mismatch.

### Fix
```bash
# Restart DLM (destroys all keys)
sudo systemctl restart jackrabbit-dlm@$USER

# Retry session creation
python3 dlm_vault.py session
```

---

## Service Keeps Restarting

### Symptom
`systemctl status` shows high restart count.

### Check
```bash
journalctl -u jackrabbit-dlm@$USER --since "1 hour ago" | grep -i "error\|exception\|traceback"
```

### Common Causes

| Cause | Fix |
|-------|-----|
| OOM killed | Increase `MemoryMax` |
| Port conflict | Check for other processes on same port |
| Python crash | Check for import errors in logs |

---

## Performance Issues

### Symptom
Gateway responses are slow.

### Check
```bash
# DLM memory usage
systemctl status jackrabbit-dlm@$USER | grep Memory

# Gateway memory
systemctl status hermes-gateway@$USER | grep Memory

# Active connections
ss -tnp | grep -E "8080|37373|37374" | wc -l
```

### Common Causes

| Cause | Fix |
|-------|-----|
| Too many sessions | Kill old sessions via `kill` command |
| DLM memory near limit | Increase `MemoryMax` or restart DLM |
| PULSE timeout | PULSE has 60s timeout on gateway calls |

---

## Uninstall Issues

### Manual Cleanup

```bash
# Stop services
sudo systemctl stop hermes-gateway@$USER
sudo systemctl stop jackrabbit-dlm@$USER

# Disable
sudo systemctl disable hermes-gateway@$USER
sudo systemctl disable jackrabbit-dlm@$USER

# Remove service files
sudo rm /etc/systemd/system/hermes-gateway@.service
sudo rm /etc/systemd/system/jackrabbit-dlm@.service
sudo systemctl daemon-reload

# Remove files
sudo rm -rf /opt/hermes-crypto

# Remove firewall rules
sudo nano /etc/nftables.conf  # Delete hermes-crypto rules
sudo nft -f /etc/nftables.conf

# JackrabbitDLM preserved (shared resource)
# To remove: rm -rf /home/JackrabbitDLM
```
