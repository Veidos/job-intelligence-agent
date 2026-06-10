# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-10
**Fase activa:** T-A2 completado. Apify eliminado. Scraper propio es la única ruta de fetch.

**Cambios de esta sesión:**

### Validación (Fase 1 ra)
- Ejecutado `python -m src.pipeline.fetch --max-items 5` → 240 ofertas nuevas
- **Cobertura:** 100% experience_min, 75% education_level, 100% skills_required, 100% enriched_at
- **Skills:** media ~7 por oferta (vs ~1-2 con Apify). LLM reclasifica core/sec desde secondary
- **COALESCE tracing verificado:** logs DEBUG confirman que experience_min y education_level del scraper no se sobrescriben
- **Cero warnings** de parseo en producción

### Fase A — Capa raw inmutable para scraper
1. `schema.sql`: `scraper_raw_responses` con `UNIQUE(offer_id)` (append-only, mismo patrón que `apify_raw_responses`)
2. `migrate.py`: migración para la nueva tabla
3. `fetch.py`: `_persist_scraper_raw()` — INSERT OR IGNORE
4. `fetch.py`: `_upsert_from_scraper_raw()` — lee raw pendientes, upsert, marca processed
5. `fetch.py`: `run_fetch_scraper()` refactorizada a 3 fases (raw → upsert → enrich)

### Fase B — T-A2 (eliminar Apify)
1. Eliminado `ApifyClient` import y `run_fetch()` completa
2. Eliminado flag `--use-apify` del CLI
3. `run.py`: actualizado a `from src.pipeline.fetch import run_fetch_scraper`
4. `requirements.txt`: eliminados `apify_client`, `apify_shared`
5. `apify_raw_responses` preservada como tabla legacy (datos históricos intactos)
6. ADR-016 marcado como `completed`
7. `204 tests pasando` (171 originales + 33 scraper), 0 regresiones

**Próximo paso (futuro):**
- Extraer `languages`, `sector`, `workday` como columnas en `offers` si se necesitan en scoring
- T-5h Fase 2 (branding + microcopy)
- Fase 4 (role_discovery, market_signals, strategic_advisor)

**Bloqueados:** ninguno
**Tests:** 204 passing
