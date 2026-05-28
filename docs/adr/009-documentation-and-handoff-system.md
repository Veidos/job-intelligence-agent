# ADR-009: Documentation and Session Handoff System

**Date:** 2026-05-27
**Type:** `operational`
**Status:** `active`
**Component:** `AGENTS.md`, `HANDOFF.md`, `docs/*.md`

---

## Context

The project has accumulated significant technical and operational changes that were not reflected in the documentation:

1. **`apify_raw_responses` table** — new immutable append-only table for Apify raw data, with 3-phase fetch refactor (`persist_raw_responses` → `upsert_from_raw` → `enrich_pending`).
2. **`keyword_generator.py`** — new module for generating search keywords from `PERFIL.md` via gemma4:e4b, with `--dry-run` and `--manage` modes.
3. **`think` logging** — `ollama_client.py` now captures and logs the `think` field from Ollama when `think=True`.
4. **Session handoff gap** — there was no mechanism to tell the next agent session "where to start." `MEMORIES.md` stores permanent learnings, `PLANS.md` tracks phases, but neither captures session state (current blockers, next step, recent decisions).

Without a handoff file, each new session forces the agent to re-discover context from scratch, leading to repeated questions and context confusion.

---

## Decision

**Adopt a three-file documentation triad with distinct lifecycles, plus a new ADR template:**

### The triad

| File | Lifecycle | Purpose |
|------|-----------|---------|
| `MEMORIES.md` | Permanent | Non-obvious learnings, bugs, effective patterns |
| `PLANS.md` | Per-phase | Feature checklist, test status, blockers |
| `HANDOFF.md` | Per-session | Current state, next step, ADRs to read |

### Update discipline

- `AGENTS.md` now includes a mandatory instruction: **"Actualizar HANDOFF.md al final de la sesión antes de cerrar."**
- All documentation files (`PIPELINE.md`, `SETUP.md`, `DATABASE.md`, `AGENTS.md`) are updated in the same session as the code changes they describe.
- `PLANS.md` and `MEMORIES.md` follow the Ledger Method: updated after each significant module or task.

### ADR scope

This ADR itself documents the adoption of the triad system. Future documentation changes (e.g., adding a new doc file) do not require a new ADR unless the change affects operational workflow or agent behavior.

---

## Discarded alternatives

- **Keep a single README with everything.** Discarded because lifecycle mismatch: permanent learnings, session state, and phase tracking change at different cadences.
- **Use a JSON file for session state.** Discarded: markdown is human-readable, git-trackable, and requires zero infrastructure.
- **Skip documentation updates and rely on the agent's context window.** Discarded: context window is limited; after multiple sessions, information degrades.

---

## Consequences

- **Each session starts with a clear handoff.** OpenCode reads `HANDOFF.md` before any tool call, reducing context waste.
- **Documentation is updated in-band with code changes.** No more "update docs later" — it's done in the same commit batch.
- **Three files, three concerns, no overlap.** `MEMORIES.md` = what we learned. `PLANS.md` = where we are. `HANDOFF.md` = what's next.
- **`AGENTS.md` enforces the discipline** by instructing agents to update `HANDOFF.md` at session close.
- **One extra file to maintain.** The cost is minimal compared to the context saved per session.

---

## References

- ADR-001 — ADR as a decision documentation system
- docs/CONVENTIONS.md — Ledger Method
