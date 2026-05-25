# 001 — ADR as a decision documentation system

**Date:** 2026-05-21
**Type:** `architecture`
**Status:** `active`

## Context
Decisions made during development were not recorded in a structured way.
MEMORIES.md accumulated technical facts but not the reasoning
behind each decision.

## Decision
Use classic ADR: one file per decision in docs/adr/, with a fixed format
and sequential numbering.

## Discarded alternatives
Monolithic DECISIONS.md: worse for agent indexing, does not scale,
git blame less useful.

## Consequences
The agent creates a new ADR file at the end of each session where a non-trivial
decision is made. The index in docs/adr/README.md is always updated.
