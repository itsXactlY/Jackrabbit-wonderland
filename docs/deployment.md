# Deployment Guide

## Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.8+ | Runtime |
| pycryptodome | Latest | AES256-GCM (only pip dependency) |
| JackrabbitDLM | Latest | Volatile key vault |
| systemd | Any | Service management |
| nftables | Any | Firewall (LAN-only) |
| sudo | Any | Service + firewall install |

## Installation

### Automatic

```bash
git clone https://github.com/itsXactlY/hermes-crypto.git
cd hermes-crypto
sudo bash install.sh
```

The installer:

1. **Checks for JackrabbitDLM** — clones to `/home/JackrabbitDLM` if missing
2. **Installs pycryptodome** — `pip install pycryptodome`
3. **Copies files** — to `/opt/hermes-crypto/`
4. **Installs systemd services** — `jackrabbit-dlm@$USER`, `hermes-gateway@$USER`
5. **Adds nftables rules** — LAN-only access (192.168.0.0/24)
6. **Starts both services**
7. **Verifies** — health check + test encrypt/decrypt

### Manual

```bash
# 1. Install JackrabbitDLM
git clone https://github.com/rapmd73/JackrabbitDLM.git /home/JackrabbitDLM

# 2. Install pycryptodome
pip install pycryptodome

# 3. Copy files
sudo mkdir -p /opt/hermes-crypto
sudo cp crypto_middleware.py dlm_vault.py crypto_plugin.py \
        lan_gateway.py remember_protocol.py /opt/hermes-crypto/

# 4. Install systemd services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 5. Add firewall rules
sudo nano /etc/nftables.conf
# Add: ip saddr 192.168.0.0/24 tcp dport { 8080, 37373, 37374 } accept
sudo nft -f /etc/nftables.conf

# 6. Start services
sudo systemctl enable --now jackrabbit-dlm@$USER
sudo systemctl enable --now hermes-gateway@$USER
```

## Service Management

```bash
# Status
systemctl status jackrabbit-dlm@$USER
systemctl status hermes-gateway@$USER

# Logs
journalctl -u jackrabbit-dlm@$USER -f
journalctl -u hermes-gateway@$USER -f

# Restart
sudo systemctl restart jackrabbit-dlm@$USER
sudo systemctl restart hermes-gateway@$USER

# Stop
sudo systemctl stop hermes-gateway@$USER
sudo systemctl stop jackrabbit-dlm@$USER
```

## Service Configuration

### jackrabbit-dlm@.service

```ini
[Service]
Type=simple
User=%i
WorkingDirectory=/home/JackrabbitDLM
ExecStart=/usr/bin/python3 /home/JackrabbitDLM/JackrabbitDLM 0.0.0.0 37373
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/home/JackrabbitDLM/Logs /home/JackrabbitDLM/Disk /home/JackrabbitDLM/Quarantine
PrivateTmp=yes
MemoryMax=256M
TasksMax=64
```

### hermes-gateway@.service

```ini
[Unit]
After=network-online.target jackrabbit-dlm@%i.service

[Service]
Type=simple
User=%i
WorkingDirectory=/opt/hermes-crypto
ExecStart=/usr/bin/python3 /opt/hermes-crypto/lan_gateway.py --port 8080 --tcp-port 37374
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/opt/hermes-crypto
PrivateTmp=yes
MemoryMax=128M
TasksMax=32
```

## Firewall

### nftables (recommended)

```nft
# /etc/nftables.conf — add these rules

# Hermes Crypto Gateway - LAN only
ip saddr 192.168.0.0/24 tcp dport { 8080, 37373, 37374 } accept
```

Apply: `sudo nft -f /etc/nftables.conf`

### iptables (legacy)

```bash
sudo iptables -A INPUT -s 192.168.0.0/24 -p tcp --dport 8080 -j ACCEPT
sudo iptables -A INPUT -s 192.168.0.0/24 -p tcp --dport 37373 -j ACCEPT
sudo iptables -A INPUT -s 192.168.0.0/24 -p tcp --dport 37374 -j ACCEPT
```

## Uninstall

```bash
sudo bash install.sh --uninstall
```

Removes:
- Systemd services
- `/opt/hermes-crypto/` directory
- nftables rules

Preserves:
- JackrabbitDLM (shared resource, used by other projects)

## Verification

```bash
# 1. Services running
systemctl is-active jackrabbit-dlm@$USER   # → active
systemctl is-active hermes-gateway@$USER    # → active

# 2. DLM reachable
curl -s http://localhost:8080/status | python3 -m json.tool

# 3. Web UI accessible
curl -s http://localhost:8080/ | head -5

# 4. Full test
cd ~/projects/hermes-crypto
python3 dlm_vault.py demo
```

## Ports

| Port | Protocol | Service | Access |
|------|----------|---------|--------|
| 8080 | HTTP | Gateway (Web UI + JSON API) | LAN only |
| 37373 | TCP | JackrabbitDLM (key vault) | LAN only |
| 37374 | TCP | Gateway (raw TCP, netcat) | LAN only |
