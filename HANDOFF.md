# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-15 (v2)
**Fase activa:** Dashboard work_mode canonical fix + doc updates

## Cambios de la sesión actual (2026-06-15)

### Reseteo de DB
- `data/jobs.db` respaldado como `data/jobs.db.v1` (8.7 MB)
- Tablas reseteadas: offers, offer_evaluations, scraper_raw_responses, apify_raw_responses, applications, user_feedback, search_runs
- Companies, search_config, user_settings, user_psychology preservados

### Fixes de scraper (403 Forbidden)
- `delay` aumentado de 2.0s → 4.0s + jitter aleatorio 2.0s
- Fingerprint rotado: `chrome131`/`safari17`/`chrome124` (random)
- `random` import añadido a `infojobs_scraper.py`

### Fix: `_upsert_from_scraper_raw()` filtraba por `run_id`
- `WHERE run_id = ? AND processed = 0` → `WHERE processed = 0`
- Ejecuciones abortadas ya no dejan filas huérfanas

### Fix: `--dry-run` no llegaba a fetch.py
- `run_fetch_scraper()` ahora acepta `dry_run: bool = False`
- En dry_run: no abre conexión, no persiste raw, no upsert
- `run.py` pasa `dry_run` correctamente

### Fix: `--limit-eval 0` y `--limit-enrich 0` como "sin límite"
- `evaluate.py:get_pending_offers()`: `limit=0` → `-1` (SQLite LIMIT -1 = sin límite)
- `fetch_company.py:run()`: batch slice `companies_to_enrich[:limit if limit > 0 else None]`
- `run.py`: help actualizado documentando que `0` = sin límite

### Fix: `published_at` nulo en scraper
- Fallback: si `_extract_published_at()` devuelve `None`, usar `datetime.now().strftime("%Y-%m-%d")`
- Previene acumulación de ofertas sin fecha en dashboard

### Pipeline resultados
- **65 ofertas** fetch + classify (5 core, 20 adjacent, 38 stretch, 2 temporal)
- **14 empresas enriquecidas** → 176 total, 100% pobladas
- **65/65 evaluadas**, 0 errores
- **3 "Aplicar"**: CONSULTOR DATA SCIENCE @ Management Solutions (0.70), Ingeniero/a procesos @ CADE (0.67), Data Scientist/ML Analyst @ Solutia (0.61)
- **Avg score**: 0.253 | 197 LLM calls, 0 fallos JSON
- **Pipeline**: ~3h45min total (ambos runs), Telegram enviado con 3 ofertas

### Dashboard
- Servidor Flask en `http://localhost:8080`
- Todos los endpoints API verificados: stats, offers, companies, runs
- Sin regresiones por zombie columns (ninguna referenciada en dashboard)
- skill_detail, scoring breakdown (M_core, F_exp, etc.) poblados correctamente

### Fix: work_mode desde título (fallback)
- `_parse_header_details()`: si el header no da modalidad, prueba chips/tags alternativos
- Si tampoco, fallback desde el título con `log.warning()` para monitoreo
- 3/8 ofertas sin work_mode corregidas vía re-scrape (scraper_lab/reparse_work_mode.py)

### Fix: skills gap empty state
- `renderSkillsGap()` ahora muestra mensaje informativo cuando gap está vacío
- En vez de return silencioso que dejaba el contenedor gris vacío

### Fix: mapa canónico WORK_MODE_CANONICAL + normalización de variantes scraper
- **Bug #1 (vuelta 1):** `work_mode=""` (6 ofertas) filtrado porque `""` no está en `allowedModes`. **Fix:** guardia `d.work_mode &&`
- **Bug #2 (vuelta 2):** `work_mode="Teletrabajo"` (2 ofertas, IDs 34, 38) filtrado porque `"Teletrabajo"` no está en `allowedModes` (solo `"Solo teletrabajo"`). Causa: el scraper produce `"Teletrabajo"` como variante.
- **Bug #3:** chart `Modalidad de trabajo` mostraba categorías `-` (6 vacías) y `Teletrabajo` (2) mezcladas con Presencial/Híbrido/Remoto
- **Causa raíz:** fragmentación de la normalización de `work_mode`: `workModeLabel()` y `workModeValue()` tenían mapas paralelos e incompletos
- **Fix estructural:** constante única `WORK_MODE_CANONICAL` que mapea las 4 variantes del scraper (`Solo teletrabajo`, `Teletrabajo`, `Híbrido`, `Presencial`) a 3 categorías (`Remoto`, `Híbrido`, `Presencial`). `workModeLabel()`, `workModeValue()` y `allowedModes` comparten el mismo namespace canónico.
- **Fix chart:** `renderWorkModeChart()` filtra solo categorías conocidas via `WORK_MODE_COLORS`, excluye vacíos y variantes no mapeadas
- **Tests:** `test_api_offers_work_mode_null` + `test_api_offers_work_mode_teletrabajo`

### Tests
- **223 tests passing** (20 dashboard + 203 resto) — 2 tests nuevos, 0 regresiones

### Bloqueadores
- Ninguno
