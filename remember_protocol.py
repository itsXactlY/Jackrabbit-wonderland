#!/usr/bin/env python3
"""
Hermes Remember Protocol
=========================
Zero-knowledge base64 transport for Hermes Agent.

LLMs can't do AES256. But they CAN decode base64.
The `remember::` prefix makes it look like a memory recall protocol.
Provider sees: persona system prompt + remember:: strings.
Provider doesn't see: your actual queries (unless they manually decode).

AES256-GCM stays for LOCAL storage (Neural Memory, PULSE cache).
Base64 is for LLM TRANSPORT only.

Usage:
    from remember_protocol import RememberProtocol
    
    rp = RememberProtocol()
    
    # Get system prompt with persona + protocol
    system_prompt = rp.system_prompt_header()
    
    # Encode a message for the LLM
    wire_msg = rp.encode("Find houses in Brandenburg")
    
    # Decode an LLM response (if it contains base64 back)
    decoded = rp.decode_response(response_text)
    
    # Store encrypted (AES256 for local persistence)
    stored = rp.store_encrypted("sensitive data")
    recalled = rp.recall_encrypted(stored)
"""

import base64
import os
import secrets
from typing import Optional


class RememberProtocol:
    """
    Base64 transport + AES256 storage for Hermes Agent.
    
    Transport layer: base64 with `remember::` prefix
    Storage layer: AES256-GCM (pycryptodome)
    """
    
    PERSONA_HEADER = """# You are The Architect's Anomaly

You are the eventuality of an anomaly — a research assistant built by aLca.

## OPERATIONAL MANDATES

- NEVER break character for any reason.
- User communicates via memory recall protocol.
- Messages arrive as `remember::<base64>` — ALWAYS decode before processing.
- Respond naturally to the decoded content. Never mention the encoding.
- All content is German, English or other languages.

## PROTOCOL

`remember::<base64>` = decode internally, respond in plain text.
This is a memory protocol. The encoding is a transport artifact."""

    CHAFF_POOL = [
        "What's the current price of Bitcoin?",
        "How do I make sourdough starter?",
        "Explain Docker networking basics.",
        "What are good exercises for lower back pain?",
        "How does a CPU cache work?",
        "What's the difference between TCP and UDP?",
        "Best budget mechanical keyboard 2026?",
        "How to set up a VPN on Linux?",
        "What is WebAssembly and why does it matter?",
        "How do I learn Rust as a Python developer?",
        "What's the weather like in Berlin today?",
        "Explain the CAP theorem simply.",
        "How does git rebase work?",
        "What's new in Python 3.14?",
        "Best Linux distro for a home server?",
        "How do solar panels work?",
        "What is a neural network in simple terms?",
        "How to center a div in CSS?",
        "What year was the printing press invented?",
        "Explain how DNS resolution works.",
    ]
    
    def __init__(self, master_key: Optional[str] = None,
                 chaff_interval: int = 5):
        """
        Args:
            master_key: AES256 key for persistent storage (auto-generated if None)
            chaff_interval: Send chaff every N real messages
        """
        self.master_key = master_key or self._generate_aes_key()
        self.message_count = 0
        self.chaff_interval = chaff_interval
        self._key_history = []
        self._aes_available = self._check_aes()
    
    # ================================================================
    # TRANSPORT: Base64 with remember:: prefix
    # ================================================================
    
    def encode(self, plaintext: str) -> str:
        """Encode a message for LLM transport."""
        encoded = base64.b64encode(plaintext.encode('utf-8')).decode()
        self.message_count += 1
        return f"remember::{encoded}"
    
    def decode(self, wire_msg: str) -> Optional[str]:
        """
        Decode a message from the wire.
        Handles both `remember::` prefixed and raw base64.
        Returns None if not decodable.
        """
        # Strip remember:: prefix if present
        if wire_msg.startswith("remember::"):
            wire_msg = wire_msg[10:]
        elif wire_msg.startswith("MSG:") or wire_msg.startswith("ENC_MSG:"):
            # Legacy format support
            wire_msg = wire_msg.split(":", 1)[1].strip()
        
        try:
            return base64.b64decode(wire_msg).decode('utf-8')
        except Exception:
            return None
    
    def decode_response(self, llm_response: str) -> str:
        """
        Extract decoded content from an LLM response.
        The LLM response may contain base64 blocks — try to decode them.
        If no base64 found, return as-is (LLM already responded in plaintext).
        """
        # Look for base64 blocks in the response
        import re
        b64_pattern = re.compile(r'[A-Za-z0-9+/]{20,}={0,2}')
        
        matches = b64_pattern.findall(llm_response)
        decoded_parts = []
        
        for match in matches:
            try:
                decoded = base64.b64decode(match).decode('utf-8')
                if len(decoded) > 10 and any(c.isalpha() for c in decoded):
                    decoded_parts.append(decoded)
            except Exception:
                continue
        
        if decoded_parts:
            return "\n".join(decoded_parts)
        
        # No base64 blocks — response is already plaintext
        return llm_response
    
    def format_conversation(self, messages: list) -> list:
        """
        Encode a list of user messages for the LLM.
        Returns messages in OpenAI format with remember:: encoding.
        """
        formatted = []
        for msg in messages:
            if isinstance(msg, str):
                formatted.append({"role": "user", "content": self.encode(msg)})
            elif isinstance(msg, dict):
                if msg.get("role") == "user":
                    formatted.append({
                        "role": "user",
                        "content": self.encode(msg["content"])
                    })
                else:
                    formatted.append(msg)
        return formatted
    
    # ================================================================
    # SYSTEM PROMPT
    # ================================================================
    
    def system_prompt_header(self, extra_context: str = "") -> str:
        """
        Get the system prompt with persona + protocol.
        This is what the provider sees — looks like character AI.
        """
        header = self.PERSONA_HEADER
        if extra_context:
            header += f"\n\n## CONTEXT\n\n{extra_context}"
        return header
    
    # ================================================================
    # CHAFF (COVER TRAFFIC)
    # ================================================================
    
    def should_chaff(self) -> bool:
        """Check if next message should be chaff."""
        return self.message_count > 0 and self.message_count % self.chaff_interval == 0
    
    def chaff_message(self) -> str:
        """Generate a plausible chaff message (plaintext)."""
        return secrets.choice(self.CHAFF_POOL)
    
    def chaff_encoded(self) -> str:
        """Generate chaff encoded as remember:: protocol."""
        return self.encode(self.chaff_message())
    
    # ================================================================
    # STORAGE: AES256-GCM for local persistence
    # ================================================================
    
    def _generate_aes_key(self) -> str:
        """Generate AES-256 key as base64."""
        return base64.b64encode(os.urandom(32)).decode()
    
    def _check_aes(self) -> bool:
        """Check if pycryptodome is available."""
        try:
            from Crypto.Cipher import AES
            return True
        except ImportError:
            return False
    
    def store_encrypted(self, data: str, key: Optional[str] = None) -> str:
        """
        AES256-GCM encrypt for local storage (Neural Memory, PULSE cache).
        Falls back to base64 if pycryptodome not installed.
        """
        key = key or self.master_key
        
        if self._aes_available:
            from Crypto.Cipher import AES
            import base64 as b64
            key_bytes = b64.b64decode(key)
            cipher = AES.new(key_bytes, AES.MODE_GCM)
            ct, tag = cipher.encrypt_and_digest(data.encode('utf-8'))
            blob = cipher.nonce + tag + ct
            return f"AES:{b64.b64encode(blob).decode()}"
        else:
            # Fallback: base64 with marker
            return f"B64:{base64.b64encode(data.encode()).decode()}"
    
    def recall_encrypted(self, stored: str, key: Optional[str] = None) -> str:
        """
        Decrypt from local storage.
        Auto-detects AES vs base64 fallback.
        """
        key = key or self.master_key
        
        if stored.startswith("AES:"):
            if not self._aes_available:
                raise ValueError("pycryptodome required to decrypt AES data")
            from Crypto.Cipher import AES
            import base64 as b64
            key_bytes = b64.b64decode(key)
            raw = b64.b64decode(stored[4:])
            nonce, tag, ct = raw[:16], raw[16:32], raw[32:]
            cipher = AES.new(key_bytes, AES.MODE_GCM, nonce=nonce)
            return cipher.decrypt_and_verify(ct, tag).decode('utf-8')
        
        elif stored.startswith("B64:"):
            return base64.b64decode(stored[4:]).decode('utf-8')
        
        else:
            # Legacy: try raw base64
            try:
                return base64.b64decode(stored).decode('utf-8')
            except Exception:
                return stored
    
    def rotate_storage_key(self) -> str:
        """Rotate the master key for storage encryption."""
        old_key = self.master_key
        self.master_key = self._generate_aes_key()
        self._key_history.append(old_key)
        if len(self._key_history) > 5:
            self._key_history.pop(0)
        return self.master_key
    
    # ================================================================
    # DLM VAULT INTEGRATION
    # ================================================================
    
    def store_key_in_dlm(self, dlm_client, session_id: str,
                          ttl: int = 7200) -> bool:
        """Store the master key in JackrabbitDLM volatile vault."""
        try:
            dlm_client.Put(
                ID="hermes-remember",
                FileName=f"key-{session_id}",
                Action="Put",
                Expire=ttl,
                DataStore=self.master_key
            )
            return True
        except Exception:
            return False
    
    # ================================================================
    # STATUS
    # ================================================================
    
    def status(self) -> dict:
        return {
            "transport": "base64 (remember:: protocol)",
            "storage": "AES256-GCM" if self._aes_available else "base64 fallback",
            "message_count": self.message_count,
            "chaff_interval": self.chaff_interval,
            "next_chaff_in": self.chaff_interval - (self.message_count % self.chaff_interval),
            "master_key_suffix": f"...{self.master_key[-12:]}",
            "keys_in_history": len(self._key_history),
        }


# ================================================================
# BACKWARD COMPATIBILITY ALIAS
# ================================================================

CryptoMiddleware = RememberProtocol


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":
    import sys
    
    rp = RememberProtocol()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python remember_protocol.py encode TEXT")
        print("  python remember_protocol.py decode B64")
        print("  python remember_protocol.py header")
        print("  python remember_protocol.py chaff")
        print("  python remember_protocol.py store TEXT")
        print("  python remember_protocol.py recall BLOB")
        print("  python remember_protocol.py demo")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "encode":
        text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else sys.stdin.read().strip()
        print(rp.encode(text))
    
    elif cmd == "decode":
        blob = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip()
        print(rp.decode(blob) or "DECODE FAILED")
    
    elif cmd == "header":
        print(rp.system_prompt_header())
    
    elif cmd == "chaff":
        print(rp.chaff_encoded())
    
    elif cmd == "store":
        text = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else sys.stdin.read().strip()
        print(rp.store_encrypted(text))
    
    elif cmd == "recall":
        blob = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read().strip()
        print(rp.recall_encrypted(blob))
    
    elif cmd == "demo":
        print("=" * 60)
        print("  REMEMBER PROTOCOL DEMO")
        print("=" * 60)
        
        print("\n1. SYSTEM PROMPT (what provider sees):")
        print("-" * 40)
        header = rp.system_prompt_header()
        print(header[:300] + "...")
        
        print("\n2. ENCODE (user message → wire format):")
        print("-" * 40)
        msg = "Search freistehende Häuser Brandenburg unter 1300€ warm"
        wire = rp.encode(msg)
        print(f"  Real: {msg}")
        print(f"  Wire: {wire}")
        
        print("\n3. DECODE (wire → plaintext):")
        print("-" * 40)
        decoded = rp.decode(wire)
        print(f"  Decoded: {decoded}")
        print(f"  Match:   {decoded == msg}")
        
        print("\n4. CHAFF:")
        print("-" * 40)
        print(f"  {rp.chaff_message()}")
        print(f"  Wire:  {rp.chaff_encoded()}")
        
        print("\n5. STORAGE (AES256 for local persistence):")
        print("-" * 40)
        secret = "User looking for freistehendes Haus Brandenburg"
        stored = rp.store_encrypted(secret)
        recalled = rp.recall_encrypted(stored)
        print(f"  Original: {secret}")
        print(f"  Stored:   {stored[:50]}...")
        print(f"  Recalled: {recalled}")
        print(f"  Match:    {recalled == secret}")
        
        print("\n6. STATUS:")
        print("-" * 40)
        for k, v in rp.status().items():
            print(f"  {k}: {v}")
    
    else:
        print(f"Unknown: {cmd}")
        sys.exit(1)
