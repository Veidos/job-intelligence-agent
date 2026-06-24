# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-19
**Fase activa:** Dashboard — indicadores LLM (cards sigma + charts histogram/score-by-signal)

## Logros de la sesión — Refactor indicadores LLM

### Cards LLM reescritas (1 archivo)
| # | Cambio | Archivo |
|---|--------|---------|
| 1 | Card 3: M_core vs M_sec → σ del match_score (discriminación del modelo) | `app.js` |
| 2 | Card 4: HTML inline → refactorizada con helper `indicatorCard()` común | `app.js` |
| 3 | Helper unificado: `rCard()` → `indicatorCard(prefix, value, ...)` | `app.js` |

### Charts reemplazados (2 archivos)
| # | Cambio | Archivo |
|---|--------|---------|
| 1 | Eliminado `chartScoreDist` (bins no-uniformes, color púrpura) | `dashboard.html` + `app.js` |
| 2 | Nueva `renderScoreHistogram()`: 10 bins uniformes 0–100, colores gradiente | `app.js` |
| 3 | Nueva `renderScoreBySignal()`: score medio por yes/maybe/no | `app.js` |
| 4 | Ambas en sección LLM, bajo subtitle "Distribución global de scores" | `dashboard.html` |

### Tests
- **231 tests passing** (0 regresiones)
- **Ruff:** ✅ **0 errores**

### Botón "Detener Pipeline" (6 archivos)

| # | Archivo | Cambio |
|---|---------|--------|
| 1 | `src/db/schema.sql` | Columna `pid INTEGER` en `search_runs` |
| 2 | `src/dashboard/server.py` | `import signal`; guarda `proc.pid` vía UPDATE post-Popen; nuevo `POST /api/pipeline/stop` (solo `os.kill(pid, SIGTERM)`, sin tocar DB); texto "Pipeline interrumpido" en condición de fin de log |
| 3 | `src/pipeline/run.py` | `import signal`; `signal.signal(SIGTERM, ...)` convierte señal en `sys.exit(0)`; `except (SystemExit, KeyboardInterrupt)` → `_persist_run(status_override="stopped")`; nuevo parámetro `status_override` evita race condition con `_watch_process` |
| 4 | `src/dashboard/templates/dashboard.html` | Botón `⏹ Detener` con `id="btnStopPipeline"` |
| 5 | `src/dashboard/static/app.js` | `stopPipeline()`, toggle visibility `btnRunPipeline`/`btnStopPipeline` según `_pipelinePolling` |
| 6 | `src/dashboard/static/style.css` | Clase `.btn-danger` con `var(--red)` |

### Fix Ruff 0 errores
| # | Problema | Solución |
|---|----------|----------|
| 1 | 8 errores pre-existentes (E402 + W291) | E402 → `# noqa` en server/migrate; E402 en backfill_scores → eliminado `sys.path.insert` legacy; W291 → trailing spaces borrados |
| 2 | `import signal` añadido desordenado en server.py | Ruff `--fix` reordenó imports automáticamente |

## Tests
- **231 tests passing** (0 regresiones)
- **Ruff:** ✅ **0 errores**
- **Verificación manual:**
  - ✅ Doble click POST → 1º started, 2º 409
  - ✅ Log polling con offset + run_id
  - ✅ finished=True detectado (texto "Pipeline completado/abortado/interrumpido" + status ≠ running en DB)
  - ✅ `_persist_run` con run_id hace UPDATE correctamente
  - ✅ Botón Detener oculto por defecto, visible durante polling
  - ✅ `POST /api/pipeline/stop` → `os.kill(pid, SIGTERM)` sin UPDATE directo a DB
  - ✅ `signal.signal(SIGTERM, ...)` en run.py convierte señal en `SystemExit`
  - ✅ `status_override="stopped"` evita race condition con `_watch_process`

## Comandos
```bash
python src/dashboard/server.py                # Dashboard en :8080
python src/pipeline/run.py                    # Pipeline completo
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
