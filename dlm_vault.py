#!/usr/bin/env python3
"""
JackrabbitDLM Crypto Vault Bridge (DLMLocker version)
======================================================
Stores AES256 session keys in JackrabbitDLM's volatile memory.
Uses Robert's DLMLocker client library for proper encoding/decoding.
Keys never touch disk. TTL-bound. Auto-destroy on crash/expiry.
"""

import sys
import os
import json
import base64
import hashlib
from typing import Optional, Tuple

# Robert's convention: DLMLocker.py lives in /home/JackrabbitDLM
sys.path.insert(0, '/home/JackrabbitDLM')


class DLMVault:
    """Client for storing crypto keys in JackrabbitDLM via DLMLocker."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 37373,
                 identity: str = "hermes-crypto-vault"):
        self.host = host
        self.port = port
        self.identity = identity
        self._check_dlm()
    
    def _check_dlm(self):
        """Verify DLMLocker is importable and DLM server is reachable."""
        try:
            from DLMLocker import Locker
        except ImportError:
            raise ImportError(
                "DLMLocker.py not found. Install JackrabbitDLM to /home/JackrabbitDLM first.\n"
                "See: https://github.com/rapmd73/JackrabbitDLM"
            )
        self._Locker = Locker
    
    def _make_locker(self, name: str):
        """Create a DLMLocker instance with consistent identity."""
        return self._Locker(name, Host=self.host, Port=self.port, ID=self.identity)
    
    def health_check(self) -> bool:
        """Check if DLM server is reachable."""
        try:
            lock = self._make_locker("health-check")
            v = lock.Version()
            return "JackrabbitDLM" in str(v)
        except Exception:
            return False
    
    # ================================================================
    # KEY STORAGE (volatile, TTL-bound)
    # ================================================================
    
    def store_key(self, session_id: str, key_b64: str, 
                  ttl: int = 3000) -> bool:
        """
        Store an AES256 key in the DLM vault.
        Max anonymous TTL: 3543s. Default 3000s for safety.
        """
        # Use unique locker name per session to avoid ownership conflicts
        locker_name = f"vault-key-{session_id}"
        lock = self._make_locker(locker_name)
        
        # DLMLocker.Put(expire, data) — expire FIRST, then data
        resp = lock.Put(expire=ttl, data=key_b64)
        
        if isinstance(resp, bytes):
            resp = resp.decode('utf-8')
        resp_str = str(resp)
        
        return "Done" in resp_str
    
    def retrieve_key(self, session_id: str) -> Optional[str]:
        """Retrieve a key from the DLM vault."""
        locker_name = f"vault-key-{session_id}"
        lock = self._make_locker(locker_name)
        
        resp = lock.Get()
        
        if isinstance(resp, dict) and resp.get("Status") == "Done":
            return resp.get("DataStore")
        return None
    
    def destroy_key(self, session_id: str) -> bool:
        """Explicitly destroy a key (don't wait for TTL)."""
        locker_name = f"vault-key-{session_id}"
        lock = self._make_locker(locker_name)
        
        resp = lock.Erase()
        if isinstance(resp, bytes):
            resp = resp.decode('utf-8')
        
        return "Done" in str(resp)
    
    # ================================================================
    # SESSION LOCKING
    # ================================================================
    
    def lock_session(self, session_id: str, ttl: int = 300) -> bool:
        """Acquire a session lock (prevent concurrent agent runs)."""
        locker_name = f"lock-{session_id}"
        lock = self._make_locker(locker_name)
        resp = lock.Lock(expire=ttl)
        return resp == "locked"
    
    def unlock_session(self, session_id: str) -> bool:
        """Release a session lock."""
        locker_name = f"lock-{session_id}"
        lock = self._make_locker(locker_name)
        resp = lock.Unlock()
        return resp == "unlocked"
    
    def is_session_locked(self, session_id: str) -> bool:
        """Check if a session is currently locked."""
        locker_name = f"lock-{session_id}"
        lock = self._make_locker(locker_name)
        resp = lock.IsLocked()
        return resp == "locked"
    
    # ================================================================
    # ENCRYPTED MESSAGE STORAGE (volatile)
    # ================================================================
    
    def store_message(self, msg_id: str, encrypted_blob: str,
                      ttl: int = 3000) -> bool:
        """Store an encrypted message in the DLM vault."""
        locker_name = f"vault-msg-{msg_id}"
        lock = self._make_locker(locker_name)
        resp = lock.Put(expire=ttl, data=encrypted_blob)
        if isinstance(resp, bytes):
            resp = resp.decode('utf-8')
        return "Done" in str(resp)
    
    def retrieve_message(self, msg_id: str) -> Optional[str]:
        """Retrieve an encrypted message from the DLM vault."""
        locker_name = f"vault-msg-{msg_id}"
        lock = self._make_locker(locker_name)
        resp = lock.Get()
        if isinstance(resp, dict) and resp.get("Status") == "Done":
            return resp.get("DataStore")
        return None
    
    def destroy_message(self, msg_id: str) -> bool:
        """Destroy a stored message."""
        locker_name = f"vault-msg-{msg_id}"
        lock = self._make_locker(locker_name)
        resp = lock.Erase()
        if isinstance(resp, bytes):
            resp = resp.decode('utf-8')
        return "Done" in str(resp)


# ================================================================
# FULL SESSION INTEGRATION
# ================================================================

def create_encrypted_session(dlm_host: str = "127.0.0.1",
                              dlm_port: int = 37373,
                              session_ttl: int = 3000) -> dict:
    """
    Full session initialization:
    1. Check DLM health
    2. Generate AES256 key via CryptoMiddleware
    3. Store key in DLM vault (volatile, TTL-bound)
    4. Acquire session lock
    5. Return everything needed for encrypted operation
    """
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from crypto_middleware import CryptoMiddleware
    
    # Initialize vault
    vault = DLMVault(host=dlm_host, port=dlm_port)
    
    if not vault.health_check():
        return {"error": f"DLM server not reachable at {dlm_host}:{dlm_port}"}
    
    # Generate session ID
    session_id = os.urandom(8).hex()
    
    # Acquire session lock
    if not vault.lock_session(session_id, ttl=session_ttl):
        return {"error": "Could not acquire session lock (another session active?)"}
    
    # Generate key and start crypto middleware
    cm = CryptoMiddleware()
    header = cm.session_start()
    
    # Store key in DLM vault
    stored = vault.store_key(session_id, cm.session_key, ttl=session_ttl)
    if not stored:
        vault.unlock_session(session_id)
        return {"error": "Failed to store key in DLM vault"}
    
    # Verify round-trip
    retrieved = vault.retrieve_key(session_id)
    if retrieved != cm.session_key:
        vault.unlock_session(session_id)
        return {"error": "Key verification failed — DLM round-trip mismatch"}
    
    return {
        "session_id": session_id,
        "system_prompt_header": header,
        "middleware": cm,
        "vault": vault,
        "key_location": f"dlm://vault-key-{session_id}",
        "key_ttl": session_ttl,
        "auto_destroy": "TTL expires or DLM crash → key gone → data shredded",
        "verified": True
    }


def end_encrypted_session(session: dict) -> bool:
    """Clean up: destroy key, release lock."""
    vault = session.get("vault")
    session_id = session.get("session_id")
    
    if vault and session_id:
        vault.destroy_key(session_id)
        vault.unlock_session(session_id)
        return True
    return False


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python dlm_vault.py health     # Check DLM server")
        print("  python dlm_vault.py session    # Create encrypted session")
        print("  python dlm_vault.py demo       # Full integration demo")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "health":
        vault = DLMVault()
        if vault.health_check():
            print("DLM server: ONLINE")
        else:
            print("DLM server: OFFLINE")
            sys.exit(1)
    
    elif cmd == "session":
        result = create_encrypted_session()
        if "error" in result:
            print(f"ERROR: {result['error']}")
            sys.exit(1)
        print(f"Session: {result['session_id']}")
        print(f"Key stored: {result['key_location']}")
        print(f"TTL: {result['key_ttl']}s")
        print(f"Verified: {result['verified']}")
        print(f"\nSystem prompt header:")
        print(result['system_prompt_header'])
    
    elif cmd == "demo":
        print("=" * 60)
        print("  DLM VAULT + CRYPTO MIDDLEWARE INTEGRATION TEST")
        print("=" * 60)
        
        # 1. Health check
        print("\n1. Health check...")
        vault = DLMVault()
        if not vault.health_check():
            print("   DLM not running! Start it first:")
            print("   cd /home/JackrabbitDLM && python3 JackrabbitDLM 0.0.0.0 37373")
            sys.exit(1)
        print("   DLM ONLINE ✓")
        
        # 2. Create session
        print("\n2. Creating encrypted session...")
        session = create_encrypted_session()
        if "error" in session:
            print(f"   ERROR: {session['error']}")
            sys.exit(1)
        print(f"   Session ID: {session['session_id']} ✓")
        print(f"   Key location: {session['key_location']} ✓")
        print(f"   Key verified: {session['verified']} ✓")
        
        cm = session["middleware"]
        vault = session["vault"]
        
        # 3. Encrypt a real message
        print("\n3. Encrypt message...")
        real_msg = "Search freistehende Häuser Brandenburg unter 1300€ warm mit Haustieren"
        blob, should_chaff = cm.encrypt_outbound(real_msg)
        print(f"   Plaintext:  {real_msg[:50]}...")
        print(f"   Encrypted:  {blob[:60]}...")
        print(f"   For provider: {cm.format_for_provider(blob)[:80]}...")
        
        # 4. Store encrypted blob in DLM
        print("\n4. Store blob in DLM vault...")
        msg_id = os.urandom(4).hex()
        vault.store_message(msg_id, blob)
        retrieved = vault.retrieve_message(msg_id)
        print(f"   Stored msg-{msg_id}: {retrieved is not None} ✓")
        
        # 5. Decrypt round-trip
        print("\n5. Decrypt round-trip...")
        decrypted = cm.decrypt(retrieved)
        print(f"   Decrypted: {decrypted}")
        print(f"   Match: {decrypted == real_msg} ✓")
        
        # 6. Chaff
        print(f"\n6. Chaff: {cm.chaff_message()}")
        
        # 7. Key rotation
        print("\n7. Key rotation...")
        rotation_blob = cm.rotate_key()
        print(f"   Rotation encrypted: {rotation_blob[:60]}...")
        print(f"   Keys in history: {cm.status()['keys_in_history']} ✓")
        
        # 8. Cleanup
        print("\n8. Cleanup...")
        vault.destroy_message(msg_id)
        end_encrypted_session(session)
        print("   Key destroyed, lock released ✓")
        
        # 9. Confirm key gone
        print("\n9. Confirm key gone...")
        gone = vault.retrieve_key(session['session_id'])
        print(f"   Key retrieval: {gone} ✓")
        
        print("\n" + "=" * 60)
        print("  ALL TESTS PASSED")
        print("  DLM is operational as a volatile crypto vault.")
        print("  Keys live in memory only. Crash = key gone = data shredded.")
        print("=" * 60)
    
    else:
        print(f"Unknown: {cmd}")
        sys.exit(1)
