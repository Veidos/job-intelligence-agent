# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-01
**Fase activa:** T-5 completado — Dashboard generado

**Último completado:**
- Batch 2 (IDs 326, 334, 325, 315, 369) evaluado — comportamiento consistente, 0 errores
- Evaluate completo contra 82 ofertas restantes — 0 errores, 92/92 evaluadas
- Bug case-sensitive fix en substring match (evaluate.py:259)
- Log de progreso cada 10 ofertas añadido
- Argparse `--limit` en evaluate.py
- Dashboard generado en `reports/dashboard.html` (static HTML + Chart.js)
  - KPIs, charts de distribución, tabla sortable con M_core/M_sec/F_exp/F_fit
  - Panel lateral con fórmula de scoring, tabla de skills, LLM verdicts

**Próximo paso:** T-6 (send.py) — validar mensaje Telegram correcto
**Bloqueados:** ninguno
**Tests:** 171 passing
**Decisión pendiente:** Tras evaluar send.py, decidir si se pasa a T-7 (run.py ciclo completo)
