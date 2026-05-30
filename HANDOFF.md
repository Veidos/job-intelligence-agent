# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-05-30
**Fase activa:** T-5 (evaluate.py) — test en 5 ofertas completado, batch completo pendiente

**Último completado:**
- ADR-012: 3 fixes en evaluate.py — candidate_years como span desde fechas, educación como skills, partial save + upsert
- Prompt evaluate_final(): añadido "titulación académica obligatoria que el candidato no posee" como ejemplo de requisito_imposible
- Test de 5 ofertas (IDs 348, 338, 336, 333, 313) completado con 0 errores
- ID 336 (Rioglass core): score subió de 0.34 a 0.49 tras incluir educación en skills_map
- ID 338 (TRAGSA AEMET): detecta apply_block=requisito_imposible por Máster Oficial
- ID 348 (TRAGSA falsa core): final LLM corrigió relevance_flag a stretch, score 0.18 filtra
- Documentación actualizada: ADR-012 creado, ADR-006 actualizado, RATING.md, MEMORIES.md, HANDOFF.md

**Próximo paso:** T-5 (evaluate.py) — ejecutar batch completo de 92 ofertas
**Bloqueados:** ninguno
**Tests:** 171 passing
**ADRs a leer para nueva sesión:** ADR-012 (evaluate.py fixes)
**Decisión pendiente:** ninguna
