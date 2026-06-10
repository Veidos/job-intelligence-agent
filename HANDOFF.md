# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-10
**Fase activa:** T-A1 completado. Pendiente T-A2 (migración total, eliminar Apify).

**Cambios de esta sesión:**

1.  **`InfoJobsScraper.search()` — añadido `max_items`** con early stop al alcanzar el límite.
2.  **Nueva `_extract_keywords_from_config()`** en `fetch.py` — extrae keywords de `role_hierarchy` sin construir URLs. `build_search_urls()` refactorizada para llamarla internamente (una fuente de verdad).
3.  **Nueva `_upsert_offer_from_scraper()`** — INSERT directo en `offers` sin pasar por `apify_raw_responses`. Skills todas a `secondary` (el LLM reclasifica en `enrich_pending()`). `raw_data` serializado desde `dataclasses.asdict(detail)` para que `enrich_pending()` lo encuentre.
4.  **`enrich_pending()` extendido** — `experience_min` y `education_level` ahora con `COALESCE(?, columna)` para no pisar los datos estructurados del scraper (mismo patrón que `salary_min`/`salary_max` ya tenían).
5.  **Nueva `run_fetch_scraper()`** — orquestador completo sin `APIFY_TOKEN`: `_extract_keywords_from_config()` → scraper.search() → scraper.detail() → `_upsert_offer_from_scraper()` → `enrich_pending()`.
6.  **`--use-apify` flag en `__main__`** — default = scraper propio. `--use-apify` = ruta Apify legacy.
7.  **204 tests pasando** (171 originales + 33 scraper), 0 regresiones.

**Fallo detectado en `--enrich-only`:** Ruta scraper ignora `--since-date` (el scraper no implementa filtro temporal en búsqueda). No bloquea — `sinceDate` en search URL del scraper es mejora futura.

**Próximo paso — T-A2 (futuro):**
- Eliminar completamente el actor Apify y sus dependencias (`apify_client`, `apify_shared`, `apify_raw_responses`)
- Validar contra ofertas reales (comparar campos scraper vs Apify)
- `APIFY_TOKEN` opcional → eliminable de `.env`

**Pendiente (futuro):**
- T-5h Fase 2 (branding + microcopy)
- Fase 4 (role_discovery, market_signals, strategic_advisor)

**Bloqueados:** ninguno
**Tests:** 204 passing (171 + 33 scraper)
