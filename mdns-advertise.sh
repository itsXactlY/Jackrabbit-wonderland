#!/usr/bin/env bash
# Advertise the hardened APK gateway on the LAN via mDNS/DNS-SD so the phone can
# auto-discover host:port — no IP in the pairing code. Publishes the cert
# fingerprint in a TXT record as a convenience/cross-check (the authoritative
# trust anchor is still the scanned QR's fp), and the LAN address as `a=`.
#
# A supervisor, not a one-shot: it outlives the conditions that used to kill it.
# Until 2026-10-08 this was one `exec avahi-publish-service` behind
# `set -euo pipefail`, and the LAN address came from `ip route get` — which
# fails at boot, before the network is up. The script exited 1, five times in
# fifteen seconds, systemd's start limit stopped it for good, and from then on
# nothing advertised the gateway: the phone found it only through an address it
# happened to remember. The same advertisement also went stale whenever DHCP
# moved the desktop to another address.
#
# Now: wait for a route instead of dying on its absence; publish; republish
# when the address changes or avahi-publish-service ends. A missing cert or a
# missing avahi are configuration errors and still exit 1, loudly.
set -uo pipefail

HOME_DIR="${MAZEMAKER_GATEWAY_HOME:-$HOME/.mazemaker-gateway}"
CRT="${GATEWAY_TLS_CERT:-$HOME_DIR/gateway.crt}"
PORT="${MM_GATEWAY_PORT:-8443}"
SVC_NAME="${MM_GATEWAY_MDNS_NAME:-Mazemaker Gateway}"
CHECK_EVERY="${MM_GATEWAY_MDNS_CHECK_SEC:-15}"

say() { echo "mdns-advertise: $*" >&2; }

if [[ ! -s "$CRT" ]]; then
  say "cert $CRT missing — run provision-apk.sh first"
  exit 1
fi
command -v avahi-publish-service >/dev/null 2>&1 || {
  say "avahi-publish-service not found (install avahi)"
  exit 1
}

fp="$(openssl x509 -in "$CRT" -noout -pubkey \
  | openssl pkey -pubin -outform der 2>/dev/null \
  | openssl dgst -sha256 -binary | openssl enc -base64)"
[[ -n "$fp" ]] || { say "could not read the fingerprint of $CRT"; exit 1; }

# The address the phone should dial: the operator's override, else the source
# address of the default route. Empty while there is no route yet.
lan_ip() {
  if [[ -n "${MM_GATEWAY_ADVERTISE_IP:-}" ]]; then echo "$MM_GATEWAY_ADVERTISE_IP"; return; fi
  ip -4 route get 1.1.1.1 2>/dev/null | grep -oE 'src [0-9.]+' | awk '{print $2}' || true
}

child=""
stop_child() {
  if [[ -n "$child" ]] && kill -0 "$child" 2>/dev/null; then
    kill "$child" 2>/dev/null
    wait "$child" 2>/dev/null
  fi
  child=""
}
trap 'stop_child; exit 0' TERM INT

waited=0
published=""
while :; do
  ip_now="$(lan_ip)"
  if [[ -z "$ip_now" ]]; then
    # No route yet (boot) or the network went away: keep waiting, say so once.
    [[ $waited == 0 ]] && say "no LAN route yet — waiting for the network"
    waited=1
    stop_child
    published=""
    sleep 5 & wait $!
    continue
  fi
  waited=0
  if [[ "$ip_now" != "$published" ]] || [[ -z "$child" ]] || ! kill -0 "$child" 2>/dev/null; then
    stop_child
    [[ -n "$published" && "$ip_now" != "$published" ]] && say "address changed $published → $ip_now — republishing"
    say "publishing _mazemaker-gw._tcp on :$PORT (fp=${fp:0:12}…, a=$ip_now)"
    avahi-publish-service "$SVC_NAME" _mazemaker-gw._tcp "$PORT" "v=1" "fp=$fp" "a=$ip_now" &
    child=$!
    published="$ip_now"
  fi
  sleep "$CHECK_EVERY" & wait $!
done
