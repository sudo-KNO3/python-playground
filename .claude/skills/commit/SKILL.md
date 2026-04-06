---
name: commit
description: Generate a conventional commit for staged or all modified changes. Analyzes the diff, writes a precise commit message, and commits. Cost-efficient — reads diff once, no back-and-forth.
allowed-tools:
  - Bash
  - Read
---

Generate and create a git commit for the current changes following Conventional Commits format.

## Steps

1. Run `git diff --staged` — if empty, run `git diff HEAD` to see unstaged changes.

2. Run `git status` to see which files are modified/untracked.

3. Analyze the diff and determine:
   - **type**: `feat` | `fix` | `refactor` | `test` | `docs` | `chore` | `perf`
   - **scope**: the affected module or component in parentheses (e.g. `parser`, `runner`, `validator`)
   - **subject**: a concise imperative description of the change (max 72 chars)
   - **body**: if the change is non-obvious, a brief explanation of *why* (not what — the diff shows what)
   - **breaking**: if any public API changed, add `BREAKING CHANGE:` footer

4. Stage all relevant changes:
   - `git add` specific files (never `git add -A` blindly — check for any `.env`, secrets, or large data files and skip them)

5. Commit using this format:
   ```
   <type>(<scope>): <subject>

   <body if needed>
   ```

6. Report the commit hash and message.

## Examples

```
feat(parser): add AERMOD STARTING keyword validation

fix(runner): handle subprocess timeout on long AERMOD runs

test(validator): add receptor grid sort order tests

docs(runbook): document UTC vs LST timestamp handling
```

## Rules

- Subject line must be lowercase after the colon
- No period at the end of subject line
- Body lines wrap at 72 characters
- Never use `--no-verify`
