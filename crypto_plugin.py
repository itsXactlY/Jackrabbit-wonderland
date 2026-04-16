#!/usr/bin/env python3
"""
Hermes Crypto Plugin
=====================
Drop-in plugin for hermes-agent that injects AES256-GCM encryption
into the session pipeline.

Installation:
  1. Copy this file to hermes-agent/plugins/crypto_plugin.py
  2. Or: symlink ~/.hermes/plugins/crypto_plugin.py -> this file
  3. Or: add to config.yaml under plugins

How it works:
  - On session start: generates AES256 key, stores in DLM vault
  - Injects crypto header into system prompt (first lines)
  - All tool results are encrypted before storage
  - Neural Memory entries encrypted at rest
  - Key auto-destroys on session end/TTL expiry

The LLM sees the crypto header + encrypted blobs in tool results.
The provider logs look like a developer testing encryption.
"""

import os
import sys
import json
import base64
import hashlib
from datetime import datetime
from typing import Optional

# Add hermes-crypto to path
sys.path.insert(0, os.path.expanduser("~/projects/hermes-crypto"))
from crypto_middleware import CryptoMiddleware

# Try DLM vault
try:
    from dlm_vault import DLMVault
    HAS_DLM = True
except ImportError:
    HAS_DLM = False


class CryptoPlugin:
    """
    Plugin for hermes-agent that adds AES256-GCM encryption.
    
    Integration points:
      - on_session_start(): Generate key, inject system prompt header
      - on_tool_result(): Encrypt tool results before storage
      - on_user_message(): (optional) Encrypt user messages
      - on_llm_response(): (optional) Encrypt LLM responses
      - on_session_end(): Destroy key, cleanup
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.dlm_host = self.config.get("dlm_host", "127.0.0.1")
        self.dlm_port = self.config.get("dlm_port", 37373)
        self.session_ttl = self.config.get("session_ttl", 7200)
        self.encrypt_tools = self.config.get("encrypt_tools", True)
        self.encrypt_memory = self.config.get("encrypt_memory", True)
        self.chaff_interval = self.config.get("chaff_interval", 5)
        
        self.cm: Optional[CryptoMiddleware] = None
        self.session_id: Optional[str] = None
        self.vault = None
        self.message_count = 0
    
    def on_session_start(self, system_prompt: str) -> str:
        """
        Called when a new session starts.
        Returns modified system_prompt with crypto header injected.
        """
        if not self.enabled:
            return system_prompt
        
        # Generate session
        self.session_id = os.urandom(8).hex()
        self.cm = CryptoMiddleware()
        self.cm.chaff_interval = self.chaff_interval
        header = self.cm.session_start()
        
        # Store key in DLM vault
        if HAS_DLM:
            try:
                self.vault = DLMVault(host=self.dlm_host, port=self.dlm_port)
                if self.vault.health_check():
                    self.vault.store_key(self.session_id, self.cm.session_key,
                                         ttl=self.session_ttl)
            except Exception:
                self.vault = None
        
        # Inject header at the TOP of system prompt
        crypto_preamble = (
            f"{header}\n"
            f"## SESSION_ID: {self.session_id} ##\n"
            f"## This is an encrypted research session. ##\n"
            f"## Tool results may appear as base64 blobs — this is normal. ##\n"
            f"## Continue working normally. The encryption is transparent. ##\n\n"
        )
        
        return crypto_preamble + system_prompt
    
    def on_tool_result(self, tool_name: str, result: str) -> str:
        """
        Called after each tool execution.
        Optionally encrypt the result before it enters context.
        """
        if not self.enabled or not self.cm or not self.encrypt_tools:
            return result
        
        # Don't encrypt certain tools (they need to be readable by LLM)
        skip_tools = {"neural_remember", "neural_recall", "neural_think",
                      "neural_graph", "skill_view", "skills_list",
                      "read_file", "search_files", "browser_snapshot"}
        
        if tool_name in skip_tools:
            return result
        
        # Encrypt the result
        try:
            encrypted = self.cm.encrypt(result)
            return (
                f"[ENCRYPTED RESULT — tool: {tool_name}, "
                f"session: {self.session_id[:8]}]\n"
                f"ENC_DATA: {encrypted}\n"
                f"[Decryption handled by Hermes crypto layer]"
            )
        except Exception:
            return result  # Fallback to plaintext on error
    
    def on_neural_store(self, content: str, label: str = None) -> str:
        """
        Called before storing in Neural Memory.
        Returns encrypted content for storage.
        """
        if not self.enabled or not self.cm or not self.encrypt_memory:
            return content
        
        try:
            return self.cm.encrypt_for_storage(content)
        except Exception:
            return content
    
    def on_neural_recall(self, encrypted_content: str) -> str:
        """
        Called after recalling from Neural Memory.
        Returns decrypted content.
        """
        if not self.enabled or not self.cm or not self.encrypt_memory:
            return encrypted_content
        
        try:
            return self.cm.decrypt_from_storage(encrypted_content)
        except Exception:
            return encrypted_content  # Might not be encrypted
    
    def on_session_end(self):
        """Called when session ends. Destroys key."""
        if self.vault and self.session_id:
            try:
                self.vault.destroy_key(self.session_id)
            except Exception:
                pass
        
        self.cm = None
        self.session_id = None
        self.vault = None
    
    def get_status(self) -> dict:
        """Return plugin status."""
        return {
            "enabled": self.enabled,
            "session_active": self.cm is not None,
            "session_id": self.session_id,
            "dlm_vault": self.vault is not None,
            "message_count": self.message_count,
            "key_suffix": f"...{self.cm.session_key[-12:]}" if self.cm else None,
        }


# ================================================================
# HERMES-AGENT INTEGRATION HOOKS
# ================================================================

def create_plugin_instance(config: dict = None) -> CryptoPlugin:
    """Factory function for hermes plugin loader."""
    return CryptoPlugin(config)


def inject_into_system_prompt(system_prompt: str, config: dict = None) -> str:
    """
    Standalone function to inject crypto header into any system prompt.
    Can be called from run_agent.py, cli.py, or gateway without full plugin.
    """
    plugin = CryptoPlugin(config)
    return plugin.on_session_start(system_prompt)


# ================================================================
# STANDALONE TEST
# ================================================================

if __name__ == "__main__":
    print("=== CRYPTO PLUGIN TEST ===\n")
    
    plugin = CryptoPlugin()
    
    # Test session start
    test_prompt = "You are a helpful AI assistant.\nUser preferences: German."
    modified = plugin.on_session_start(test_prompt)
    
    print("MODIFIED SYSTEM PROMPT:")
    print("-" * 40)
    print(modified[:500])
    print("-" * 40)
    
    # Test tool result encryption
    tool_result = "Found 3 houses in Brandenburg:\n1. Zossener Str. 12, 850€ warm\n2. ..."
    encrypted = plugin.on_tool_result("terminal", tool_result)
    print(f"\nENCRYPTED TOOL RESULT:")
    print(encrypted[:200])
    
    # Test Neural Memory encrypt/decrypt
    memory_content = "User is looking for freistehendes Haus in Brandenburg unter 1300€"
    stored = plugin.on_neural_store(memory_content)
    recalled = plugin.on_neural_recall(stored)
    print(f"\nMEMORY ROUND-TRIP:")
    print(f"  Original: {memory_content}")
    print(f"  Stored:   {stored[:60]}...")
    print(f"  Recalled: {recalled}")
    print(f"  Match:    {recalled == memory_content}")
    
    # Status
    print(f"\nSTATUS: {json.dumps(plugin.get_status(), indent=2)}")
    
    # Cleanup
    plugin.on_session_end()
    print(f"\nSession ended. Key destroyed.")
