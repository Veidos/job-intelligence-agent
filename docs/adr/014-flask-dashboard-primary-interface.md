# ADR-014: Flask Dashboard como Interfaz Principal

**Date:** 2026-06-02
**Type:** `architecture`
**Status:** `active`
**Component:** `src/dashboard/`

---

## Context

El pipeline original terminaba en Telegram: `send.py` enviaba las top 3 ofertas del día a un chat. Esto tenía limitaciones:

1. **Solo 3 ofertas visibles por día.** Las 89 restantes quedaban en la DB sin revisión.
2. **Sin exploración.** No se podía filtrar, ordenar, ni comparar ofertas.
3. **Feedback limitado a comandos `/f1 /f2 /f3`.** Sin interfaz para ver scoring breakdown, skills table, ni dar feedback contextual.
4. **Sin seguimiento de aplicaciones.** No había forma de trackear si ya aplicaste, en qué estado está, o cuándo hacer seguimiento.
5. **Sin análisis.** No había charts, distribución de scores, ni comparativa por empresa.

Necesitábamos una interfaz local más rica que reemplazara a Telegram como interfaz principal, manteniendo Telegram como canal secundario opcional.

---

## Decision

**Crear un dashboard web Flask (SPA con Jinja2 + Chart.js) como interfaz principal del sistema. Telegram pasa a ser secundario.**

### Stack

| Capa | Elección | Por qué no la alternativa |
|------|----------|--------------------------|
| Framework | **Flask** | 9 endpoints locales, sin necesidad de Pydantic/ASGI. FastAPI era overkill. |
| ORM | **Ninguno (sqlite3 directo)** | Consultas simples (SELECT, INSERT, DELETE). SQLAlchemy añadía complejidad sin beneficio. |
| Frontend | **Jinja2 SPA + fetch()** | Datos servidos como JSON API, renderizados en cliente. Sin framework JS. |
| Charts | **Chart.js v4 vía CDN** | Mismo patrón que dashboard legacy. Sin dependencia npm. |
| Timeline | **CSS grid semanal** | FullCalendar es overkill para MVP. CSS puro es más ligero y suficientemente expresivo. |

### API REST (9 endpoints)

| Endpoint | Propósito |
|----------|-----------|
| `GET /api/stats` | KPIs del pipeline |
| `GET /api/offers` | Ofertas evaluadas con filtros |
| `GET /api/offers/<id>` | Detalle completo + feedback + application |
| `GET /api/companies` | Empresas con score promedio |
| `GET/POST /api/feedback` | Listar/crear feedback |
| `GET/POST /api/applications` | Listar/crear aplicaciones |
| `DELETE /api/applications/<id>` | Eliminar aplicación |
| `GET /api/runs` | Historial de ejecuciones |

### Secciones del dashboard

1. **📊 Pipeline** — KPIs + doughnut distribución
2. **📋 Evaluaciones** — Tabla sortable/filterable + modal detalle (scoring breakdown, skills, HR, feedback, application tracker)
3. **🏢 Empresas** — Click → filtra ofertas
4. **💬 Aplicaciones** — Timeline semanal con estados
5. **📈 Estadísticos** — 4 charts (distribución, recomendación×relevancia, señal×recomendación, tendencia)
6. **⚙️ Runs** — Historial del pipeline

### Tabla `applications`

Separada de `user_feedback` porque representan conceptos diferentes:

| Concepto | `user_feedback` | `applications` |
|----------|-----------------|----------------|
| Qué es | Evaluación del match oferta-perfil | Estado de seguimiento de candidatura |
| Quién lo crea | Pipeline (vía Telegram) | Usuario (vía dashboard) |
| Ciclo de vida | Por oferta, una vez | mutable: applied → interviewing → rejected/offer/accepted |
| Propósito | Contexto psicológico para gemma4 | Tracking de proceso de búsqueda |

Columnas: `offer_id`, `applied_at`, `status`, `notes`, `contact_name`, `next_action_date`.

`contact_name` y `next_action_date` se añaden desde el principio (principio "cheap now, expensive later").

---

## Discarded alternatives

- **FastAPI.** Descartado por overkill: 9 endpoints locales sin necesidad de validación compleja, async, ni OpenAPI. Flask + Jinja2 es el nivel de complejidad correcto para un dashboard local de uso personal.
- **SQLAlchemy en dashboard.** Descartado: el dashboard solo lee y escribe con consultas simples. La indirección del ORM no aporta valor y añade una dependencia que no usamos en el resto del pipeline.
- **Telegram como interfaz principal.** Descartado por las limitaciones de UX descritas arriba. Telegram se mantiene como canal secundario para notificaciones rápidas.
- **FullCalendar.** Descartado: la librería es pesada para lo que necesitamos (lista semanal de tarjetas). CSS grid con agrupación por semana es más rápido de cargar y mantener.
- **Framework JS (React/Vue/Svelte).** Descartado: el dashboard es una sola página con 6 secciones. Jinja2 + fetch() + Chart.js vía CDN es suficiente y evita tooling.

---

## Consequences

- **Dashboard es ahora la interfaz principal.** El pipeline termina en `http://localhost:8080`. `send.py` (Telegram) es opcional.
- **`_normalize_none()` se añade a `evaluate.py`.** gemma4 a veces emite `"null"` (string) en lugar de JSON `null` en apply_block/apply_block_reason. El dashboard necesita `null` real para mostrar badges correctamente.
- **Flask añadido como dependencia.** Solo para el dashboard. El resto del pipeline no depende de Flask.
- **T-10 en TESTING.md** cubre verificación de todos los endpoints y secciones del dashboard.
- **location_match eliminado del payload del dashboard.** No filtra en la práctica (correlaciona 1:1 con work_mode) y es puramente informativo.
- **Posible migración futura:** si el dashboard crece en complejidad (WebSockets, auth, multi-usuario), considerar migrar a FastAPI + framework JS. Por ahora, Flask + vanilla JS es la relación costo/beneficio correcta.

---

## References

- ADR-008 — Scoring determinista (location_match como input)
- ADR-013 — Score Rebalance v2 (F_exp sin gap)
- docs/MEMORIES.md — sección "Flask Dashboard (T-5f)"
- docs/PIPELINE.md — Step 4: Dashboard
- docs/TESTING.md — T-10 Dashboard checklist
