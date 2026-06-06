# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-06
**Fase activa:** Pipeline completado (30 evaluadas, 0 errores, avg 0.42). Dashboard en http://localhost:8080 y accesible vía Tailscale (--host 0.0.0.0).

**Cambios de esta sesión:**

1. **`--since-date` en fetch.py y run.py** — flag CLI con valores InfoJobs reales (`_24_HOURS`, `_7_DAYS`, `_15_DAYS`, `ANY`), default `_24_HOURS`.
2. **`tqdm` en evaluate.py** — barra de progreso con ETA en el loop de evaluación LLM.
3. **`--skip-cv-check` en run.py** — salta el CV freshness check en modo headless/nohup.
4. **requirements.txt** — `tqdm`, `flask` añadidos; `apify-client` duplicado eliminado.
5. **Dashboard re-arrancado** en `0.0.0.0:8080` (accesible desde Tailscale).
6. **`scripts/job-dashboard.service`** — servicio systemd para auto-arranque del dashboard.
7. **docs/SETUP.md** — sección "Acceso Remoto (Tailscale)" añadida.
8. **MEMORIES.md** — `sinceDate` real + lección CV check headless.

**Pipeline ejecutado (PID 8496):** 30 ofertas evaluadas, avg 0.42, 0 errores. Una oferta en rango Priority (0.80). Telegram enviado ✅.

**Pendiente (futuro):**
- T-5h Fase 2 (branding + microcopy)
- Fase 4 (role_discovery, market_signals, strategic_advisor)
- Instalar Tailscale en PC + móvil (pendiente de ti)

**Bloqueados:** ninguno
**Tests:** 171 passing ✅
**Documentación:** HANDOFF.md, MEMORIES.md, PIPELINE.md actualizados
