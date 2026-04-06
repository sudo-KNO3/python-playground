---
name: validate-pipeline
description: Validate AERMOD Pipeline V4 inputs and outputs. Checks runstream files, met data, receptor grids, and output files for correctness before and after a model run. Pass a directory or file path as the argument.
allowed-tools:
  - Read
  - Glob
  - Bash
---

Validate the AERMOD pipeline inputs and/or outputs at the path given in `$ARGUMENTS`. If no path is given, scan the current working directory for AERMOD-related files.

## Input Validation (Runstream Files)

For each `.inp` or runstream file found:

1. **Structure checks**:
   - First non-comment, non-blank line must start with `CO STARTING`
   - All pathway blocks (`CO`, `SO`, `RE`, `ME`, `OU`) must have matching `STARTING` and `FINISHED` keywords
   - No duplicate keyword entries within a pathway block

2. **Source group checks**:
   - All source IDs referenced in `SO SRCGROUP` must be defined in `SO LOCATION`
   - Emission rates must be positive floats

3. **Receptor grid checks**:
   - Cartesian receptors: X values ascending within each Y row
   - Y rows must be sorted ascending
   - No duplicate receptor coordinates
   - All coordinates must be in valid UTM range (X: 100,000–900,000 m; Y: 0–10,000,000 m)

4. **Met data reference**:
   - Surface and upper air file paths in `ME SURFFILE` / `ME PROFFILE` must exist on disk
   - Met data date range must span the `CO STARTEND` period

## Output Validation (AERMOD Results)

For each `.out` or `_conc.dat` / `_depo.dat` file found:

1. **Completion check**: scan for `*** AERMOD Finishes Successfully ***` — flag if missing
2. **Warning scan**: extract all `*** WARNING` lines and list them
3. **Error scan**: extract all `*** ERROR` lines — these are blockers
4. **Concentration range check**: flag any receptor with concentration = 0.0 for all averaging periods (may indicate a grid/source mismatch)
5. **Timestamp continuity**: check that output timestamps are sequential with no gaps

## Report Format

```
VALIDATION REPORT
=================
Path: <path>
Files scanned: <n>

INPUTS
------
[PASS/FAIL] <filename>: <issue or "OK">

OUTPUTS
-------
[PASS/FAIL] <filename>: <issue or "OK">

SUMMARY
-------
Blockers:    <n>
Warnings:    <n>
Passed:      <n>
```
