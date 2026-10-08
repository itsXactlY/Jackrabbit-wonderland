#!/usr/bin/env python3
"""
`cmd:llm` — the phone's agent reaching the desktop's local model through the
gateway instead of over plaintext <desktop-ip>:8080.

Self-contained: a fake OpenAI-compatible server on loopback stands in for the
llama-server, and a real gateway process runs against it (plain HTTP, like
test_apk_hardening.py).
Run: python3 tests/test_llm_route.py
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
GATEWAY = os.path.join(os.path.dirname(HERE), "lan_gateway.py")
TOKEN = "test-token-llm"
SEEN = []          # what the fake model received: (path, auth header, body)


class FakeModel(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        raw = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        SEEN.append((self.path, self.headers.get("Authorization"), None))
        self._send({"data": [{"id": "qwen-local"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append((self.path, self.headers.get("Authorization"), body))
        self._send({"choices": [{"index": 0, "finish_reason": "stop",
                                 "message": {"role": "assistant", "content": "Grüße vom lokalen Modell"}}]})


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _gateway(llm_url: str, key: str = ""):
    port, tcp = _free_port(), _free_port()
    env = dict(os.environ, GATEWAY_TOKEN=TOKEN, GATEWAY_TOKEN_FILE="/nonexistent",
               MM_LLM_URL=llm_url, MM_LLM_API_KEY=key)
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


def _post(base, payload, token=None):
    req = urllib.request.Request(base + "/command", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    failures = []

    def check(name, ok):
        print(("  ✓ " if ok else "  ✗ ") + name)
        if not ok:
            failures.append(name)

    model_port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", model_port), FakeModel)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    proc, base = _gateway(f"http://127.0.0.1:{model_port}", key="desk-only-key")
    try:
        check("llm rejected without a token", _post(base, {"cmd": "llm", "args": "{}"})[0] == 401)
        _, body = _post(base, {"cmd": "llm", "args": json.dumps({"method": "GET", "path": "health"})}, TOKEN)
        check("only v1/ paths reach the model", "invalid path" in str(body.get("error", "")))
        _, body = _post(base, {"cmd": "llm", "args": json.dumps({"method": "GET", "path": "v1/../etc"})}, TOKEN)
        check("no traversal", "invalid path" in str(body.get("error", "")))

        _, body = _post(base, {"cmd": "llm", "args": json.dumps({"method": "GET", "path": "v1/models"})}, TOKEN)
        check("models listed through the gateway", body.get("data", [{}])[0].get("id") == "qwen-local")

        req = {"model": "x", "stream": True, "messages": [{"role": "user", "content": "Grüß dich"}]}
        _, body = _post(base, {"cmd": "llm", "args": json.dumps(
            {"method": "POST", "path": "v1/chat/completions", "body": req})}, TOKEN)
        check("completion comes back whole",
              body.get("choices", [{}])[0].get("message", {}).get("content") == "Grüße vom lokalen Modell")
        path, auth, sent = SEEN[-1]
        check("asked for as a whole answer (stream forced off)", sent.get("stream") is False)
        check("non-ASCII prompt arrives intact", sent["messages"][0]["content"] == "Grüß dich")
        check("the desktop's key is added on the desktop", auth == "Bearer desk-only-key")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        server.shutdown()

    # Nothing listening: the answer says so, and names no cloud.
    proc, base = _gateway(f"http://127.0.0.1:{_free_port()}")
    try:
        _, body = _post(base, {"cmd": "llm", "args": json.dumps({"method": "GET", "path": "v1/models"})}, TOKEN)
        check("a stopped model is reported as such",
              body.get("code") == "llm_down" and "not running" in body.get("error", ""))
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    # A remote URL is an upstream provider, not "the local model": refused.
    proc, base = _gateway("https://api.minimax.io")
    try:
        _, body = _post(base, {"cmd": "llm", "args": json.dumps({"method": "GET", "path": "v1/models"})}, TOKEN)
        check("never a plaintext path to a remote model", body.get("code") == "llm_not_local")
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    print(f"\n{'FAILED' if failures else 'OK'}: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
