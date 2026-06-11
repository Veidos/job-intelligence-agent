# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-11
**Fase activa:** ADR-017 — Eliminación de Phase 3 enrich_pending y role_level_label.

## Cambios de la sesión actual (2026-06-11)

### fetch.py — Phase 3 eliminada
- `enrich_pending()` eliminada — el scraper proporciona todos los campos estructurados directamente del HTML
- Skills del `<dl>` "Conocimientos" van directamente a `core` en `_upsert_offer_from_scraper()`
  (antes iban a `secondary` esperando reclasificación del LLM)
- `enriched_at` se setea en el mismo upsert (INSERT y UPDATE con COALESCE en UPDATE)
- `--enrich-only` eliminado del CLI
- Import de `cleaner.py` eliminado

### evaluate.py — role_level_label eliminado, L binario
- `compute_skill_score()` ya no acepta `role_level_label`: L = 1.0 si presente, 0.0 si no
- `run_evaluate()` ya no pasa `role_level_label` a compute_skill_score
- `get_pending_offers()`: `o.role_level_label` eliminado del SELECT
- `level_multiplier()`, `LEVEL_ORDINAL`, `ROLE_LEVEL_TO_SKILL_LEVEL` eliminados (código muerto)

### Datos que validaron la decisión
- `experience_min` del scraper coincidía al 100% con el valor del LLM
- Ninguna skill en DB tenía `level_required` explícito
- `role_level_label` era 67% "mid" — proxy ruidoso

### Docs y ADR
- ADR-017 creado documentando el cambio completo
- MEMORIES.md actualizado (stale references corregidas, nueva sección)
- PIPELINE.md actualizado (Phase 3 eliminada, --enrich-only eliminado)
- RATING.md actualizado (sección "Skills: binary presence")
- scraper_lab/reparse_offers.py: import de enrich_pending eliminado

### Tests
- **203 tests passing, 0 regresiones**
- ruff format: 28 files OK
- ruff check: solo errores pre-existentes E402 (migrate.py, server.py)

### Bloqueadores
- Ninguno

### Próximos pasos
- T-5h Fase 2 (branding + microcopy dashboard)
- Fase 4 (role_discovery, market_signals, strategic_advisor)
- Extraer languages, sector, workday como columnas en offers (si se necesitan en scoring)
