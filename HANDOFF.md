# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-16
**Fase activa:** Dashboard fixes + send priority + evaluación resultados

## Cambios de la sesión actual (2026-06-16)

### Pipeline ejecutado
- **Fetch:** 25 ofertas nuevas (fix safari17 aplicado — fingerprint eliminado)
- **Classify:** 25 clasificadas
- **Enrich:** 5 empresas enriquecidas, 0 errores
- **Evaluate:** 25 evaluadas, 0 errores, 0 JSON parse failures (100 LLM calls)
- **Send:** 3 ofertas enviadas a Telegram
- **Pipeline completado:** ~98 min (5892544 ms)

### Fix: safari17 eliminado de _FINGERPRINTS
- **Problema:** `curl_cffi==0.15.0` no soporta `safari17` como fingerprint. `Impersonating safari17 is not supported` al iniciar sesión.
- **Fix:** `_FINGERPRINTS = ["chrome131", "chrome124"]` (línea 658)
- **Archivo:** `src/pipeline/infojobs_scraper.py`

### Fix: Dashboard tabla de ofertas no se renderizaba
- **Problema:** `renderWeeklySparkline()` en `loadOffers()` se ejecutaba ANTES que `recalcOffers()`. Si Chart.js fallaba (CDN incorrecta), la excepción impedía renderizar la tabla.
- **Fix #1:** CDN revertida de unpkg (404) a jsdelivr (200) en `dashboard.html`
- **Fix #2:** `recalcOffers()` ejecutado antes de `renderWeeklySparkline()` en `loadOffers()`
- **Fix #3:** Sparkline envuelto en `try/catch` dentro de `loadOffers()`
- **Fix #4:** `.catch()` añadido a `loadOffers()` con mensaje visible en tabla
- **Fix #5:** Guard profesional `typeof Chart === 'undefined'` en `renderCharts()` con mensaje informativo al usuario
- **Archivos:** `src/dashboard/static/app.js`, `src/dashboard/templates/dashboard.html`

### Fix: Prioridad de envío en send.py
- **Problema:** `get_top_offers()` ordenaba solo por `match_score DESC`. Ofertas con "Con expectativas bajas"/señal "no" podían enviarse antes que "Aplicar"/señal "yes".
- **Fix:** ORDER BY por 3 niveles: `recommendation` → `llm_apply_signal` → `match_score DESC`
- **Archivo:** `src/telegram/send.py`

### Hallazgos de la evaluación de resultados
- **⚠️ Inconsistencia:** `llm_apply_signal='no'` pero `apply_recommendation` dice "Con expectativas bajas" en 5 ofertas. Es comportamiento esperado: el threshold (≥35) gana sobre la señal LLM.
- **✅ Sin falsos negativos:** 0 ofertas con score < 35 que tengan "Aplicar"
- **✅ Calidad LLM:** gemma_verdicts sustantivos, sin boilerplate, específicos por oferta
- **✅ apply_block:** 75% imposibles reales, 25% geográfico (debatible como bloqueo duro)
- **🔴 Bug conocido (no fix):** `send.py` no filtra `apply_block` — oferta bloqueada (score 53, requisito_imposible de geografía) se envió al usuario. Se documenta pero no se corrige por ahora.

### Tests
- **223 tests passing**
- **Ruff:** sin errores

## Comandos principales
```bash
python src/pipeline/run.py                    # Pipeline completo
python src/dashboard/server.py                # Dashboard en :8080
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```

## Próximos pasos naturales
1. Decidir si filtrar `apply_block` en `send.py` (geográfico como bloqueo vs penalización)
2. Lock file (`uv lock` o `pip-compile --generate-hashes`)
3. Coverage de tests para el dashboard
