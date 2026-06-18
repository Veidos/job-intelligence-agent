# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-18
**Fase activa:** Botón Detener Pipeline (SIGTERM + status_override + polling)

## Logros de la sesión — Pipeline Stop + Ruff 0

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
