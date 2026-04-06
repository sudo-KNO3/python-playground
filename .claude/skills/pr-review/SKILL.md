---
name: pr-review
description: Review a pull request for the AERMOD Pipeline V4. Checks correctness, simplicity, test coverage, and AERMOD-specific gotchas. Pass a PR number or branch name as the argument.
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
---

Review the pull request or branch diff provided as `$ARGUMENTS`. If no argument is given, review uncommitted changes vs main.

## Steps

1. **Get the diff**:
   - If `$ARGUMENTS` is a branch name: `git diff main...$ARGUMENTS`
   - If `$ARGUMENTS` is empty: `git diff main...HEAD`

2. **Read changed files in full** — do not review just the diff, read the full file for context.

3. **Check each changed file against these criteria:**

### Correctness
- [ ] No off-by-one errors in AERMOD coordinate or grid calculations
- [ ] Subprocess calls have a `timeout=` argument set
- [ ] File paths use `pathlib.Path`, not raw string concatenation
- [ ] No `print()` in `src/` — logging only
- [ ] Floats for UTM coordinates formatted to exactly 2 decimal places

### AERMOD-Specific Rules
- [ ] Runstream keyword order is respected (`STARTING` first)
- [ ] Receptor grids sorted (X asc, then Y asc) before writing
- [ ] Met data treated as UTC; any output conversion to LST is explicit
- [ ] Structured writers used for AERMOD input files — no f-string formatting of column-sensitive lines

### Simplicity & Cleanliness
- [ ] No speculative abstractions or unused parameters
- [ ] Functions do one thing — no hidden side effects
- [ ] New public functions have type hints
- [ ] No code left commented out

### Test Coverage
- [ ] New logic has corresponding tests in `tests/`
- [ ] Tests are specific — no `assert result is not None` style assertions
- [ ] Edge cases covered (empty inputs, malformed files, timeout scenarios)

4. **Run the tests**: `pytest tests/ -x -q`

5. **Output a structured review**:
   - **Summary**: one paragraph on what this PR does
   - **Issues** (must fix): numbered list of blockers
   - **Suggestions** (optional): improvements that are not blockers
   - **Verdict**: APPROVE / REQUEST CHANGES / NEEDS DISCUSSION
