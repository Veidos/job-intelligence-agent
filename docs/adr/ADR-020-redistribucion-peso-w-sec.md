# ADR-020: Redistribución de peso W_SEC cuando secondary está vacío

- **Estado:** Activo
- **Fecha:** 2026-06-17
- **Commit:** f7be13f

## Contexto

El scraper de InfoJobs extrae skills del `<dl>` de Requisitos como lista plana,
sin distinción entre skills obligatorias y deseables. Como resultado,
`skills_required.secondary` siempre llegaba vacío a `compute_skill_score`.

Con `secondary = []`, `M_sec = 0.0` siempre. La fórmula original:

    S = 0.45·M_core + 0.15·M_sec + 0.25·F_exp + 0.15·F_fit

penalizaba todas las ofertas en hasta 0.15 puntos por ausencia de datos,
no por falta de match real del candidato.

## Decisión

Redistribuir `W_SEC=0.15` a `W_CORE` cuando `secondary` está vacío:

    w_core = 0.60, w_sec = 0.00  →  si secondary = []
    w_core = 0.45, w_sec = 0.15  →  si secondary tiene datos

Los pesos reales usados se almacenan en `scoring_detail.weights` junto
con el flag `secondary_redistributed: true` para trazabilidad de auditoría.

## Consecuencias

- 66 ofertas existentes recalculadas vía backfill. Scores subieron entre
  +1 y +15 puntos. 225 tests, 0 regresiones.
- `W_SEC` está diseñado pero inactivo hasta que Fix 2 esté validado.
- **Fix 2 es prerequisito** para que `W_SEC` contribuya al score real:
  integrar `extract_fields_with_llm` en `_upsert_offer_from_scraper`
  para que el LLM clasifique skills en core/secondary durante el fetch.
- Resultado de la POC (`scraper_lab/poc_secondary_skills.py`): 5/5 ofertas
  con secondary no vacío → Fix 2 viable.
