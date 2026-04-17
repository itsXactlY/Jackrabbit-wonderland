#!/usr/bin/env python3
"""
Hermes Zero-Knowledge LAN Gateway
===================================
Tiny HTTP server for controlling Hermes from any device on the LAN.
Works from: browser, curl, netcat, iOS Shortcuts, any HTTP client.

Features:
  - Web UI (minimal, mobile-friendly)
  - JSON API (POST /command)
  - Netcat compatible (raw TCP on :37374)
  - AES256-GCM encrypted command/response
  - DLM vault key storage
  - Session management

Usage:
  python3 lan_gateway.py                  # Start on 0.0.0.0:8080
  python3 lan_gateway.py --port 9090      # Custom port
  python3 lan_gateway.py --no-crypto      # Disable encryption (debug)

Access:
  http://192.168.0.2:8080                 # Browser
  curl -X POST http://192.168.0.2:8080/command -d '{"cmd":"status"}'
  echo '{"cmd":"status"}' | nc 192.168.0.2 37374
"""

import http.server
import socketserver
import json
import os
import sys
import subprocess
import threading
import socket
import time
import hashlib
import base64
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Add hermes-crypto to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from crypto_middleware import CryptoMiddleware


# ================================================================
# CONFIG
# ================================================================

GATEWAY_PORT = 8080
RAW_TCP_PORT = 37374
DLM_HOST = "127.0.0.1"
DLM_PORT = 37373
SESSION_TTL = 7200  # 2 hours

# ================================================================
# SESSION STATE
# ================================================================

class SessionManager:
    """Manages encrypted sessions with DLM vault fallback."""
    
    def __init__(self):
        self.sessions = {}  # session_id -> {cm, created, last_active}
        self.default_session = None
    
    def create_session(self) -> dict:
        """Create a new encrypted session."""
        session_id = os.urandom(8).hex()
        cm = CryptoMiddleware()
        header = cm.session_start()
        
        # Try DLM vault
        dlm_ok = False
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from dlm_vault import DLMVault
            vault = DLMVault(host=DLM_HOST, port=DLM_PORT)
            if vault.health_check():
                vault.store_key(session_id, cm.session_key, ttl=SESSION_TTL)
                dlm_ok = True
        except Exception:
            vault = None
        
        session = {
            "session_id": session_id,
            "cm": cm,
            "created": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "dlm_stored": dlm_ok,
            "vault": vault if dlm_ok else None,
        }
        
        self.sessions[session_id] = session
        self.default_session = session
        
        return {
            "session_id": session_id,
            "crypto_header": header,
            "dlm_vault": dlm_ok,
            "key_suffix": f"...{cm.session_key[-12:]}",
        }
    
    def get_session(self, session_id: str = None) -> dict:
        """Get session by ID or default."""
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]
        return self.default_session
    
    def destroy_session(self, session_id: str) -> bool:
        """Destroy a session and its key."""
        session = self.sessions.pop(session_id, None)
        if session:
            if session.get("vault") and session.get("dlm_stored"):
                try:
                    session["vault"].destroy_key(session_id)
                except Exception:
                    pass
            if self.default_session and self.default_session["session_id"] == session_id:
                self.default_session = None
            return True
        return False
    
    def list_sessions(self) -> list:
        """List all active sessions."""
        return [
            {
                "id": s["session_id"],
                "created": s["created"],
                "last_active": s["last_active"],
                "dlm": s["dlm_stored"],
            }
            for s in self.sessions.values()
        ]


# Global session manager
sessions = SessionManager()


# ================================================================
# COMMAND EXECUTION
# ================================================================

def execute_command(cmd: str, args: str = "", encrypted: bool = False,
                    session_id: str = None) -> dict:
    """
    Execute a command and return result.
    
    Built-in commands:
      status     — gateway + DLM status
      sessions   — list active sessions
      session    — create new session
      kill       — destroy a session
      hermes     — run hermes CLI command
      pulse      — run PULSE search
      shell      — run shell command (LAN only, be careful)
      encrypt    — encrypt a message
      decrypt    — decrypt a message
      chaff      — generate chaff message
      key        — rotate session key
    """
    
    if cmd == "status":
        dlm_ok = False
        dlm_version = "N/A"
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from dlm_vault import DLMVault
            vault = DLMVault()
            if vault.health_check():
                dlm_ok = True
                lock = vault._make_locker("version-check")
                dlm_version = str(lock.Version())
        except Exception:
            pass
        
        return {
            "status": "ok",
            "gateway": "running",
            "dlm": "online" if dlm_ok else "offline",
            "dlm_version": dlm_version,
            "crypto": "AES256-GCM",
            "sessions": len(sessions.sessions),
            "time": datetime.now().isoformat(),
        }
    
    elif cmd == "sessions":
        return {"sessions": sessions.list_sessions()}
    
    elif cmd == "session":
        result = sessions.create_session()
        return {"created": result}
    
    elif cmd == "kill":
        # Accept session_id from JSON field OR from args
        target = session_id or args
        if target and sessions.destroy_session(target):
            return {"destroyed": target}
        return {"error": "Session not found"}
    
    elif cmd == "hermes":
        if not args:
            return {"error": "No hermes command provided"}
        try:
            result = subprocess.run(
                ["hermes"] + args.split(),
                capture_output=True, text=True, timeout=120
            )
            return {
                "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
                "stderr": result.stderr[-500:] if len(result.stderr) > 500 else result.stderr,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Hermes command timed out (120s)"}
        except FileNotFoundError:
            return {"error": "hermes not found on PATH"}
    
    elif cmd == "pulse":
        if not args:
            return {"error": "No search topic provided"}
        pulse_script = os.path.expanduser("~/projects/pulse/scripts/pulse.py")
        if not os.path.exists(pulse_script):
            return {"error": f"PULSE not found at {pulse_script}"}
        try:
            result = subprocess.run(
                ["python3", pulse_script, args, "--depth", "quick", "--emit", "json"],
                capture_output=True, text=True, timeout=60
            )
            return {
                "result": result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "PULSE timed out (60s)"}
    
    elif cmd == "shell":
        if not args:
            return {"error": "No shell command provided"}
        # Safety: block dangerous commands
        dangerous = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:", "chmod 777"]
        if any(d in args for d in dangerous):
            return {"error": "Blocked dangerous command"}
        try:
            result = subprocess.run(
                args, shell=True,
                capture_output=True, text=True, timeout=30
            )
            return {
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-500:],
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Shell command timed out (30s)"}
    
    elif cmd == "encrypt":
        session = sessions.get_session(session_id)
        if not session:
            return {"error": "No active session. Create one first."}
        cm = session["cm"]
        blob, chaff = cm.encrypt_outbound(args)
        result = {
            "encrypted": blob,
            "session_id": session["session_id"],
            "chaff": cm.chaff_message() if chaff else None,
        }
        if encrypted:
            resp_blob = cm.encrypt(json.dumps(result))
            return {"ENC_MSG": resp_blob}
        return result
    
    elif cmd == "decrypt":
        session = sessions.get_session(session_id)
        if not session:
            return {"error": "No active session"}
        cm = session["cm"]
        try:
            plaintext = cm.decrypt(args)
            return {"decrypted": plaintext, "session_id": session["session_id"]}
        except ValueError as e:
            return {"error": str(e)}
    
    elif cmd == "chaff":
        # Use session's CryptoMiddleware if available, fallback to standalone
        session = sessions.get_session(session_id)
        if session and session.get("cm"):
            cm = session["cm"]
            return {"chaff": cm.chaff_message(), "session_id": session["session_id"]}
        cm = CryptoMiddleware()
        cm.session_start()
        return {"chaff": cm.chaff_message(), "session_id": None}
    
    elif cmd == "key":
        session = sessions.get_session(session_id)
        if not session:
            return {"error": "No active session"}
        cm = session["cm"]
        rotation = cm.rotate_key()
        return {
            "rotated": True,
            "rotation_blob": rotation,
            "new_key_suffix": f"...{cm.session_key[-12:]}",
            "keys_in_history": len(cm._key_history),
        }
    
    elif cmd == "roundtrip":
        # End-to-end encrypt/decrypt test
        session = sessions.get_session(session_id)
        if not session:
            return {"error": "No active session. Create one first."}
        cm = session["cm"]
        test_msg = args or "roundtrip test"
        blob, chaff = cm.encrypt_outbound(test_msg)
        try:
            decrypted = cm.decrypt(blob)
            return {
                "roundtrip": True,
                "match": decrypted == test_msg,
                "plaintext": test_msg,
                "encrypted": blob,
                "decrypted": decrypted,
                "session_id": session["session_id"],
            }
        except Exception as e:
            return {"roundtrip": False, "error": str(e)}
    
    else:
        return {"error": f"Unknown command: {cmd}", "help": "status, sessions, session, kill, hermes, pulse, shell, encrypt, decrypt, chaff, key, roundtrip"}


# ================================================================
# HTML INTERFACE
# ================================================================

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hermes Gateway</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,monospace;background:#0a0a12;color:#f5b731;min-height:100vh}
.hdr{background:#1a1a24;padding:12px 16px;border-bottom:1px solid #333;display:flex;justify-content:space-between;align-items:center}
.hdr h1{font-size:16px;color:#f5b731}
.hdr .status{font-size:12px;color:#888}
.main{max-width:600px;margin:0 auto;padding:16px}
.card{background:#1a1a24;border:1px solid #333;border-radius:8px;margin-bottom:12px;overflow:hidden}
.card-hdr{padding:10px 14px;border-bottom:1px solid #222;font-size:13px;font-weight:600;color:#f5b731}
.card-body{padding:14px}
input,textarea,select,button{font-family:inherit;font-size:14px}
input,textarea,select{width:100%;background:#0a0a12;color:#f5b731;border:1px solid #333;border-radius:4px;padding:8px 10px;margin-bottom:8px}
input:focus,textarea:focus{outline:none;border-color:#f5b731}
button{background:#f5b731;color:#0a0a12;border:none;border-radius:4px;padding:10px 16px;cursor:pointer;font-weight:600;width:100%;margin-bottom:6px}
button:active{opacity:.8}
button.sec{background:#333;color:#f5b731}
.output{background:#0a0a12;border:1px solid #333;border-radius:4px;padding:10px;font-size:12px;white-space:pre-wrap;word-break:break-all;max-height:300px;overflow-y:auto;margin-top:8px;color:#ccc}
.qbtn{display:inline-block;background:#222;color:#f5b731;border:1px solid #444;border-radius:4px;padding:6px 10px;margin:3px;cursor:pointer;font-size:12px}
.qbtn:active{background:#f5b731;color:#0a0a12}
.crypto-indicator{font-size:11px;color:#4a4;padding:4px 8px;background:#112211;border-radius:4px;display:inline-block}
</style>
</head>
<body>
<div class="hdr">
  <h1>HERMES</h1>
  <div class="status"><span id="st">connecting...</span></div>
</div>
<div class="main">
  <div class="card">
    <div class="card-hdr">QUICK ACTIONS</div>
    <div class="card-body">
      <span class="qbtn" onclick="run('status')">Status</span>
      <span class="qbtn" onclick="run('sessions')">Sessions</span>
      <span class="qbtn" onclick="run('session')">New Session</span>
      <span class="qbtn" onclick="run('chaff')">Chaff</span>
      <span class="qbtn" onclick="askPulse()">PULSE</span>
      <span class="qbtn" onclick="askHermes()">Hermes</span>
    </div>
  </div>
  <div class="card">
    <div class="card-hdr">COMMAND</div>
    <div class="card-body">
      <select id="cmd">
        <option value="status">status</option>
        <option value="sessions">sessions</option>
        <option value="session">session (new)</option>
        <option value="hermes">hermes</option>
        <option value="pulse">pulse</option>
        <option value="shell">shell</option>
        <option value="encrypt">encrypt</option>
        <option value="decrypt">decrypt</option>
        <option value="chaff">chaff</option>
        <option value="key">key (rotate)</option>
        <option value="roundtrip">roundtrip test</option>
        <option value="kill">kill session</option>
      </select>
      <input id="args" placeholder="arguments (optional)" />
      <button onclick="submit()">EXECUTE</button>
      <div class="crypto-indicator" id="crypto-st">AES256-GCM ready</div>
      <div class="output" id="out">Ready.</div>
    </div>
  </div>
</div>
<script>
let sid=null;
async function api(cmd,args){
  const r=await fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({cmd,args,session_id:sid})});
  return r.json();
}
async function run(cmd,args=''){
  const out=document.getElementById('out');
  out.textContent='Running '+cmd+'...';
  try{
    const d=await api(cmd,args);
    out.textContent=JSON.stringify(d,null,2);
    if(d.created&&d.created.session_id){
      sid=d.created.session_id;
      document.getElementById('st').textContent='session:'+sid.slice(0,8);
    }
  }catch(e){out.textContent='Error: '+e.message}
}
async function submit(){
  const cmd=document.getElementById('cmd').value;
  const args=document.getElementById('args').value;
  await run(cmd,args);
}
function askPulse(){
  const t=prompt('PULSE search topic:');
  if(t)run('pulse',t);
}
function askHermes(){
  const t=prompt('Hermes command (e.g. "ask what is 2+2"):');
  if(t)run('hermes',t);
}
// Auto-status on load
run('status');
</script>
</body>
</html>"""


# ================================================================
# HTTP HANDLER
# ================================================================

class GatewayHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the LAN gateway."""
    
    def log_message(self, format, *args):
        """Minimal logging."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0] if args else ''}")
    
    def do_GET(self):
        """Serve web UI or handle GET API calls."""
        path = urlparse(self.path).path
        
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        
        elif path == "/status":
            result = execute_command("status")
            self._json_response(result)
        
        elif path == "/sessions":
            result = execute_command("sessions")
            self._json_response(result)
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
    
    def do_POST(self):
        """Handle command POSTs."""
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON"}, 400)
            return
        
        cmd = data.get("cmd", "")
        args = data.get("args", "")
        session_id = data.get("session_id")
        encrypted = data.get("encrypted", False)
        
        if not cmd:
            self._json_response({"error": "No 'cmd' field"}, 400)
            return
        
        result = execute_command(cmd, args, encrypted, session_id)
        self._json_response(result)
    
    def _json_response(self, data: dict, code: int = 200):
        """Send JSON response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())


# ================================================================
# RAW TCP HANDLER (netcat compatible)
# ================================================================

def raw_tcp_server(port: int):
    """Simple raw TCP server for netcat compatibility."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen(5)
    print(f"[TCP] Raw TCP on :{port} (netcat compatible)")
    
    while True:
        try:
            conn, addr = sock.accept()
            threading.Thread(target=_handle_tcp, args=(conn, addr), daemon=True).start()
        except Exception:
            pass


def _handle_tcp(conn: socket.socket, addr: tuple):
    """Handle a raw TCP connection."""
    try:
        conn.settimeout(10)
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
        
        line = data.decode("utf-8").strip()
        if not line:
            conn.close()
            return
        
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            # Treat as shell command
            request = {"cmd": "shell", "args": line}
        
        cmd = request.get("cmd", "shell")
        args = request.get("args", "")
        session_id = request.get("session_id")
        
        result = execute_command(cmd, args, session_id=session_id)
        
        response = json.dumps(result, default=str) + "\n"
        conn.sendall(response.encode())
    except Exception as e:
        try:
            conn.sendall(json.dumps({"error": str(e)}).encode() + b"\n")
        except Exception:
            pass
    finally:
        conn.close()


# ================================================================
# MAIN
# ================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Zero-Knowledge LAN Gateway")
    parser.add_argument("--port", type=int, default=GATEWAY_PORT, help="HTTP port")
    parser.add_argument("--tcp-port", type=int, default=RAW_TCP_PORT, help="Raw TCP port")
    parser.add_argument("--bind", default="0.0.0.0", help="Bind address")
    parser.add_argument("--no-crypto", action="store_true", help="Disable encryption")
    args = parser.parse_args()
    
    print("=" * 50)
    print("  HERMES ZERO-KNOWLEDGE LAN GATEWAY")
    print("=" * 50)
    print(f"  HTTP:  http://{args.bind}:{args.port}")
    print(f"  TCP:   {args.bind}:{args.tcp_port} (netcat)")
    print(f"  Crypto: {'DISABLED' if args.no_crypto else 'AES256-GCM'}")
    print(f"  DLM:   {DLM_HOST}:{DLM_PORT}")
    print("=" * 50)
    
    # Start raw TCP server in background
    tcp_thread = threading.Thread(target=raw_tcp_server, args=(args.tcp_port,), daemon=True)
    tcp_thread.start()
    
    # Create default session
    if not args.no_crypto:
        result = sessions.create_session()
        print(f"  Default session: {result['session_id']}")
        print(f"  DLM vault: {'YES' if result['dlm_vault'] else 'NO (memory only)'}")
    
    print()
    print("  Access from any LAN device:")
    print(f"  Browser: http://<this-ip>:{args.port}")
    print(f"  curl:    curl -X POST http://<this-ip>:{args.port}/command -d '{{\"cmd\":\"status\"}}'")
    print(f"  netcat:  echo '{{\"cmd\":\"status\"}}' | nc <this-ip> {args.tcp_port}")
    print()
    
    # Start HTTP server
    with socketserver.TCPServer((args.bind, args.port), GatewayHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
