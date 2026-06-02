# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-02
**Fase activa:** T-5g — Rediseño profesional dashboard (ADR-015)

**Último completado:**
- Rediseño completo del dashboard: 4 secciones jerárquicas (Ofertas, Aplicaciones, Empresas, Monitor)
- Tabla 9 columnas: Score, Título, Empresa, Modalidad, Publicado, Salario, Recomendación, Señal, Bloqueo — sin M_core/M_sec/F_exp/F_fit
- Modal con descripción colapsable + enlace InfoJobs + desglose scoring + skills + sticky footer CTA (2-state: "Añadir a aplicaciones" / "En aplicaciones · Ver →")
- Aplicaciones: lista con inline `<select>` de estado, expandable card con notas/contacto/next_action, botón "Ver oferta"
- Empresas: tabla + 2 charts (top5 ofertas, sector doughnut)
- Monitor: narrativo en 4 secciones (Resumen → Calidad → Precisión → Actividad)
- `filterBlocked` desmarcado por defecto (opt-in)
- Bugfixes: skills "Undefined" (try/catch en JSON.parse), salary nowrap, offer fallback desde APP_DATA
- Ningún cambio en server.py — todo HTML/CSS/JS
- Creado ADR-015 documentando la decisión
- 171 tests passing, ruff clean

**Próximo paso:** T-6 (send.py) — validar mensaje Telegram correcto
**Bloqueados:** ninguno
**Tests:** 171 passing
**Decisión pendiente:** Tras evaluar send.py, decidir si se pasa a T-7 (run.py ciclo completo)
