#!/usr/bin/env python3
"""
APK LAN-hardening regression tests.

Covers the phone<->gateway security layer added for the Mazemaker mobile app:
  - bearer-token auth gates protected commands (shell/hermes/... = no RCE)
  - open commands (status) stay reachable for liveness/UI
  - client-key handshake: an authenticated `session` returns the AES key
  - encrypted (`enc`) round-trip both directions, with decrypt-as-auth
  - legacy mode (no token configured) is unchanged: no key leak, open commands

Self-contained: spins its own gateway on an ephemeral port over plain HTTP
(memory sessions, no DLM, no TLS — TLS is orthogonal stdlib ssl wrapping).
Run: python3 tests/test_apk_hardening.py
"""
import base64
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from Crypto.Cipher import AES

HERE = os.path.dirname(os.path.abspath(__file__))
GATEWAY = os.path.join(os.path.dirname(HERE), "lan_gateway.py")
TOKEN = "test-token-" + base64.b16encode(os.urandom(8)).decode()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _start(token: str):
    port, tcp = _free_port(), _free_port()
    env = dict(os.environ, GATEWAY_TOKEN=token, GATEWAY_TOKEN_FILE="/nonexistent")
    proc = subprocess.Popen(
        [sys.executable, GATEWAY, "--port", str(port), "--tcp-port", str(tcp),
         "--bind", "127.0.0.1", "--no-tls"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/health", timeout=1).read()
            break
        except Exception:
            time.sleep(0.1)
    return proc, base


def _post(base, body, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + "/command", data=json.dumps(body).encode(),
                                 headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _aes_enc(key_b64, text):
    c = AES.new(base64.b64decode(key_b64), AES.MODE_GCM)
    ct, tag = c.encrypt_and_digest(text.encode())
    return base64.b64encode(c.nonce + tag + ct).decode()


def _aes_dec(key_b64, blob):
    raw = base64.b64decode(blob)
    n, t, ct = raw[:16], raw[16:32], raw[32:]
    return AES.new(base64.b64decode(key_b64), AES.MODE_GCM, nonce=n).decrypt_and_verify(ct, t).decode()


def main():
    failures = []

    def check(name, cond):
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        if not cond:
            failures.append(name)

    proc, base = _start(TOKEN)
    try:
        check("open command (status) needs no token", _post(base, {"cmd": "status"})[0] == 200)
        check("protected command (shell) rejected w/o token", _post(base, {"cmd": "shell", "args": "id"})[0] == 401)
        code, body = _post(base, {"cmd": "shell", "args": "echo ok"}, TOKEN)
        check("protected command runs with token", code == 200 and body.get("stdout", "").strip() == "ok")
        code, body = _post(base, {"cmd": "session"}, TOKEN)
        ck = body.get("created", {}).get("client_key")
        sid = body.get("created", {}).get("session_id")
        check("authenticated session returns client_key", bool(ck) and bool(sid))
        if ck and sid:
            enc = _aes_enc(ck, json.dumps({"cmd": "status"}))
            code, body = _post(base, {"session_id": sid, "enc": enc})  # no header: decrypt == auth
            ok = code == 200 and "enc" in body
            inner = json.loads(_aes_dec(ck, body["enc"])) if ok else {}
            check("encrypted round-trip both directions", ok and inner.get("gateway") == "running")
        check("bad enc on unknown session rejected", _post(base, {"session_id": "nope", "enc": "AAAA"})[0] in (400, 401))
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    # Legacy mode: no token configured -> auth off, no key leak.
    proc2, base2 = _start("")
    try:
        code, body = _post(base2, {"cmd": "session"})
        check("legacy: session does not leak client_key", "client_key" not in body.get("created", {}))
        check("legacy: open shell (no token configured)", _post(base2, {"cmd": "shell", "args": "echo x"})[0] == 200)
    finally:
        proc2.terminate()
        proc2.wait(timeout=5)

    print(f"\n  {len(failures)} failed" if failures else "\n  all APK-hardening tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
