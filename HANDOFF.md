# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-03
**Fase activa:** T-5h Fase 1 completa — KPIs implementados. Próximo: Branding + microcopy + tooltips (Fase 2)

**Últimos 10 commits (afdb0d7..a1b6e48):**

1. T-5h plan: dashboard enrichment — planificación inicial
2. **T-5h Fase 1**: 6 KPIs nuevos en dashboard (skills demand/gap, salary dist, weekly activity + sparkline, app funnel, model accuracy). server.py expone skill_detail + salary_min/max
3. **Hotfix:** skills charts separan core/secondary por categoría — "Master Oficial" ya no contamina top técnico. computeSkillsData itera sd.core / sd.secondary separadamente
4. **Top 10:** skills de 12→10, 3 charts en línea (Core, Secondary, Gap)
5. **Altura 320px:** chart-box-tall para labels de skills sin colapsar
6. **Sparkline:** tooltips activados con "Ofertas publicadas", label → "Ofertas publicadas por semana"
7. **Columna Ubicación** en tabla Ofertas + charts ciudad y modalidad en Monitor
8. **Adiós doughnuts:** chartRecDist → bar, chartCityDist → stacked city×modo, chartWorkMode → bar
9. **Layout:** leyenda stacked bar derecha, workMode maintainAspectRatio false
10. **chartCityMode** chart-box-tall para 10 labels sin colapsar

**Próximo paso:** T-5h Fase 2 — Branding JIA + microcopy + tooltips KPIs + interactividad (click chart → filtra tabla)

**Bloqueados:** ninguno
**Tests:** 171 passing
**Documentación:** HANDOFF.md, MEMORIES.md, PIPELINE.md actualizados
