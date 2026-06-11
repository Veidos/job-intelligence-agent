# 017 — Eliminar Phase 3 (enrich_pending) y role_level_label del scoring

**Date:** 2026-06-11
**Type:** `architecture`
**Status:** `active`

## Context

El pipeline de fetch operaba en 3 fases, siendo la Phase 3 (`enrich_pending`)
una llamada a gemma4:e4b que extraía campos estructurados de cada oferta:
`description_clean`, `role_level`, `skills_required` (core/secondary),
`experience_min`, `education_level`, `salary_min/max`.

Desde el reemplazo de Apify por el scraper propio (ADR-016, junio 2026),
el scraper extrae estos campos directamente del HTML estructurado de InfoJobs:

- `experience_min_years` desde el header (`"Al menos N años"`) y desde el
  `<dl>` de Requisitos (label "experiencia")
- `education_min` desde el header y el `<dl>` de Requisitos (label "estudios")
- `skills` desde el `<dl>` de Requisitos (label "conocimientos")
- `salary_min/max` desde el header
- `description_text` desde selectores semánticos
- `published_at` desde texto plano (5 formatos)

Datos en DB confirmaban que `experience_min` del scraper coincidía al 100%
con el valor que el LLM devolvía (COALESCE lo preservaba). El LLM no añadía
información nueva para estos campos.

Además, `role_level_label` (junior/mid/senior inferido por el LLM) se usaba
en `compute_skill_score()` para mapear a `level_required` via
`ROLE_LEVEL_TO_SKILL_LEVEL`. Pero:

- Ninguna skill en DB tenía `level_required` explícito — todas dependían del default
- 176/262 ofertas (67%) eran "mid" por defecto del LLM
- Cuando `experience_min_years` está disponible como dato estructurado,
  el proxy categórico junior/mid/senior → basic/intermediate/advanced es ruido

## Decision

Eliminar la Phase 3 del fetch y el `role_level_label` del scoring:

1. **Skills del `<dl>` van directamente a `core`** en `_upsert_offer_from_scraper()`.
   Ya no pasan por `secondary` esperando reclasificación del LLM.

2. **`enriched_at` se setea en el upsert**, no en una fase separada.
   No hay Phase 3 — el scraper deja la oferta completa desde el INSERT.

3. **`role_level_label` eliminado** de `compute_skill_score()`.
   `L_i` es binario: `1.0` si el candidato tiene la skill, `0.0` si no.

4. **`enrich_pending()` y `--enrich-only` eliminados** de fetch.py.

5. **`level_multiplier()`, `LEVEL_ORDINAL`, `ROLE_LEVEL_TO_SKILL_LEVEL`**
   eliminados de evaluate.py por quedar como código muerto.

6. **`extract_fields_with_llm()` se conserva** como función utilidad
   (no llamada desde el pipeline), útil para futuras necesidades de
   extracción desde descripciones.

## Discarded alternatives

1. **Mantener enrich_pending sin LLM** (solo setear enriched_at). Se descartó
   porque una función que solo hace un UPDATE trivial es deuda técnica desde
   el día 1 — el trabajo se hace en el upsert.

2. **Mantener role_level_label pero hacerlo determinista desde experience_min.**
   Se descartó porque el orden correcto es: eliminar el proxy, medir impacto,
   y solo entonces diseñar un reemplazo si es necesario. Con experience_min
   disponible y L binario, el proxy no aportaba señal independiente.

3. **Cache de skills** para evitar llamadas LLM redundantes. Se descartó por
   premature optimization — el problema actual no es la caché sino trabajo
   estructuralmente redundante.

4. **Separar fuentes de skills en enrich_pending** (LLM solo para extraer
   skills de la descripción). Se descartó porque `M_sec` con peso 0.15 y sin
   skills secundarias es aceptable, y se puede reintroducir en el futuro
   con heurística ligera sin LLM.

## Consequences

### Positivas
- **0 tokens LLM** gastados en enrichment por oferta nueva (antes 1 llamada
  a gemma4 con context 8192)
- **Scoring más simple y transparente**: M_core/M_sec miden presencia de
  skills, F_exp mide profundidad vía experience_min del scraper
- **Código más pequeño**: ~120 líneas eliminadas de fetch.py, ~30 de evaluate.py
- **Pipeline más rápido**: el fetch ya no espera a gemma4 para enrichment
- **Sin regresión en scores**: `role_level_label` era un proxy ruidoso que
  ya tenía default "mid" el 67% del tiempo

### Negativas
- **`M_sec` siempre 0** para ofertas sin skills secundarias (solo core del
  `<dl>`). El impacto en score es acotado por el peso 0.15 de W_SEC.
- **Perdemos extracción de skills desde descripción libre**. Skills que
  aparecen solo en el texto (no en el `<dl>` de Requisitos) no se capturan.
  Aceptable porque son "nice to have" por definición.
- **Ofertas sin `experience_min`** (campo NULL) no tendrán diferenciación
  de profundidad. Es el mismo comportamiento que antes (el LLM defaultaba a "mid"
  para experience_min=0, que es el mismo resultado que L binario + F_exp=1.0).

### Supersedes
Este ADR modifica parcialmente ADR-008 (scoring determinista con level
multipliers) y ADR-010 (mención a 3-phase fetch que ahora es 2-phase).
Los ADR originales se mantienen como registro histórico.

### Tests
203 tests passing, 0 regresiones.
