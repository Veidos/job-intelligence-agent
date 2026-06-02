# ADR-013: Score Rebalance v2 — F_exp sin gap, location_match determinista

**Date:** 2026-06-01 (retroactivo — refactor aplicado en commits `dacd6bc` y `7500fb4`)
**Type:** `architecture`
**Status:** `active`
**Component:** `src/pipeline/evaluate.py`, `src/db/schema.sql`

---

## Context

El scoring original (ADR-008) usaba `GAP_MULTIPLIER` que convertía el employment gap en una penalización multiplicativa sobre `F_exp`:

| Gap (años) | Multiplicador |
|------------|---------------|
| 0–1        | 1.00          |
| 1–2        | 0.85          |
| 2–3        | 0.70          |
| 3–4        | 0.55          |
| 4+         | 0.40          |

Con candidate_years=4.3 y employment_gap=3.7, el gap multiplier era 0.55, lo que capaba F_exp al 55% máximo. Con W_EXP=0.25, el score máximo teórico era 0.74, y ninguna oferta sin experiencia explícita podía superar 0.55 en F_exp. Esto **no distinguía reconversión activa de inactividad real**.

Además:
- `location_match` estaba hardcodeado a 0 (ver ADR-008 "set to 0") porque el LLM lo hacía impreciso.
- `experience_min` no se seleccionaba en `get_pending_offers()`, causando que `F_exp` siempre viera req=0 → years_match=1 → plano en 0.55.
- 7 columnas de `offer_evaluations` (education_match, trajectory_coherence, recency_relevance, penalty, company_fit_score, company_green_flags, company_red_flags) nunca se poblaban desde el refactor determinista (commit `7a4709b`).

---

## Decision

1. **Eliminar `GAP_MULTIPLIER` de `F_exp`.** El gap laboral pasa a ser contexto cualitativo exclusivo del HR LLM (ya estaba en el prompt de `evaluate_hr`). `F_exp = years_match` solo, sin multiplicador.

2. **`location_match` determinista.** Python calcula desde `work_mode` y `candidate_city`:
   - Remoto → 1.0
   - Híbrido → 0.7
   - Presencial, misma ciudad → 0.5
   - Presencial, fuera → 0.2

3. **`experience_min` en SELECT.** `get_pending_offers()` ahora incluye `o.experience_min`.

4. **Eliminar 7 zombie columns** de `offer_evaluations` via `migrate.py`. Renombrar `penalty_breakdown` → `scoring_detail`.

---

## Discarded alternatives

- **Mantener gap_multiplier pero con tabla más suave.** Descartado porque el gap es un factor cualitativo (reconversión activa vs inactividad) que el LLM evalúa mejor que una fórmula fija.
- **Location_match vía LLM.** Descartado en ADR-008 por impreciso. El determinismo es más justo y trazable.
- **Dejar zombie columns como NULL.** Descartado por hygiene: columnas nunca pobladas añaden ruido y confunden.

---

## Consequences

- **Impacto real (T-5c):** avg score 29.8 → 41.4 (+11.6 pts). 10 ofertas "Aplicar" (57–74), 51 "Con expectativas bajas" (35–54), 31 "No aplicar" (<35).
- **M_core es ahora el bottleneck** (0.0 → score máximo 35). F_exp ya no limita artificialmente.
- **location_match funcional:** 60 ofertas presenciales → 0.2, 28 híbridas → 0.7, 4 teletrabajo → 1.0.
- **7 zombie columns eliminadas** via migration. `scoring_detail` almacena desglose v2 (M_core, M_sec, F_exp, F_fit, skill_detail).
- **171 tests actualizados y passing.** Ninguna regresión.
- **Referencias en ADR-008 y ADR-012 actualizadas** para apuntar a este ADR.

---

## References

- ADR-008 — Scoring determinista 0-1 original (donde nació GAP_MULTIPLIER)
- ADR-012 — evaluate.py fixes (contexto de candidate_years span)
- docs/MEMORIES.md — sección "Scoring rebalance — ADR-013"
- docs/RATING.md — sección "Gap — context qualitativo"
