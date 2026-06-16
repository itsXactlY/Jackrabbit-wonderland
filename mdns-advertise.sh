#!/usr/bin/env bash
# Advertise the hardened APK gateway on the LAN via mDNS/DNS-SD so the phone can
# auto-discover host:port — no IP in the pairing code. Publishes the cert
# fingerprint in a TXT record as a convenience/cross-check (the authoritative
# trust anchor is still the scanned QR's fp). Foreground process: meant to be
# run by mazemaker-apk-gateway-mdns.service (avahi-publish-service blocks until
# killed, deregistering on exit).
set -euo pipefail

HOME_DIR="${HERMES_CRYPTO_HOME:-$HOME/.hermes-crypto}"
CRT="${GATEWAY_TLS_CERT:-$HOME_DIR/gateway.crt}"
PORT="${MM_GATEWAY_PORT:-8443}"
SVC_NAME="${MM_GATEWAY_MDNS_NAME:-Mazemaker Gateway}"

if [[ ! -s "$CRT" ]]; then
  echo "mdns-advertise: cert $CRT missing — run provision-apk.sh first" >&2
  exit 1
fi
command -v avahi-publish-service >/dev/null 2>&1 || {
  echo "mdns-advertise: avahi-publish-service not found (install avahi)" >&2
  exit 1
}

# base64(sha256(SPKI)) — same value provision-apk.sh puts in the pairing code.
fp="$(openssl x509 -in "$CRT" -noout -pubkey \
  | openssl pkey -pubin -outform der 2>/dev/null \
  | openssl dgst -sha256 -binary | openssl enc -base64)"

echo "mdns-advertise: publishing _mazemaker-gw._tcp on :$PORT (fp=${fp:0:12}…)" >&2
exec avahi-publish-service "$SVC_NAME" _mazemaker-gw._tcp "$PORT" "v=1" "fp=$fp"
