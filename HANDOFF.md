# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-01
**Fase activa:** T-5d — Zombie columns cleanup + test alignment

**Último completado:**
- Identificadas 7 zombie columns en offer_evaluations (education_match, trajectory_coherence, recency_relevance, penalty, company_fit_score, company_green_flags, company_red_flags) — nunca pobladas tras refactor determinista (7a4709b)
- penalty_breakdown → scoring_detail rename
- Migración DB: DROP COLUMN + RENAME COLUMN vía migrate.py
- schema.sql actualizado con schema limpio
- evaluate.py: save_evaluation refactor (params, _COLUMNS, _SET_CLAUSE sincronizados)
- generate_dashboard.py: SELECT sin zombies, scoring_detail aliased
- Tests alineados: 3 test files actualizados (test_db_evaluations, test_db_operations)
- 171 tests passing, 0 lint errors (pre-existing E402 en migrate.py sin config)

**Próximo paso:** T-6 (send.py) — validar mensaje Telegram correcto
**Bloqueados:** ninguno
**Tests:** 171 passing
**Decisión pendiente:** Tras evaluar send.py, decidir si se pasa a T-7 (run.py ciclo completo)
