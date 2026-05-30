# ADR-012: evaluate.py — candidate_years span, education as skills, partial save

**Date:** 2026-05-30
**Type:** `architecture`
**Status:** `active`
**Component:** `src/pipeline/evaluate.py`

---

## Context

The evaluation pipeline (`evaluate.py`) had three independent problems surfaced during T-5 testing on 5 selected offers:

### Problem 1: candidate_years always 0.0

`load_experience_years_from_perfil()` used this regex:
```python
r"(?:años?.*experiencia|experiencia.*años?).*?([\d.]+)"
```
PERFIL.md does not contain "años de experiencia" as explicit text. The regex always returned 0.0, meaning `F_exp = 0` for any offer with `experience_min > 0`. The candidate actually has ~4.3 years of professional experience (May 2018 — Sep 2022) recorded in `## Experiencia` with `**Duración:**` date ranges.

### Problem 2: skills_map missing education/domain competencies

`load_skills_from_perfil()` only parsed the `## Skills técnicas` section. The candidate's academic background (e.g., "Ingeniería Técnica Industrial, Especialidad Mecánica") from `## Educación` was never included in the skills_map passed to the technical LLM and the skill matcher. This meant Step 1 could never detect "Ingeniería Industrial" as present in core skills, even though the candidate holds the degree.

### Problem 3: no fault tolerance for Step 6 (evaluate_final)

If Step 6 timed out or crashed, Steps 1–5 results were lost entirely because `save_evaluation()` was called only after Step 6 completed. The function was a single INSERT with no upsert capability, and `is_evaluated` was set to 1 atomically with the save.

---

## Decision

### Fix 1: candidate_years as span from date ranges

Replace the brittle regex with a two-fallback strategy:

1. **Explicit mention** (existing regex, kept for backward compatibility): catches "X años de experiencia" if present.
2. **Span calculation from `## Experiencia` dates** (new): parses all `**Duración:** {month} {year} – {month} {year}` entries, finds the earliest and latest dates, and computes `span_months / 12`. This avoids double-counting overlapping employments.

For the current PERFIL.md: May 2018 → Sep 2022 = 52 months ≈ **4.3 years**.

### Fix 2: education titles as domain skills

`load_skills_from_perfil()` now also parses `## Educación` after `## Skills técnicas`. Each `- **{Title}**` entry is added to the skills list with level `"avanzado"` and source `"formación académica"`. Bootcamps and academic entries that overlap with existing skills are skipped via a lowercase name dedup.

This enriches the `candidate_skills_map` so both the LLM (Step 1 semantic detection) and the Python matcher (`compute_skill_score` substring matching) can find education-derived competencies like "Ingeniería Técnica Industrial" when the offer requires "Ingeniería Industrial".

### Fix 3: upsert + partial save pattern

`save_evaluation()` refactored:
- Checks `SELECT id FROM offer_evaluations WHERE offer_id = ?` before INSERT/UPDATE
- `partial=True` parameter: saves Steps 1–5 data, leaves final fields as NULL, does NOT set `offers.is_evaluated=1`
- `partial=False`: same as before, marks evaluated

New `update_evaluation_final(offer_id, final)` function:
- UPDATEs only the Step 6 fields (relevance_validation, apply_block, etc.)
- Sets `offers.is_evaluated=1`

The `run_evaluate()` loop now does:
1. Steps 1–5 → `save_evaluation(partial=True)`
2. Step 6 → `update_evaluation_final()`

If Step 6 crashes, the partial row exists with `is_evaluated=0`. On restart, `get_pending_offers()` selects it again, the upsert detects the existing row and UPDATEs it instead of duplicating.

---

## Discarded alternatives

- **Keep regex-only approach.** Discarded because PERFIL.md can be regenerated without explicit "años de experiencia" line. The regex proved fragile.
- **Add explicit line to PERFIL.md (e.g., "- **Años de experiencia:** 4.3").** Discarded because it requires manual maintenance and will diverge from actual date ranges over time.
- **LLM-based extraction for candidate_years.** Overkill for a deterministic calculation from existing structured data.
- **Hardcode domain competencies per degree.** ADR-005 rule: no hardcoded decisions in Python. The education section is parsed dynamically, the semantic mapping is delegated to the LLM in Step 1.
- **Single INSERT with final fields nullable but no upsert.** Discarded because restarting after a Step 6 crash would cause duplicate `offer_evaluations` rows (no UNIQUE constraint on `offer_id`).

---

## Consequences

- **F_exp now reflects real experience.** For this candidate, all offers get `F_exp = years_match * 0.55` (gap multiplier for 3.7 years). Offers with `experience_min >= 4.3` get partial credit; offers with `experience_min = 0` get full 0.55.
- **Education-derived skills are present in the LLM prompt.** The technical LLM can now map "Ingeniería Técnica Industrial, esp. Mecánica" to "Ingeniería Industrial" semantically. In testing, ID 336 (Rioglass) M_core rose from 0.1667 to 0.5000 and score from 0.34 to 0.49.
- **Partial evaluation rows survive crashes.** If Step 6 times out, the partial row is in the DB, restartable via upsert detection.
- **No schema migration needed.** The existing `offer_evaluations` schema supports NULL final fields and the `offers.is_evaluated` flag. The upsert is purely application-level.
- **The `candidate_skills_map` grows with education.** From 6 skills (Python, SQL, ML, Pandas, Numpy, Scikit-learn) to 8 (plus "Data Science Bootcamp" and "Ingeniería Técnica Industrial, Especialidad Mecánica"). The bootcamp entry is a byproduct; it does not interfere with matching because no offer skill substrings its name.

---

## References

- ADR-008 — Deterministic scoring (established the evaluate.py architecture)
- ADR-006 — evaluate_final prompt (complemented by Fix 3's fault tolerance)
- ADR-005 — Axis separation pattern (LLM reasons, Python decides; same pattern here)
- `PERFIL.md` — source of truth for candidate_years date ranges and education
