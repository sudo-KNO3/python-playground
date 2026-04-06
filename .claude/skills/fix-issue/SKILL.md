---
name: fix-issue
description: Investigate and fix a bug or GitHub issue for the AERMOD pipeline. Pass an issue number, description, or error message as the argument. Follows think-first, surgical-change principles.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
---

Fix the issue described in `$ARGUMENTS`. Follow the think-first, surgical-change workflow from CLAUDE.md.

## Phase 1: Understand (do NOT write any code yet)

1. Read `CLAUDE.md` to refresh project rules.

2. Parse `$ARGUMENTS` to identify:
   - Error message / traceback (if provided)
   - Affected feature or file (if named)
   - Expected vs actual behavior

3. Locate the relevant code:
   - Use Grep to find the error message or function name across the codebase
   - Read the full affected file(s), not just the matching lines

4. Reproduce the issue mentally — trace the execution path from entry point to failure.

5. **State your diagnosis** before writing any code:
   - Root cause (one sentence)
   - Files that need to change
   - Files that do NOT need to change
   - Estimated lines of change

6. If the diagnosis is uncertain or multiple causes are plausible, **ask for clarification** before proceeding.

## Phase 2: Fix (surgical)

7. Write a failing test that demonstrates the bug (in `tests/`).

8. Make the minimal code change to fix the root cause:
   - Touch only the files identified in Phase 1
   - Do not refactor surrounding code
   - Do not add unrequested features

9. Verify the fix: `pytest tests/ -x -q`

10. If tests pass, create a commit using the `/commit` skill conventions.

## Phase 3: Report

Output a concise fix summary:
- Root cause
- What changed and why
- Test added
- Any related areas that may have the same issue (flag but do not fix unless asked)
