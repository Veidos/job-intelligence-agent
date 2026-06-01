# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-01
**Fase activa:** T-5f — Megadashboard web (Flask)

**Último completado:**
- nueva tabla `applications` en schema.sql + migrate.py
- servidor Flask en src/dashboard/server.py con API REST completa
- dashboard HTML con 6 secciones: Pipeline, Evaluaciones, Empresas, Aplicaciones, Estadísticos, Runs
- Tabla Evaluaciones con filtros inline, ordenación por columna, modal detalle
- Feedback inline desde el modal (POST /api/feedback)
- Seguimiento de aplicaciones con estados y timeline semanal
- Charts: distribución scores, recomendación×relevance, señal×recomendación, tendencia
- pip install flask como nueva dependencia
- 171 tests passing, ruff clean

**Próximo paso:** T-6 (send.py) — validar mensaje Telegram correcto
**Bloqueados:** ninguno
**Tests:** 171 passing
**Decisión pendiente:** Tras evaluar send.py, decidir si se pasa a T-7 (run.py ciclo completo)
