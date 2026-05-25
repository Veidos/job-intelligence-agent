# ADR-008: Deterministic 0-1 scoring with level multipliers

**Date:** 2026-05-25
**Type:** `architecture`
**Status:** `active`
**Component:** `src/pipeline/evaluate.py`, `src/pipeline/fetch.py`

---

## Context

The previous scoring system delegated all numeric evaluation to gemma4:e4b:
- `evaluate_technical` returned 4 numbers (skills_hard_match 0-30, experience_match 0-20, education_match 0-10, location_match 0-5) and `evaluate_hr` returned 4 numbers (trajectory_coherence 0-15, recency_relevance 0-15, market_competitiveness 0-5) plus a penalty 0-25.
- Each prompt asked the model to reason and emit integer scores within a bounded range, and Python summed them with implicit weights (30+20+10+5 + 15+15+5 - 25 = 100 pts).

This had problems:
1. **Inconsistency across offers.** Same skill, same level, different score because the model could weight differently across calls (temperature 0.1 in technical).
2. **Black box.** No traceability of why a skill scored X and not Y. The model's reasoning was narrative, not replicable.
3. **Duplicate penalization.** The work gap was penalized both in the HR penalty and via reduced experience_match, with no clear rules.
4. **Output not bounded to 0-1.** The 0-100 score was mapped to discrete ratings, but the ranges were arbitrary and not calibrated against the real profile.
5. **skills_required legacy.** The DB stored skills_required as a flat JSON array without an associated level, making level-based matching impossible.

---

## Decision

**Replace the LLM's narrative scoring with a deterministic 0-1 model using level multipliers, where the LLM only detects skill presence and cultural context, and Python computes the score with fixed rules.**

The new flow per offer:

1. `evaluate_technical()` — gemma4 detects only skill presence/level (temp 0.0). Returns no numbers.
2. `compute_skill_score()` — Python computes `M_core` and `M_sec` with `level_multiplier(candidate_level, required_level) = min(cand/req, 1.0)`. If `required_level=None` → 1.0.
3. `compute_experience_score()` — Python computes `F_exp = years_match * G(gap)`, with fixed `GAP_MULTIPLIER`.
4. `evaluate_hr()` — gemma4 returns only `context_fit` (0.0-1.0), no numeric scores.
5. Final score: `S = 0.45*M_core + 0.15*M_sec + 0.25*F_exp + 0.15*F_fit`
6. `evaluate_final()` — same as before, validates relevance_flag and blockers.

### skills_required schema

Now stored as structured JSON:

```json
{
  "core": [{"name": "Python", "level_required": "intermedio"}, ...],
  "secondary": [{"name": "Git", "level_required": null}, ...]
}
```

`parse_skills_required()` in fetch.py automatically converts legacy arrays and other formats to the new schema, guaranteeing backward compatibility.

### GAP_MULTIPLIER table

| Gap (years) | Multiplier |
|-------------|------------|
| 0 - 1       | 1.00       |
| 1 - 2       | 0.85       |
| 2 - 3       | 0.70       |
| 3 - 4       | 0.55       |
| 4+          | 0.40       |

No narrative LLM penalty. The gap is applied as a multiplicative factor over `years_match`, not as arbitrary subtraction.

### Levels

| Level | Ordinal |
|-------|---------|
| basic | 1 |
| intermediate | 2 |
| advanced / expert | 3 |

`level_multiplier = min(ord(candidate), ord(required)) / ord(required)`. Overqualification capped at 1.0.

---

## Discarded alternatives

- **Keep scoring via LLM.** Discarded due to inconsistency across offers and lack of traceability. The model decided whether to penalize based on its state, not fixed rules.
- **Point system with correspondence table (e.g. Python basic = 2 pts).** Discarded because it does not scale to new skills the model might invent. Substring + level matching allows any skill.
- **Delegate everything to gemma4 with temperature 0.0.** Discarded in ADR-006+: the LLM is still needed for semantic skill detection (synonyms, equivalents) and cultural context evaluation. But numeric scoring must be deterministic.
- **Keep flat array in skills_required.** Discarded because without an associated level, `level_multiplier` cannot be computed. Migration is automatic via `parse_skills_required`.

---

## Consequences

- **Fully deterministic and traceable scoring.** `skill_detail` is stored in `penalty_breakdown` with individual L_i per skill for auditing.
- **The LLM can no longer invent scores.** It only responds present/absent and detected level. Python assigns the weight.
- **Backward compatibility.** `parse_skills_required` handles legacy data (flat array, JSON string, None) without DB migration.
- **`education_match` and `location_match` are set to 0.** The previous model weighted 10 pts for education and 5 pts for location with imprecise rules. These factors are now qualitative context within `context_fit` from HR.
- **`trajectory_coherence`, `recency_relevance`, `penalty` are set to 0.** The work gap is applied as a deterministic multiplier, not as subtraction. Trajectory coherence is qualitative context.
- **Final score in 0.0-1.0**, not 0-100. `match_score` in DB is stored as `round(score * 100)` for compatibility with existing queries.
- **171 tests updated and passing.**
- **Legacy columns in `offer_evaluations` are still written** with fixed values (0 or None) to avoid breaking existing queries.

---

## References

- ADR-006 — evaluate_final and pre-filter removal
- ADR-005 — Axis separation in classifier (pattern: LLM reasons + Python decides)
- docs/RATING.md — scoring system (outdated, pending update)
- docs/CONVENTIONS.md — implementation phases (Phase 4 complete)
