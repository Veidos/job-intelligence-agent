# ADR-006: evaluate.py — third prompt (evaluate_final) and pre-filter removal

**Date:** 2026-05-23
**Type:** `architecture`
**Status:** `active`
**Component:** `src/pipeline/evaluate.py`

---

## Context

The evaluation pipeline ran two prompts per offer (technical + HR) preceded
by a pre-filter that called gemma4 to detect structurally impossible
requirements. If the pre-filter discarded the offer, it was saved with `match_score=0`
and `descarte_tipo="requisito_imposible"`, skipping the real evaluation.

This had three problems:

1. **Information loss.** An offer with a legal blocker (e.g. university internships)
   but good technical match (score ~70) was recorded as score=0, invisible
   to market analysis and human validation.
2. **Responsibility duplication.** The pre-filter and the HR penalty evaluated
   similar concepts (application blockers) from different prompts, with risk
   of inconsistency.
3. **No classifier validation.** There was no step that contrasted the
   `relevance_flag` assigned by `role_classifier` against the full description
   and the evaluations.

---

## Decision

**Remove the early pre-filter (`check_impossible_requirements`) and add a
third prompt (`evaluate_final`) that runs after technical+HR, with
temperature=0.0, to validate the relevance_flag and detect application blockers
with all available information (description + evaluations + score).**

The new flow per offer is:

1. `evaluate_technical()` — gemma4, temp 0.1 (block A, 60 pts)
2. `evaluate_hr()` — gemma4, temp 0.0 (block B + penalty, 40 pts)
3. Compute `match_score` = `max(0, min(100, block_A + block_B - penalty))`
4. `evaluate_final()` — gemma4, temp 0.0 (validation + blockers, does not alter score)
5. `save_evaluation()` with the 6 new columns

Fields added to `offer_evaluations`:

| Column | Purpose |
|---------|---------|
| `relevance_validation` | `confirmed` or `corrected` — validation of the classifier's relevance_flag |
| `relevance_corrected` | Corrected value if applicable |
| `relevance_reasoning` | Brief explanation of the validation |
| `apply_block` | `requisito_imposible`, `practicas`, `other` or `null` |
| `apply_block_reason` | Explanation of the blocker |
| `llm_apply_signal` | `yes/maybe/no` from the LLM (independent of the numeric rating) |

What **does not change**:
- `recommendation` remains `get_rating(raw_score)` — rating based on score
- `apply_recommendation` (existing column) is not touched — preserves historical data
- `offers.relevance_flag` is not modified from evaluate.py — the classifier's flag
  is the historical truth; `relevance_corrected` is a second opinion

---

## Discarded alternatives

- **Keep the pre-filter as an early step.** Discarded because discarding with
  score=0 destroys market information. The cost of 2 extra calls per
  discardable offer (~15-50 offers/day) is acceptable compared to the benefit of having
  the real score for all offers.
- **Merge evaluate_final with evaluate_hr.** Discarded because mixing classifier
  validation with HR evaluation contaminates both judgments. By separating the prompts
  each has a clear objective and independent temperature.
- **Use the existing `apply_recommendation` field for the LLM signal.**
  Discarded due to semantic breakage with historical data. `llm_apply_signal` is created instead.

---

## Consequences

- **Every evaluated offer has a real score**, even blocked ones. Allows
  human validation (T-5) and market analysis on offers with blockers.
- **Three gemma4 calls per offer** instead of 1-2. Acceptable for the daily
  pipeline volume.
- **The `descarte_tipo` and `descarte_razon` columns are no longer written** (not
  physically deleted due to SQLite limitations). Historical data is
  preserved.
- **The classifier's relevance_flag now has contrast.** `relevance_corrected`
  allows measuring classifier quality a posteriori.
- **Tests updated:** 3 pre-filter tests removed, 5 updated for
  the third mock. 171 tests passing.
- **New column `llm_apply_signal`** added to the schema. Any future
  consumer must decide whether to use `recommendation` (numeric rating) or `llm_apply_signal`
  (LLM judgment).

---

## References

- PRD 5.2.3 — HR evaluation with penalty
- ADR-005 — Axis separation in classifier (same pattern: LLM reasons,
  Python decides)
