# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-02
**Fase activa:** T-5g — Rediseño profesional dashboard (ADR-015)

**Último completado (hotfixes post-T-5g, commit 6248c9c + 1ff3fce):**
- Fix fechas NaN: nuevo helper `_parseDate()` que no duplica sufijo `Z` — `dateFmt()`, `fullDate()`, sort publicado, chart trend corregidos
- Fix skills agrupados por categoría: `skill_detail` es objeto `{core: [...], secondary: [...]}`, no array plano. Normalizado con `Object.entries()` + filas `.skill-cat` con label Core/Secundarias
- Fix modal fallback: `Object.assign(d, o)` ahora es condicional (solo cuando `!d.salary_display`) y parsea JSON strings a arrays
- Fix runs vacío: mensaje "Sin ejecuciones registradas" en vez de tabla vacía
- Todo en app.js + style.css, sin cambios en server.py
- 171 tests passing, ruff clean

**Próximo paso:** T-6 (send.py) — validar mensaje Telegram correcto
**Bloqueados:** ninguno
**Tests:** 171 passing
**Decisión pendiente:** Tras evaluar send.py, decidir si se pasa a T-7 (run.py ciclo completo)
