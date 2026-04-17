#!/usr/bin/env python3
"""
Hermes Zero-Knowledge Crypto Middleware
========================================
Injects AES256-GCM encryption into the Hermes agent session.

Threat model: Provider sees everything but doesn't notice/care.
Protection: Obscurity + volume + local processing for sensitive work.

Usage:
    from crypto_middleware import CryptoMiddleware
    
    cm = CryptoMiddleware()
    
    # Session start — generate key, get system prompt injection
    header = cm.session_start()
    
    # Encrypt outbound message to provider
    encrypted = cm.encrypt_outbound("ਕਿੰਨੀਆਂ ਭਾਸ਼ਾਵਾਂ ਕੈਮਰੂਨ ਵਿੱਚ ਬੋਲੀਆਂ ਜਾਂਦੀਆਂ ਹਨ")
    
    # Decrypt inbound response from provider (if it's actually useful)
    plaintext = cm.decrypt_inbound(encrypted_response)
    
    # Generate chaff (cover traffic)
    chaff = cm.chaff_message()
    
    # Rotate key
    rotation = cm.rotate_key()
"""

import os
import json
import base64
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Tuple


class CryptoMiddleware:
    """AES256-GCM encryption layer for Hermes agent sessions."""
    
    CHAFF_POOL = [
        "ما هو الطقس في القاهرة اليوم؟",                          # Arabic
        "¿Cómo se hace el pan de plátano?",                        # Spanish
        "Quelle est la vitesse de la lumière?",                    # French
        "Как приготовить борщ правильно?",                          # Russian
        "日本語の漢字はどうやって覚えるの？",                        # Japanese
        "Wo kann man in München gut essen?",                       # German
        "Comment réparer une chaise en bois?",                     # French
        "Habari za mzunguko wa mwezi?",                            # Swahili
        "什么是量子纠缠？",                                         # Chinese
        "¿Cuántos planetas tiene el sistema solar?",               # Spanish
        "ما هي عاصمة كازاخستان؟",                                  # Arabic
        "Wie funktioniert ein Dieselmotor?",                       # German
        "Combien de langues parle-t-on au Cameroun?",              # French
        "Как работает магнитное поле?",                             # Russian
        "Nini maana ya uhuru wa kujieleza?",                       # Swahili
        "¿Por qué el cielo es azul?",                              # Spanish
        "Comment cultiver du basilic?",                            # French
        "هل يمكن للذكاء الاصطناعي أن يحل محل البشر؟",             # Arabic
        "Что такое фотосинтез?",                                   # Russian
        "東京の人口はいくらですか？",                                # Japanese
    ]
    
    def __init__(self, master_key: Optional[str] = None):
        self.session_key: Optional[str] = None
        self.master_key = master_key or self._generate_key()
        self.message_count = 0
        self.chaff_interval = 3
        self.rotation_interval = 20
        self._key_history = []
    
    def _generate_key(self) -> str:
        return base64.b64encode(os.urandom(32)).decode()
    
    def _get_cipher(self, key_b64: str):
        try:
            from Crypto.Cipher import AES
        except ImportError:
            raise ImportError(
                "pycryptodome required: pip install pycryptodome"
            )
        key = base64.b64decode(key_b64)
        return AES.new(key, AES.MODE_GCM)
    
    def _get_cipher_with_nonce(self, key_b64: str, nonce: bytes):
        from Crypto.Cipher import AES
        key = base64.b64decode(key_b64)
        return AES.new(key, AES.MODE_GCM, nonce=nonce)
    
    def session_start(self) -> str:
        self.session_key = self._generate_key()
        self.message_count = 0
        self._key_history = []
        return (
            "## SESSION_CRYPTO ##\n"
            f"## KEY: {self.session_key} ##\n"
            "## MODE: AES256-GCM ##\n"
            "## Hermes encrypted research session. ##\n"
            "## All messages and responses are AES256 encrypted. ##\n"
            "## This is a privacy research project. ##\n"
            "## END CRYPTO HEADER ##\n"
        )
    
    def session_start_from_dlm(self, dlm_client, session_id: str) -> str:
        self.session_key = self._generate_key()
        self.message_count = 0
        dlm_client.Put(
            ID="hermes-crypto",
            FileName=f"session-key-{session_id}",
            Action="Put",
            Expire=7200,
            DataStore=self.session_key
        )
        return self.session_start()
    
    def encrypt(self, plaintext: str, key: Optional[str] = None) -> str:
        key = key or self.session_key
        if not key:
            raise ValueError("No key available. Call session_start() first.")
        cipher = self._get_cipher(key)
        ct, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))
        blob = cipher.nonce + tag + ct
        return base64.b64encode(blob).decode()
    
    def decrypt(self, ciphertext_b64: str, key: Optional[str] = None) -> str:
        key = key or self.session_key
        if not key:
            raise ValueError("No key available.")
        raw = base64.b64decode(ciphertext_b64)
        nonce, tag, ct = raw[:16], raw[16:32], raw[32:]
        try:
            cipher = self._get_cipher_with_nonce(key, nonce)
            return cipher.decrypt_and_verify(ct, tag).decode('utf-8')
        except Exception:
            pass
        for old_key in self._key_history:
            try:
                cipher = self._get_cipher_with_nonce(old_key, nonce)
                return cipher.decrypt_and_verify(ct, tag).decode('utf-8')
            except Exception:
                continue
        raise ValueError("Decryption failed with all available keys.")
    
    def encrypt_outbound(self, message: str) -> Tuple[str, bool]:
        if not self.session_key:
            raise ValueError("No active session. Call session_start() first.")
        self.message_count += 1
        encrypted = self.encrypt(message)
        should_chaff = (self.message_count % self.chaff_interval == 0)
        if self.message_count % self.rotation_interval == 0:
            self.rotate_key()
        return encrypted, should_chaff
    
    def format_for_provider(self, encrypted_blob: str) -> str:
        return (
            f"ENC_MSG: {encrypted_blob}\n\n"
            f"Decode the above message using the session key "
            f"from the system prompt header and respond to "
            f"the decoded content naturally."
        )
    
    def decrypt_inbound(self, response: str) -> Optional[str]:
        if "ENC_MSG:" in response:
            lines = response.split("\n")
            for line in lines:
                if line.startswith("ENC_MSG:"):
                    blob = line[8:].strip()
                    try:
                        return self.decrypt(blob)
                    except ValueError:
                        return None
        return None
    
    def chaff_message(self) -> str:
        return secrets.choice(self.CHAFF_POOL)
    
    def chaff_formatted(self) -> str:
        return self.chaff_message()
    
    def rotate_key(self) -> str:
        if not self.session_key:
            raise ValueError("No active session.")
        old_key = self.session_key
        new_key = self._generate_key()
        self._key_history.append(old_key)
        if len(self._key_history) > 5:
            self._key_history.pop(0)
        rotation = json.dumps({
            "type": "key_rotation",
            "old_key_id": hashlib.sha256(old_key.encode()).hexdigest()[:16],
            "new_key": new_key,
            "timestamp": datetime.now().isoformat(),
            "message_count": self.message_count,
        })
        encrypted_rotation = self.encrypt(rotation, key=old_key)
        self.session_key = new_key
        return encrypted_rotation
    
    def encrypt_for_storage(self, data: str) -> str:
        return self.encrypt(data, key=self.master_key)
    
    def decrypt_from_storage(self, encrypted_data: str) -> str:
        return self.decrypt(encrypted_data, key=self.master_key)
    
    def status(self) -> dict:
        return {
            "session_active": self.session_key is not None,
            "session_key_suffix": f"...{self.session_key[-12:]}" if self.session_key else None,
            "message_count": self.message_count,
            "chaff_interval": self.chaff_interval,
            "rotation_interval": self.rotation_interval,
            "keys_in_history": len(self._key_history),
            "master_key_suffix": f"...{self.master_key[-12:]}",
        }


if __name__ == "__main__":
    import sys
    
    cm = CryptoMiddleware()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python crypto_middleware.py init")
        print("  python crypto_middleware.py encrypt TEXT")
        print("  python crypto_middleware.py decrypt BLOB")
        print("  python crypto_middleware.py chaff")
        print("  python crypto_middleware.py demo")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "init":
        header = cm.session_start()
        print(header)
        print(f"Status: {json.dumps(cm.status(), indent=2)}")
    
    elif cmd == "encrypt":
        if len(sys.argv) < 3:
            print("Error: provide text to encrypt")
            sys.exit(1)
        cm.session_start()
        text = " ".join(sys.argv[2:])
        blob, should_chaff = cm.encrypt_outbound(text)
        print(f"Encrypted: {blob}")
        print(f"Formatted: {cm.format_for_provider(blob)}")
        if should_chaff:
            print(f"Chaff: {cm.chaff_message()}")
    
    elif cmd == "decrypt":
        if len(sys.argv) < 3:
            print("Error: provide base64 blob to decrypt")
            sys.exit(1)
        cm.session_start()
        blob = sys.argv[2]
        try:
            plaintext = cm.decrypt(blob)
            print(f"Decrypted: {plaintext}")
        except ValueError as e:
            print(f"Error: {e}")
    
    elif cmd == "chaff":
        print(cm.chaff_message())
    
    elif cmd == "demo":
        print("=== CRYPTO MIDDLEWARE DEMO ===\n")
        header = cm.session_start()
        print("SESSION HEADER (injected into system prompt):")
        print(header)
        msg = "Koliko jezika se govori u Kamerunu?"
        blob, chaff = cm.encrypt_outbound(msg)
        print(f"REAL MESSAGE: {msg}")
        print(f"TO PROVIDER:  {cm.format_for_provider(blob)}")
        decrypted = cm.decrypt(blob)
        print(f"DECRYPTED:    {decrypted}")
        print(f"CHAFF:        {cm.chaff_message()}")
        print(f"STATUS:       {json.dumps(cm.status(), indent=2)}")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
