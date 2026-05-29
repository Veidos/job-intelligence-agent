# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-05-28
**Fase activa:** Fase 3 — Testing (T-2 completado)
**Último completado:**
- Reset DB completo + fetch histórico (--max-items 0): 150 raw items, 92 ofertas únicas
- Fix parse_salary: Apify devuelve salary como dict, no string
- Fix enrich: think=True + num_ctx=8192 → 92/92 enriquecidas, 0 errores
- Añadido --enrich-only y --max-items a fetch.py
- Añadido num_ctx como parámetro configurable en ollama_call
- docs/PIPELINE.md actualizado con comandos de referencia
**Próximo paso:** T-3 (fetch_company) o verificación de ofertas enriquecidas, a elección
**Bloqueados:** ninguno
**Tests:** 171 passing (no se tocaron tests en esta sesión)
**ADRs a leer para nueva sesión:** ninguno
**Decisión pendiente:** ninguna
