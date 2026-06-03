# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-03
**Fase activa:** T-5h — KPIs nuevos en dashboard (6 charts, server.py +1 línea)

**Último completado (hotfix charts skills):**
- Fix: skills charts aplanaban core+secondary juntos → "Máster Oficial" y "Trabajo en equipo" contaminaban el top 12
- `computeSkillsData` ahora itera por categoría (`sd.core` / `sd.secondary`) separadamente
- 3 charts: Skills Core (técnicos), Skills Secundarios/Soft, Gap accionable (solo core)
- Renombrado `chartSkillsDemand` → `chartSkillsCore`, añadido `chartSkillsSecondary`
- server.py: expuestos `salary_min`, `salary_max`, `skill_detail` en `/api/offers` (necesario para charts de skills y salarios)
- dashboard.html: sparkline de actividad semanal en cabecera de Ofertas. Monitor reorganizado con 3 nuevas subsecciones (Mercado de skills, Embudo de aplicaciones) + 7 nuevos canvas (chartSkillsDemand, chartSkillsGap, chartSalaryDist, chartWeeklyActivity, chartWeeklySparkline, chartModelAccuracy, chartAppFunnel)
- style.css: clases `.ofertas-meta`, `.sparkline-wrap`, `.sparkline-label`
- app.js: 6 nuevas funciones + 3 integraciones (renderCharts, nav monitor, loadOffers)
- Fixes: `s.skill || s.name` en skills agg, `!= null` en salary dist, sparkline responsive=false con size explícito

**Próximo paso:** T-5h Fase 2 — Branding + microcopy + tooltips KPIs

**Bloqueados:** ninguno
**Tests:** 171 passing (sin cambios en lógica Python)
