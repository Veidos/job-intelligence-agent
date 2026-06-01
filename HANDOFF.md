# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-01
**Fase activa:** T-5e — Dashboard improvements + null normalization

**Último completado:**
- evaluate.py: _normalize_none() para aplicar_block/apply_block_reason (evita string "null"/"None" del LLM)
- generate_dashboard.py: nuevas columnas Modalidad (🏠/🔄/🏢) y 💰 Salario en tabla
- generate_dashboard.py: bloqueo ahora muestra badge verde "Sin bloqueo" en vez de celda vacía
- generate_dashboard.py: location_match eliminado del payload (no se usaba)
- TRAGSA documentado en MEMORIES.md (datos incompletos por ATS custom)
- Dashboard regenerado con cambios visibles

**Próximo paso:** T-6 (send.py) — validar mensaje Telegram correcto
**Bloqueados:** ninguno
**Tests:** 171 passing
**Decisión pendiente:** Tras evaluar send.py, decidir si se pasa a T-7 (run.py ciclo completo)
