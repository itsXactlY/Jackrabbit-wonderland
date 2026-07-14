# Mazemaker on Android — Full Stack, A → Z

**What this builds:** a real `hermes-agent` running natively inside a rootless
Linux VM (Podroid) on a *stock, unrooted* Android phone, wired to the
Mazemaker memory pod on your desktop — over an encrypted PRO gateway with
**zero hardcoded IPs and zero baked secrets**. Install the Mazemaker APK and
you get the PRO tier: full federation into the desktop's ~200k-memory graph.

This is the complete build-and-deploy runbook: from an empty machine to a
phone that recalls a real memory (e.g. `id=955714 @ sim 0.5624`) out of the
desktop graph. Verified end-to-end on release builds, 2026-07-14.

---

## 0. The picture

```
  ┌──────────────────────────── DESKTOP (GPU host) ────────────────────────────┐
  │                                                                             │
  │   Mazemaker POD (rootless Podman / Quadlet)                                 │
  │   ┌─────────────────────────────────────────────┐                          │
  │   │ mazemaker.pod  (PublishPort 8765)            │   localhost/mazemaker-v2-*│
  │   │  • mazemaker-mcp        :8000  (MCP+engine)  │   images, :gpu on Pro     │
  │   │  • wonderland MCP front :8765  ← published   │                          │
  │   │  • embedding-worker     :8766  (bge-m3, GPU) │                          │
  │   │  • pgvector             :5432  (PG16)        │                          │
  │   │  • dream-worker                (GPU)         │                          │
  │   └───────────────▲─────────────────────────────┘                          │
  │                   │ http://127.0.0.1:8765 (loopback, zero auth)             │
  │   PRO gateway     │                                                         │
  │   mazemaker-apk-gateway.service  (systemd --user)                          │
  │   lan_gateway.py  :8443  TLS + bearer token + AES + cmd:pod proxy          │
  │        ▲  mDNS _mazemaker-gw._tcp (avahi)                                   │
  └────────┼────────────────────────────────────────────────────────────────── ┘
           │  LAN  (TLS, token-gated, cert pinned by fingerprint)
  ┌────────┼──────────────────────── PHONE (unrooted) ─────────────────────────┐
  │        │                                                                    │
  │   Mazemaker APK  (dev.mazemaker.mobile 1.4.0)                               │
  │    • GatewayClient  → desktop :8443   (paired via QR / base64)             │
  │    • LocalPodMcpProxy → binds AVF TAP iface 10.198.95.x:8790 (guest-only)  │
  │                              ▲                                              │
  │   Podroid APK  (com.excp.podroid 1.2.5)   │ guest→host over AVF TAP        │
  │    • AVF / pKVM VM (crosvm), Alpine 3.23 squashfs + ext4 overlay           │
  │    ┌───────────────────────────────────────┼──────────────────────────┐   │
  │    │ GUEST (Alpine, OpenRC PID 1)          │                          │   │
  │    │   hermes-agent  :8088  (api_server, per-install key)             │   │
  │    │   podroid-hermes-mcp watcher → writes mcp_servers.mazemaker =    │   │
  │    │        http://<default-gw>:8790/mcp  ────────────────────────────┘   │
  │    └──────────────────────────────────────────────────────────────────┘   │
  └────────────────────────────────────────────────────────────────────────────┘

  Recall path:  guest hermes → app :8790 → gateway :8443 (cmd:pod /mcp)
                → pod :8765 → mazemaker MCP → 200k memory graph
```

**Three trust anchors, no hardcoded IPs:**
1. Pod ↔ gateway: loopback only (`127.0.0.1:8765`), no auth needed.
2. Phone ↔ gateway: bearer **token** + pinned **cert fingerprint**, both
   delivered by the QR / base64 pairing code. Host is found via mDNS.
3. App ↔ guest hermes: per-install `api_server.key` generated in the VM on
   first boot, pasted once into the app. Nothing ships in the binaries.

---

## 1. Host prerequisites (desktop / build machine)

Arch / Garuda (the operator's host). Podman only — never docker.

```bash
# Container + VM-image build tooling
sudo pacman -S --needed podman qemu-user-static qemu-user-static-binfmt \
                        avahi nss-mdns openssl qrencode
sudo systemctl enable --now systemd-binfmt.service   # arm64 binfmt on Arch
sudo systemctl enable --now avahi-daemon.service      # mDNS advertisement

# Verify arm64 emulation for the rootfs build
podman run --rm --platform=linux/arm64 docker.io/alpine:3.23 uname -m   # → aarch64

# Android build host
sudo pacman -S --needed jdk17-openjdk android-tools
export ANDROID_HOME="$HOME/Android/Sdk"
# sdkmanager: platform 35, build-tools 35.0.0, platform-tools, NDK (for Podroid)

# NVIDIA CDI for the pod (GPU passthrough into rootless Podman)
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
podman run --rm --device nvidia.com/gpu=all docker.io/nvidia/cuda:12-base nvidia-smi
```

> The whole stack is GPU-first: embedding / recall / ColBERT / DAE all run on
> GPU. On a GPU host the installer rewrites pod images `:latest → :gpu`.

---

## 2. Layer 1 — the Mazemaker pod (desktop)

Rootless Podman via Quadlet. Units live in `~/.config/containers/systemd/`.

### 2.1 Secrets, license, config (one-time)

```bash
mkdir -p ~/.mazemaker/{data,pgvector-data,sockets}

# PG password as a rootless podman secret (referenced by both containers)
printf '%s' "$(openssl rand -hex 24)" | podman secret create mazemaker_pg_password -

# License (Pro/Enterprise JWT + Ed25519 pubkey) — required for the Postgres
# backend, ColBERT, REM, Insight, DAE. Without it mcp silently drops to the
# SQLite community tier and SPLITS writes from dream-worker.
cp <your>/license.jwt            ~/.mazemaker/license.jwt
cp <your>/jwt.v1.pub.ed25519     ~/.mazemaker/jwt.v1.pub.ed25519

# Backend + compute selectors
cat > ~/.mazemaker/db.toml      <<'EOF'
[backend]
kind = "postgres"
EOF
cat > ~/.mazemaker/compute.toml <<'EOF'
[compute]
device = "auto"   # resolves to cuda on an nvidia host
EOF
```

### 2.2 The Quadlet units

Five files (already present on the operator's host):

| Unit | Image | Port | Role |
|---|---|---|---|
| `mazemaker.pod` | — | **8765 published** | pod, wonderland MCP front |
| `mazemaker-mcp.container` | `localhost/mazemaker-v2-mcp:latest` (`:gpu` on Pro) | 8000 (internal) | MCP server + neural-memory engine |
| `mazemaker-embedding-worker.container` | `localhost/mazemaker-v2-embedding-worker:latest` | 8766 (internal) | bge-m3 embeddings, GPU |
| `mazemaker-pgvector.container` | `docker.io/pgvector/pgvector:pg16-trixie` | 5432 (internal) | Postgres + pgvector |
| `mazemaker-license-client.container` | — | 8767 (internal) | license gate |
| `mazemaker-dream-worker.container` | `…-dream-worker:gpu` | — | NREM/REM/Insight consolidation |

Only `:8765` is published to the host; everything else is pod-internal.
`8765` binds `0.0.0.0` for federation, but authorization is the pre-shared
peer_key — a LAN scanner sees the pod but can't sync.

Key invariants baked into the units:
- `AddDevice=nvidia.com/gpu=all` on mcp + embedding + dream (installer strips
  it on non-CDI hosts).
- `MM_DREAM_DISABLED=1` on mcp — the in-pod dream loop is off; an external
  daemon (or the dream-worker container) drives consolidation so it doesn't
  fight the interactive path for the GPU.
- `MemoryMax`: mcp 8G, pgvector 8G, embedding 6G (tuned on a 200k corpus;
  bump for >500k).
- Images are **local-only**; Quadlet `.container.d/` drop-ins set
  `Pull=never`. Never `podman image prune` untagged layers → crash-loop.

### 2.3 Bring it up

```bash
systemctl --user daemon-reload
systemctl --user start mazemaker-pod.service
systemctl --user status mazemaker-mcp.service     # wait for GpuRecall warm-up

# Smoke: MCP is stateless JSON-in/JSON-out; no SSE / session needed
curl -s -H 'Accept: application/json' -H 'Content-Type: application/json' \
  http://127.0.0.1:8765/mcp \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | head -c 400
# → 31 tools (mazemaker_recall, mazemaker_remember, …)
```

---

## 3. Layer 2 — the PRO gateway (desktop)

`~/projects/hermes-crypto` — the encrypted bridge the phone dials. It wraps
the loopback-only pod in TLS + a bearer token + AES, and proxies `cmd:pod`
requests (including `/mcp`) straight through to `:8765`.

### 3.1 Provision token + cert + pairing code

```bash
cd ~/projects/hermes-crypto
./provision-apk.sh                 # autodetects primary LAN IPv4 + 127.0.0.1
```

This writes to `~/.hermes-crypto/`:
- `gateway.token` — `openssl rand -hex 32`, gates every request.
- `gateway.crt` / `gateway.key` — self-signed RSA-4096, SANs for each LAN IP,
  `CN=mazemaker-gateway`, 10-year.

and prints the **pairing code** — a tiny `base64(JSON{v,token,fp})` where
`fp = base64(sha256(SPKI))`. **No host in it** (mDNS supplies host:port) and
**no cert** (the app fetches the cert on pairing and verifies its SPKI hash
== `fp` before pinning). For mDNS-blocked networks:
`MM_GATEWAY_INCLUDE_HOST=1 ./provision-apk.sh` bakes a `host` fallback.

It also emits a scannable QR (needs `qrencode`) for Settings → Secure Gateway
→ SCAN QR.

### 3.2 The systemd services

```bash
# gateway itself (systemd --user)
systemctl --user enable --now mazemaker-apk-gateway.service
#   ExecStart: python3 lan_gateway.py --port 8443 --tcp-port 38374 --bind 0.0.0.0
#   Env: MM_POD_URL=http://127.0.0.1:8765   (the cmd:pod target)

# mDNS advertisement so the phone finds host:port with no baked IP
systemctl --user enable --now mazemaker-apk-gateway-mdns.service
#   avahi-publish-service "Mazemaker Gateway" _mazemaker-gw._tcp 8443 v=1 fp=… a=<lan-ip>

# Health
ss -tlnp | grep :8443     # → LISTEN 0 5  (Recv-Q MUST be 0 — see §10.1)
```

> `install.sh` is the all-in-one path (JackrabbitDLM vault + middleware +
> service + nftables LAN-only rules). `--check` verifies, `--uninstall`
> removes.

---

## 4. Layer 3 — Podroid: the Linux VM on the phone

`~/projects/jrwl-messenger/android/podroid` — the AVF/pKVM variant we ship
(**not** the older proot `podroid-hermes` thin app). A rootless Alpine 3.23
squashfs + persistent ext4 overlay, OpenRC as PID 1, booted by crosvm inside
Android's Virtualization Framework.

### 4.1 Build the Alpine rootfs squashfs

`build-rootfs/build-rootfs.sh` (run inside `Dockerfile.rootfs` via the build
script). It `apk add`s the base system — `alpine-base openrc busybox-openrc
bash podman crun fuse-overlayfs iptables nftables dropbear curl ca-certificates
shadow-uidmap slirp4netns aardvark-dns netavark **python3** …` — sets rootless
uid-map caps, seeds `doas`/`sudo` for `wheel`, root password `podroid`, strips
docs/locale, then **bakes the hermes pod**:

- Copies `files/etc/init.d/podroid-hermes` (starts hermes) and
  `files/etc/init.d/podroid-hermes-mcp` (the MCP watcher) into the rootfs.
- Unpacks the hermes venv vendor tarball
  (`files/usr/local/share/hermes/hermes-podroid.tar`) to `/opt/hermes`, or
  falls back to the seeded `files/opt/hermes/{start.sh,config.template.yaml,
  mcp-mazemaker-watch.sh}`.
- Adds both services to the boot runlevel.

`python3` is **mandatory** — hermes-agent's api_server is a Python venv; a
rootfs without it dies with `exec: /opt/hermes/venv/bin/hermes: not found`
(dangling interpreter). Alpine 3.23.4 ships Python 3.12.13, matching the
venv's `pyvenv.cfg`.

```bash
cd ~/projects/jrwl-messenger/android/podroid
./build-all.sh rootfs
#   → app/src/main/assets/alpine-rootfs.squashfs  (~384 MB)
```

### 4.2 Build + install the Podroid APK

```bash
./build-all.sh              # build_rootfs (if stale) then ./gradlew assemble…
#   debug:   ./gradlew assembleDebug
#   release: ./gradlew assembleRelease   (needs its own keystore — see §6)
# com.excp.podroid 1.2.5 (versionCode 28)

DEV=<adb-serial>
adb -s $DEV install -r app/build/outputs/apk/release/app-release.apk
```

### 4.3 Grant the AVF permissions (critical)

AVF is gated behind two signature/privileged permissions that are **revoked
on every reinstall**. Without them crosvm can't open the TAP and the VM
dead-ends (misreads as `TUNSETIFF EACCES`).

```bash
PKG=com.excp.podroid        # or .debug
adb -s $DEV shell pm grant $PKG android.permission.MANAGE_VIRTUAL_MACHINE
adb -s $DEV shell pm grant $PKG android.permission.USE_CUSTOM_VIRTUAL_MACHINE
adb -s $DEV shell am force-stop $PKG      # EngineHolder resolves the engine
adb -s $DEV shell monkey -p $PKG 1        #   once per process — relaunch

# Verify GRANTED (dumpsys lists *requested* perms even when not granted):
adb -s $DEV shell dumpsys package $PKG | grep -A1 VIRTUAL_MACHINE | grep granted=true
```

Boot the VM from the app. On AVF/pKVM it comes up in ~6 s (vs ~190 s on
QEMU/TCG emulation — only fall back to TCG on non-KVM devices).

---

## 5. Layer 4 — hermes-agent + the per-install key

hermes-agent 0.15.1 (Nous Research) runs inside the guest as an
OpenAI-compatible `api_server` on `:8088`, forwarded to Android loopback.

**No key ships in anything.** On first boot `files/opt/hermes/start.sh`:

```sh
# generate a per-install key if absent, persist in the overlay
[ -s /opt/hermes/api_server.key ] || \
  python3 -c 'import secrets;print(secrets.token_hex(32))' > /opt/hermes/api_server.key
# seed config.template.yaml → config.yaml on first run (openrouter_free, EMPTY api_key)
```

`api_server` **enforces** the key (no bearer → 401) and **refuses to start**
with an empty key. Read it once to paste into the apps:

```
# in the Podroid terminal, inside the guest:
cat /opt/hermes/api_server.key      # 64 hex chars
```

The model provider key (OpenRouter etc.) is likewise empty in the template;
paste it into `/opt/hermes/config.yaml` (or reuse `~/.hermes/config.yaml` on
the desktop as reference). **Grep proof of no baked secrets:**

```bash
grep -rn "sk-\|token_hex\|BEARER\|192\.168\." app/src/main | grep -v '""' # → nothing incriminating
```

---

## 6. Layer 5 — the Android apps (release, signed)

Three apps, each with a real release keystore (never publish debug-signed).

### 6.1 Mazemaker APK — `dev.mazemaker.mobile` 1.4.0 (code 7)

`~/projects/mazemaker-mobile/android`. Signing reads a **gitignored**
`keystore.properties`; absent, release falls back to the debug key so CI /
fresh clones still build.

```bash
cd ~/projects/mazemaker-mobile/android
cat > keystore.properties <<EOF
storeFile=keystore/mazemaker-release.jks
storePassword=…
keyAlias=…
keyPassword=…
EOF
# one-time keystore (CN=Mazemaker Mobile):
keytool -genkeypair -v -keystore keystore/mazemaker-release.jks \
  -alias mazemaker -keyalg RSA -keysize 4096 -validity 10000

./gradlew assembleRelease
adb install -r app/build/outputs/apk/release/app-release.apk
```

Two non-negotiable build settings (both are load-bearing bug fixes):
- `camera-* 1.4.2+` — 1.3.4's `libimage_processing_util_jni.so` is 4 KB-aligned
  and Android 15+ rejects it on 16 KB-page devices ("isn't 16 KB compatible").
- `proguard-android.txt` (non-optimize), **not** `-optimize` — R8's optimize
  pass miscompiles bundled ML-Kit barcode classes into a `VerifyError` on the
  QR path. Shrinking + obfuscation stay on; only the optimize pass is dropped.
  (Same fix applied defensively to thin-hermes + iris.)

What the app wires up after pairing:
- `GatewayClient` → desktop `:8443` (TLS pinned to `fp`, token bearer).
- `LocalPodMcpProxy` — a raw `ServerSocket` bound **only** to the AVF TAP
  interface (`10.198.95.x:8790`, guest-only); forwards `POST /mcp` through
  `gatewayProvider().pod(...)`. Lifecycle gated on `gatewayClient != null`
  (not on `localPodAvailable` — that caused a restart feedback loop).
- Settings → **ON-DEVICE POD KEY**: paste `api_server.key` → "pod unlocked".
- Settings → **Secure Gateway**: paste base64 payload or SCAN QR → PAIR.

### 6.2 Podroid APK — `com.excp.podroid` 1.2.5 (code 28)

See §4. Owns the VM; needs the two AVF permissions.

### 6.3 Thin Hermes APK — `dev.hermes.chat` 0.2.0 (code 2)

`~/projects/podroid-hermes/android/hermes-android` — the standalone chat
client for users **without** the Mazemaker app (no MCP proxy, talks straight
to guest `:8088`). Same per-install-key paste field, `proguard-android.txt`.
Build the gutted client from its own worktree (a full-checkout build pulls in
old VM assets → 265 MB; the thin build is ~1.3 MB).

```bash
cd ~/projects/podroid-hermes/android && ./build-all.sh
```

---

## 7. Layer 6 — pairing & wiring (the "PRO federation" moment)

On the phone, with the pod + gateway up on the desktop:

1. **Podroid** → boot the VM (§4.3). Open the terminal, `cat
   /opt/hermes/api_server.key`.
2. **Mazemaker → Settings → ON-DEVICE POD KEY** → paste the key → SAVE KEY →
   "● pod unlocked".
3. **Mazemaker → Settings → Secure Gateway** → paste the base64 pairing code
   (from §3.1) or SCAN QR → **PAIR**.
   - App finds the gateway via mDNS `_mazemaker-gw._tcp`, fetches its cert,
     verifies `sha256(SPKI) == fp`, pins it, stores the token.
   - Success: `● ENCRYPTED — TLS + token + AES via gateway`, `● Paired with
     <ip>:8443`, POD CONNECTION auto-filled.
4. On pairing, `gatewayClient != null` → `LocalPodMcpProxy` binds the AVF TAP
   `:8790` (`MzkMcpProxy: MCP proxy listening on 10.198.95.x:8790 (guest-only)`).
5. Inside the guest, the `podroid-hermes-mcp` watcher (`mcp-mazemaker-watch.sh`)
   resolves the default gateway, writes
   `mcp_servers.mazemaker = http://<gw>:8790/mcp`, and restarts
   `podroid-hermes` when the proxy is reachable but hermes has 0 tools —
   loading the 31 mazemaker tools.

Now the recall path is live: **guest hermes → app :8790 → gateway :8443
(`cmd:pod` `/mcp`) → pod :8765 → mazemaker graph.**

---

## 8. Layer 7 — website & docs

`~/projects/mazemaker-v2-stack/frontend` → Cloudflare Pages.

```bash
cd ~/projects/mazemaker-v2-stack/frontend
./deploy-pages.sh          # curl Cloudflare API (needs $ACCOUNT/$PROJECT/token)
#   or: wrangler pages deploy <dir> --project-name <project>
```

`~/.cf_api` is dead — use `wrangler login` (OAuth) if the API-token path fails.
The 1.4.0 site adds the "Hermes — on the phone" section, the rootless-android
pod story (replacing the Dream Engine mermaid deep-dive), an "Android app"
docs card, and the Pro APK download on the dashboard.

---

## 9. Full end-to-end verification (release)

The acceptance test — everything on release builds:

```bash
# 1. desktop: pod + gateway healthy
curl -s -H 'Accept: application/json' http://127.0.0.1:8765/mcp \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' >/dev/null && echo POD_OK
ss -tlnp | grep :8443 | grep -q 'LISTEN 0' && echo GATEWAY_OK

# 2. phone: Podroid VM booted (AVF), Mazemaker [POD·ON], pod unlocked, paired
# 3. Mazemaker → Hermes tab → send:
#      "Nutze dein mazemaker_recall Tool. Suche ColBERT dedup und gib mir
#       memory-id plus Inhalt."
```

**Pass criteria:** hermes replies with real graph content in mazemaker's
`id + similarity` format (verified run: top hit `id=955714 @ 0.5624`, plus
`955710/955709` and real commit SHAs). Confirm it is not hallucinated:

```bash
# on the desktop, via your own MCP access
mazemaker_get(memory_id=955714)   # → found:true, the 2026-07-08 ColBERT-dedup memory
```

If `mazemaker_get` returns `found:true` and the content matches what hermes
said, the whole chain — release VM → app proxy → encrypted gateway → pod →
graph — is proven, with no hardcoded IP and a per-install key.

---

## 10. Troubleshooting (the gotchas that actually bit us)

### 10.1 PAIR fails / gateway wedged accept queue
Symptom: app shows `✗ failed to connect to <ip>:8443 … after 6000ms`, and a
local TLS handshake from the desktop **itself** also times out — yet `ss`
shows the socket LISTENING. Diagnose the **queue**, not the network:

```bash
ss -tlnp | grep :8443     # BAD: "LISTEN 6 5" — Recv-Q(6) > backlog(5)
```

The TLS handshake happens in the server's accept path; dead half-open
connections (piled up from repeated PAIR taps before the phone had a stable
WiFi/DHCP lease) starve `accept()` and new SYNs drop. Fix:

```bash
systemctl --user restart mazemaker-apk-gateway.service   # → LISTEN 0 5, PAIR succeeds
```

### 10.2 QR "Empty host" after pairing
The QR payload carries no host (mDNS supplies it). Old builds only rebuilt the
gateway client when `_currentHost` was non-blank → QR users never connected.
Fixed: `applyGatewayConfig()` rebuilds unconditionally. `readTimeout=0` masked
it (the call never fired, so no error surfaced). The app dictates **no**
timeouts — the gateway is the sole deadline authority.

### 10.3 "isn't 16 KB compatible" dialog
CameraX 1.3.4 native lib. Bump to `camera-* 1.4.2+` (§6.1). A stale system
dialog can persist after the fix — dismiss + relaunch.

### 10.4 hermes: `exec: /opt/hermes/venv/bin/hermes: not found`
`python3` missing from the rootfs → dangling venv interpreter. It's in the
`apk add` list (§4.1); rebuild the squashfs.

### 10.5 MCP proxy restart feedback loop
Gating the proxy on `localPodAvailable` → hermes restart drops :8088 → proxy
killed → 0 tools → watcher restarts → loop. Gate on `gatewayClient != null`
only.

### 10.6 Black `adb screencap`
A locked/dozing phone screencaps pure black — not an R8 render bug. Unlock and
recapture before diagnosing anything visual.

### 10.7 Route C relay 404
`[relay-client] disconnected: 404 … wss://api.mazemaker.dev/relay/gw` in the
gateway log is the (down) remote relay for off-LAN reach. **It does not affect
LAN pairing or recall.** Ignore it when testing on-network.

---

## 11. Security model — why "customer-safe"

- **No hardcoded IP.** Host is discovered via mDNS; the pairing code carries
  only `{v, token, fp}`. Optional `host` fallback is opt-in.
- **No baked secrets.** The gateway token + cert are provisioned per desktop;
  the `api_server.key` is generated per VM install and pasted once; provider
  keys are pasted, never shipped. Client code carries zero external hints.
- **Pinned TLS.** The app pins `sha256(SPKI)` from the scanned fingerprint —
  the trust anchor is the QR, not any CA.
- **Loopback pod.** `:8765` is reachable off-box only through the
  token+TLS+AES gateway; the raw pod has no auth by design (loopback only).
- **PRO = the Mazemaker app.** Installing it and pairing is what unlocks full
  federation into the desktop graph; the thin Hermes app stays local-only.

---

*Verified end-to-end on release builds, 2026-07-14. Memory anchors:
`ops:android-release-chain-e2e-verified-2026-07-14` (id 996194),
`bug:gateway-accept-queue-wedge-blocks-pairing` (id 996195).*
