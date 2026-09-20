#!/usr/bin/env bash
# install-apk-gateway.sh — take a pod from nothing to "ready to scan QR".
#
# This is the orchestration that was missing. Every step below was, on
# alca-desk 2026-09-20, performed by hand after the app failed to connect, and
# every one of them is a way a customer pod silently ends up un-pairable:
#
#   1. the /opt hermes-gateway@ service was RUNNING and holding :8443. It is a
#      pre-TLS build — no --tls-* flags, no /pair, no token auth — so it answers
#      /status while being the wrong process. Anything that binds :8443 after it
#      dies with "Address already in use", and the pod looks healthy throughout.
#   2. mazemaker-apk-gateway.service was never started. Its EnvironmentFile had
#      no leading '-', so a missing container/gateway.env makes it refuse to start.
#   3. no gateway.token -> /pair answers 503 "gateway not hardened".
#   4. no TLS cert -> the gateway serves plaintext, and the app's URL is
#      hardcoded "https://", so it can never connect.
#   5. mazemaker-apk-gateway-mdns.service was never started -> the host-less
#      pairing code resolves to nothing and the app reports "could not find the
#      gateway on this device".
#   6. /home/JackrabbitDLM/Quarantine was missing, and jackrabbit-dlm@.service
#      lists it in ReadWritePaths. systemd fails mount-namespace setup for a
#      nonexistent path and kills the unit before Python runs; Restart=always
#      then loops it as `activating (auto-restart)` forever.
#
# Idempotent — safe to re-run. --dry-run prints every action without taking it.
#
# Usage:  bash install-apk-gateway.sh [--dry-run] [--force]
#           --force  regenerate the token + cert even if they exist

set -euo pipefail

DRY=0; FORCE=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --force)   FORCE=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HC="${HERMES_CRYPTO_HOME:-$HOME/.hermes-crypto}"
UD="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
PORT="${MM_GATEWAY_PORT:-8443}"
DLM_DIR="${JACKRABBITDLM_HOME:-/home/JackrabbitDLM}"
SVC_USER="${SUDO_USER:-$USER}"

step() { printf '\n== %s\n' "$*"; }
say()  { printf '  %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*" >&2; }
die()  { printf '\n\033[31mABORT:\033[0m %s\n' "$*" >&2; exit 1; }
run()  { if [[ $DRY == 1 ]]; then printf '  [dry-run] %s\n' "$*"; else "$@"; fi; }

[[ -f "$REPO/lan_gateway.py" ]] || die "lan_gateway.py not found in $REPO — run from the hermes-crypto checkout"
[[ -d "$REPO/systemd/user" ]]   || die "missing $REPO/systemd/user/ — this checkout predates the versioned units"

step "Preconditions"
command -v openssl >/dev/null || die "openssl is required (token + self-signed cert)"
if ! command -v avahi-publish-service >/dev/null; then
  warn "avahi-publish-service not found — the app discovers the gateway over mDNS,"
  warn "so without it pairing fails with 'could not find the gateway on this device'."
  if   command -v pacman  >/dev/null; then run sudo pacman -S --noconfirm avahi nss-mdns
  elif command -v apt-get >/dev/null; then run sudo apt-get install -y avahi-daemon avahi-utils
  else die "install avahi manually (need avahi-publish-service), then re-run"; fi
else
  ok "avahi present"
fi
command -v qrencode >/dev/null || warn "qrencode missing — no QR will be rendered (the code still prints)"

step "Retire the stale /opt service (it squats :$PORT and looks healthy)"
# hermes-gateway@ is the OLD /opt deployment: pre-TLS, no /pair, no token auth.
# It must not hold the port the app is paired against. Only touched when it is
# actually installed — this is not the same unit as the APK gateway.
if systemctl list-unit-files "hermes-gateway@${SVC_USER}.service" >/dev/null 2>&1 \
   && systemctl is-active --quiet "hermes-gateway@${SVC_USER}.service" 2>/dev/null; then
  run sudo systemctl disable --now "hermes-gateway@${SVC_USER}.service"
  ok "stopped + disabled hermes-gateway@${SVC_USER} (the /opt pre-TLS build)"
else
  ok "hermes-gateway@${SVC_USER} not active — nothing squatting :$PORT"
fi

step "DLM read-write paths (a missing one kills the unit at NAMESPACE)"
if [[ -d "$DLM_DIR" ]]; then
  for d in Logs Disk Quarantine; do
    if [[ -d "$DLM_DIR/$d" ]]; then ok "$DLM_DIR/$d exists"
    else run mkdir -p "$DLM_DIR/$d"; ok "created $DLM_DIR/$d"; fi
  done
else
  warn "$DLM_DIR not present — JackrabbitDLM is not installed; skipping"
fi

step "Secrets: bearer token + self-signed TLS cert (provision-apk.sh)"
# Test the VALUE, not setness: `${FORCE:+ --force}` emits the flag for FORCE=0
# too, because 0 is a set, non-empty value — a dry-run then claims it is about
# to force-regenerate live secrets it will not touch.
PROV_ARGS=()
if [[ $FORCE == 1 ]]; then PROV_ARGS+=(--force); fi
if [[ $DRY == 1 ]]; then
  say "[dry-run] bash $REPO/provision-apk.sh ${PROV_ARGS[*]:-}"
else
  bash "$REPO/provision-apk.sh" ${PROV_ARGS[@]+"${PROV_ARGS[@]}"} | sed 's/^/  /'
fi

step "Provider env (the unit's EnvironmentFile must exist for it to start)"
if [[ -f "$REPO/container/gateway.env" ]]; then ok "container/gateway.env present"
elif [[ -f "$REPO/container/gateway.env.example" ]]; then
  run cp "$REPO/container/gateway.env.example" "$REPO/container/gateway.env"
  warn "created container/gateway.env from the example — set your provider key"
else
  warn "no gateway.env or .example — the LLM proxy will have no upstream"
fi

step "Install the user units"
run mkdir -p "$UD"
for u in mazemaker-apk-gateway.service mazemaker-apk-gateway-mdns.service; do
  if [[ $DRY == 1 ]]; then say "[dry-run] install -m644 $REPO/systemd/user/$u $UD/"
  else install -m644 "$REPO/systemd/user/$u" "$UD/$u"; ok "installed $u"; fi
done
run systemctl --user daemon-reload

step "Retire the old /opt-style system copy so the user unit is what runs"
if [[ -f /etc/systemd/system/mazemaker-apk-gateway.service ]]; then
  run sudo systemctl disable --now mazemaker-apk-gateway.service 2>/dev/null || true
  warn "a SYSTEM mazemaker-apk-gateway.service existed and was disabled"
fi

step "Start + enable"
run systemctl --user enable mazemaker-apk-gateway.service
run systemctl --user restart mazemaker-apk-gateway.service
run systemctl --user enable mazemaker-apk-gateway-mdns.service
run systemctl --user restart mazemaker-apk-gateway-mdns.service

if [[ $DRY == 1 ]]; then
  printf '\n== Dry run complete — nothing was changed.\n'
  exit 0
fi

step "Verify"

# POLL, do not sleep-and-hope. The gateway needs a moment to complete its DLM
# session handshake, and avahi a moment to register the service. A fixed
# `sleep 2` reported a fully healthy gateway (listening on :8443, advertising
# with 4 resolved records) as broken on 2026-09-20 — the check was wrong, not
# the service. Anything that reports a false failure here trains the operator
# to ignore the one time it is real.
_poll() {  # _poll <timeout-s> <label> <cmd...>
  local timeout="$1" label="$2"; shift 2
  local deadline=$(( $(date +%s) + timeout ))
  until "$@" >/dev/null 2>&1; do
    if (( $(date +%s) >= deadline )); then return 1; fi
    sleep 1
  done
  return 0
}

fail=0
for u in mazemaker-apk-gateway.service mazemaker-apk-gateway-mdns.service; do
  st="$(systemctl --user is-active "$u" 2>/dev/null || true)"
  printf '  %-42s %s\n' "$u" "$st"
  [[ "$st" == active ]] || fail=1
done

if _poll 30 "gateway" bash -c "curl -sk --max-time 5 'https://127.0.0.1:$PORT/status' 2>/dev/null | grep -q '\"gateway\"'"; then
  ok "TLS on :$PORT answers"
else
  warn "https://127.0.0.1:$PORT/status did not answer within 30s"
  warn "  journalctl --user -u mazemaker-apk-gateway.service -n 40"
  fail=1
fi

if command -v avahi-browse >/dev/null; then
  if _poll 20 "mdns" bash -c "timeout 5 avahi-browse -rtp _mazemaker-gw._tcp 2>/dev/null | grep -q _mazemaker-gw"; then
    ok "mDNS advertising _mazemaker-gw._tcp (the app can discover it)"
  else
    warn "nothing advertising _mazemaker-gw._tcp within 20s — the app will not find the gateway"
    warn "  journalctl --user -u mazemaker-apk-gateway-mdns.service -n 40"
    fail=1
  fi
fi

cat <<EOF

== Pair your phone
   Open  https://127.0.0.1:$PORT/pair  in a browser ON THIS HOST.
   (Loopback-only by design — a LAN origin gets 403, because the page carries
   the bearer token.) Scan the QR from the app:
       Settings > Secure Gateway > SCAN QR
EOF

if [[ $fail != 0 ]]; then
  die "one or more checks failed — see the warnings above"
fi
ok "gateway is up and discoverable"
