# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-11
**Fase activa:** Sesión de evaluación y fixes de calidad.

## Cambios de la sesión actual (2026-06-11)

### server.py — SQL injection fix
- `LIMIT ?` con parámetro en vez de `f" LIMIT {limit}"` (riesgo bajo, limit ya era int)

### role_classifier.py — Logging lazy, DB_PATH unificado
- 11 f-string logging → lazy `%s` formatting
- `DB_PATH` hardcodeado eliminado, ahora usa `get_connection()` de `init_db.py`
  (respeta `DB_PATH` env var, consistente con el resto del proyecto)
- `run_classifier()` simplificado: usa `get_connection()` en vez de re-calcular path

### evaluate.py — Default --limit consistente
- `--limit` default cambiado de 10 a 30 (igual que run.py)

### Tests — Dashboard + pre-existing bugs
- 18 tests nuevos para server.py (todos los endpoints REST + HTML serve)
- `test_excluye_ofertas_ya_enviadas` en test_db_evaluations.py: hardcode `offer_id IN (1)` → lookup dinámico
- `test_run_evaluate_procesa_oferta_y_guarda_en_db` en test_evaluate_cassettes.py: hardcode `offer_id = 1` → JOIN por source_id
- `test_multiple_ofertas_procesadas_en_orden` en test_pipeline.py: hardcode `offer_id IN (1, 2)` → JOIN por source_id
- test_feedback.py: unused `mock_save` y unused `pytest` import eliminados

### Resultado final
- **221 tests passing** (203 originales + 18 nuevos), 0 regresiones
- ruff format: 35 files OK
- ruff check: solo errores pre-existentes E402 (migrate.py, server.py)

### Bloqueadores
- Ninguno

### Próximos pasos
- T-5h Fase 2 (branding + microcopy dashboard)
- Fase 4 (role_discovery, market_signals, strategic_advisor)
- Extraer languages, sector, workday como columnas en offers (si se necesitan en scoring)
