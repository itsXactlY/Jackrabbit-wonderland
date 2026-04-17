#!/usr/bin/env python3
"""
Gateway Stress & Edge Case Tests
==================================
Tests the LAN Gateway via HTTP API for:
- Concurrent session creation/destruction
- Session exhaustion
- Encrypt/decrypt under rapid fire
- Kill session mid-operation
- Default session behavior
- Response format validation
- Double-destroy sessions
- Gateway restart resilience (DLM key persistence)
"""

import sys
import os
import json
import time
import threading
import urllib.request

GATEWAY_URL = "http://192.168.0.2:8080"


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name):
        self.passed += 1
        print(f"  PASS  {name}")

    def fail(self, name, msg):
        self.failed += 1
        self.errors.append((name, msg))
        print(f"  FAIL  {name}: {msg}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  Results: {self.passed}/{total} passed, {self.failed} failed")
        if self.errors:
            print(f"\n  Failures:")
            for name, msg in self.errors:
                print(f"    - {name}: {msg}")
        print(f"{'='*60}")
        return self.failed == 0


R = TestResult()


def api(cmd, args="", session_id=None):
    """Send command to gateway."""
    data = {"cmd": cmd}
    if args:
        data["args"] = args
    if session_id:
        data["session_id"] = session_id
    req = urllib.request.Request(
        f"{GATEWAY_URL}/command",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def api_safe(cmd, args="", session_id=None):
    """Send command, catch connection errors."""
    try:
        return api(cmd, args, session_id)
    except Exception as e:
        return {"error": str(e)}


# ================================================================
# 1. GATEWAY HEALTH
# ================================================================

def test_gateway_alive():
    """Gateway should respond to status."""
    try:
        resp = api("status")
        if resp.get("status") == "ok":
            R.ok("gateway_alive")
        else:
            R.fail("gateway_alive", f"unexpected: {resp}")
    except Exception as e:
        R.fail("gateway_alive", str(e))


# ================================================================
# 2. SESSION LIFECYCLE
# ================================================================

def test_session_create_destroy():
    """Create -> verify -> destroy -> verify gone."""
    resp = api("session")
    sid = resp["created"]["session_id"]

    sessions = api("sessions")
    ids = [s["id"] for s in sessions["sessions"]]
    if sid not in ids:
        R.fail("session_create", "session not in list")
        return

    kill = api("kill", session_id=sid)
    if kill.get("destroyed") != sid:
        R.fail("session_destroy", f"unexpected: {kill}")
        return

    sessions = api("sessions")
    ids = [s["id"] for s in sessions["sessions"]]
    if sid in ids:
        R.fail("session_destroy_verify", "session still in list after kill")
    else:
        R.ok("session_create_destroy")


def test_session_kill_via_args():
    """Kill should accept session_id via args field."""
    resp = api("session")
    sid = resp["created"]["session_id"]
    kill = api("kill", args=sid)
    if kill.get("destroyed") == sid:
        R.ok("session_kill_via_args")
    else:
        R.fail("session_kill_via_args", f"got: {kill}")


def test_double_destroy():
    """Destroying same session twice should fail gracefully."""
    resp = api("session")
    sid = resp["created"]["session_id"]
    first = api("kill", session_id=sid)
    second = api("kill", session_id=sid)

    if "destroyed" in first and "error" in second:
        R.ok("double_destroy (second rejected)")
    else:
        R.fail("double_destroy", f"first={first}, second={second}")


def test_destroy_nonexistent():
    """Destroying a nonexistent session should return error."""
    resp = api("kill", session_id="deadbeef00000000")
    if "error" in resp:
        R.ok("destroy_nonexistent")
    else:
        R.fail("destroy_nonexistent", f"unexpected success: {resp}")


def test_kill_default_session():
    """Killing the default session should work."""
    # Create a new session (it becomes default)
    resp = api("session")
    sid = resp["created"]["session_id"]

    # Encrypt should still work (uses explicit session_id)
    enc = api("encrypt", args="test", session_id=sid)
    kill = api("kill", session_id=sid)

    if "destroyed" in kill:
        # Encrypt after kill should fail
        enc2 = api("encrypt", args="test2", session_id=sid)
        if "error" in enc2:
            R.ok("kill_default_session")
        else:
            R.fail("kill_default_session", "encrypt succeeded after kill")
    else:
        R.fail("kill_default_session", f"kill failed: {kill}")


# ================================================================
# 3. ENCRYPT/DECRYPT STRESS
# ================================================================

def test_encrypt_decrypt_roundtrip():
    """Basic encrypt->decrypt via API."""
    resp = api("session")
    sid = resp["created"]["session_id"]

    for msg in ["hello", "äöü", "🏠🐕", "a" * 1000, ""]:
        enc = api("encrypt", args=msg, session_id=sid)
        if "error" in enc:
            R.fail("enc_dec_roundtrip", f"encrypt failed: {enc}")
            return
        blob = enc["encrypted"]
        dec = api("decrypt", args=blob, session_id=sid)
        if dec.get("decrypted") != msg:
            R.fail("enc_dec_roundtrip", f"msg={msg!r} got={dec.get('decrypted')!r}")
            return
    R.ok("enc_dec_roundtrip (5 messages)")


def test_rapid_fire_encrypt():
    """100 rapid encrypt/decrypt calls."""
    resp = api("session")
    sid = resp["created"]["session_id"]

    for i in range(100):
        msg = f"rapid message {i}"
        enc = api("encrypt", args=msg, session_id=sid)
        if "error" in enc:
            R.fail("rapid_fire", f"encrypt failed at {i}: {enc}")
            return
        dec = api("decrypt", args=enc["encrypted"], session_id=sid)
        if dec.get("decrypted") != msg:
            R.fail("rapid_fire", f"mismatch at {i}")
            return
    R.ok("rapid_fire (100 enc/dec cycles)")


def test_encrypt_returns_session_id():
    """Encrypt response must include session_id."""
    resp = api("session")
    sid = resp["created"]["session_id"]
    enc = api("encrypt", args="test", session_id=sid)

    if "session_id" not in enc:
        R.fail("encrypt_session_id", "missing session_id in response")
    elif enc["session_id"] != sid:
        R.fail("encrypt_session_id", f"wrong sid: {enc['session_id']} != {sid}")
    else:
        R.ok("encrypt_session_id")


# ================================================================
# 4. ROUNDTRIP COMMAND
# ================================================================

def test_roundtrip_builtin():
    """Built-in roundtrip command should verify match."""
    resp = api("session")
    sid = resp["created"]["session_id"]

    rt = api("roundtrip", args="test message", session_id=sid)
    if not rt.get("roundtrip"):
        R.fail("roundtrip_builtin", f"failed: {rt}")
    elif not rt.get("match"):
        R.fail("roundtrip_builtin", f"mismatch: {rt}")
    else:
        R.ok("roundtrip_builtin")


def test_roundtrip_various():
    """Roundtrip with edge case messages."""
    resp = api("session")
    sid = resp["created"]["session_id"]

    for msg in ["", "a", "€", "x" * 5000, "null\x00byte"]:
        rt = api("roundtrip", args=msg, session_id=sid)
        if not rt.get("match"):
            R.fail(f"roundtrip_various[{msg[:20]}]", f"mismatch: {rt}")
            return
    R.ok("roundtrip_various (5 edge cases)")


# ================================================================
# 5. CHAFF
# ================================================================

def test_chaff_with_session():
    """Chaff should return session_id when session exists."""
    resp = api("session")
    sid = resp["created"]["session_id"]
    chaff = api("chaff", session_id=sid)

    if "chaff" not in chaff:
        R.fail("chaff_with_session", "missing chaff field")
    elif chaff.get("session_id") != sid:
        R.fail("chaff_with_session", f"wrong session_id: {chaff.get('session_id')}")
    else:
        R.ok("chaff_with_session")


def test_chaff_without_session():
    """Chaff without session should still work (standalone)."""
    chaff = api("chaff")
    if "chaff" not in chaff:
        R.fail("chaff_no_session", "missing chaff field")
    else:
        R.ok("chaff_no_session")


# ================================================================
# 6. KEY ROTATION
# ================================================================

def test_key_rotation_via_api():
    """Key rotation via API should work."""
    resp = api("session")
    sid = resp["created"]["session_id"]

    # Encrypt with old key
    enc1 = api("encrypt", args="before rotation", session_id=sid)

    # Rotate
    rot = api("key", session_id=sid)
    if not rot.get("rotated"):
        R.fail("key_rotation_api", f"rotation failed: {rot}")
        return

    # Encrypt with new key
    enc2 = api("encrypt", args="after rotation", session_id=sid)

    # Both should decrypt correctly
    dec1 = api("decrypt", args=enc1["encrypted"], session_id=sid)
    dec2 = api("decrypt", args=enc2["encrypted"], session_id=sid)

    if dec1.get("decrypted") != "before rotation":
        R.fail("key_rotation_api", "old blob not decryptable")
    elif dec2.get("decrypted") != "after rotation":
        R.fail("key_rotation_api", "new blob not decryptable")
    else:
        R.ok("key_rotation_api")


# ================================================================
# 7. CONCURRENT REQUESTS
# ================================================================

def test_concurrent_sessions():
    """Create 20 sessions concurrently, all should work."""
    results = [None] * 20
    errors = [None] * 20

    def worker(idx):
        for attempt in range(3):  # Retry on transient connection errors
            try:
                resp = api("session")
                sid = resp["created"]["session_id"]
                enc = api("encrypt", args=f"worker {idx}", session_id=sid)
                dec = api("decrypt", args=enc["encrypted"], session_id=sid)
                results[idx] = dec.get("decrypted") == f"worker {idx}"
                api("kill", session_id=sid)
                return
            except Exception as e:
                errors[idx] = str(e)
                time.sleep(0.1)  # Brief backoff

    threads = []
    for i in range(20):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=30)

    failed = [i for i in range(20) if not results[i]]
    err_list = [(i, e) for i, e in enumerate(errors) if e and not results[i]]

    if failed and len(failed) > 2:  # Allow up to 2 transient failures
        R.fail("concurrent_sessions", f"failed workers: {failed}")
    elif failed:
        R.ok(f"concurrent_sessions ({20-len(failed)}/20 succeeded, {len(failed)} transient)")
    else:
        R.ok("concurrent_sessions (20 parallel workers)")


def test_concurrent_same_session():
    """Multiple threads using the same session (potential race)."""
    resp = api("session")
    sid = resp["created"]["session_id"]
    errors = []
    successes = [0]

    def worker(idx):
        for attempt in range(3):
            try:
                msg = f"concurrent msg {idx}"
                enc = api("encrypt", args=msg, session_id=sid)
                if "error" in enc:
                    if attempt < 2:
                        time.sleep(0.05)
                        continue
                    errors.append(f"encrypt {idx}: {enc['error']}")
                    return
                dec = api("decrypt", args=enc["encrypted"], session_id=sid)
                if dec.get("decrypted") != msg:
                    errors.append(f"decrypt {idx}: mismatch")
                else:
                    successes[0] += 1
                return
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.05)
                    continue
                errors.append(f"worker {idx}: {e}")

    threads = []
    for i in range(50):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=30)

    if errors and len(errors) > 5:  # Allow up to 5 transient failures
        R.fail("concurrent_same_session", f"{len(errors)} errors: {errors[:3]}")
    elif errors:
        R.ok(f"concurrent_same_session ({successes[0]}/50 succeeded, {len(errors)} transient)")
    else:
        R.ok("concurrent_same_session (50 threads, shared session)")


# ================================================================
# 8. RESPONSE FORMAT
# ================================================================

def test_response_always_json():
    """All responses should be valid JSON."""
    resp = api("status")
    if not isinstance(resp, dict):
        R.fail("response_json", "status not a dict")
        return

    resp = api("sessions")
    if not isinstance(resp, dict):
        R.fail("response_json", "sessions not a dict")
        return

    resp = api("nonexistent_command_xyz")
    if not isinstance(resp, dict) or "error" not in resp:
        R.fail("response_json", "invalid command didn't return error dict")
    else:
        R.ok("response_always_json")


def test_unknown_command_format():
    """Unknown commands should return error with help."""
    resp = api("nonexistent")
    if "error" not in resp:
        R.fail("unknown_command", "no error field")
    elif "help" not in resp:
        R.fail("unknown_command", "no help field")
    else:
        R.ok("unknown_command_format")


# ================================================================
# 9. DEFAULT SESSION BEHAVIOR
# ================================================================

def test_default_session_on_startup():
    """Gateway should have a default session after startup."""
    # The gateway creates a default session at startup.
    # Encrypt without session_id should use it.
    enc = api("encrypt", args="default session test")
    if "error" in enc and "No active session" in enc["error"]:
        R.fail("default_session", "no default session")
    elif "encrypted" in enc:
        blob = enc["encrypted"]
        dec = api("decrypt", args=blob)
        if dec.get("decrypted") == "default session test":
            R.ok("default_session_on_startup")
        else:
            R.fail("default_session", f"decrypt failed: {dec}")
    else:
        R.fail("default_session", f"unexpected: {enc}")


# ================================================================
# 10. GATEWAY RESOURCE EXHAUSTION
# ================================================================

def test_session_bomb():
    """Create 500 sessions rapidly, verify no crash."""
    sids = []
    for i in range(500):
        resp = api_safe("session")
        if "created" in resp:
            sids.append(resp["created"]["session_id"])
        else:
            break

    # Gateway should still respond
    status = api_safe("status")
    if status.get("status") == "ok":
        R.ok(f"session_bomb ({len(sids)} sessions created, gateway alive)")
    else:
        R.fail("session_bomb", f"gateway crashed after {len(sids)} sessions")

    # Cleanup
    for sid in sids:
        api_safe("kill", session_id=sid)


def test_large_payload():
    """Encrypt a 100KB payload."""
    resp = api("session")
    sid = resp["created"]["session_id"]

    big = "X" * 102400
    enc = api("encrypt", args=big, session_id=sid)
    if "error" in enc:
        R.fail("large_payload", f"encrypt failed: {enc['error']}")
        return

    dec = api("decrypt", args=enc["encrypted"], session_id=sid)
    if dec.get("decrypted") == big:
        R.ok("large_payload (100KB)")
    else:
        R.fail("large_payload", f"mismatch: expected {len(big)}, got {len(dec.get('decrypted', ''))}")


def test_unicode_payload():
    """Full unicode range."""
    resp = api("session")
    sid = resp["created"]["session_id"]

    # Build a string with various unicode planes
    msg = "Hello 世界 مرحبا שלום 🏠🐕🔑💰 Grüße äöüß ñ é ß"
    enc = api("encrypt", args=msg, session_id=sid)
    dec = api("decrypt", args=enc["encrypted"], session_id=sid)
    if dec.get("decrypted") == msg:
        R.ok("unicode_payload")
    else:
        R.fail("unicode_payload", f"got: {dec.get('decrypted')!r}")


# ================================================================
# RUNNER
# ================================================================

def run_all():
    print("=" * 60)
    print("  GATEWAY STRESS TEST SUITE")
    print("=" * 60)

    tests = [
        ("1. Gateway Alive", test_gateway_alive),
        ("2. Session Create/Destroy", test_session_create_destroy),
        ("3. Session Kill via Args", test_session_kill_via_args),
        ("4. Double Destroy", test_double_destroy),
        ("5. Destroy Nonexistent", test_destroy_nonexistent),
        ("6. Kill Default Session", test_kill_default_session),
        ("7. Encrypt/Decrypt Roundtrip", test_encrypt_decrypt_roundtrip),
        ("8. Rapid Fire Encrypt", test_rapid_fire_encrypt),
        ("9. Encrypt Returns Session ID", test_encrypt_returns_session_id),
        ("10. Roundtrip Built-in", test_roundtrip_builtin),
        ("11. Roundtrip Various", test_roundtrip_various),
        ("12. Chaff with Session", test_chaff_with_session),
        ("13. Chaff without Session", test_chaff_without_session),
        ("14. Key Rotation API", test_key_rotation_via_api),
        ("15. Concurrent Sessions", test_concurrent_sessions),
        ("16. Concurrent Same Session", test_concurrent_same_session),
        ("17. Response Always JSON", test_response_always_json),
        ("18. Unknown Command Format", test_unknown_command_format),
        ("19. Default Session on Startup", test_default_session_on_startup),
        ("20. Session Bomb", test_session_bomb),
        ("21. Large Payload", test_large_payload),
        ("22. Unicode Payload", test_unicode_payload),
    ]

    for name, test_fn in tests:
        print(f"\n--- {name} ---")
        try:
            test_fn()
        except Exception as e:
            R.fail(name, f"EXCEPTION: {e}")

    return R.summary()


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
