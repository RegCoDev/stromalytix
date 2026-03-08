"""
Development Loop - Test-Driven Implementation Helper

Runs pytest repeatedly and tracks progress toward 17/17 passing tests.
Alternative to Ralph Loop for manual iterative development.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

MAX_ITERATIONS = 20
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"dev_loop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

def log(message: str):
    """Log to both console and file."""
    print(message)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def run_tests() -> tuple:
    """Run pytest and return (exit_code, output)."""
    result = subprocess.run(
        ["uv", "run", "pytest", "tests/test_overnight.py", "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout + result.stderr

def count_passed(output: str) -> int:
    """Extract number of passed tests from pytest output."""
    for line in output.split("\n"):
        if "passed" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "passed" and i > 0:
                    try:
                        return int(parts[i-1])
                    except ValueError:
                        continue
    return 0

def main():
    log("=" * 60)
    log("Stromalytix Development Loop")
    log("=" * 60)
    log(f"Max iterations: {MAX_ITERATIONS}")
    log(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Log file: {log_file}")
    log("")

    for iteration in range(1, MAX_ITERATIONS + 1):
        log("=" * 60)
        log(f"ITERATION {iteration} / {MAX_ITERATIONS}")
        log("=" * 60)
        log("")

        log("Running tests...")
        exit_code, output = run_tests()
        log(output)

        passed = count_passed(output)
        log("")
        log(f"Tests passed: {passed}/17")

        if passed == 17 and exit_code == 0:
            log("")
            log("[OK] SUCCESS: All 17 tests passing!")
            log("DONE: All overnight tests passing")
            log(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return 0

        log("")
        log("[PENDING] Tests still have failures/skips")
        log("   Review .ralph/overnight_implementation.md for next steps")
        log("   Implement fixes, then press Enter to continue...")
        log("")

        try:
            input("Press Enter for next iteration (Ctrl+C to stop): ")
        except KeyboardInterrupt:
            log("\n\n[STOPPED] Stopped by user")
            log(f"Completed {iteration} iterations")
            return 1

    log("")
    log("[MAX ITER] Max iterations reached without completion")
    log(f"Review {log_file} for details")
    return 1

if __name__ == "__main__":
    sys.exit(main())
