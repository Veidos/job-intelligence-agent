# Rating System — ADR-008

Deterministic 0–1 score. No LLM generates numeric scores.

## Formula

```
S = W_core · M_core + W_sec · M_sec + W_exp · F_exp + W_fit · F_fit
```

| Weight | Variable | Source |
|--------|----------|--------|
| 0.45 | `M_core` | Core skills from offer vs CV |
| 0.15 | `M_sec` | Secondary skills from offer vs CV |
| 0.25 | `F_exp` | Years of experience (sin gap — cualitativo en HR) |
| 0.15 | `F_fit` | gemma4:e4b (context_fit cualitativo) |

## Skills: binary presence

Skills evaluate presence, not depth. `L_i` is binary:

```
L_i = 1.0 if candidate has the skill (or equivalent detected by gemma4 in step 1)
L_i = 0.0 otherwise
```

The depth dimension is captured by `F_exp` (experience_min_years from the scraper).
This replaces the previous `role_level_label` → `level_required` mapping, which
was a noisy proxy (67% default "mid") when `experience_min_years` is available
as structured data.

## Education as domain skills (ADR-012)

`load_skills_from_perfil()` also parses `## Educación` from PERFIL.md. Each
academic title is added to the `candidate_skills_map` with level `"avanzado"`.
This allows the technical LLM (Step 1) to semantically match education-derived
competencies against offer skills.

Example: "Ingeniería Técnica Industrial, Especialidad Mecánica" (education)
matches "Ingeniería Industrial" (offer skill) via both LLM semantic detection
and Python substring matching.

Individual multiplier (binary):

```
L_i = 1.0  if candidate has the skill
L_i = 0.0  otherwise
```

- `M_core = avg(L_i)` over core skills
- `M_sec = avg(L_i)` over secondary skills

## Experience

```
F_exp = years_match

years_match = 1.0                                  if experience_min = 0 or NULL
years_match = min(candidate_years / experience_min, 1.0)  otherwise
```

`candidate_years` is extracted from PERFIL.md via two fallbacks:
1. Explicit "X años de experiencia" text (regex)
2. Span from earliest to latest `**Duración:**` date in `## Experiencia` section (default)

The span approach (ADR-012) uses all employment dates to calculate total professional
experience, avoiding overcounting overlapping employments. For the current profile:
May 2018 → Sep 2022 = 4.3 years.

### Gap — context qualitativo (ADR-013)

Employment gap is NOT part of the numeric score. It is passed as context to the
HR LLM (Step 4), which evaluates whether the gap is a real barrier for each
specific offer. The gap multiplier table is still used for severity classification
(low/medium/high) passed to the prompt, but does NOT multiply F_exp.

This avoids a blind heuristic from capping all scores —
gemma4 evaluates contextually whether the gap matters for each role and company.

## Location

```
location_match = f(work_mode, candidate_city, offer_city)
```

Deterministic, computed in Python:

| Condition | Score |
|---|---|
| Remote | 1.0 |
| Hybrid | 0.7 |
| On-site, same city | 0.5 |
| On-site, different city | 0.2 |

Covers the 60 on-site, 28 hybrid, 4 remote offers in the current dataset,
providing real signal for W_FIT = 0.15.

## Context

`F_fit` is the only LLM value. gemma4:e4b evaluates `context_fit` (0–1)
considering culture, location, work mode, and personal profile.

> ℹ️ `location_match` is a **separate DB column** used for dashboard display
> (Ubicación column). It is **NOT** part of the scoring formula. See
> `F_fit` vs `location_match`: HR model considers location qualitatively;
> `location_match` is a deterministic Python heuristic shown to the user.

## Final rating

| Score | Label |
|-------|-------|
| 0.75 ≤ S ≤ 1.00 | Priority |
| 0.55 ≤ S < 0.75 | Apply |
| 0.35 ≤ S < 0.55 | Low expectations |
| 0.00 ≤ S < 0.35 | Skip |

## Notes

- HR temperature = 0.0 guarantees deterministic verdicts
- Legacy per-skill `level_required` values are still valid if present in DB;
  if `None`, they are resolved automatically from the offer's role level
- ADR-008 documents the full rationale for switching to 0–1 deterministic scoring
