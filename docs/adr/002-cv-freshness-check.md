# 002 — CV freshness check with interactive regeneration

**Date:** 2026-05-21
**Type:** `operational`
**Status:** `active`

## Context
The pipeline ran `evaluate()` against `PERFIL.md` even when the CV
(`assets/cv.pdf`) was outdated, producing inconsistent evaluations.
The user had to remember to run `onboarding/run.py` manually after each
CV update.

## Decision
`run.py` detects changes in `assets/cv.pdf` via SHA-256, asks the user
whether to regenerate `PERFIL.md` with a full interview, and if accepted,
runs full onboarding before continuing the pipeline. In `--dry-run` or
headless (cron) execution, it only warns and stops.

## Discarded alternatives
- **Automatic regeneration without asking:** violates the AGENTS.md rule
  (never auto-regenerate PERFIL.md without explicit confirmation).
- **Warning only without interactive option:** poor UX for the average user
  who does not want to remember manual commands.
- **Continuous background watcher:** over-engineering for the real use case.

## Consequences
- `.cv_hash` is created at the project root (gitignored).
- The first `run.py` after a CV update runs full onboarding (extraction +
  interview), lengthening that run.
- Zero impact on the normal flow: no CV change = 0 additional lines.
- In headless (cron) mode the pipeline does not run if there is a new CV,
  avoiding inconsistent evaluations.
