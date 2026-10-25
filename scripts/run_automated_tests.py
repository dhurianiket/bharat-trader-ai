"""
Automated Test Runner for BharatTrader-AI.
Executes the full test suite, runs end-to-end webhook simulations,
and generates a verification report.
"""

import sys
import time
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("TestRunner")


def run_command(cmd: list) -> bool:
    cmd_str = " ".join(cmd)
    logger.info(f"Running: {cmd_str}")
    start = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start

    if res.returncode == 0:
        logger.info(f"PASSED ({elapsed:.2f}s)\n{res.stdout}")
        return True
    else:
        logger.error(f"FAILED ({elapsed:.2f}s)\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        return False


def main():
    logger.info("================================================================")
    logger.info("       BHARAT-TRADER AI: AUTOMATED TEST & VERIFICATION SUITE    ")
    logger.info("================================================================")

    python_exe = sys.executable

    tasks = [
        ("Pytest Test Suite (Unit & E2E Integration)", [python_exe, "-m", "pytest", "tests/", "-v"]),
        ("CLI Diagnostics: Options Greeks & IV", [python_exe, "main.py", "--test-greeks"]),
        ("CLI Diagnostics: Market Regime Classifier", [python_exe, "main.py", "--test-regime"]),
        ("CLI Diagnostics: Simulated Signal Execution", [python_exe, "main.py", "--test-signal"]),
    ]

    all_passed = True
    results = []

    for name, cmd in tasks:
        logger.info(f"\n--- Testing: {name} ---")
        passed = run_command(cmd)
        results.append((name, passed))
        if not passed:
            all_passed = False

    logger.info("\n================================================================")
    logger.info("                      TEST SUMMARY REPORT                       ")
    logger.info("================================================================")
    for name, passed in results:
        status_str = "PASSED" if passed else "FAILED"
        logger.info(f"[{status_str}] {name}")

    if all_passed:
        logger.info("\nALL AUTOMATED TESTS PASSED SUCCESSFULLY! The engine is 100% operational.")
        sys.exit(0)
    else:
        logger.error("\nONE OR MORE TESTS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
