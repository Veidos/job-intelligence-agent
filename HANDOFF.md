# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-18
**Fase activa:** Dashboard → Lanzar Pipeline desde la UI (mutex + log en vivo)

## Logros de la sesión — Lanzar Pipeline desde el Dashboard

### Pipeline execution desde la UI (4 archivos)

| # | Archivo | Cambio |
|---|---------|--------|
| 1 | `src/dashboard/server.py` | `POST /api/pipeline/run` (mutex vía `status='running'` en DB + subprocess + `_watch_process` daemon thread que cierra file descriptor y actualiza status a error si returncode != 0), `GET /api/pipeline/log` (doble condición de fin: texto "Pipeline completado/abortado" en log + status en DB), `PYTHONUNBUFFERED=1` para evitar buffering en pipe |
| 2 | `src/pipeline/run.py` | `--run-id` CLI opcional; `_persist_run()` hace UPDATE si hay run_id, INSERT si no; `try/except` envuelve pipeline para capturar crashes |
| 3 | `src/dashboard/templates/dashboard.html` | Botón "▶ Lanzar Pipeline" + `<pre id="pipelineLog">` en sección Pipeline |
| 4 | `src/dashboard/static/app.js` | `launchPipeline()` (POST + polling), `pollPipelineLog()` (cada 2s con offset + run_id), `stopPipelinePolling()` (reactiva botón y recarga data) |
| 5 | `src/dashboard/static/style.css` | Clase `.btn-primary` |

### Fix post-implementación (detectado en test)
| # | Problema | Solución |
|---|----------|----------|
| 1 | E741 `l` como variable en `api_pipeline_log()` → Ruff pasó de 8 a 9 errores | Renombrado `l` → `line`. Ruff vuelve a 8 errores. |

## Tests
- **231 tests passing** (0 regresiones)
- **Ruff:** 0 errores nuevos (8 pre-existentes: E402 en server/migrate/backfill, W291 en cv_extractor/role_classifier)
- **Verificación manual:**
  - ✅ Doble click POST → 1º started, 2º 409
  - ✅ Log polling con offset + run_id
  - ✅ finished=True detectado (texto en log + status en DB)
  - ✅ `_persist_run` con run_id hace UPDATE correctamente

## Comandos
```bash
python src/dashboard/server.py                # Dashboard en :8080
python src/pipeline/run.py                    # Pipeline completo
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
