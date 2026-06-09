# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-08
**Fase activa:** Dashboard — Sistema de caducidad de ofertas + seguimiento de aplicaciones.

**Cambios de esta sesión:**

1. **Pipeline ejecutado:** 30 ofertas nuevas, 30 evaluadas, 0 errores, avg 0.429, Telegram enviado. ✅
2. **Sistema de caducidad de ofertas (30 días):** Nuevo filtro "Ocultar ofertas >30 días" checked por defecto en pestaña Ofertas. Badge de antigüedad (🟢🟡🟠🔴⚫) en columna "Publicado". Sin cambios en server.py. ✅
3. **Sistema de seguimiento en Aplicaciones:** Badge de follow-up (Esperando/Follow-up/Insistir/Descartar) según días desde applied_at. Badge "🔔 Acción vencida" si next_action_date pasada. ✅
4. **Tabla de Seguimiento en Monitor:** Nueva sección debajo del embudo con KPIs (Total/Follow-up/Urgentes/Vencidas) + tabla con columnas Seguimiento→Oferta→Estado→Apl. hace→Acción→Contacto→Score. Ordenada por urgencia. Botón 🔍 abre modal de detalle. Fetch compartido con renderAppFunnel (sin duplicación). ✅
5. **Docs actualizados:** HANDOFF.md.

**Próximo paso — Multi-perfil vía `PERFIL_PATH` env var:**

1. Modificar 4 archivos (run.py, evaluate.py, role_classifier.py, keyword_generator.py) para leer `PERFIL_PATH` del entorno
2. Añadir `PERFIL_PATH` a `query_params` en `_persist_run()`
3. Crear `profiles/test/PERFIL.md` con CV sintético distinto
4. Ejecutar: `DB_PATH=data/test.db PERFIL_PATH=profiles/test/PERFIL.md python src/pipeline/run.py --skip-cv-check --dry-run`
5. Evaluar generalización del modelo

**Pendiente (futuro):**
- T-5h Fase 2 (branding + microcopy)
- Fase 4 (role_discovery, market_signals, strategic_advisor)

**Bloqueados:** ninguno
**Tests:** 171 passing ✅
