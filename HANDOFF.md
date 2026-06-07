# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-06
**Fase activa:** Verificación `--since-date _24_HOURS` + fix Bug 2 en `run.py`.

**Cambios de esta sesión:**

1. **Verificado `_24_HOURS` en `build_search_urls()`:** Test unitario confirmó que `&sinceDate=_24_HOURS` aparece en todas las URLs generadas. El filtro viaja correctamente hasta Apify.
2. **Bug 2 corregido — `run.py:159`:** `fetch_company.run()` devuelve `{enriched, linked, skipped, errors, pending}`, no `{new, updated, linked}`. Se cambió el log para usar las keys reales y se añadieron `errors` y `pending` al mensaje.
3. **Nueva funcionalidad — persistencia en `search_runs`:** `run_pipeline()` ahora registra cada ejecución en la tabla `search_runs`. Guarda: timestamp, query_params, offers_fetched, new_offers, evaluated, errors, duration_ms, status. Errores individuales (enrich, send) no detienen el pipeline pero se registran. Testeado con inserción directa ✅.
4. **Pipeline ejecutado:** 25 nuevas ofertas, 30 evaluadas, 0 errores, avg 0.39, Telegram enviado ✅
5. **Nuevo filtro — Ocultar aplicadas:** Checkbox `#filterHideApplied` (checked por defecto) en la barra de filtros de Ofertas. Las ofertas ya aplicadas no aparecen en la tabla. Desmarcar para verlas. Sin cambios en server.py.
6. **Docs actualizados:** PLANS.md (T-7 ✅), MEMORIES.md, DATABASE.md (columnas search_runs), SETUP.md (cron con --skip-cv-check).

**No se tocó `max_items`:** `run_fetch()` conserva su default 30. `--limit` de `run.py` solo controla evaluate y fetch_company.

**Pendiente (futuro):**
- T-5h Fase 2 (branding + microcopy)
- Fase 4 (role_discovery, market_signals, strategic_advisor)
- Tailscale ya instalado por el usuario

**Bloqueados:** ninguno
**Tests:** 171 passing ✅
