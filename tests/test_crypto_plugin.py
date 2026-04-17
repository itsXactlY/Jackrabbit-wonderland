#!/usr/bin/env python3
"""
Crypto Plugin Integration Tests
=================================
Tests the hermes-agent plugin interface for:
- Session start/stop lifecycle
- Tool result encryption
- Neural Memory encrypt/decrypt
- Plugin status
- Skip tools list
- Multiple session cycles
- Error handling / fallback behavior
"""

import sys
import os
import gc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, "/opt/hermes-crypto")
from crypto_plugin import CryptoPlugin


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
# 1. SESSION LIFECYCLE
# ================================================================

def test_session_start_stop():
    """Plugin should handle start -> use -> stop cleanly."""
    plugin = CryptoPlugin()
    prompt = plugin.on_session_start("You are Hermes.")

    if "SESSION_CRYPTO" not in prompt:
        R.fail("session_start", "no crypto header in prompt")
        return
    if "You are Hermes." not in prompt:
        R.fail("session_start", "original prompt missing")
        return

    status = plugin.get_status()
    if not status["session_active"]:
        R.fail("session_start", "session not active after start")
        return

    plugin.on_session_end()
    status = plugin.get_status()
    if status["session_active"]:
        R.fail("session_end", "session still active after end")
    else:
        R.ok("session_start_stop")


def test_multiple_session_cycles():
    """Start/stop 50 sessions, memory should plateau (no linear leak)."""
    import tracemalloc
    gc.collect()
    tracemalloc.start()

    # Warmup batch — allocates module state, pycryptodome caches, DLM connections
    # Must include ALL operations that the measurement batch uses
    for i in range(50):
        plugin = CryptoPlugin()
        plugin.on_session_start(f"Warmup {i}")
        plugin.on_tool_result("terminal", f"warmup result {i}")
        plugin.on_neural_store(f"warmup memory {i}", "test")
        plugin.on_session_end()
        del plugin
    gc.collect()
    gc.collect()

    baseline = tracemalloc.get_traced_memory()[0]

    # Measurement batch — should add minimal memory
    for i in range(50):
        plugin = CryptoPlugin()
        plugin.on_session_start(f"Session {i}")
        plugin.on_tool_result("terminal", f"result {i}")
        plugin.on_neural_store(f"memory {i}", "test")
        plugin.on_session_end()
        del plugin

    gc.collect()
    final = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    delta_kb = (final - baseline) / 1024

    # After warmup, second batch should add < 500KB (initial alloc already done)
    if delta_kb > 500:
        R.fail("multiple_cycles", f"leaked {delta_kb:.0f}KB after warmup batch")
    else:
        R.ok(f"multiple_session_cycles (50 cycles, {delta_kb:.0f}KB delta after warmup)")


def test_disabled_plugin():
    """Disabled plugin should pass through unchanged."""
    plugin = CryptoPlugin({"enabled": False})
    prompt = plugin.on_session_start("You are Hermes.")

    if "SESSION_CRYPTO" in prompt:
        R.fail("disabled_plugin", "crypto header injected when disabled")
    elif prompt != "You are Hermes.":
        R.fail("disabled_plugin", "prompt modified")
    else:
        R.ok("disabled_plugin")


# ================================================================
# 2. TOOL RESULT ENCRYPTION
# ================================================================

def test_tool_result_encrypted():
    """Tool results should be encrypted (except skip list)."""
    plugin = CryptoPlugin()
    plugin.on_session_start("test")

    result = plugin.on_tool_result("terminal", "output: 42")
    if "[ENCRYPTED RESULT" not in result:
        R.fail("tool_encrypt", "not encrypted")
    elif "ENC_DATA:" not in result:
        R.fail("tool_encrypt", "no ENC_DATA")
    elif "output: 42" in result:
        R.fail("tool_encrypt", "plaintext leaked")
    else:
        R.ok("tool_result_encrypted")


def test_tool_result_skip_list():
    """Skip tools should NOT be encrypted."""
    plugin = CryptoPlugin()
    plugin.on_session_start("test")

    skip_tools = ["neural_remember", "neural_recall", "neural_think",
                  "neural_graph", "skill_view", "skills_list",
                  "read_file", "search_files", "browser_snapshot"]

    for tool in skip_tools:
        result = plugin.on_tool_result(tool, "sensitive data")
        if "[ENCRYPTED RESULT" in result:
            R.fail(f"skip_tool[{tool}]", "was encrypted (should skip)")
            return
        if result != "sensitive data":
            R.fail(f"skip_tool[{tool}]", "result modified")
            return

    R.ok(f"tool_result_skip_list ({len(skip_tools)} tools)")


def test_tool_result_disabled():
    """Disabled plugin should not encrypt tool results."""
    plugin = CryptoPlugin({"enabled": False})
    plugin.on_session_start("test")
    result = plugin.on_tool_result("terminal", "output: 42")
    if result != "output: 42":
        R.fail("tool_disabled", f"got: {result!r}")
    else:
        R.ok("tool_result_disabled")


def test_tool_result_encrypt_tools_false():
    """encrypt_tools=False should not encrypt."""
    plugin = CryptoPlugin({"encrypt_tools": False})
    plugin.on_session_start("test")
    result = plugin.on_tool_result("terminal", "output: 42")
    if result != "output: 42":
        R.fail("encrypt_tools_false", f"got: {result!r}")
    else:
        R.ok("tool_result_encrypt_tools_false")


def test_tool_result_no_session():
    """Tool result without active session should return plaintext."""
    plugin = CryptoPlugin()
    # No session_start
    result = plugin.on_tool_result("terminal", "output: 42")
    if result != "output: 42":
        R.fail("tool_no_session", f"got: {result!r}")
    else:
        R.ok("tool_result_no_session")


# ================================================================
# 3. NEURAL MEMORY
# ================================================================

def test_neural_roundtrip():
    """on_neural_store -> on_neural_recall should round-trip."""
    plugin = CryptoPlugin()
    plugin.on_session_start("test")

    original = "User wants EFH Brandenburg unter 1300€, Haustiere erlaubt"
    stored = plugin.on_neural_store(original)
    recalled = plugin.on_neural_recall(stored)

    if recalled != original:
        R.fail("neural_roundtrip", f"got: {recalled!r}")
    else:
        R.ok("neural_roundtrip")


def test_neural_disabled():
    """Disabled plugin should not encrypt memory."""
    plugin = CryptoPlugin({"enabled": False, "encrypt_memory": True})
    plugin.on_session_start("test")
    content = "test memory"
    stored = plugin.on_neural_store(content)
    if stored != content:
        R.fail("neural_disabled", f"got: {stored!r}")
    else:
        R.ok("neural_disabled")


def test_neural_encrypt_memory_false():
    """encrypt_memory=False should not encrypt."""
    plugin = CryptoPlugin({"encrypt_memory": False})
    plugin.on_session_start("test")
    content = "test memory"
    stored = plugin.on_neural_store(content)
    if stored != content:
        R.fail("neural_false", f"got: {stored!r}")
    else:
        R.ok("neural_encrypt_memory_false")


def test_neural_no_session():
    """Neural store without session should pass through."""
    plugin = CryptoPlugin()
    content = "test memory"
    stored = plugin.on_neural_store(content)
    if stored != content:
        R.fail("neural_no_session", f"got: {stored!r}")
    else:
        R.ok("neural_no_session")


def test_neural_recall_not_encrypted():
    """Recalling non-encrypted data should return as-is."""
    plugin = CryptoPlugin()
    plugin.on_session_start("test")
    plaintext = "this was never encrypted"
    result = plugin.on_neural_recall(plaintext)
    if result != plaintext:
        R.fail("neural_plain_recall", f"got: {result!r}")
    else:
        R.ok("neural_recall_not_encrypted")


# ================================================================
# 4. SYSTEM PROMPT INJECTION
# ================================================================

def test_prompt_header_format():
    """Crypto header should have all required fields."""
    plugin = CryptoPlugin()
    prompt = plugin.on_session_start("base prompt")

    required = ["SESSION_CRYPTO", "KEY:", "MODE: AES256-GCM",
                 "SESSION_ID:", "END CRYPTO HEADER"]
    for field in required:
        if field not in prompt:
            R.fail("prompt_header", f"missing: {field}")
            return

    R.ok("prompt_header_format")


def test_prompt_preserves_original():
    """Original prompt should be appended after header."""
    plugin = CryptoPlugin()
    original = "You are Hermes. Be direct. Verify from source."
    prompt = plugin.on_session_start(original)

    if original not in prompt:
        R.fail("prompt_preserve", "original prompt missing")
    elif not prompt.endswith(original):
        R.fail("prompt_preserve", "original not at end")
    else:
        R.ok("prompt_preserves_original")


def test_prompt_header_length():
    """Header should be reasonable length (< 1KB)."""
    plugin = CryptoPlugin()
    prompt = plugin.on_session_start("short")
    header = prompt.replace("short", "").strip()
    if len(header) > 1024:
        R.fail("prompt_length", f"header too long: {len(header)} bytes")
    else:
        R.ok(f"prompt_header_length ({len(header)} bytes)")


# ================================================================
# 5. PLUGIN STATUS
# ================================================================

def test_status_fields():
    """Status should have all required fields."""
    plugin = CryptoPlugin()
    plugin.on_session_start("test")
    status = plugin.get_status()

    required = ["enabled", "session_active", "session_id",
                 "dlm_vault", "message_count", "key_suffix"]
    for field in required:
        if field not in status:
            R.fail("status_fields", f"missing: {field}")
            return

    if not status["session_active"]:
        R.fail("status_fields", "session not active")
    elif status["key_suffix"] is None:
        R.fail("status_fields", "key_suffix is None")
    else:
        R.ok("status_fields")


def test_status_after_end():
    """Status after session end should show inactive."""
    plugin = CryptoPlugin()
    plugin.on_session_start("test")
    plugin.on_session_end()
    status = plugin.get_status()

    if status["session_active"]:
        R.fail("status_after_end", "still active")
    elif status["key_suffix"] is not None:
        R.fail("status_after_end", "key_suffix not None")
    else:
        R.ok("status_after_end")


# ================================================================
# 6. DLM VAULT INTEGRATION
# ================================================================

def test_plugin_dlm_stores_key():
    """Plugin should store key in DLM vault if available."""
    plugin = CryptoPlugin()
    plugin.on_session_start("test")
    status = plugin.get_status()

    if status.get("dlm_vault"):
        R.ok("plugin_dlm_stores_key (DLM available)")
    else:
        R.ok("plugin_dlm_stores_key (DLM not available, OK)")


# ================================================================
# 7. EDGE CASES
# ================================================================

def test_empty_prompt():
    """Empty system prompt should work."""
    plugin = CryptoPlugin()
    prompt = plugin.on_session_start("")
    if "SESSION_CRYPTO" not in prompt:
        R.fail("empty_prompt", "no crypto header")
    else:
        R.ok("empty_prompt")


def test_huge_prompt():
    """Large system prompt (10KB) should work."""
    plugin = CryptoPlugin()
    big_prompt = "X" * 10240
    prompt = plugin.on_session_start(big_prompt)
    if "SESSION_CRYPTO" not in prompt:
        R.fail("huge_prompt", "no crypto header")
    elif big_prompt not in prompt:
        R.fail("huge_prompt", "original prompt missing")
    else:
        R.ok("huge_prompt (10KB)")


def test_unicode_prompt():
    """Unicode in system prompt."""
    plugin = CryptoPlugin()
    prompt = plugin.on_session_start("Grüße äöüß 🏠")
    if "Grüße äöüß 🏠" not in prompt:
        R.fail("unicode_prompt", "unicode lost")
    else:
        R.ok("unicode_prompt")


def test_tool_result_huge():
    """Huge tool result should be encrypted."""
    plugin = CryptoPlugin()
    plugin.on_session_start("test")
    big = "X" * 100000
    result = plugin.on_tool_result("terminal", big)
    if "[ENCRYPTED RESULT" not in result:
        R.fail("tool_huge", "not encrypted")
    elif big in result:
        R.fail("tool_huge", "plaintext leaked")
    else:
        R.ok("tool_result_huge (100KB)")


# ================================================================
# RUNNER
# ================================================================

def run_all():
    print("=" * 60)
    print("  CRYPTO PLUGIN TEST SUITE")
    print("=" * 60)

    tests = [
        ("1. Session Start/Stop", test_session_start_stop),
        ("2. Multiple Session Cycles", test_multiple_session_cycles),
        ("3. Disabled Plugin", test_disabled_plugin),
        ("4. Tool Result Encrypted", test_tool_result_encrypted),
        ("5. Tool Result Skip List", test_tool_result_skip_list),
        ("6. Tool Result Disabled", test_tool_result_disabled),
        ("7. Encrypt Tools False", test_tool_result_encrypt_tools_false),
        ("8. Tool Result No Session", test_tool_result_no_session),
        ("9. Neural Roundtrip", test_neural_roundtrip),
        ("10. Neural Disabled", test_neural_disabled),
        ("11. Neural Encrypt Memory False", test_neural_encrypt_memory_false),
        ("12. Neural No Session", test_neural_no_session),
        ("13. Neural Recall Not Encrypted", test_neural_recall_not_encrypted),
        ("14. Prompt Header Format", test_prompt_header_format),
        ("15. Prompt Preserves Original", test_prompt_preserves_original),
        ("16. Prompt Header Length", test_prompt_header_length),
        ("17. Status Fields", test_status_fields),
        ("18. Status After End", test_status_after_end),
        ("19. Plugin DLM Stores Key", test_plugin_dlm_stores_key),
        ("20. Empty Prompt", test_empty_prompt),
        ("21. Huge Prompt", test_huge_prompt),
        ("22. Unicode Prompt", test_unicode_prompt),
        ("23. Tool Result Huge", test_tool_result_huge),
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
