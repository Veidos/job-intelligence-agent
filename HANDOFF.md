# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-01
**Fase activa:** T-5c completado — Re-evaluación v2 (92/92, 0 errores)

**Último completado:**
- Fix A: experience_min al SELECT (get_pending_offers)
- Opción C: Gap eliminado de F_exp → contexto cualitativo HR
- Location_match determinista (remoto=1.0, híbrido=0.7, presencial fuera=0.2)
- Re-evaluación de 92 ofertas con nueva fórmula (avg 29.8 → 41.4, 10 "Aplicar")
- Dashboard v2 en reports/evaluations-v2.html (v1 preservado como evaluations-v1.html)
- Symlink reports/evaluations.html → evaluations-v2.html

**Próximo paso:** T-6 (send.py) — validar mensaje Telegram correcto
**Bloqueados:** ninguno
**Tests:** 171 passing
**Decisión pendiente:** Tras evaluar send.py, decidir si se pasa a T-7 (run.py ciclo completo)
