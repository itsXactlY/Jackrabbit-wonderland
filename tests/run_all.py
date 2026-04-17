#!/usr/bin/env python3
"""
Jackrabbit-Wonderland: Full Test Suite Runner
===============================================
Runs all test suites and reports aggregate results.

Usage:
  python3 tests/run_all.py           # Run all suites
  python3 tests/run_all.py crypto    # Run specific suite
  python3 tests/run_all.py gateway   # Run gateway tests only
  python3 tests/run_all.py dlm       # Run DLM vault tests only
  python3 tests/run_all.py plugin    # Run plugin tests only
"""

import sys
import os
import time
import subprocess

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)

SUITES = {
    "crypto": "test_crypto_middleware.py",
    "gateway": "test_gateway_stress.py",
    "dlm": "test_dlm_vault.py",
    "plugin": "test_crypto_plugin.py",
}


def run_suite(name, script):
    """Run a test suite as subprocess, capture output."""
    path = os.path.join(TEST_DIR, script)
    if not os.path.exists(path):
        return False, f"Script not found: {path}", 0

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=PROJECT_DIR,
        )
        elapsed = time.time() - start
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return success, output, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return False, f"TIMEOUT after {elapsed:.1f}s", elapsed
    except Exception as e:
        elapsed = time.time() - start
        return False, f"EXCEPTION: {e}", elapsed


def main():
    print("=" * 70)
    print("  JACKRABBIT-WONDERLAND — FULL TEST SUITE")
    print("=" * 70)
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  CWD: {PROJECT_DIR}")
    print("=" * 70)

    # Determine which suites to run
    if len(sys.argv) > 1:
        requested = sys.argv[1:]
        suites = {k: v for k, v in SUITES.items() if k in requested}
        if not suites:
            print(f"Unknown suite(s): {requested}")
            print(f"Available: {', '.join(SUITES.keys())}")
            sys.exit(1)
    else:
        suites = SUITES

    results = {}
    total_passed = 0
    total_failed = 0
    total_time = 0

    for name, script in suites.items():
        print(f"\n{'#'*70}")
        print(f"  RUNNING: {name} ({script})")
        print(f"{'#'*70}\n")

        success, output, elapsed = run_suite(name, script)
        total_time += elapsed

        # Print output
        print(output)

        results[name] = success
        if success:
            total_passed += 1
        else:
            total_failed += 1

    # Final summary
    print("\n" + "=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)

    for name, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"  {status:4s}  {name}")

    print(f"\n  Suites: {total_passed} passed, {total_failed} failed")
    print(f"  Total time: {total_time:.1f}s")
    print("=" * 70)

    if total_failed > 0:
        print("\n  FAILED SUITES:")
        for name, success in results.items():
            if not success:
                print(f"    - {name}")
        print()

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
