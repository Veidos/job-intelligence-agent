# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-09
**Fase activa:** Documentación — Revisión y sincronización post-implementación.

**Cambios de esta sesión:**

1. **Docs revisados y sincronizados:** 13 issues corregidos:
   - MEMORIES.md: qwen2.5 contradicción resuelta (qwen2.5:7b = MODEL_COMPANY), test count 171, columnas 9→10
   - PLANS.md: T-6 marcado completado, columnas 9→10, test count 171
   - PIPELINE.md: paso 2.5 (company enrichment) añadido, hideExpired/follow-up documentados
   - RATING.md: location_match aclarado como columna independiente, NO parte de F_fit
   - CONVENTIONS.md: Fase 6 (Dashboard/Applications) añadida
   - SETUP.md: keyword_generator paths corregidos, --limit flag añadido
   - AGENTS.md: qwen2.5:7b añadido a modelos, send_daily como auto-ejecutado por run.py
   - HANDOFF.md: actualizada para esta sesión
2. **Pipeline ejecutado (sesión anterior):** 30 ofertas nuevas, 30 evaluadas, 0 errores, avg 0.429, Telegram enviado. ✅

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
