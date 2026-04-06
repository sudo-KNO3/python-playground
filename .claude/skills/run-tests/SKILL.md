---
name: run-tests
description: Run the AERMOD Pipeline V4 test suite with coverage reporting. Diagnoses failures and suggests targeted fixes. Optionally pass a path or keyword to run a subset (e.g. "parser", "tests/test_validator.py").
allowed-tools:
  - Bash
  - Read
  - Grep
---

Run the test suite for the AERMOD Pipeline V4. If `$ARGUMENTS` is provided, run only tests matching that path or keyword.

## Steps

1. **Install/verify dependencies** (fast check):
   ```bash
   pip show pytest pytest-cov 2>/dev/null | grep -E "^Name|^Version"
   ```
   If missing, install: `pip install pytest pytest-cov`

2. **Run tests**:
   - If `$ARGUMENTS` provided: `pytest $ARGUMENTS -v --tb=short 2>&1`
   - Otherwise: `pytest tests/ -v --tb=short --cov=src --cov=utilities --cov-report=term-missing 2>&1`

3. **Parse results**:
   - Count passed / failed / error / skipped
   - For each failure or error, read the full traceback

4. **Diagnose failures**:
   For each failing test:
   - Identify the root cause (assertion mismatch, exception, import error, etc.)
   - Read the relevant source file to understand whether the test or the implementation is wrong
   - State your diagnosis clearly

5. **Report**:
   ```
   TEST RESULTS
   ============
   Passed:  <n>
   Failed:  <n>
   Errors:  <n>
   Skipped: <n>

   Coverage: <overall %>

   FAILURES
   --------
   [test name]
     Cause: <one-line diagnosis>
     Fix:   <what needs to change — test or src>

   LOW COVERAGE (< 80%)
   --------------------
   <module>: <coverage %>  — untested paths: <brief note>
   ```

6. If all tests pass, confirm: "All tests passing. Coverage: X%."

## Rules

- Do NOT auto-fix failures unless explicitly asked — diagnose only
- Never skip tests or use `pytest --ignore` to hide failures
- If an import error prevents collection, investigate and fix the import first
