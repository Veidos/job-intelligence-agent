# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-05-30
**Fase activa:** T-5 (evaluate.py) — Batch 1 completado, Batch 2 (otras 5 ofertas) pendiente

**Último completado:**
- ADR-012: 3 fixes en evaluate.py — candidate_years como span desde fechas, educación como skills, partial save + upsert
- Prompt evaluate_final(): añadido "titulación académica obligatoria que el candidato no posee" como ejemplo de requisito_imposible
- Batch 1 de 5 ofertas (IDs 348, 338, 336, 333, 313) completado con 0 errores
- ID 336 (Rioglass core): score subió de 0.34 a 0.49 tras incluir educación en skills_map
- ID 338 (TRAGSA AEMET): detecta apply_block=requisito_imposible por Máster Oficial
- ID 348 (TRAGSA falsa core): final LLM corrigió relevance_flag a stretch, score 0.18 filtra
- Documentación actualizada: ADR-012 creado, ADR-006 actualizado, RATING.md, MEMORIES.md, HANDOFF.md

**Batch 2 propuesto (validar antes de lanzar las 92):**

| ID | Flag | Role | Empresa | Gap | Nivel | Escenario |
|----|------|------|---------|-----|-------|-----------|
| 326 | stretch | bi_analyst | Sagalés | seniority | mid | 4 tech matches, ver si alcanza "Aplicar" |
| 334 | adjacent | ml_engineer | PELAYO | herramienta | mid | ML real + salario 42-45k |
| 325 | adjacent | data_engineer | METRICA | herramienta | mid | Primer data_engineer, SQL+Python |
| 315 | stretch | data_analyst | BETWEEN | seniority | mid | 3 tech matches + salario 36-42k |
| 369 | core | process_engineer | Moove Cars | none | senior | Único core restante, senior level |

**Próximo paso:** Ejecutar Batch 2 y validar comportamiento antes de lanzar las 87 ofertas restantes
**Bloqueados:** ninguno
**Tests:** 171 passing
**ADRs a leer para nueva sesión:** ADR-012 (evaluate.py fixes)
**Decisión pendiente:** Tras Batch 2, decidir si lanzar evaluate.py contra las 87 ofertas restantes o hacer más ajustes
