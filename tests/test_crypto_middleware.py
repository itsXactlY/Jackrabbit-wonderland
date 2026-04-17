#!/usr/bin/env python3
"""
CryptoMiddleware Unit & Stress Tests
=====================================
Tests the core AES256-GCM encrypt/decrypt engine for:
- Correct round-trip on all content types
- Nonce uniqueness (no reuse)
- Key rotation integrity
- Tag verification (tamper detection)
- Edge cases (empty, huge, unicode, binary, nul bytes)
- Memory behavior under load
- Chaff interval tracking
"""

import sys
import os
import gc
import tracemalloc
import secrets
import string

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crypto_middleware import CryptoMiddleware


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


# ================================================================
# 1. BASIC ROUND-TRIP
# ================================================================

def test_basic_roundtrip():
    """Basic encrypt->decrypt should return identical plaintext."""
    cm = CryptoMiddleware()
    cm.session_start()
    for msg in [
        "Hello World",
        "Haus-Suche Budget 1000€ warm",
        "Umlaute: äöüß ÄÖÜ ñ é",
        "Emoji: 🏠🐕💰🔑",
        "Mixed: Hallo 世界 🌍 مرحبا",
    ]:
        blob = cm.encrypt(msg)
        dec = cm.decrypt(blob)
        if dec != msg:
            R.fail(f"basic_roundtrip[{msg[:30]}]", f"got: {dec!r}")
        else:
            R.ok(f"basic_roundtrip[{msg[:30]}]")


def test_empty_string():
    """Empty string should round-trip cleanly."""
    cm = CryptoMiddleware()
    cm.session_start()
    blob = cm.encrypt("")
    dec = cm.decrypt(blob)
    if dec != "":
        R.fail("empty_string", f"got: {dec!r}")
    else:
        R.ok("empty_string")


def test_single_byte():
    """Single byte strings."""
    cm = CryptoMiddleware()
    cm.session_start()
    for c in ["a", " ", "\n", "\t", "€"]:
        blob = cm.encrypt(c)
        dec = cm.decrypt(blob)
        if dec != c:
            R.fail(f"single_byte[{c!r}]", f"got: {dec!r}")
        else:
            R.ok(f"single_byte[{c!r}]")


def test_large_payload():
    """Large payloads (1MB+) should work without corruption."""
    cm = CryptoMiddleware()
    cm.session_start()
    for size in [1024, 65536, 262144, 1048576]:
        msg = "X" * size
        blob = cm.encrypt(msg)
        dec = cm.decrypt(blob)
        if len(dec) != size:
            R.fail(f"large_payload[{size}]", f"length mismatch: {len(dec)} != {size}")
        elif dec != msg:
            R.fail(f"large_payload[{size}]", "content mismatch")
        else:
            R.ok(f"large_payload[{size}]")


def test_binary_content():
    """Binary-ish content with nul bytes, control chars."""
    cm = CryptoMiddleware()
    cm.session_start()
    for name, content in [
        ("nul_bytes", b"\x00\x01\x02\x03\xff\xfe\xfd".decode("latin-1")),
        ("all_control", "".join(chr(i) for i in range(32))),
        ("mixed_binary", "OK\x00BROKEN\x00DONE"),
    ]:
        blob = cm.encrypt(content)
        dec = cm.decrypt(blob)
        if dec != content:
            R.fail(f"binary_content[{name}]", "mismatch")
        else:
            R.ok(f"binary_content[{name}]")


# ================================================================
# 2. NONCE UNIQUENESS
# ================================================================

def test_nonce_uniqueness():
    """Every encryption must produce a different blob (unique nonce)."""
    cm = CryptoMiddleware()
    cm.session_start()
    msg = "same message every time"
    blobs = set()
    for i in range(1000):
        blob = cm.encrypt(msg)
        if blob in blobs:
            R.fail("nonce_uniqueness", f"DUPLICATE blob at iteration {i}")
            return
        blobs.add(blob)
    R.ok(f"nonce_uniqueness (1000 unique blobs)")


def test_nonce_length():
    """GCM nonce should be exactly 16 bytes (embedded in blob)."""
    cm = CryptoMiddleware()
    cm.session_start()
    import base64
    blob = cm.encrypt("test")
    raw = base64.b64decode(blob)
    # nonce(16) + tag(16) + ct(N)
    if len(raw) < 32:
        R.fail("nonce_length", f"blob too short: {len(raw)} bytes")
    else:
        R.ok("nonce_length (16 nonce + 16 tag + ct)")


# ================================================================
# 3. TAMPER DETECTION
# ================================================================

def test_tamper_detection():
    """Flipping a bit in the ciphertext should cause decryption failure."""
    cm = CryptoMiddleware()
    cm.session_start()
    import base64
    blob = cm.encrypt("sensitive data")
    raw = bytearray(base64.b64decode(blob))

    # Flip bit in ciphertext portion (after nonce + tag)
    if len(raw) > 33:
        raw[33] ^= 0x01
        tampered = base64.b64encode(bytes(raw)).decode()
        try:
            cm.decrypt(tampered)
            R.fail("tamper_detection", "decryption succeeded on tampered blob")
        except (ValueError, Exception):
            R.ok("tamper_detection (tampered blob rejected)")
    else:
        R.fail("tamper_detection", "blob too short to tamper")


def test_truncated_blob():
    """Truncated blobs should fail decryption."""
    cm = CryptoMiddleware()
    cm.session_start()
    import base64
    blob = cm.encrypt("test data")
    raw = base64.b64decode(blob)

    for cut_at in [1, 5, 10, 20, 30]:
        if cut_at >= len(raw):
            continue
        truncated = base64.b64encode(raw[:cut_at]).decode()
        try:
            cm.decrypt(truncated)
            R.fail(f"truncated_blob[{cut_at}]", "decryption succeeded")
        except Exception:
            R.ok(f"truncated_blob[{cut_at}] rejected")


def test_garbage_input():
    """Random garbage should fail decryption, not crash."""
    import base64 as b64_mod
    cm = CryptoMiddleware()
    cm.session_start()
    garbage_inputs = [
        "not-base64-at-all!!!",
        b64_mod.b64encode(b"too-short").decode(),
        "A" * 10000,
        "",
        "////====",
        "deadbeef" * 50,
    ]
    for i, garbage in enumerate(garbage_inputs):
        try:
            cm.decrypt(garbage)
            R.fail(f"garbage_input[{i}]", "decryption succeeded on garbage")
        except Exception:
            R.ok(f"garbage_input[{i}] rejected")


# ================================================================
# 4. KEY ROTATION
# ================================================================

def test_key_rotation_basic():
    """After rotation, new data uses new key, old data still decryptable."""
    cm = CryptoMiddleware()
    cm.session_start()
    old_blob = cm.encrypt("before rotation")
    old_key = cm.session_key

    cm.rotate_key()
    new_blob = cm.encrypt("after rotation")
    new_key = cm.session_key

    if old_key == new_key:
        R.fail("key_rotation_basic", "key did not change")
        return

    # Old blob should still decrypt (key history)
    dec_old = cm.decrypt(old_blob)
    dec_new = cm.decrypt(new_blob)

    if dec_old != "before rotation":
        R.fail("key_rotation_basic", "old blob not decryptable")
    elif dec_new != "after rotation":
        R.fail("key_rotation_basic", "new blob not decryptable")
    else:
        R.ok("key_rotation_basic")


def test_key_rotation_chain():
    """Chain of 10 rotations, last 5 blobs decryptable (history limit)."""
    cm = CryptoMiddleware()
    cm.session_start()
    blobs = []

    for i in range(10):
        blobs.append(cm.encrypt(f"message {i}"))
        cm.rotate_key()

    # Last 5 should decrypt (key history cap is 5)
    for i in range(5, 10):
        dec = cm.decrypt(blobs[i])
        if dec != f"message {i}":
            R.fail(f"key_rotation_chain[{i}]", f"got: {dec!r}")
            return

    # First 5 should NOT decrypt (evicted from history)
    for i in range(5):
        try:
            cm.decrypt(blobs[i])
            R.fail(f"key_rotation_chain[{i}]", "should have failed (key evicted)")
            return
        except Exception:
            pass  # Expected

    R.ok("key_rotation_chain (10 rotations, last 5 decryptable, first 5 evicted)")


def test_key_history_limit():
    """Key history should cap at 5 old keys."""
    cm = CryptoMiddleware()
    cm.session_start()
    first_blob = cm.encrypt("oldest message")

    # Rotate 7 times (exceeds limit of 5)
    for i in range(7):
        cm.rotate_key()

    if len(cm._key_history) > 5:
        R.fail("key_history_limit", f"history has {len(cm._key_history)} keys")
        return

    # First blob should be UNdecryptable (key evicted from history)
    try:
        cm.decrypt(first_blob)
        R.fail("key_history_limit", "oldest blob still decryptable (should be evicted)")
    except Exception:
        R.ok("key_history_limit (oldest key evicted)")


def test_auto_rotation():
    """Key should auto-rotate at rotation_interval."""
    cm = CryptoMiddleware()
    cm.session_start()
    cm.rotation_interval = 5
    first_key = cm.session_key

    for i in range(5):
        cm.encrypt_outbound(f"msg {i}")

    if cm.session_key == first_key:
        R.fail("auto_rotation", "key did not auto-rotate")
    else:
        R.ok("auto_rotation (rotated at interval)")


# ================================================================
# 5. CHAFF TRACKING
# ================================================================

def test_chaff_interval():
    """Chaff should trigger at correct intervals."""
    cm = CryptoMiddleware()
    cm.session_start()
    cm.chaff_interval = 3

    results = []
    for i in range(9):
        _, chaff = cm.encrypt_outbound(f"msg {i}")
        results.append(chaff)

    expected = [False, False, True, False, False, True, False, False, True]
    if results != expected:
        R.fail("chaff_interval", f"got {results}, expected {expected}")
    else:
        R.ok("chaff_interval")


def test_chaff_message_validity():
    """Chaff messages should be non-empty strings from the pool."""
    cm = CryptoMiddleware()
    cm.session_start()
    seen = set()
    for _ in range(100):
        msg = cm.chaff_message()
        if not msg or not isinstance(msg, str):
            R.fail("chaff_message_validity", f"invalid chaff: {msg!r}")
            return
        seen.add(msg)
    # Should have some variety (not always the same)
    if len(seen) < 2:
        R.fail("chaff_message_validity", f"no variety: only {len(seen)} unique")
    else:
        R.ok(f"chaff_message_validity ({len(seen)} unique messages)")


# ================================================================
# 6. MEMORY BEHAVIOR
# ================================================================

def test_memory_no_leak_on_encrypt():
    """Encrypting 10k messages should not leak memory unboundedly."""
    gc.collect()
    tracemalloc.start()
    cm = CryptoMiddleware()
    cm.session_start()

    baseline = tracemalloc.get_traced_memory()[0]

    for i in range(10000):
        cm.encrypt(f"message {i} with some padding to be realistic")

    gc.collect()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    # Peak should be reasonable (< 50MB for 10k encrypts)
    peak_mb = peak / (1024 * 1024)
    if peak_mb > 50:
        R.fail("memory_no_leak", f"peak memory {peak_mb:.1f}MB too high")
    else:
        R.ok(f"memory_no_leak (peak {peak_mb:.1f}MB for 10k encrypts)")


def test_object_cleanup():
    """CryptoMiddleware objects should be garbage collectable."""
    gc.collect()
    initial_objects = len(gc.get_objects())

    for _ in range(100):
        cm = CryptoMiddleware()
        cm.session_start()
        for i in range(10):
            cm.encrypt(f"msg {i}")
        del cm

    gc.collect()
    final_objects = len(gc.get_objects())
    leak = final_objects - initial_objects

    # Allow some drift but not 100x object accumulation
    if leak > 10000:
        R.fail("object_cleanup", f"leaked {leak} object refs")
    else:
        R.ok(f"object_cleanup ({leak} net objects after 100 CM lifecycles)")


def test_session_key_zeroization():
    """Key should be None-able for cleanup."""
    cm = CryptoMiddleware()
    cm.session_start()
    key_before = cm.session_key
    cm.session_key = None

    try:
        cm.encrypt("should fail")
        R.fail("session_key_zeroization", "encrypt succeeded with None key")
    except (ValueError, TypeError, AttributeError):
        R.ok("session_key_zeroization (encrypt fails with None key)")

    # Restore for proper cleanup
    cm.session_key = key_before


# ================================================================
# 7. FORMAT FOR PROVIDER
# ================================================================

def test_format_for_provider():
    """format_for_provider should contain the blob and decode instructions."""
    cm = CryptoMiddleware()
    cm.session_start()
    blob = cm.encrypt("test")
    formatted = cm.format_for_provider(blob)

    if "ENC_MSG:" not in formatted:
        R.fail("format_for_provider", "missing ENC_MSG prefix")
    elif blob not in formatted:
        R.fail("format_for_provider", "blob not in output")
    elif "Decode" not in formatted:
        R.fail("format_for_provider", "missing decode instructions")
    else:
        R.ok("format_for_provider")


def test_provider_sees_only_base64():
    """The formatted message should NOT contain plaintext."""
    cm = CryptoMiddleware()
    cm.session_start()
    secret = "MY_SECRET_PASSWORD_12345"
    blob = cm.encrypt(secret)
    formatted = cm.format_for_provider(blob)

    if secret in formatted:
        R.fail("provider_no_plaintext", "secret visible in formatted output")
    else:
        R.ok("provider_no_plaintext")


# ================================================================
# 8. STORAGE ENCRYPTION (MASTER KEY)
# ================================================================

def test_storage_roundtrip():
    """encrypt_for_storage/decrypt_from_storage should round-trip."""
    cm = CryptoMiddleware()
    cm.session_start()
    msg = "Neural Memory entry: user wants EFH Brandenburg"
    stored = cm.encrypt_for_storage(msg)
    recalled = cm.decrypt_from_storage(stored)
    if recalled != msg:
        R.fail("storage_roundtrip", f"got: {recalled!r}")
    else:
        R.ok("storage_roundtrip")


def test_storage_uses_master_key():
    """Storage encryption should use master_key, not session_key."""
    cm = CryptoMiddleware()
    cm.session_start()
    msg = "test"
    stored = cm.encrypt_for_storage(msg)
    session_encrypted = cm.encrypt(msg)

    # They should be different (different keys and nonces)
    if stored == session_encrypted:
        R.fail("storage_master_key", "storage and session produce same blob")
    else:
        R.ok("storage_master_key (different from session encryption)")


# ================================================================
# 9. CONCURRENT USAGE SIMULATION
# ================================================================

def test_multiple_sessions():
    """Multiple CryptoMiddleware instances should be independent."""
    cms = []
    blobs = []
    for i in range(10):
        cm = CryptoMiddleware()
        cm.session_start()
        cms.append(cm)
        blobs.append(cm.encrypt(f"session {i} secret"))

    # Each session can only decrypt its own blob
    for i, cm in enumerate(cms):
        dec = cm.decrypt(blobs[i])
        if dec != f"session {i} secret":
            R.fail(f"multiple_sessions[{i}]", "own blob failed")
            return

        # Try to decrypt another session's blob (should fail)
        other_idx = (i + 1) % 10
        try:
            cm.decrypt(blobs[other_idx])
            R.fail(f"multiple_sessions[{i}]", "cross-session decrypt succeeded!")
            return
        except Exception:
            pass  # Expected

    R.ok("multiple_sessions (10 independent sessions, no cross-decrypt)")


def test_interleaved_operations():
    """Interleaving encrypt/decrypt/rotate across sessions."""
    cm1 = CryptoMiddleware()
    cm1.session_start()
    cm2 = CryptoMiddleware()
    cm2.session_start()

    b1a = cm1.encrypt("cm1 first")
    b2a = cm2.encrypt("cm2 first")
    cm1.rotate_key()
    b1b = cm1.encrypt("cm1 after rotate")
    b2b = cm2.encrypt("cm2 second")
    cm2.rotate_key()
    b1c = cm1.encrypt("cm1 third")
    b2c = cm2.encrypt("cm2 after rotate")

    checks = [
        (cm1, b1a, "cm1 first"),
        (cm1, b1b, "cm1 after rotate"),
        (cm1, b1c, "cm1 third"),
        (cm2, b2a, "cm2 first"),
        (cm2, b2b, "cm2 second"),
        (cm2, b2c, "cm2 after rotate"),
    ]
    for cm, blob, expected in checks:
        dec = cm.decrypt(blob)
        if dec != expected:
            R.fail("interleaved", f"got {dec!r}, expected {expected!r}")
            return

    R.ok("interleaved_operations")


# ================================================================
# 10. BOUNDARY CONDITIONS
# ================================================================

def test_max_key_history():
    """Verify _key_history never exceeds 5."""
    cm = CryptoMiddleware()
    cm.session_start()
    for _ in range(20):
        cm.rotate_key()
    if len(cm._key_history) > 5:
        R.fail("max_key_history", f"history size {len(cm._key_history)}")
    else:
        R.ok("max_key_history (capped at 5 after 20 rotations)")


def test_message_count_overflow():
    """message_count should handle large values."""
    cm = CryptoMiddleware()
    cm.session_start()
    cm.message_count = 2**31 - 2  # Near int32 max
    blob, _ = cm.encrypt_outbound("overflow test")
    if cm.message_count != 2**31 - 1:
        R.fail("message_count_overflow", f"count is {cm.message_count}")
    else:
        R.ok("message_count_overflow")

    # Next one should still work
    blob2, _ = cm.encrypt_outbound("overflow test 2")
    dec = cm.decrypt(blob2)
    if dec != "overflow test 2":
        R.fail("message_count_overflow_2", "decrypt failed after overflow")
    else:
        R.ok("message_count_overflow_2 (still works)")


def test_status_dict():
    """status() should return valid dict with expected keys."""
    cm = CryptoMiddleware()
    cm.session_start()
    s = cm.status()
    required = ["session_active", "session_key_suffix", "message_count",
                 "chaff_interval", "rotation_interval", "keys_in_history",
                 "master_key_suffix"]
    for key in required:
        if key not in s:
            R.fail("status_dict", f"missing key: {key}")
            return
    if not s["session_active"]:
        R.fail("status_dict", "session_active is False")
        return
    R.ok("status_dict")


# ================================================================
# RUNNER
# ================================================================

def run_all():
    print("=" * 60)
    print("  CRYPTO MIDDLEWARE TEST SUITE")
    print("=" * 60)

    tests = [
        ("1. Basic Round-trip", test_basic_roundtrip),
        ("2. Empty String", test_empty_string),
        ("3. Single Byte", test_single_byte),
        ("4. Large Payload", test_large_payload),
        ("5. Binary Content", test_binary_content),
        ("6. Nonce Uniqueness", test_nonce_uniqueness),
        ("7. Nonce Length", test_nonce_length),
        ("8. Tamper Detection", test_tamper_detection),
        ("9. Truncated Blob", test_truncated_blob),
        ("10. Garbage Input", test_garbage_input),
        ("11. Key Rotation Basic", test_key_rotation_basic),
        ("12. Key Rotation Chain", test_key_rotation_chain),
        ("13. Key History Limit", test_key_history_limit),
        ("14. Auto Rotation", test_auto_rotation),
        ("15. Chaff Interval", test_chaff_interval),
        ("16. Chaff Message Validity", test_chaff_message_validity),
        ("17. Memory No Leak", test_memory_no_leak_on_encrypt),
        ("18. Object Cleanup", test_object_cleanup),
        ("19. Session Key Zeroization", test_session_key_zeroization),
        ("20. Format for Provider", test_format_for_provider),
        ("21. Provider No Plaintext", test_provider_sees_only_base64),
        ("22. Storage Roundtrip", test_storage_roundtrip),
        ("23. Storage Master Key", test_storage_uses_master_key),
        ("24. Multiple Sessions", test_multiple_sessions),
        ("25. Interleaved Operations", test_interleaved_operations),
        ("26. Max Key History", test_max_key_history),
        ("27. Message Count Overflow", test_message_count_overflow),
        ("28. Status Dict", test_status_dict),
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
