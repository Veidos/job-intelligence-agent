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
| 0.25 | `F_exp` | Years of experience + employment gap |
| 0.15 | `F_fit` | gemma4:e4b (only LLM intervention) |

## Skills: per-skill level

Each skill has an inferred required level:

```
level_required = sk_level_required                         if skill has explicit level
level_required = ROLE_LEVEL_TO_SKILL_LEVEL[role_level_label]   otherwise
```

Mapping:

| `role_level_label` | Inferred level |
|---|---|
| junior | básico (ord=1) |
| mid | intermedio (ord=2) |
| senior | avanzado (ord=3) |

Individual multiplier:

```
L_i = min(ord(candidate_level), ord(required_level)) / ord(required_level)
```

- Candidate lacks the skill → `L_i = 0`
- Overqualification capped at `1.0`
- `M_core = avg(L_i)` over core skills
- `M_sec = avg(L_i)` over secondary skills

## Experience

```
F_exp = years_match · G(gap)

years_match = 1.0                                  if experience_min = 0
years_match = min(candidate_years / experience_min, 1.0)  otherwise
```

### Gap multiplier

| Gap (years) | G |
|-------------|---|
| 0 – <1 | 1.00 |
| 1 – <2 | 0.85 |
| 2 – <3 | 0.70 |
| 3 – <4 | 0.55 |
| ≥ 4 | 0.40 |

## Context

`F_fit` is the only LLM value. gemma4:e4b evaluates `context_fit` (0–1)
considering culture, location, work mode, and personal profile.

## Final rating

| Score | Label |
|-------|-------|
| 0.75 ≤ S ≤ 1.00 | Prioritario |
| 0.55 ≤ S < 0.75 | Aplicar |
| 0.35 ≤ S < 0.55 | Con expectativas bajas |
| 0.00 ≤ S < 0.35 | No aplicar |

## Notes

- HR temperature = 0.0 guarantees deterministic verdicts
- Legacy per-skill `level_required` values are still valid if present in DB;
  if `None`, they are resolved automatically from the offer's role level
- ADR-008 documents the full rationale for switching to 0–1 deterministic scoring
