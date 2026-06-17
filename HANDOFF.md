# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-17
**Fase activa:** Date scope + fallback histórico en send.py

## Cambios de la sesión actual (2026-06-17)

### Pipeline ejecutado (2026-06-16)
- **Fetch:** 27 nuevas (safari17 fix OK)
- **Classify:** 27 clasificadas: 18 stretch, 9 adjacent. 2 roles nuevos (data_governance_analyst, medical_specialist)
- **Enrich:** 8 nuevas, 11 actualizadas, 0 errores
- **Evaluate:** 27 evaluadas, 0 errores, 114 LLM calls, score avg 0.269
- **Send:** 3 ofertas (Ing. industrial 63, Ing. procesos 58, Data Tech Analyst 52)
- **Pipeline:** 107 min

### Fix: Date scope + fallback histórico en send.py
- **Problema:** `get_top_offers()` mezclaba ofertas de distintos días. "Ingeniero de redacción de patentes" (score 36, 2026-06-11, signal=yes) se envió antes que "Data - Technology Analyst Junior" (score 52, 2026-06-16, signal=maybe) porque `llm_apply_signal='yes'` pesaba más que la fecha.
- **Fix:**
  - `get_top_offers(date_scope='latest')` filtra por `MAX(date(fetched_at))` — solo ofertas del día más reciente
  - `get_top_offers(date_scope='all')` mantiene comportamiento anterior (sin filtro de fecha)
  - `send_daily()` intenta `'latest'` primero; si no hay ofertas, cae a `'all'` como fallback histórico
  - Ofertas del fallback llevan `📅 fecha` visible y header "Hoy no hay ofertas nuevas que encajen, pero estas de días anteriores merecen un vistazo:"
  - Si no hay ofertas en absoluto: "Sin ofertas relevantes disponibles."
- **Archivo:** `src/telegram/send.py`
- **3 tests nuevos:** `test_get_top_offers_date_scope_latest`, `test_get_top_offers_date_scope_all`, más el existente `test_top_offers_excluye_bajo_score`

### Tests
- **225 tests passing** (+2)
- **Ruff:** 0 errores nuevos (7 pre-existentes en otros archivos)

## Comandos principales
```bash
python src/pipeline/run.py                    # Pipeline completo
python src/dashboard/server.py                # Dashboard en :8080
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
