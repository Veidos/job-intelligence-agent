# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-06
**Fase activa:** Verificación `--since-date _24_HOURS` + persistencia `search_runs` + filtro Ocultar aplicadas.

**Cambios de esta sesión:**

1. **Verificado `_24_HOURS` en `build_search_urls()`:** ✅
2. **Bug corregido — keys de `fetch_company` en `run.py`:** `enriched`/`linked`/`errors`/`pending`. ✅
3. **Persistencia en `search_runs`:** Cada ejecución registrada con query_params, offers_fetched, evaluated, errors, duration_ms, status. ✅
4. **Pipeline ejecutado:** 25 nuevas ofertas, 30 evaluadas, 0 errores, avg 0.39, Telegram enviado. ✅
5. **Filtro "Ocultar aplicadas":** Checkbox checked por defecto. Auto-refresh al añadir/eliminar. Sin cambios en server.py. ✅
6. **Docs actualizados:** PLANS.md (T-7 ✅), MEMORIES.md, DATABASE.md, SETUP.md.

**Próximo paso — Multi-perfil vía `PERFIL_PATH` env var:**

1. Modificar 4 archivos (run.py, evaluate.py, role_classifier.py, keyword_generator.py) para leer `PERFIL_PATH` del entorno
2. Añadir `PERFIL_PATH` a `query_params` en `_persist_run()`
3. Crear `profiles/test/PERFIL.md` con CV sintético distinto
4. Ejecutar: `DB_PATH=data/test.db PERFIL_PATH=profiles/test/PERFIL.md python src/pipeline/run.py --skip-cv-check --dry-run`
5. Evaluar generalización del modelo

**Pendiente (futuro):**
- T-5h Fase 2 (branding + microcopy)
- Fase 4 (role_discovery, market_signals, strategic_advisor)

**Bloqueados:** ninguno
**Tests:** 171 passing ✅
