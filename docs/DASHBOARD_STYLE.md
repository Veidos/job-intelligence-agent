# Dashboard Style Guide

> Convenciones visuales para charts, tablas y componentes del dashboard.
> Fuente única de estilo: `src/dashboard/static/style.css`.

---

## 1. Paleta de colores

Todos los colores se definen en `:root` de `style.css`. **No hardcodear hex nuevos** en JS.

| Rol | Variable | Hex | Uso |
|-----|----------|-----|-----|
| Positivo / Sí | `--green` | `#22c55e` | `llm_apply_signal=yes`, score alto, badge `.tag-green` |
| Neutro / Quizás | `--yellow` | `#eab308` | `llm_apply_signal=maybe`, score medio, badge `.tag-yellow` |
| Negativo / No | `--red` | `#ef4444` | `llm_apply_signal=no`, score bajo, badge `.tag-red` |
| Primario / neutral | `--accent` | `#6366f1` | Series sin semántica clara, KPI principal, botón CTA |
| Secundario | `--blue` | `#3b82f6` | Segunda serie neutral, enlaces, etiqueta `.tag-blue` |
| Fondo página | `--bg` | `#0b0b12` | Color de fondo general |
| Superficie | `--surface` | `#14141d` | Fondos de cards, tablas, modales |
| Superficie 2 | `--surface2` | `#1c1c28` | Hover, inputs, secciones de detalle |
| Borde | `--border` | `#22223a` | Bordes de cards, tablas, inputs |
| Texto | `--text` | `#e6e6f0` | Texto principal |
| Texto secundario | `--text2` | `#7a7a90` | Labels, subtítulos, hints |

### Chart.js — aplicación

Chart.js no soporta `var(--green)` en canvas. Usar el hex directamente:

```js
// Bien — mismo hex que --green en style.css
backgroundColor: '#22c55e'

// Mal — hex inventado que no está en la paleta
backgroundColor: '#6daa45'
```

### Categorical palette (3+ series)

Cuando un chart necesita más colores de los que cubre la paleta semántica:

```js
['#6366f1', '#22c55e', '#eab308', '#ef4444', '#3b82f6', '#a855f7', '#14b8a6']
```

Orden: accent → green → yellow → red → blue → purple → teal.

---

## 2. Nomenclatura

| No usar | Usar |
|---------|------|
| M_core | Skills core |
| F_exp | Experiencia |
| location_match / loc | Ubicación |
| market_competitiveness / market / F_fit | Fit cultural |
| environment_compatibility | Ajuste del entorno |
| llm_apply_signal | Señal |
| recommendation | Recomendación |
| score_ge_50 | ≥50 pts |
| sent_via_telegram / sent | Enviadas |

Siempre en español, legible para un reclutador o candidato. Sin acrónimos internos del código.

---

## 3. Charts

### 3.1 Títulos

```js
title: { display: true, text: 'Texto en español', color: '#e4e4e7' }
```

- Siempre `display: true`
- Color `#e4e4e7` (no varía)
- Texto en español, sin acrónimos

### 3.2 Ejes

```js
x: { ticks: { color: '#8a8a95' } }
y: { ticks: { color: '#8a8a95' }, beginAtZero: true }
```

- Ticks siempre `#8a8a95`
- Eje Y siempre `beginAtZero: true` excepto en scatter
- `max: 100` para escalas porcentuales
- Usar `title: { display: true, text: '...' }` con color `#e4e4e7`

### 3.3 Tooltips

```js
tooltip: {
  callbacks: {
    label(ctx) {
      return `${ctx.dataset.label}: ${ctx.raw}`;
    },
  },
}
```

- Incluir dataset label + valor
- Para scatter: `ctx.raw.title`, `ctx.raw.company`, `ctx.raw.score`

### 3.4 Leyenda

Posición determinada por la geometría del chart (referencia: Carbon/IBM, Microsoft Office dataviz guidelines):

| Tipo de chart | Posición | Razón |
|---------------|----------|-------|
| Single dataset | `display: false` | No hay series que distinguir |
| Bar vertical agrupado | `top` | La leyenda no compite con el eje X |
| Bar horizontal (`indexAxis: 'y'`) | `top` | El eje Y ya usa el ancho — `right` comprime el área |
| Scatter | `top` | Los puntos ocupan toda el área |
| Doughnut / Pie | `right` | El círculo deja espacio natural al lado |
| Line multi-serie | `top` | Igual que bar vertical |

```js
// Ejemplo — bar vertical multi-serie
legend: { position: 'top', labels: { color: '#e4e4e7', font: { size: 11 } } }

// Ejemplo — doughnut
legend: { position: 'right', labels: { color: '#e4e4e7', font: { size: 11 } } }

// Ejemplo — single dataset
legend: { display: false }
```

### 3.5 Empty states

Ningún chart debe desaparecer sin dejar rastro. Siempre mostrar mensaje:

```js
if (!data.length) {
  $(canvasId).innerHTML = '<div style="...">— Sin datos</div>';
  return;
}
```

### 3.6 Gridlines

```js
scales: {
  x: { grid: { color: '#22223a', borderDash: [3, 3] } },
  y: { grid: { color: '#22223a', borderDash: [3, 3] } },
}
```

- Color `--border` (`#22223a`), siempre `borderDash: [3, 3]`, nunca sólidas
- Eje Y con gridlines visibles por defecto
- Eje X con gridlines ocultas en charts de barras (ya es default de Chart.js)

### 3.7 Tipos de chart

| Tipo | Cuándo usar |
|------|-------------|
| `bar` (vertical) | Distribuciones, comparaciones entre categorías |
| `bar` (horizontal, `indexAxis: 'y'`) | Muchas categorías (>6), rankings |
| `bar` (stacked) | Composición, partes de un todo |
| `scatter` | Correlación entre dos variables continuas |
| `line` | Series temporales, tendencias |

---

## 4. Tablas

### 4.1 Estructura

```html
<table>
  <thead>
    <tr>
      <th class="num">Score</th>
      <th>Título</th>
      <th class="num">Salario</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td class="num">75</td>
      <td>Oferta</td>
      <td class="num">45k–60k</td>
    </tr>
  </tbody>
</table>
```

### 4.2 Reglas

- Columnas numéricas: clase `num`, alineación derecha
- Columnas de texto: sin clase, alineación izquierda
- Header: `<th>` con color `--text2`
- Hover: `tr:hover td { background: var(--surface2); }` (ya en CSS)
- Score cells: usar clases `.cell-score.high` / `.mid` / `.low`

---

## 5. Orden de datos

Categorías con orden semántico — **nunca orden alfabético**.

```js
// Bien
const bandOrder = { lt_30: 0, grey: 1, gt_50: 2 };
bands.sort((a, b) => bandOrder[a.band] - bandOrder[b.band]);

// Bien — orden explícito en arrays
const recOrder = ['Prioritario', 'Aplicar', 'Con expectativas bajas', 'No aplicar'];

// Mal — asumir ORDER BY de SQL o orden de Object.keys()
```

---

## 6. Guard de Chart.js

Siempre proteger contra Chart.js no cargado:

```js
function renderFoo() {
  if (typeof Chart === 'undefined') return;
  // ...
}
```

---

## 7. Convenciones generales

- `destroyChart(id)` antes de crear un nuevo chart con el mismo canvas
- `charts.{id}` = instancia del chart (para limpiar en destroy)
- `responsive: true, maintainAspectRatio: false` en todos los charts
- `let _pipelineAllOffers = null` — caché de datos compartidos entre funciones del mismo módulo
- Fetch API con `.then()`, no async/await, para consistencia con el código existente
