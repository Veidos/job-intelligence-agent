# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-05
**Fase activa:** Pipeline en ejecución (PID 8496) — fetch Apify en progreso. Dashboard accesible en http://localhost:8080

**Cambios de esta sesión:**

1. **`--since-date` en fetch.py y run.py** — flag CLI con valores InfoJobs reales (`_24_HOURS`, `_7_DAYS`, `_15_DAYS`, `ANY`), default `_24_HOURS`. `run.py` lo pasa directamente a `run_fetch()`.
2. **`tqdm` en evaluate.py** — barra de progreso con ETA en el loop de evaluación LLM.
3. **`--skip-cv-check` en run.py** — salta el CV freshness check en modo headless/nohup.
4. **MEMORIES.md** — documentación corregida de `sinceDate` + lección sobre falso positivo del CV check en headless.
5. **requirements.txt** — añadido `tqdm==4.68.1`, añadido `flask==3.1.3`, eliminado `apify-client==1.8.1` duplicado.
6. **docs/SETUP.md** — eliminado `pip install flask` manual (ahora en requirements.txt).

**Próximo paso (sesión siguiente):**
1. Verificar resultado del pipeline (revisar `logs/pipeline.log`)
2. Refrescar Dashboard y explorar ofertas nuevas
3. T-5h Fase 2 (branding + microcopy) si procede

**Bloqueados:** ninguno
**Tests:** 171 passing ✅
**Documentación:** HANDOFF.md, MEMORIES.md, PIPELINE.md actualizados
