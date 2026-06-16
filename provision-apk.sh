#!/usr/bin/env bash
# Provision the LAN-hardening secrets the gateway needs to serve mobile clients
# securely: a bearer token (gates shell/hermes/pulse) and a self-signed TLS cert
# (the app pins it). Idempotent — existing files are kept unless --force.
#
# Usage:
#   ./provision-apk.sh [LAN_IP ...]        # default: autodetect primary LAN IPv4
#   ./provision-apk.sh --force 192.168.0.2
#
# Prints the token and the cert SHA-256 fingerprint to paste/pin in the app.
set -euo pipefail

HOME_DIR="${HERMES_CRYPTO_HOME:-$HOME/.hermes-crypto}"
FORCE=0
IPS=()
for a in "$@"; do
  if [[ "$a" == "--force" ]]; then FORCE=1; else IPS+=("$a"); fi
done
if [[ ${#IPS[@]} -eq 0 ]]; then
  primary="$(ip -4 route get 1.1.1.1 2>/dev/null | grep -oE 'src [0-9.]+' | awk '{print $2}')"
  [[ -n "${primary:-}" ]] && IPS+=("$primary")
fi
IPS+=("127.0.0.1")

mkdir -p "$HOME_DIR"; chmod 700 "$HOME_DIR"
TOKEN_FILE="$HOME_DIR/gateway.token"
CRT="$HOME_DIR/gateway.crt"
KEY="$HOME_DIR/gateway.key"

# --- token ---
if [[ $FORCE -eq 1 || ! -s "$TOKEN_FILE" ]]; then
  openssl rand -hex 32 > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
  echo "token: generated $TOKEN_FILE"
else
  echo "token: kept existing $TOKEN_FILE"
fi

# --- self-signed cert with SANs for every LAN IP the phone might dial ---
if [[ $FORCE -eq 1 || ! -s "$CRT" || ! -s "$KEY" ]]; then
  san=""; i=0
  for ip in "${IPS[@]}"; do san+="IP:$ip,"; i=$((i+1)); done
  san+="DNS:localhost"
  openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
    -keyout "$KEY" -out "$CRT" \
    -subj "/CN=mazemaker-gateway" \
    -addext "subjectAltName=${san}" >/dev/null 2>&1
  chmod 600 "$KEY" "$CRT"
  echo "cert:  generated $CRT (SAN ${san})"
else
  echo "cert:  kept existing $CRT"
fi

echo
echo "=== paste/pin these in the Mazemaker app ==="
echo "GATEWAY_TOKEN     : $(cat "$TOKEN_FILE")"
fp="$(openssl x509 -in "$CRT" -noout -fingerprint -sha256 | sed 's/.*=//')"
echo "CERT SHA-256 (pin): $fp"
# OkHttp CertificatePinner wants base64(sha256(SPKI)); emit that too.
spki="$(openssl x509 -in "$CRT" -noout -pubkey \
  | openssl pkey -pubin -outform der 2>/dev/null \
  | openssl dgst -sha256 -binary | openssl enc -base64)"
echo "OkHttp pin        : sha256/$spki"

# Pairing code — a TINY base64(JSON{v,host,token,fp}). The ~2 KB cert is NOT in
# the code: the app fetches it from the gateway at pair time and verifies
# sha256(SPKI) == fp before pinning it. So the code stays ~120 chars (crisp QR,
# short paste) while the scanned fingerprint remains the trust anchor.
first_ip="${IPS[0]}"
payload_host="${MM_GATEWAY_HOST:-$first_ip:8443}"
payload="$(GATEWAY_HOST="$payload_host" \
  TOKEN="$(cat "$TOKEN_FILE")" FP="$spki" python3 - <<'PY'
import os, json, base64
doc = {
    "v": 1,
    "host": os.environ["GATEWAY_HOST"],
    "token": os.environ["TOKEN"],
    "fp": os.environ["FP"],   # base64(sha256(SPKI)) — fetched cert verified against this
}
print(base64.b64encode(json.dumps(doc).encode()).decode())
PY
)"
echo
echo "=== app pairing code (paste into Settings → Secure Gateway) ==="
echo "$payload"
echo "(${#payload} chars — cert is fetched+verified on pairing, not embedded)"

# Scannable QR for Settings → Secure Gateway → SCAN QR (Phase-3 pairing).
if command -v qrencode >/dev/null 2>&1; then
  echo
  echo "=== or scan this QR (Settings → Secure Gateway → SCAN QR) ==="
  printf '%s' "$payload" | qrencode -t ANSIUTF8
  png="$HOME_DIR/pairing-qr.png"
  printf '%s' "$payload" | qrencode -o "$png" -s 6 2>/dev/null && echo "QR PNG: $png"
else
  echo "(install qrencode to render a scannable QR of the payload above)"
fi
