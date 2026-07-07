#!/usr/bin/env python3
"""relay_client.py — gateway side of Route C (self-hosted circuit-relay).

Opt-in via MM_RELAY_URL. When set, the hermes-crypto gateway keeps a
persistent OUTBOUND WebSocket to the relay (relay.py, on a reachable host)
so a phone outside the LAN can reach this pod with NO inbound port here.

Flow: connect → prove ownership of `fp` (present the TLS cert whose
sha256(SPKI)==fp + sign the relay's nonce with the matching key) → then, for
every forwarded `{corr_id, path:/command, body}`, REPLAY it against the
gateway's OWN loopback https://127.0.0.1:<port>/command and ship the response
back as {corr_id, status, body}. Replaying locally means zero refactor of the
gateway's 1800-line request path — token, session, and AES envelope handling
all run exactly as they do for a LAN client. The relay never sees plaintext.

Started as a daemon thread from lan_gateway.py; reconnects with backoff.
Deps: aiohttp, cryptography (both already used by the gateway host).
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import ssl
import threading
import time

import aiohttp
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, ec


def _load_cert_der_and_fp(cert_pem_path: str):
    with open(cert_pem_path, "rb") as f:
        pem = f.read()
    cert = x509.load_pem_x509_certificate(pem)
    der = cert.public_bytes(serialization.Encoding.DER)
    spki = cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    import hashlib
    fp = hashlib.sha256(spki).hexdigest()
    return der, fp


def _sign(key_pem_path: str, message: bytes) -> bytes:
    with open(key_pem_path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    if isinstance(key, ec.EllipticCurvePrivateKey):
        return key.sign(message, ec.ECDSA(hashes.SHA256()))
    return key.sign(message, padding.PKCS1v15(), hashes.SHA256())


async def _serve(relay_url: str, cert_pem: str, key_pem: str, local_port: int):
    der, fp = _load_cert_der_and_fp(cert_pem)
    # Loopback to our own TLS gateway — self-signed, so no verification.
    local_base = f"https://127.0.0.1:{local_port}"
    noverify = ssl.create_default_context()
    noverify.check_hostname = False
    noverify.verify_mode = ssl.CERT_NONE

    timeout = aiohttp.ClientTimeout(total=None, sock_connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.ws_connect(relay_url, heartbeat=30, max_msg_size=8 * 1024 * 1024) as ws:
            # 1. registration handshake
            chal = await ws.receive_json(timeout=30)
            if chal.get("type") != "challenge":
                raise RuntimeError(f"expected challenge, got {chal}")
            nonce = chal["nonce"].encode()
            sig = _sign(key_pem, nonce)
            await ws.send_json({
                "fp": fp,
                "cert": base64.b64encode(der).decode(),
                "sig": base64.b64encode(sig).decode(),
            })
            ok = await ws.receive_json(timeout=30)
            if ok.get("type") != "registered":
                raise RuntimeError(f"registration rejected: {ok}")
            print(f"[relay-client] registered fp={fp[:16]}… at {relay_url}", flush=True)

            # 2. serve forwarded requests by replaying against local /command
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                        break
                    continue
                try:
                    frame = json.loads(msg.data)
                except Exception:
                    continue
                if frame.get("type") != "request":
                    continue
                corr = frame.get("corr_id")
                body = frame.get("body", "")
                hdrs = {"Content-Type": "application/json"}
                if frame.get("auth"):
                    hdrs["Authorization"] = frame["auth"]
                try:
                    async with session.post(
                        f"{local_base}/command", data=body,
                        headers=hdrs,
                        ssl=noverify,
                    ) as r:
                        text = await r.text()
                        status = r.status
                except Exception as exc:  # noqa: BLE001
                    text = json.dumps({"error": f"gateway loopback failed: {exc}"})
                    status = 502
                await ws.send_json({"corr_id": corr, "status": status, "body": text})


def _run_forever(relay_url: str, cert_pem: str, key_pem: str, local_port: int):
    backoff = 2
    while True:
        try:
            asyncio.run(_serve(relay_url, cert_pem, key_pem, local_port))
            backoff = 2  # clean exit → reset
        except Exception as exc:  # noqa: BLE001
            print(f"[relay-client] disconnected: {exc} — retry in {backoff}s", flush=True)
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def start(relay_url: str, cert_pem: str, key_pem: str, local_port: int) -> threading.Thread:
    """Spawn the relay client in a daemon thread. No-op guard on empty URL."""
    if not relay_url:
        return None
    t = threading.Thread(
        target=_run_forever, args=(relay_url, cert_pem, key_pem, local_port),
        name="relay-client", daemon=True,
    )
    t.start()
    return t


if __name__ == "__main__":
    _run_forever(
        os.environ["MM_RELAY_URL"],
        os.path.expanduser(os.environ.get("GATEWAY_TLS_CERT", "~/.hermes-crypto/gateway.crt")),
        os.path.expanduser(os.environ.get("GATEWAY_TLS_KEY", "~/.hermes-crypto/gateway.key")),
        int(os.environ.get("GATEWAY_PORT", "8443")),
    )
