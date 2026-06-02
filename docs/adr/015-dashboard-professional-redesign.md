# ADR-015: Dashboard Professional Redesign — 4-Section Navigation and UX Improvements

**Date:** 2026-06-02
**Type:** `architecture`
**Status:** `active`
**Component:** `src/dashboard/`

---

## Context

The original Flask dashboard (ADR-014) had 6 flat sections (Pipeline, Evaluaciones, Empresas, Aplicaciones, Estad&iacute;sticos, Runs) with no hierarchy between user-facing and admin views. Several UX issues were identified:

1. **Landing page was "Pipeline"** — monitorizaci&oacute;n del sistema, no la herramienta principal de b&uacute;squeda.
2. **Internal scoring columns (M_core, M_sec, F_exp, F_fit)** exposed in the main table — noise for the end user.
3. **Application tracking duplicated** — the offer detail modal had a full status manager, but a separate "Aplicaciones" section also existed.
4. **6 flat tabs, no hierarchy** — user flows (browse offers, track applications) mixed with admin flows (pipeline stats, chart monitoring).
5. **Modal CTA buried at bottom** — the "Save to applications" action required scrolling past all content.
6. **No offer description in modal** — users had to open InfoJobs to see the full description.
7. **Skills section showed "Undefined"** — fragile `JSON.parse` when `scoring_detail` contained the literal string `"null"`.

---

## Decision

Redesign the dashboard into **4 sections with clear hierarchy**, hiding internal scoring from primary views and adding professional UX patterns.

### New navigation

| Section | Audience | Purpose | Contents |
|---------|----------|---------|----------|
| **Ofertas** (default) | Candidate daily use | Explore and discover opportunities | 9-column sortable/filterable table; detail modal with collapsible scoring, description, and external link |
| **Aplicaciones** | Candidate active tracking | Manage application pipeline | List with inline status `<select>`, expandable notes/contact/next-action panel, "Ver oferta" button |
| **Empresas** | Candidate research | Company intelligence | Table + 2 charts (top 5 by offers, by sector) |
| **Monitor** | Developer / power user | System health | KPIs, charts, pipeline runs — all in a single section with narrative subsections |

### Table columns (9)

```
Score · T&iacute;tulo · Empresa · Modalidad · Publicado · Salario · Recomendaci&oacute;n · Se&ntilde;al · Bloqueo
```

- No M_core/M_sec/F_exp/F_fit (moved to collapsible section in modal)
- Bloqueo at the end (only relevant when "Mostrar bloqueadas" checkbox is on)
- `filterBlocked` default = unchecked (blocked offers hidden by default)

### Modal detail (hierarchical layout)

```
┌─────────────────────────────────────────────┐
│ T&iacute;tulo @ Empresa                           │
│ 💰 Salario · 📍 Ciudad · 🏢 Modalidad        │  ← quick decision
├─────────────────────────────────────────────┤
│ Recomendaci&oacute;n + Se&ntilde;al + Bloqueo + Score     │  ← model verdict
│ [Ver en InfoJobs →]                         │  ← external link
│ ▸ Descripci&oacute;n de la oferta (collapsible) │  ← full context
│ Veredicto HR                                │  ← qualitative context
│ Fortalezas / Concerns / Interview Prep      │  ← preparation
│ ▸ Desglose scoring (collapsible)            │  ← audit only
│ ▸ Skills (collapsible)                      │  ← technical detail
│ Feedback                                    │  ← personal history
├─────────────────────────────────────────────┤
│ [💾 A&ntilde;adir a aplicaciones]  (sticky footer) │  ← CTA always visible
└─────────────────────────────────────────────┘
```

### CTA button states

| State | Button |
|-------|--------|
| Offer not in applications | `[💾 A&ntilde;adir a aplicaciones]` (primary, sticky) |
| Offer already saved | `✓ En aplicaciones · [Ver en Aplicaciones →]` (ghost) |

### Applications list (inline status management)

- List of cards, each with inline `<select>` for status (applied → interviewing → offer → rejected → archived)
- Click card header to expand notes/contact/next-action panel
- "Ver oferta" button calls `openModal(offer_id)` for full detail
- Placeholders with context hints: "Notas sobre el proceso", "Ej: Maria G. — RRHH", tooltip on date for "Pr&oacute;ximo follow-up"
- Kanban board explicitly discarded (low application volume makes column-based view sparse)

### Monitor (narrative sections)

```
Resumen              →  [KPI grid]
Calidad de ofertas   →  [score histogram + recommendation doughnut]
Precisi&oacute;n del modelo →  [recommendation×relevance + signal×recommendation]
Actividad            →  [score trend + pipeline runs collapsible]
```

### Charts added to Empresas

- Top 5 companies by offer count (horizontal bar chart)
- Companies by sector (doughnut chart)
- Computed client-side from `/api/companies` — no backend changes.

### Bug fixes

- **Skills "Undefined":** `JSON.parse(o.scoring_detail)` replaced with `try/catch` because Ollama sometimes emits the literal string `"null"` as `scoring_detail`. The original code used `JSON.parse(o.scoring_detail || '{}')` which parsed `"null"` → `null` → crash on `.skill_detail`.
- **Salary wrapping:** `white-space: nowrap` added to salary column cells.
- **Offer not in OFFERS array:** `openModal()` now falls back to `APP_DATA` when the offer is not in the currently loaded `OFFERS` array (relevant when clicking "Ver oferta" from Aplicaciones after filtering).

---

## Discarded alternatives

| Alternative | Reason for rejection |
|-------------|---------------------|
| **6 flat sections (original)** | No hierarchy; user and admin flows mixed |
| **Kanban board for Aplicaciones** | Low volume (<20 apps) makes 4 columns sparse; list with inline status is denser and more practical |
| **Full application manager in modal** | Duplicates the Aplicaciones section; modal should be "save and go", not "manage here" |
| **Show scoring breakdown by default** | Internal detail confuses non-technical users; collapsible is appropriate |
| **Show blocked offers by default** | Presents overwhelming red badges on first load; user should opt-in |
| **Table with 7 columns (no Publicado/Bloqueo)** | User needs to see publication date and block status at a glance |
| **FullCalendar for timeline** | Overkill for <20 applications; CSS grid week grouping is sufficient |

---

## Consequences

- **4 sections replace 6** — cleaner navigation, clearer purpose per tab.
- **M_core/M_sec/F_exp/F_fit removed from primary view** — hidden behind collapsible `<details>` in modal.
- **Sticky footer CTA ensures "A&ntilde;adir a aplicaciones" is always visible** without scrolling.
- **"Ver oferta" from Aplicaciones avoids data duplication** by calling `openModal()`.
- **Empresas section now has charts** — top 5 by offers + sector distribution.
- **Monitor tells a story** (Resumen → Calidad → Precisi&oacute;n → Actividad) instead of showing random charts.
- **No backend changes** — all improvements are HTML/CSS/JS in `src/dashboard/`.
- **171 tests still passing** — `server.py` unchanged.

---

## References

- ADR-014 — Flask Dashboard como Interfaz Principal (original dashboard)
- ADR-010 — Documentation and Session Handoff System
- `src/dashboard/templates/dashboard.html`
- `src/dashboard/static/app.js`
- `src/dashboard/static/style.css`
