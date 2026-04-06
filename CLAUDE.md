# AERMOD Pipeline V4 — Claude Code Guidelines

## Project Overview

AERMOD Pipeline V4 is a Python-based processing pipeline for the EPA's AERMOD atmospheric dispersion model. It handles input file preparation, model execution orchestration, output parsing, and results validation.

## Core Principles (Karpathy Method)

### 1. Think Before Coding
- State assumptions explicitly before writing any code
- If a task is ambiguous, present two or three interpretations and ask which is intended
- Surface inconsistencies in requirements — do not silently pick one path
- Ask clarifying questions before touching files, not after

### 2. Simplicity First
- Write the minimum code that solves the problem — no speculative abstractions
- Do not add unrequested features, helpers, or "nice to have" utilities
- If a fix is 10 lines, do not write 100 lines
- Prefer flat, readable code over clever, nested abstractions

### 3. Surgical Changes
- Touch only the files directly relevant to the task
- Preserve existing code style and naming conventions
- Do not refactor surrounding code that is not broken
- Only remove dead code you personally orphaned in this change

### 4. Goal-Driven Execution
- Define what "done" looks like before starting (success criteria)
- Transform vague tasks into verifiable objectives; write a failing test first when possible
- Loop until tests pass and outputs validate — do not declare done prematurely

---

## Project Structure

```
src/           # Pipeline modules (parsers, runners, validators)
experiments/   # One-off scripts and prototypes (never import from here)
utilities/     # Shared helpers (path resolution, logging, config loading)
tests/         # pytest test suite — must pass before any commit
docs/          # Architecture decisions and runbook
```

## Development Rules

- **Tests must pass** before any commit: `pytest tests/`
- **Type hints required** on all new public functions
- **No print statements** in src/ — use `logging` module
- **AERMOD input files** are space/column-sensitive — never use string formatting for them; use the structured writers in `utilities/`
- **Numeric precision** matters: all AERMOD coordinates are UTM in meters, floats to 2 decimal places

## Key Boundaries

- `src/` code must be importable with no side effects
- Pipeline stages must be idempotent — re-running a stage must not corrupt output
- External calls (subprocess AERMOD runs) must always have a timeout set

## Common Gotchas

- AERMOD `STARTING` keyword must be the first non-comment line in runstream files
- Receptor grids must be sorted (X ascending, then Y ascending) — the model silently errors otherwise
- All met data timestamps are UTC; output timestamps are local standard time
