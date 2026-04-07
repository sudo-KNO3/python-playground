# AERMOD Pipeline V4

A Python-based processing pipeline for the EPA's AERMOD atmospheric dispersion model. Handles input file preparation, model execution orchestration, output parsing, and results validation.

## Project Structure

```
src/           # Pipeline modules — parsers, runners, validators
utilities/     # Shared helpers — path resolution, logging, config loading
experiments/   # One-off scripts and prototypes (not imported by src/)
tests/         # pytest test suite
docs/          # Architecture decisions and runbook
```

## Setup

**Requirements:** Python 3.10+

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Development

Run the test suite before committing:

```bash
pytest tests/
```

Code quality tools configured in this project:

| Tool | Purpose | Command |
|------|---------|---------|
| pytest | Test runner | `pytest tests/` |
| black | Code formatter | `black src/ utilities/` |
| flake8 | Linter | `flake8 src/ utilities/` |
| mypy | Type checker | `mypy src/ utilities/` |

## Claude Code Skills

This project includes six Claude Code skills for AI-assisted development. Invoke them with `/skill-name`:

| Skill | Purpose |
|-------|---------|
| `/context-prime` | Load full project context at the start of a session |
| `/commit` | Generate a conventional commit from current changes |
| `/run-tests` | Run pytest with coverage and diagnose failures |
| `/fix-issue` | Think-first bug fix workflow with test-first approach |
| `/pr-review` | Structured PR review with AERMOD-specific checklist |
| `/validate-pipeline` | Validate AERMOD runstream inputs and model outputs |

## Key Rules

- **No print statements** in `src/` — use the `logging` module
- **Type hints required** on all new public functions
- **AERMOD input files** are column-sensitive — use the structured writers in `utilities/`, never raw string formatting
- **UTM coordinates** are in metres, floats to 2 decimal places
- **Pipeline stages must be idempotent** — re-running a stage must not corrupt output
- **Subprocess calls** to AERMOD must always set a `timeout`

## AERMOD Gotchas

- The `CO STARTING` keyword must be the first non-comment line in every runstream file
- Receptor grids must be sorted — X ascending within each Y row, Y rows ascending — the model silently errors otherwise
- Met data timestamps are UTC; AERMOD output timestamps are local standard time
