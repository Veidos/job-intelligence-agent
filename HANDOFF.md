# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-06
**Fase activa:** Dashboard mejorado — filterByCompany con reset, empresas sortable + Top 5 por score, Score Trend agregado por día.

**Cambios de esta sesión:**

1. **Issue 1 — filterByCompany con reset:** Nueva función `clearCompanyFilter()`, badge "Filtrando por: [Empresa] ✕", `FILTER_COMPANY` global, `switchTab()` extraída.
2. **Issue 2 — Empresas sortable + Top 5 score:** `sortCompanies()`, click handlers en `<th>`, chart `chartEmpTop5Score` con top 5 por avg_score.
3. **Issue 3 — Score Trend por día:** Agregación diaria (agrupa por `evaluated_at` → promedio), en vez de plotear cada oferta individual.
4. **HTML:** +`#filterCompanyInfo`, +`<canvas id="chartEmpTop5Score">`.
5. **Mobile responsive:** breakpoint 480px (nav scroll, 5 cols tabla, bottom sheet modal, touch targets 44px).

**Pendiente (futuro):**
- T-5h Fase 2 (branding + microcopy)
- Fase 4 (role_discovery, market_signals, strategic_advisor)
- Tailscale ya instalado por el usuario

**Bloqueados:** ninguno
**Tests:** 171 passing ✅
**Documentación:** HANDOFF.md, MEMORIES.md, PIPELINE.md actualizados
