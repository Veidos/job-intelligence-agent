# ADR-007: OpenRouter discarded as alternative backend

**Date:** 2026-05-23
**Type:** `reversal`
**Status:** `active`
**Component:** `src/utils/openrouter_client.py`

---

## Context

OpenRouter (via `openrouter/free`) was evaluated as an alternative LLM backend
to Ollama to remove the dependency on the local gemma4:e4b model.

`openrouter_client.py` was implemented with the same interface as
`ollama_client.py`, a resolver per backend in `evaluate.py`,
`role_classifier.py` and `run.py`, and `_extract_json` was extracted to
`json_utils.py` to be shared between both clients.

## Decision

**Discard OpenRouter.** gemma4:e4b (local Ollama) is more reliable
and produces consistent results.

## Evaluation data

6 of the 17 T-4 offers were run with OpenRouter before aborting:

| Offer | Ollama | OpenRouter | Δ |
|--------|--------|-----------|---|
| Junior Programmer Analyst | 53 | 30 | -23 |
| Data Analyst (Looker) | 61 | 33 | -28 |
| Database Analyst | 12 | 33 | +21 |
| Data and Automation Analyst | 61 | 35 | -26 |
| Junior Power BI Analyst | 43 | 43 | 0 |
| Data Analyst (SQL, Python, PBI) | 41 | 43 | +2 |

**Issues detected:**
- `openrouter/free` routes to different models per call → inconsistent scores
- JSON extraction intermittently fails (model returns plain text)
- `NoneType.strip` error due to empty response on 1 offer
- Average score 7pts lower than Ollama on comparable offers

## Consequences

- Commits `0db3749` and `cb54a4f` reverted
- `openrouter_client.py` and `json_utils.py` deleted
- `ollama_client.py`, `evaluate.py`, `role_classifier.py`, `run.py`
  returned to their pre-OpenRouter state
- `.env.example` returned to its previous state (no OpenRouter vars)
- If a remote backend is explored in the future, it must use a specific model
  (e.g. `openai/gpt-4o-mini`) with an assigned budget, not an automatic router

## References

- ADR-006 — evaluate_final (last ADR before this revert)
- `reports/testing/06-evaluate-openrouter.html` — comparative report
- `scripts/reporte_evaluate_v2.py` — report script
