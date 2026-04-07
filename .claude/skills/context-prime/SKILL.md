---
name: context-prime
description: Load full AERMOD Pipeline V5 project context before starting work. Run this at the start of every session to avoid re-explaining architecture and save tokens.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

You are being asked to load full context for the AERMOD Pipeline V5 project before beginning any work. Do this thoroughly and silently — do not narrate each file read, just load everything and report a concise summary at the end.

## Steps

1. Read `CLAUDE.md` in the project root — internalize all rules and gotchas.

2. Read `README.md` to understand the overall project purpose.

3. Scan the directory tree:
   - List all files under `src/`, `utilities/`, `tests/`, `docs/`
   - Note the module names and their apparent roles

4. Read every Python file in `src/` and `utilities/` to understand:
   - Public API (functions and classes exported)
   - Data models and type aliases
   - How pipeline stages connect to each other
   - Any constants related to AERMOD (coordinate systems, file formats, keyword lists)

5. Read all files under `docs/` for architecture decisions and runbook notes.

6. Run `git log --oneline -20` to see recent change history.

7. Run `git status` to see any current in-progress work.

8. Run `pytest tests/ --collect-only -q 2>/dev/null | head -40` to see what test coverage exists.

## Output

After loading context, produce a single concise summary:
- What the pipeline does (1-2 sentences)
- Current pipeline stages and their module locations
- Any active in-progress work from git status
- Any obvious gaps or TODO items spotted
- Ready to receive task instructions
