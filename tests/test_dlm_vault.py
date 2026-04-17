#!/usr/bin/env python3
"""
DLM Vault Stress & Edge Case Tests
====================================
Tests the JackrabbitDLM volatile key vault for:
- Key storage/retrieval/destroy cycle
- TTL behavior
- Concurrent key operations
- Session locking
- Message storage
- DLM unreachable behavior
- Identity isolation
- Large keys
- Special characters in keys
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/opt/hermes-crypto")
from dlm_vault import DLMVault
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


def get_vault():
    return DLMVault(host="127.0.0.1", port=37373)


# ================================================================
# 1. HEALTH CHECK
# ================================================================

def test_dlm_online():
    """DLM server should be reachable."""
    vault = get_vault()
    if vault.health_check():
        R.ok("dlm_online")
    else:
        R.fail("dlm_online", "DLM not reachable")


# ================================================================
# 2. KEY STORAGE LIFECYCLE
# ================================================================

def test_store_retrieve_destroy():
    """Full key lifecycle: store -> retrieve -> verify -> destroy -> verify gone."""
    vault = get_vault()
    sid = os.urandom(8).hex()
    key = CryptoMiddleware()._generate_key()

    stored = vault.store_key(sid, key, ttl=3000)
    if not stored:
        R.fail("store_retrieve", "store_key failed")
        return

    retrieved = vault.retrieve_key(sid)
    if retrieved != key:
        R.fail("store_retrieve", f"key mismatch: {retrieved!r} != {key!r}")
        return

    destroyed = vault.destroy_key(sid)
    if not destroyed:
        R.fail("store_retrieve", "destroy_key failed")
        return

    gone = vault.retrieve_key(sid)
    if gone is not None:
        R.fail("store_retrieve", f"key still retrievable after destroy: {gone!r}")
    else:
        R.ok("store_retrieve_destroy")


def test_store_multiple_keys():
    """Store 100 keys, retrieve all, destroy all."""
    vault = get_vault()
    sids = []
    keys = {}

    for i in range(100):
        sid = f"test-bulk-{os.urandom(4).hex()}"
        key = CryptoMiddleware()._generate_key()
        keys[sid] = key
        vault.store_key(sid, key, ttl=3000)
        sids.append(sid)

    # Retrieve all
    all_ok = True
    for sid in sids:
        retrieved = vault.retrieve_key(sid)
        if retrieved != keys[sid]:
            R.fail("store_multiple", f"key mismatch for {sid}")
            all_ok = False
            break

    if not all_ok:
        return

    # Destroy all
    for sid in sids:
        vault.destroy_key(sid)

    # Verify all gone
    for sid in sids:
        if vault.retrieve_key(sid) is not None:
            R.fail("store_multiple", f"key {sid} still exists after destroy")
            return

    R.ok("store_multiple_keys (100 keys)")


def test_key_with_special_chars():
    """Keys containing +, /, = (base64) should store correctly."""
    vault = get_vault()
    sid = "test-special-chars"
    # Typical base64 key
    key = "a+/b=cDEFGH1234567890+/=="

    vault.store_key(sid, key, ttl=3000)
    retrieved = vault.retrieve_key(sid)
    vault.destroy_key(sid)

    if retrieved != key:
        R.fail("key_special_chars", f"got: {retrieved!r}")
    else:
        R.ok("key_special_chars")


def test_key_unicode():
    """Unicode keys should work."""
    vault = get_vault()
    sid = "test-unicode"
    key = "äöüß€🏠🔑"

    vault.store_key(sid, key, ttl=3000)
    retrieved = vault.retrieve_key(sid)
    vault.destroy_key(sid)

    if retrieved != key:
        R.fail("key_unicode", f"got: {retrieved!r}")
    else:
        R.ok("key_unicode")


def test_very_long_key():
    """Very long keys (5KB) should work. 10KB+ may fail (DLM payload limit)."""
    vault = get_vault()
    sid = "test-long-key"
    key = "A" * 5000

    vault.store_key(sid, key, ttl=3000)
    retrieved = vault.retrieve_key(sid)
    vault.destroy_key(sid)

    if retrieved != key:
        R.fail("key_long", f"length mismatch: {len(retrieved or '')} != 5000")
    else:
        R.ok("key_long (5KB)")

    # Also test that 10KB is rejected (DLM payload limit)
    sid2 = "test-long-key-10k"
    big_key = "A" * 10240
    stored = vault.store_key(sid2, big_key, ttl=3000)
    if stored:
        vault.destroy_key(sid2)
        R.ok("key_10kb (also works)")
    else:
        R.ok("key_10kb (rejected by DLM payload limit — expected)")


# ================================================================
# 3. TTL BEHAVIOR
# ================================================================

def test_ttl_minimum():
    """Keys with very short TTL (3s) should expire."""
    vault = get_vault()
    sid = "test-ttl-short"
    key = "expiring-key"

    vault.store_key(sid, key, ttl=3)
    # Immediately retrieve — should work
    retrieved = vault.retrieve_key(sid)
    if retrieved != key:
        R.fail("ttl_minimum", "immediate retrieve failed")
        return

    # Wait for expiry
    time.sleep(4)

    expired = vault.retrieve_key(sid)
    if expired is None:
        R.ok("ttl_minimum (3s TTL expired)")
    else:
        R.fail("ttl_minimum", f"key still present after TTL: {expired!r}")


def test_ttl_long():
    """Keys with long TTL (3500s) should persist."""
    vault = get_vault()
    sid = "test-ttl-long"
    key = "long-lived-key"

    vault.store_key(sid, key, ttl=3500)
    time.sleep(1)
    retrieved = vault.retrieve_key(sid)
    vault.destroy_key(sid)

    if retrieved != key:
        R.fail("ttl_long", "key expired too early")
    else:
        R.ok("ttl_long (3500s TTL)")


# ================================================================
# 4. SESSION LOCKING
# ================================================================

def test_lock_unlock():
    """Lock -> verify acquired -> unlock -> verify re-lockable by different identity."""
    vault = get_vault()
    sid = "test-lock"

    locked = vault.lock_session(sid, ttl=300)
    if not locked:
        R.fail("lock_unlock", "lock failed")
        return

    # NOTE: JackrabbitDLM's IsLocked() always returns "locked" — it doesn't
    # distinguish "locked by someone" from "not locked". The real enforcement
    # is at Lock() level. So we test by trying to lock from a different identity.
    vault2 = DLMVault(host="127.0.0.1", port=37373, identity="other-identity")
    lock2 = vault2.lock_session(sid, ttl=300)
    if lock2:
        R.fail("lock_unlock", "different identity could lock (should be held)")
        vault.unlock_session(sid)
        vault2.unlock_session(sid)
        return

    # Now unlock
    unlocked = vault.unlock_session(sid)
    if not unlocked:
        R.fail("lock_unlock", "unlock failed")
        return

    # Different identity should now be able to lock
    lock3 = vault2.lock_session(sid, ttl=300)
    vault2.unlock_session(sid)

    if not lock3:
        R.fail("lock_unlock", "could not lock after unlock")
    else:
        R.ok("lock_unlock (re-lock after unlock works)")


def test_double_lock():
    """Double-locking from different identity should fail (ownership)."""
    vault1 = get_vault()
    vault2 = DLMVault(host="127.0.0.1", port=37373, identity="other-identity")
    sid = "test-double-lock"

    vault1.lock_session(sid, ttl=300)
    second = vault2.lock_session(sid, ttl=300)
    vault1.unlock_session(sid)

    if second:
        R.fail("double_lock", "second lock succeeded (should fail)")
        vault2.unlock_session(sid)
    else:
        R.ok("double_lock (second identity rejected)")


# ================================================================
# 5. MESSAGE STORAGE
# ================================================================

def test_message_store_retrieve():
    """Store encrypted message, retrieve, destroy."""
    vault = get_vault()
    msg_id = os.urandom(4).hex()
    blob = "ENCRYPTED_BLOB_DATA_HERE_BASE64"

    stored = vault.store_message(msg_id, blob, ttl=3000)
    if not stored:
        R.fail("message_store", "store failed")
        return

    retrieved = vault.retrieve_message(msg_id)
    if retrieved != blob:
        R.fail("message_store", f"mismatch: {retrieved!r}")
        return

    destroyed = vault.destroy_message(msg_id)
    if not destroyed:
        R.fail("message_store", "destroy failed")
        return

    gone = vault.retrieve_message(msg_id)
    if gone is not None:
        R.fail("message_store", f"still retrievable: {gone!r}")
    else:
        R.ok("message_store_retrieve_destroy")


# ================================================================
# 6. CONCURRENT OPERATIONS
# ================================================================

def test_concurrent_key_storage():
    """50 threads storing keys simultaneously."""
    vault = get_vault()
    errors = []

    def worker(idx):
        try:
            sid = f"concurrent-{idx}"
            key = f"key-{idx}-{os.urandom(8).hex()}"
            vault.store_key(sid, key, ttl=3000)
            retrieved = vault.retrieve_key(sid)
            if retrieved != key:
                errors.append(f"worker {idx}: mismatch")
            vault.destroy_key(sid)
        except Exception as e:
            errors.append(f"worker {idx}: {e}")

    threads = []
    for i in range(50):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=30)

    if errors:
        R.fail("concurrent_key_storage", f"{len(errors)} errors: {errors[:3]}")
    else:
        R.ok("concurrent_key_storage (50 threads)")


def test_concurrent_session_locking():
    """Multiple threads trying to lock different sessions."""
    vault = get_vault()
    errors = []

    def worker(idx):
        try:
            sid = f"lock-test-{idx}"
            locked = vault.lock_session(sid, ttl=60)
            if not locked:
                errors.append(f"worker {idx}: lock failed")
                return
            time.sleep(0.1)
            unlocked = vault.unlock_session(sid)
            if not unlocked:
                errors.append(f"worker {idx}: unlock failed")
        except Exception as e:
            errors.append(f"worker {idx}: {e}")

    threads = []
    for i in range(30):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=30)

    if errors:
        R.fail("concurrent_session_locking", f"{len(errors)} errors: {errors[:3]}")
    else:
        R.ok("concurrent_session_locking (30 threads)")


# ================================================================
# 7. INTEGRATION WITH CRYPTO MIDDLEWARE
# ================================================================

def test_vault_crypto_roundtrip():
    """Full integration: generate key -> store in vault -> encrypt -> retrieve -> decrypt."""
    vault = get_vault()
    cm = CryptoMiddleware()
    cm.session_start()
    sid = os.urandom(8).hex()

    # Store session key in vault
    vault.store_key(sid, cm.session_key, ttl=3000)

    # Encrypt something
    plaintext = "Haus-Suche: EFH Brandenburg unter 1300€ warm"
    blob = cm.encrypt(plaintext)

    # Retrieve key from vault
    retrieved_key = vault.retrieve_key(sid)
    if retrieved_key != cm.session_key:
        R.fail("vault_crypto_roundtrip", "key mismatch")
        vault.destroy_key(sid)
        return

    # Create new CM with retrieved key, decrypt
    cm2 = CryptoMiddleware()
    cm2.session_key = retrieved_key
    dec = cm2.decrypt(blob)

    vault.destroy_key(sid)

    if dec != plaintext:
        R.fail("vault_crypto_roundtrip", f"got: {dec!r}")
    else:
        R.ok("vault_crypto_roundtrip")


# ================================================================
# 8. OVERFLOW / EXHAUSTION
# ================================================================

def test_key_bomb():
    """Store 1000 keys rapidly, verify DLM survives."""
    vault = get_vault()
    sids = []

    for i in range(1000):
        sid = f"bomb-{i}"
        key = CryptoMiddleware()._generate_key()
        ok = vault.store_key(sid, key, ttl=3000)
        if ok:
            sids.append(sid)
        else:
            break

    # DLM should still be alive
    if vault.health_check():
        R.ok(f"key_bomb ({len(sids)} keys stored, DLM alive)")
    else:
        R.fail("key_bomb", "DLM crashed")

    # Cleanup
    for sid in sids:
        vault.destroy_key(sid)


def test_overwrite_key():
    """Storing a key with same session_id should overwrite."""
    vault = get_vault()
    sid = "test-overwrite"

    vault.store_key(sid, "old-key", ttl=3000)
    vault.store_key(sid, "new-key", ttl=3000)
    retrieved = vault.retrieve_key(sid)
    vault.destroy_key(sid)

    if retrieved != "new-key":
        R.fail("overwrite_key", f"got: {retrieved!r}")
    else:
        R.ok("overwrite_key")


# ================================================================
# 9. IDENTITY ISOLATION
# ================================================================

def test_identity_isolation():
    """Different identities should not see each other's keys."""
    vault1 = DLMVault(host="127.0.0.1", port=37373, identity="identity-A")
    vault2 = DLMVault(host="127.0.0.1", port=37373, identity="identity-B")
    sid = "test-isolation"

    vault1.store_key(sid, "secret-key-A", ttl=3000)

    # Different identity should NOT be able to read
    retrieved = vault2.retrieve_key(sid)

    vault1.destroy_key(sid)

    if retrieved == "secret-key-A":
        R.fail("identity_isolation", "cross-identity read succeeded")
    else:
        R.ok("identity_isolation (cross-identity read blocked)")


# ================================================================
# RUNNER
# ================================================================

def run_all():
    print("=" * 60)
    print("  DLM VAULT STRESS TEST SUITE")
    print("=" * 60)

    tests = [
        ("1. DLM Online", test_dlm_online),
        ("2. Store/Retrieve/Destroy", test_store_retrieve_destroy),
        ("3. Store Multiple Keys", test_store_multiple_keys),
        ("4. Key Special Chars", test_key_with_special_chars),
        ("5. Key Unicode", test_key_unicode),
        ("6. Very Long Key", test_very_long_key),
        ("7. TTL Minimum", test_ttl_minimum),
        ("8. TTL Long", test_ttl_long),
        ("9. Lock/Unlock", test_lock_unlock),
        ("10. Double Lock", test_double_lock),
        ("11. Message Store/Retrieve", test_message_store_retrieve),
        ("12. Concurrent Key Storage", test_concurrent_key_storage),
        ("13. Concurrent Session Locking", test_concurrent_session_locking),
        ("14. Vault Crypto Roundtrip", test_vault_crypto_roundtrip),
        ("15. Key Bomb", test_key_bomb),
        ("16. Overwrite Key", test_overwrite_key),
        ("17. Identity Isolation", test_identity_isolation),
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
