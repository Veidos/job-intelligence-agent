# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-01
**Fase activa:** T-5 completado — Dashboard de evaluaciones generado

**Último completado:**
- Batch 2 (IDs 326, 334, 325, 315, 369) evaluado — comportamiento consistente
- Evaluate completo contra 82 ofertas restantes — 0 errores, 92/92 evaluadas
- Bug case-sensitive fix en substring match (evaluate.py:259)
- Log de progreso cada 10 ofertas + argparse `--limit` en evaluate.py
- Dashboard `reports/evaluations.html` generado desde `src/pipeline/generate_dashboard.py`
  - KPIs, charts (doughnut + grouped bar), tabla sortable con M_core/M_sec/F_exp/F_fit
  - Panel lateral con fórmula de scoring, tabla de skills por fila, LLM verdicts
  - Fechas contextuales (published_at, evaluated_at, date range, generated_at)
  - Ordenación inteligente: numérica, ordinal (relevance, recommendation, signal), alfabética
- Documentación actualizada: PLANS.md, MEMORIES.md, AGENTS.md, PIPELINE.md, SETUP.md, TESTING.md

**Próximo paso:** T-6 (send.py) — validar mensaje Telegram correcto
**Bloqueados:** ninguno
**Tests:** 171 passing
**Decisión pendiente:** Tras evaluar send.py, decidir si se pasa a T-7 (run.py ciclo completo)
