# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-05-30
**Fase activa:** Fase 3 → Fase 4 (T-3 + T-4 completados)
**Último completado:**
- Rediseño de fetch_company.py con enriquecimiento via LLM (qwen2.5:7b)
- 68/68 empresas enriquecidas con sector, tamaño, descripción, green/red flags
- Nuevo modelo MODEL_COMPANY = "qwen2.5:7b" en ollama_client.py
- Eliminación de modelos hardcodeados: fetch.py, keyword_generator.py, role_classifier.py ahora usan MODEL_TECHNICAL
- role_classifier.py: añadido think=True + parámetro model en classify_offer()
- 92/92 ofertas clasificadas (30 roles únicos, 19 descubiertos)
- 6 nuevas columnas en companies: llm_description, green_flags, red_flags, llm_confidence, enriched_by_llm_at, llm_model
**Próximo paso:** T-5 (evaluate.py) — evaluar ofertas clasificadas
**Bloqueados:** ninguno (T-3 ✅, T-4 ✅)
**Tests:** 171 passing
**ADRs a leer para nueva sesión:** ninguno
**Decisión pendiente:** ninguna
