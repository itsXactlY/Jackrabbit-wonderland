# Deployment Guide

## Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.8+ | Runtime |
| pycryptodome | Latest | AES256-GCM (only pip dependency) |
| JackrabbitDLM | Latest | Volatile key vault |
| Podman | 4+ | Container deployment |
| systemd | Any | Service management |
| nftables | Any | Firewall (LAN-only) |
| sudo | Any | Service + firewall install |

## Installation

### Podman

This repo can run as a two-container Podman pod: one JackrabbitDLM container and
one gateway container. The pod publishes the OpenAI-compatible Wonderland proxy
on `http://127.0.0.1:18080/v1`.

Traffic from the Wonderland proxy to real LLM endpoints uses the Remember
Protocol only: `remember::<base64>` user/tool payloads and the Remember Protocol
system header. The gateway does not send AES headers, AES ciphertext, or AES key
material upstream.

Podman maps host ports `18080`, `17373`, and `17374` to the container's internal
gateway/DLM ports `8080`, `37373`, and `37374` to avoid colliding with native
systemd deployments.

```bash
cd /home/alca/projects/hermes-crypto

# Build the local image.
container/run-podman.sh build

# Start JackrabbitDLM + gateway in one pod.
container/run-podman.sh start

# Verify.
container/run-podman.sh status
curl -s http://127.0.0.1:18080/v1/models | python3 -m json.tool
```

Client projects should not duplicate the endpoint/model settings. Source the
repo-owned file instead:

```bash
set -a
. /home/alca/projects/hermes-crypto/container/wonderland.env
set +a
```

That file is the source of truth for projects using `wonderland`:

| Variable | Value |
|----------|-------|
| `OPENAI_BASE_URL` | `http://127.0.0.1:18080/v1` |
| `OPENAI_MODEL` | `wonderland` |
| `WONDERLAND_BASE_URL` | `http://127.0.0.1:18080/v1` |
| `WONDERLAND_MODEL` | `wonderland` |

To make the host Hermes CLI use that same gateway by default, sync its local
provider config from the source-of-truth file:

```bash
container/run-podman.sh configure-hermes
```

This creates or updates the named Hermes custom provider `wonderland`, sets the
default model to `wonderland`, and keeps a timestamped backup of
`~/.hermes/config.yaml`.

If the gateway needs provider keys or a specific upstream provider model, copy
`container/gateway.env.example` to `container/gateway.env`. That local file is
ignored by git.

```bash
cp container/gateway.env.example container/gateway.env
$EDITOR container/gateway.env
container/run-podman.sh restart
```

You can also use Compose-compatible Podman:

```bash
podman compose -f container/podman-compose.yml up -d --build
```

The image includes only JackrabbitDLM and the Wonderland gateway/encryption
proxy. It does not install `hermes-agent` inside the pod.

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
