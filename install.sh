#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  HERMES-CRYPTO — Zero-Knowledge AES256 Layer for Hermes Agent
#  All-in-one installer
# ═══════════════════════════════════════════════════════════════
#
#  Installs:
#    1. JackrabbitDLM (if not present) — volatile key vault
#    2. Hermes Crypto middleware — AES256-GCM encrypt/decrypt
#    3. LAN Gateway — HTTP + raw TCP control interface
#    4. Systemd services — auto-start on boot
#    5. nftables rules — LAN-only access
#
#  Usage:
#    bash install.sh              # Full install
#    bash install.sh --check      # Verify only
#    bash install.sh --uninstall  # Remove everything
#    bash install.sh --no-firewall # Skip nftables
#
#  Requirements:
#    - Python 3.8+
#    - sudo access (for systemd + nftables)
#    - Internet (for pycryptodome pip install)
#
set -euo pipefail

# ─── Config ───────────────────────────────────────────────────

INSTALL_DIR="/opt/hermes-crypto"
DLM_DIR="/home/JackrabbitDLM"
DLM_REPO="https://github.com/rapmd73/JackrabbitDLM.git"
GATEWAY_PORT=8080
RAW_TCP_PORT=37374
DLM_PORT=37373
SERVICE_USER="${SUDO_USER:-$USER}"

# ─── Colors ───────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

# ─── Parse args ───────────────────────────────────────────────

MODE="install"
SKIP_FIREWALL=false

for arg in "$@"; do
    case $arg in
        --check)       MODE="check" ;;
        --uninstall)   MODE="uninstall" ;;
        --no-firewall) SKIP_FIREWALL=true ;;
        --help|-h)
            echo "Usage: bash install.sh [--check|--uninstall|--no-firewall]"
            exit 0
            ;;
    esac
done

# ─── Banner ───────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║  HERMES-CRYPTO — Zero-Knowledge AES256       ║${NC}"
echo -e "${BOLD}${CYAN}║  JackrabbitDLM + LAN Gateway + Hermes        ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ─── Uninstall ────────────────────────────────────────────────

if [ "$MODE" = "uninstall" ]; then
    echo -e "${BOLD}Uninstalling hermes-crypto...${NC}"
    
    # Stop services
    sudo systemctl stop hermes-gateway@"$SERVICE_USER" 2>/dev/null && ok "Stopped gateway" || true
    sudo systemctl disable hermes-gateway@"$SERVICE_USER" 2>/dev/null && ok "Disabled gateway" || true
    sudo systemctl stop jackrabbit-dlm@"$SERVICE_USER" 2>/dev/null && ok "Stopped DLM" || true
    sudo systemctl disable jackrabbit-dlm@"$SERVICE_USER" 2>/dev/null && ok "Disabled DLM" || true
    
    # Remove service files
    sudo rm -f /etc/systemd/system/hermes-gateway@"$SERVICE_USER".service
    sudo rm -f /etc/systemd/system/jackrabbit-dlm@"$SERVICE_USER".service
    sudo systemctl daemon-reload
    ok "Removed systemd services"
    
    # Remove install dir
    if [ -d "$INSTALL_DIR" ]; then
        sudo rm -rf "$INSTALL_DIR"
        ok "Removed $INSTALL_DIR"
    fi
    
    # Remove nftables rules
    if [ -f /etc/nftables.conf ]; then
        sudo sed -i '/# Hermes Crypto Gateway/,/accept$/d' /etc/nftables.conf 2>/dev/null && ok "Removed nftables rules" || true
    fi
    
    echo ""
    echo -e "${GREEN}Uninstall complete.${NC}"
    echo -e "${YELLOW}JackrabbitDLM at $DLM_DIR was NOT removed (shared resource).${NC}"
    exit 0
fi

# ─── Check mode ───────────────────────────────────────────────

echo -e "${BOLD}Checking system...${NC}"
echo ""

CHECKS_PASSED=0
CHECKS_TOTAL=0

check() {
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    if eval "$2" >/dev/null 2>&1; then
        ok "$1"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
    else
        fail "$1"
    fi
}

check "Python 3 available"         "python3 --version"
check "pip available"              "python3 -m pip --version"
check "pycryptodome installed"     "python3 -c 'from Crypto.Cipher import AES'"
check "JackrabbitDLM exists"       "test -f $DLM_DIR/JackrabbitDLM"
check "DLMLocker.py exists"        "test -f $DLM_DIR/DLMLocker.py"
check "hermes-crypto files exist"  "test -f $INSTALL_DIR/crypto_middleware.py"
check "Gateway service installed"  "test -f /etc/systemd/system/hermes-gateway@${SERVICE_USER}.service"
check "DLM service installed"      "test -f /etc/systemd/system/jackrabbit-dlm@${SERVICE_USER}.service"
check "Gateway running"            "curl -sf http://127.0.0.1:$GATEWAY_PORT/status"
check "DLM running"                "python3 -c \"import sys; sys.path.insert(0,'$DLM_DIR'); from DLMLocker import Locker; l=Locker('hc',Host='127.0.0.1',Port=$DLM_PORT,ID='test'); l.Version()\""
check "nftables rules present"     "grep -q 'Hermes Crypto' /etc/nftables.conf"

echo ""
echo -e "  ${BOLD}$CHECKS_PASSED/$CHECKS_TOTAL checks passed${NC}"

if [ "$MODE" = "check" ]; then
    exit 0
fi

# ─── Install ──────────────────────────────────────────────────

echo ""
echo -e "${BOLD}Installing...${NC}"
echo ""

# 1. Python + pip
info "Checking Python..."
python3 --version || { fail "Python 3 not found"; exit 1; }
ok "Python $(python3 --version 2>&1 | cut -d' ' -f2)"

# 2. pycryptodome
info "Installing pycryptodome..."
if python3 -c "from Crypto.Cipher import AES" 2>/dev/null; then
    ok "pycryptodome already installed"
else
    python3 -m pip install pycryptodome --break-system-packages --quiet 2>/dev/null || \
    python3 -m pip install pycryptodome --quiet
    ok "pycryptodome installed"
fi

# 3. JackrabbitDLM
info "Checking JackrabbitDLM..."
if [ -f "$DLM_DIR/JackrabbitDLM" ]; then
    ok "JackrabbitDLM already installed at $DLM_DIR"
else
    info "Cloning JackrabbitDLM..."
    sudo git clone "$DLM_REPO" "$DLM_DIR"
    sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$DLM_DIR"
    ok "JackrabbitDLM installed"
fi

# 4. Create install directory
info "Setting up $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp -v crypto_middleware.py "$INSTALL_DIR/"
sudo cp -v remember_protocol.py "$INSTALL_DIR/"
sudo cp -v dlm_vault.py "$INSTALL_DIR/"
sudo cp -v crypto_plugin.py "$INSTALL_DIR/"
sudo cp -v lan_gateway.py "$INSTALL_DIR/"
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
ok "Files copied to $INSTALL_DIR"

# 5. Systemd services
info "Installing systemd services..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

sudo cp "$SCRIPT_DIR/systemd/jackrabbit-dlm@.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/hermes-gateway@.service" /etc/systemd/system/
sudo systemctl daemon-reload
ok "Systemd services installed"

# Enable services
sudo systemctl enable jackrabbit-dlm@"$SERVICE_USER" 2>/dev/null && ok "DLM enabled on boot" || warn "Could not enable DLM"
sudo systemctl enable hermes-gateway@"$SERVICE_USER" 2>/dev/null && ok "Gateway enabled on boot" || warn "Could not enable gateway"

# 6. Start services
info "Starting services..."

# Kill existing processes if running
pkill -f "python3.*JackrabbitDLM.*37373" 2>/dev/null && sleep 1 || true
pkill -f "python3.*lan_gateway.py" 2>/dev/null && sleep 1 || true

sudo systemctl start jackrabbit-dlm@"$SERVICE_USER" 2>/dev/null && ok "DLM started" || warn "DLM may already be running"
sleep 2
sudo systemctl start hermes-gateway@"$SERVICE_USER" 2>/dev/null && ok "Gateway started" || warn "Gateway may already be running"

# 7. nftables
if [ "$SKIP_FIREWALL" = false ]; then
    info "Configuring firewall..."
    if [ -f /etc/nftables.conf ]; then
        if grep -q "Hermes Crypto" /etc/nftables.conf; then
            ok "nftables rules already present"
        else
            # Add after Ollama rule
            sudo sed -i '/tcp dport 11434 accept/a\\n        # Hermes Crypto Gateway - LAN only\n        # JackrabbitDLM :37373, HTTP gateway :8080, Raw TCP :37374\n        ip saddr 192.168.0.0\/24 tcp dport { 8080, 37373, 37374 } accept' /etc/nftables.conf
            sudo nft -f /etc/nftables.conf 2>/dev/null && ok "nftables rules applied" || warn "nftables reload failed (manual: sudo nft -f /etc/nftables.conf)"
        fi
    else
        warn "No /etc/nftables.conf found — skipping firewall rules"
    fi
else
    info "Skipping firewall (--no-firewall)"
fi

# 8. Verify
echo ""
echo -e "${BOLD}Verifying installation...${NC}"
echo ""

sleep 2

check "DLM running"     "systemctl is-active jackrabbit-dlm@$SERVICE_USER"
check "Gateway running"  "systemctl is-active hermes-gateway@$SERVICE_USER"
check "HTTP responds"    "curl -sf http://127.0.0.1:$GATEWAY_PORT/status"
check "TCP responds"     "echo '{\"cmd\":\"chaff\"}' | nc -w 2 127.0.0.1 $RAW_TCP_PORT"
check "Crypto works"     "cd $INSTALL_DIR && python3 crypto_middleware.py demo"

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║  INSTALLATION COMPLETE                       ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Services:${NC}"
echo -e "    DLM:     systemctl status jackrabbit-dlm@$SERVICE_USER"
echo -e "    Gateway: systemctl status hermes-gateway@$SERVICE_USER"
echo ""
echo -e "  ${BOLD}Access:${NC}"
echo -e "    Browser: http://$(hostname -I | awk '{print $1}'):$GATEWAY_PORT"
echo -e "    curl:    curl -X POST http://127.0.0.1:$GATEWAY_PORT/command -d '{\"cmd\":\"status\"}'"
echo -e "    netcat:  echo '{\"cmd\":\"chaff\"}' | nc 127.0.0.1 $RAW_TCP_PORT"
echo ""
echo -e "  ${BOLD}Hermes integration:${NC}"
echo -e "    cp $INSTALL_DIR/crypto_plugin.py ~/.hermes/plugins/"
echo -e "    (or symlink it)"
echo ""
echo -e "  ${BOLD}Logs:${NC}"
echo -e "    journalctl -u jackrabbit-dlm@$SERVICE_USER -f"
echo -e "    journalctl -u hermes-gateway@$SERVICE_USER -f"
echo ""
echo -e "  ${BOLD}Uninstall:${NC}"
echo -e "    bash install.sh --uninstall"
echo ""
