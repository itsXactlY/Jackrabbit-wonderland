#!/usr/bin/env python3
"""relay.py — self-hosted circuit-relay for the hermes-crypto gateway.

Route C of the pairing story: lets a phone reach the user's own pod from
OUTSIDE its LAN, without the pod needing any inbound port, and WITHOUT a
third party ever seeing plaintext.

Topology
--------
    phone  --HTTPS POST-->  relay (this, on a reachable host)  <--WSS out-- gateway (pod)

  * The gateway (hermes-crypto lan_gateway) dials OUT to the relay over a
    persistent WebSocket and registers under its fingerprint `fp`
    (= sha256 of its TLS cert SubjectPublicKeyInfo — the SAME id the QR
    pairing code already carries). No inbound port on the pod.
  * The phone POSTs the exact same AES-GCM `/command` envelope it would send
    on the LAN to  /gw/<fp>/command ; the relay forwards it down the matching
    gateway's socket, awaits the reply, and returns it.

Zero-knowledge / trust model
----------------------------
  * The relay is a BLIND pipe. The `/command` body is already AES-GCM sealed
    with the session key that ONLY the paired gateway holds; the relay never
    has it. Auth of the request is the inner envelope + bearer token, verified
    by the gateway, not here.
  * Registration is bound to the cert: to claim `fp` a gateway must present its
    DER cert whose sha256(SPKI) == fp AND sign a relay-issued nonce with the
    matching private key. So an attacker cannot squat someone else's fp. Even
    if it could, it would only receive ciphertext it cannot open and cannot
    forge a valid reply for — confidentiality holds regardless; this only
    protects availability.

Run:  MM_RELAY_BIND=0.0.0.0:9443 python3 relay.py
Deps: aiohttp, cryptography
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
from typing import Dict, Optional

from aiohttp import web, WSMsgType
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, ec
from cryptography.exceptions import InvalidSignature

# fp (hex sha256 of cert SPKI) -> live gateway connection
_GATEWAYS: "Dict[str, GatewayConn]" = {}
# correlation id -> Future awaiting the gateway's reply
_PENDING: "Dict[str, asyncio.Future]" = {}

REQ_TIMEOUT = float(os.environ.get("MM_RELAY_REQ_TIMEOUT", "600"))  # server is timeout authority
MAX_BODY = int(os.environ.get("MM_RELAY_MAX_BODY", str(4 * 1024 * 1024)))


def _spki_fp(cert_der: bytes) -> str:
    cert = x509.load_der_x509_certificate(cert_der)
    spki = cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(spki).hexdigest()


def _verify_sig(cert_der: bytes, message: bytes, sig: bytes) -> bool:
    """Verify `sig` over `message` with the cert's public key (RSA or EC)."""
    pub = x509.load_der_x509_certificate(cert_der).public_key()
    try:
        if isinstance(pub, ec.EllipticCurvePublicKey):
            pub.verify(sig, message, ec.ECDSA(hashes.SHA256()))
        else:  # RSA
            pub.verify(sig, message, padding.PKCS1v15(), hashes.SHA256())
        return True
    except (InvalidSignature, Exception):
        return False


class GatewayConn:
    """One registered gateway's outbound socket."""

    def __init__(self, fp: str, ws: web.WebSocketResponse):
        self.fp = fp
        self.ws = ws
        self.registered_at = time.time()


# ── gateway side: persistent outbound WS + cert-bound registration ──────────
async def ws_gateway(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=30, max_msg_size=MAX_BODY)
    await ws.prepare(request)

    # 1. challenge → the gateway must prove it owns the fp it claims.
    nonce = secrets.token_hex(32)
    await ws.send_json({"type": "challenge", "nonce": nonce})

    fp: Optional[str] = None
    try:
        first = await ws.receive(timeout=30)
        if first.type != WSMsgType.TEXT:
            await ws.close()
            return ws
        reg = json.loads(first.data)
        cert_der = base64.b64decode(reg["cert"])
        sig = base64.b64decode(reg["sig"])
        claimed = reg["fp"].lower()
        # bind: fp must equal the cert's SPKI hash, and the sig over the nonce
        # must verify against that cert.
        if _spki_fp(cert_der) != claimed:
            await ws.send_json({"type": "error", "msg": "fp != cert spki"})
            await ws.close()
            return ws
        if not _verify_sig(cert_der, nonce.encode(), sig):
            await ws.send_json({"type": "error", "msg": "bad registration signature"})
            await ws.close()
            return ws
        fp = claimed
    except Exception as exc:  # noqa: BLE001
        try:
            await ws.send_json({"type": "error", "msg": f"registration failed: {exc}"})
        except Exception:
            pass
        await ws.close()
        return ws

    # replace any stale connection for this fp (last cert-proven wins)
    old = _GATEWAYS.get(fp)
    if old is not None:
        try:
            await old.ws.close()
        except Exception:
            pass
    conn = GatewayConn(fp, ws)
    _GATEWAYS[fp] = conn
    await ws.send_json({"type": "registered", "fp": fp})
    print(f"[relay] gateway registered fp={fp[:16]}… ({len(_GATEWAYS)} online)", flush=True)

    # 2. serve replies: the gateway sends {corr_id, status, body} for each
    #    forwarded request; resolve the awaiting phone future.
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                frame = json.loads(msg.data)
            except Exception:
                continue
            if frame.get("type") == "pong":
                continue
            corr = frame.get("corr_id")
            fut = _PENDING.get(corr)
            if fut and not fut.done():
                fut.set_result(frame)
    finally:
        if _GATEWAYS.get(fp) is conn:
            del _GATEWAYS[fp]
        print(f"[relay] gateway gone fp={fp[:16]}… ({len(_GATEWAYS)} online)", flush=True)
    return ws


# ── phone side: forward an opaque /command envelope to a gateway by fp ──────
async def http_command(request: web.Request) -> web.Response:
    fp = request.match_info["fp"].lower()
    conn = _GATEWAYS.get(fp)
    if conn is None:
        return web.json_response({"error": "gateway offline", "fp": fp}, status=502)
    if request.content_length and request.content_length > MAX_BODY:
        return web.json_response({"error": "body too large"}, status=413)
    body = await request.text()

    corr = secrets.token_hex(16)
    loop = asyncio.get_event_loop()
    fut: asyncio.Future = loop.create_future()
    _PENDING[corr] = fut
    try:
        await conn.ws.send_json({
            "type": "request", "corr_id": corr,
            "path": "/command", "body": body,
        })
        frame = await asyncio.wait_for(fut, timeout=REQ_TIMEOUT)
    except asyncio.TimeoutError:
        return web.json_response({"error": "gateway timeout"}, status=504)
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": f"relay error: {exc}"}, status=502)
    finally:
        _PENDING.pop(corr, None)

    status = int(frame.get("status", 200))
    resp_body = frame.get("body", "")
    return web.Response(status=status, text=resp_body,
                        content_type="application/json")


async def http_health(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "gateways_online": len(_GATEWAYS),
        "pending": len(_PENDING),
    })


def build_app() -> web.Application:
    app = web.Application(client_max_size=MAX_BODY)
    app.router.add_get("/gw", ws_gateway)                     # gateway registers here
    app.router.add_post("/gw/{fp}/command", http_command)     # phone forwards here
    app.router.add_get("/health", http_health)
    return app


def main() -> None:
    bind = os.environ.get("MM_RELAY_BIND", "0.0.0.0:9443")
    host, port = bind.rsplit(":", 1)
    print(f"[relay] hermes-crypto circuit-relay on {host}:{port}", flush=True)
    web.run_app(build_app(), host=host, port=int(port), print=None)


if __name__ == "__main__":
    main()
