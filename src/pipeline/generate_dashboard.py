"""
Generates a static HTML dashboard of all evaluations.
Output: reports/dashboard.html (self-contained, no server needed)
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

DB = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"
OUT = Path(__file__).resolve().parent.parent.parent / "reports" / "dashboard.html"

QUERY = """
SELECT
    o.id,
    o.title,
    o.company_name,
    o.city,
    o.province,
    o.url,
    o.salary_min,
    o.salary_max,
    o.published_at,
    o.work_mode,
    o.role_normalized,
    o.relevance_flag,
    e.match_score,
    e.evaluated_at,
    e.recommendation,
    e.llm_apply_signal,
    e.gemma_verdict,
    e.strengths,
    e.red_flags,
    e.hr_concerns,
    e.interview_prep,
    e.apply_block,
    e.apply_block_reason,
    e.environment_compatibility,
    e.skills_hard_match,
    e.experience_match,
    e.education_match,
    e.location_match,
    e.penalty_breakdown,
    c.sector AS company_sector,
    c.size_range AS company_size
FROM offers o
JOIN offer_evaluations e ON o.id = e.offer_id
LEFT JOIN companies c ON o.company_id = c.id
WHERE o.relevance_flag IS NOT NULL
ORDER BY e.match_score DESC
"""


def _parse_json(val):
    if not val:
        return None
    try:
        return json.loads(val) if isinstance(val, str) else val
    except (json.JSONDecodeError, TypeError):
        return None


def _fmt_salary(row):
    smin = row.get("salary_min")
    smax = row.get("salary_max")
    if smin is not None and smax is not None:
        return f"{round(smin/1000)}k–{round(smax/1000)}k"
    if smin is not None:
        return f"{round(smin/1000)}k"
    return None


def _fmt_url(url):
    if not url:
        return None
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return "https://www.infojobs.net" + u
    return u


def fetch_data():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(QUERY).fetchall()
    conn.close()

    records = []
    for r in rows:
        r = dict(r)
        pb = _parse_json(r["penalty_breakdown"]) or {}
        rec = {
            "id": r["id"],
            "title": r["title"] or "",
            "company_name": r["company_name"] or "",
            "city": r["city"] or "",
            "province": r["province"] or "",
            "location": ", ".join(filter(None, [r["city"], r["province"]])),
            "url": _fmt_url(r["url"]),
            "salary_min": r["salary_min"],
            "salary_max": r["salary_max"],
            "salary_display": _fmt_salary(r),
            "published_at": r["published_at"],
            "evaluated_at": r["evaluated_at"],
            "work_mode": r["work_mode"] or "",
            "role_normalized": r["role_normalized"] or "",
            "relevance_flag": r["relevance_flag"] or "",
            "match_score": r["match_score"] or 0,
            "recommendation": r["recommendation"] or "",
            "llm_apply_signal": r["llm_apply_signal"] or "",
            "apply_block": r["apply_block"],
            "apply_block_reason": r["apply_block_reason"],
            "environment_compatibility": r["environment_compatibility"] or "",
            "company_sector": r["company_sector"] or "",
            "company_size": r["company_size"] or "",
            "experience_match": r["experience_match"],
            "education_match": r["education_match"],
            "location_match": r["location_match"],
            "gemma_verdict": r["gemma_verdict"] or "",
            "M_core": pb.get("M_core"),
            "M_sec": pb.get("M_sec"),
            "F_exp": pb.get("F_exp"),
            "F_fit": pb.get("F_fit"),
            "weights": pb.get("weights"),
            "skill_detail": pb.get("skill_detail", {}),
            "strengths": _parse_json(r["strengths"]) or [],
            "red_flags": _parse_json(r["red_flags"]) or [],
            "hr_concerns": _parse_json(r["hr_concerns"]) or [],
            "interview_prep": _parse_json(r["interview_prep"]) or [],
        }
        # Calculate weighted score from components for verification
        w = rec["weights"] or {"W_CORE": 0.45, "W_SEC": 0.15, "W_EXP": 0.25, "W_FIT": 0.15}
        mc = rec["M_core"] or 0
        ms = rec["M_sec"] or 0
        fe = rec["F_exp"] or 0
        ff = rec["F_fit"] or 0
        calc = round(w.get("W_CORE", 0.45) * mc + w.get("W_SEC", 0.15) * ms
                     + w.get("W_EXP", 0.25) * fe + w.get("W_FIT", 0.15) * ff, 4)
        rec["calc_score"] = calc
        rec["score_diff"] = round(rec["match_score"] / 100.0 - calc, 4) if rec["match_score"] else None
        records.append(rec)

    # Calculate date range from all published_at dates
    dates = []
    for rec in records:
        if rec.get("published_at"):
            try:
                d = rec["published_at"][:10]
                dates.append(d)
            except (IndexError, TypeError):
                pass

    meta = {
        "n_offers": len(records),
        "generated_at": datetime.now().strftime("%d %b %Y %H:%M"),
        "date_range_min": min(dates) if dates else "—",
        "date_range_max": max(dates) if dates else "—",
    }

    return records, meta


def _score_class(s):
    if s >= 55:
        return "green"
    if s >= 35:
        return "yellow"
    return "red"


def _signal_class(s):
    mapping = {"yes": "green", "maybe": "yellow", "no": "red"}
    return mapping.get(s and s.lower(), "gray")


def _size_label(sz):
    mapping = {"gran_empresa": "Gran Empresa", "mediana": "Mediana", "pequena": "Pequeña", "startup": "Startup"}
    return mapping.get(sz, sz or "")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Intelligence — Dashboard de Evaluaciones</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --surface2: #1c2333;
  --border: #30363d;
  --text: #e6edf3;
  --text2: #8b949e;
  --green: #3fb950;
  --green-dim: rgba(63,185,80,.12);
  --yellow: #d29922;
  --yellow-dim: rgba(210,153,34,.12);
  --red: #f85149;
  --red-dim: rgba(248,81,73,.12);
  --orange: #f0883e;
  --accent: #58a6ff;
  --accent-dim: rgba(88,166,255,.12);
  --radius: 8px;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; background:var(--bg); color:var(--text); padding:20px 24px; }
h1 { font-size:20px; margin-bottom:2px; display:flex; align-items:center; gap:10px; }
h1 small { font-size:13px; font-weight:400; color:var(--text2); }
.subtitle { color:var(--text2); font-size:13px; margin-bottom:16px; }

/* KPI */
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; margin-bottom:20px; }
.kpi { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:12px 14px; }
.kpi .label { font-size:10px; text-transform:uppercase; letter-spacing:.6px; color:var(--text2); }
.kpi .value { font-size:22px; font-weight:700; margin-top:2px; }
.kpi .value.green { color:var(--green); }
.kpi .value.yellow { color:var(--yellow); }
.kpi .value.red { color:var(--red); }
.kpi .value.orange { color:var(--orange); }
.kpi .value.blue { color:var(--accent); }

/* Charts row */
.charts-row { display:flex; gap:14px; margin-bottom:20px; }
.chart-card { flex:1; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:14px; min-height:200px; }
.chart-card h3 { font-size:11px; text-transform:uppercase; letter-spacing:.8px; color:var(--text2); margin-bottom:6px; }
.chart-card .chart-wrap { position:relative; height:210px; }

/* Filters */
.filters { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px; align-items:center; }
.filters label { font-size:12px; color:var(--text2); display:flex; align-items:center; gap:4px; }
.filters input, .filters select {
  background:var(--surface); border:1px solid var(--border); border-radius:5px;
  padding:4px 8px; color:var(--text); font-size:12px;
}
.filters input:focus, .filters select:focus { outline:none; border-color:var(--accent); }

/* Stats line */
#statsLine { font-size:12px; color:var(--text2); margin-bottom:6px; }

/* Table */
.table-wrap { overflow-x:auto; border:1px solid var(--border); border-radius:var(--radius); background:var(--surface); }
table { width:100%; border-collapse:collapse; font-size:12px; }
th {
  background:var(--surface2); padding:7px 8px; text-align:left;
  cursor:pointer; user-select:none; white-space:nowrap; position:sticky; top:0; z-index:1;
  font-size:11px; text-transform:uppercase; letter-spacing:.4px; color:var(--text2);
}
th:hover { background:#212d42; }
th .arrow { color:var(--text2); margin-left:3px; font-size:9px; }
td { padding:6px 8px; border-top:1px solid var(--border); vertical-align:middle; }
tbody tr { cursor:pointer; transition:background .12s; }
tbody tr:hover { background:var(--surface2); }
tbody tr.active { background:#1c2a42; }

.cell-score { font-weight:700; font-size:13px; white-space:nowrap; }
.cell-comp { font-size:11px; white-space:nowrap; color:var(--text2); }
.cell-comp strong { color:var(--text); }
.cell-date { font-size:11px; white-space:nowrap; color:var(--text2); font-family:monospace; }

.tag {
  display:inline-block; padding:1px 7px; border-radius:10px; font-size:10px;
  font-weight:600; border:1px solid transparent; white-space:nowrap;
}
.tag.green { color:var(--green); border-color:var(--green); background:var(--green-dim); }
.tag.yellow { color:var(--yellow); border-color:var(--yellow); background:var(--yellow-dim); }
.tag.red { color:var(--red); border-color:var(--red); background:var(--red-dim); }
.tag.blue { color:var(--accent); border-color:var(--accent); background:var(--accent-dim); }
.tag.gray { color:var(--text2); border-color:var(--border); }
.tag.orange { color:var(--orange); border-color:var(--orange); background:rgba(240,136,62,.12); }

/* Panel overlay */
.panel-overlay {
  position:fixed; top:0; right:0; width:560px; max-width:100vw; height:100vh;
  background:var(--surface); border-left:1px solid var(--border);
  transform:translateX(100%); transition:transform .25s ease;
  z-index:100; overflow-y:auto; padding:20px;
}
.panel-overlay.open { transform:translateX(0); }
.panel-overlay .close {
  float:right; background:none; border:none; color:var(--text2); font-size:20px;
  cursor:pointer; padding:2px 6px; line-height:1; border-radius:4px;
}
.panel-overlay .close:hover { background:var(--surface2); color:var(--text); }
.panel-h2 { font-size:16px; margin-bottom:2px; padding-right:28px; line-height:1.3; }
.panel-meta { font-size:12px; color:var(--text2); margin-bottom:12px; }
.panel-meta a { color:var(--accent); }
.panel-section { margin-bottom:14px; }
.panel-section h3 {
  font-size:10px; text-transform:uppercase; letter-spacing:.7px; color:var(--text2);
  margin-bottom:4px; padding-bottom:4px; border-bottom:1px solid var(--border);
}
.panel-section p, .panel-section li { font-size:12px; line-height:1.5; }
.panel-section ul { padding-left:16px; }
.panel-section ul li { margin-bottom:2px; }
.panel-score-formula { font-size:13px; padding:8px 10px; background:var(--surface2); border-radius:5px; margin:6px 0; font-family:monospace; }
.panel-score-formula .highlight { color:var(--accent); font-weight:600; }
.panel-score-formula .op { color:var(--text2); }
.panel-score-formula .result { color:var(--green); font-weight:700; }

/* Skill table inside panel */
.skill-table { width:100%; border-collapse:collapse; font-size:11px; margin-top:4px; }
.skill-table th { background:var(--surface2); padding:4px 6px; font-size:10px; text-transform:uppercase; letter-spacing:.3px; }
.skill-table td { padding:3px 6px; border-top:1px solid var(--border); }
.skill-table .cat-label { font-weight:600; font-size:10px; text-transform:uppercase; color:var(--text2); background:var(--bg); }

/* Backdrop */
.backdrop {
  position:fixed; top:0; left:0; width:100vw; height:100vh;
  background:rgba(0,0,0,.5); z-index:99; display:none;
}

@media(max-width:768px) {
  .kpi-grid { grid-template-columns:repeat(3,1fr); }
  .charts-row { flex-direction:column; }
  .panel-overlay { width:100vw; }
}

/* Utility */
.nowrap { white-space:nowrap; }
</style>
</head>
<body>

<h1>Dashboard de Evaluaciones <small id="totalOffers"></small></h1>
<div class="subtitle">__SUBTITLE_PLACEHOLDER__</div>

<div class="kpi-grid" id="kpiGrid">
  <div class="kpi"><div class="label">Total evaluadas</div><div class="value blue" id="kpiTotal">—</div></div>
  <div class="kpi"><div class="label">Score promedio</div><div class="value" id="kpiAvg">—</div></div>
  <div class="kpi"><div class="label">Aplicar (≥55)</div><div class="value green" id="kpiHigh">—</div></div>
  <div class="kpi"><div class="label">Exp. bajas (35–54)</div><div class="value yellow" id="kpiMid">—</div></div>
  <div class="kpi"><div class="label">No aplicar (&lt;35)</div><div class="value red" id="kpiLow">—</div></div>
  <div class="kpi"><div class="label">Bloqueadas</div><div class="value orange" id="kpiBlocked">—</div></div>
</div>

<div class="charts-row">
  <div class="chart-card">
    <h3>Distribución por recomendación</h3>
    <div class="chart-wrap"><canvas id="chartDist"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Señal de aplicación por recomendación</h3>
    <div class="chart-wrap"><canvas id="chartSignal"></canvas></div>
  </div>
</div>

<div class="filters">
  <label>Score ≥ <input type="number" id="filterScore" min="0" max="100" value="0" style="width:50px;"></label>
  <label>Recomendación <select id="filterRec"><option value="">Todas</option></select></label>
  <label>Señal <select id="filterSignal"><option value="">Todas</option></select></label>
  <label>Relevance <select id="filterRel"><option value="">Todas</option></select></label>
  <label><input type="checkbox" id="filterBlocked" checked> Incluir bloqueadas</label>
  <button id="resetFilters" style="background:var(--surface);border:1px solid var(--border);border-radius:5px;color:var(--text2);padding:4px 10px;font-size:11px;cursor:pointer;">Reset</button>
</div>

<div id="statsLine">Mostrando <strong id="shownCount">0</strong> ofertas</div>

<div class="table-wrap">
<table>
<thead>
<tr>
  <th data-col="match_score" class="nowrap">Score <span class="arrow">▼</span></th>
  <th data-col="M_core" class="nowrap">M_core <span class="arrow"></span></th>
  <th data-col="M_sec" class="nowrap">M_sec <span class="arrow"></span></th>
  <th data-col="F_exp" class="nowrap">F_exp <span class="arrow"></span></th>
  <th data-col="F_fit" class="nowrap">F_fit <span class="arrow"></span></th>
  <th data-col="title">Título <span class="arrow"></span></th>
  <th data-col="company_name">Empresa <span class="arrow"></span></th>
  <th data-col="role_normalized">Rol <span class="arrow"></span></th>
  <th data-col="relevance_flag">Relevance <span class="arrow"></span></th>
  <th data-col="published_at" class="nowrap">📅 Publicado <span class="arrow"></span></th>
  <th data-col="location">Ubicación <span class="arrow"></span></th>
  <th data-col="llm_apply_signal">Señal <span class="arrow"></span></th>
  <th data-col="recommendation">Recomendación <span class="arrow"></span></th>
  <th data-col="apply_block">Bloqueo <span class="arrow"></span></th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>
</div>

<div class="backdrop" id="backdrop" onclick="closePanel()"></div>
<div class="panel-overlay" id="panel">
  <button class="close" id="panelClose">&times;</button>
  <div class="panel-h2" id="panelTitle"></div>
  <div class="panel-meta" id="panelMeta"></div>

  <div class="panel-section">
    <h3>Fórmula de puntuación</h3>
    <div class="panel-score-formula" id="panelFormula"></div>
  </div>

  <div class="panel-section">
    <h3>Desglose de skills</h3>
    <table class="skill-table" id="skillTable">
      <thead><tr><th>Categoría</th><th>Skill</th><th>Nivel req.</th><th>Nivel cand.</th><th>Match</th><th>L</th></tr></thead>
      <tbody id="skillTbody"></tbody>
    </table>
  </div>

  <div class="panel-section">
    <h3>Veredicto gemma4</h3>
    <p id="panelVerdict"></p>
  </div>

  <div class="panel-section" id="panelStrengthsSection">
    <h3>Fortalezas</h3>
    <ul id="panelStrengths"></ul>
  </div>

  <div class="panel-section" id="panelRedFlagsSection">
    <h3>Red Flags</h3>
    <ul id="panelRedFlags"></ul>
  </div>

  <div class="panel-section" id="panelHRConcernsSection">
    <h3>HR Concerns</h3>
    <ul id="panelHRConcerns"></ul>
  </div>

  <div class="panel-section" id="panelInterviewPrepSection">
    <h3>Consejos para entrevista</h3>
    <ul id="panelInterviewPrep"></ul>
  </div>

  <div class="panel-section" id="panelBlockSection" style="display:none;">
    <h3>Bloqueo</h3>
    <p id="panelBlock"></p>
  </div>
</div>

<script>
const DATA = __DATA_PLACEHOLDER__;

/* --- Filters setup --- */
const recSet = new Set(), sigSet = new Set(), relSet = new Set();
DATA.forEach(d => { recSet.add(d.recommendation); sigSet.add(d.llm_apply_signal); relSet.add(d.relevance_flag); });
document.getElementById('filterRec').innerHTML = '<option value="">Todas</option>' + [...recSet].sort().map(v => `<option value="${v}">${v}</option>`).join('');
document.getElementById('filterSignal').innerHTML = '<option value="">Todas</option>' + [...sigSet].sort().map(v => `<option value="${v}">${v}</option>`).join('');
document.getElementById('filterRel').innerHTML = '<option value="">Todas</option>' + [...relSet].sort().map(v => `<option value="${v}">${v}</option>`).join('');

/* --- State --- */
let sortCol = 'match_score', sortDir = -1;
let selectedId = null;
let chartDistInst = null, chartSignalInst = null;

/* --- Helpers --- */
const MONTHS = ['','Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
function dateFmt(iso) {
  if (!iso) return '—';
  const p = iso.slice(0,10).split('-');
  if (p.length !== 3) return '—';
  return `${parseInt(p[2])} ${MONTHS[parseInt(p[1])]}`;
}
function scoreClass(s) { return s >= 55 ? 'green' : s >= 35 ? 'yellow' : 'red'; }
function signalClass(s) { return ({yes:'green',maybe:'yellow',no:'red'})[s && s.toLowerCase()] || 'gray'; }
function recTag(r) {
  const c = r === 'Aplicar' ? 'green' : r === 'Con expectativas bajas' ? 'yellow' : r === 'No aplicar' ? 'red' : 'gray';
  return `<span class="tag ${c}">${r}</span>`;
}
function signalTag(s) {
  if (!s) return '';
  const c = signalClass(s);
  const label = ({yes:'Sí',maybe:'Quizás',no:'No'})[s.toLowerCase()] || s;
  return `<span class="tag ${c}">${label}</span>`;
}
function relTag(r) {
  if (!r) return '';
  const c = r === 'core' ? 'green' : r === 'adjacent' ? 'blue' : r === 'stretch' ? 'yellow' : r === 'temporal' ? 'orange' : 'gray';
  return `<span class="tag ${c}">${r}</span>`;
}
function blockTag(b) {
  if (!b) return '';
  return `<span class="tag red">${b}</span>`;
}
function pct(v) { return v != null ? (v*100).toFixed(0) : '—'; }
function compPct(v, label) {
  if (v == null) return '';
  const c = v >= 70 ? 'green' : v >= 50 ? 'yellow' : 'red';
  return `<span class="cell-comp"><strong>${v}</strong> ${label}</span>`;
}

/* --- SORT configuration --- */
const SORT_ORDERS = {
  relevance_flag: ['temporal','stretch','adjacent','core'],
  recommendation: ['No aplicar','Con expectativas bajas','Aplicar'],
  llm_apply_signal: ['no','maybe','yes'],
};
const NUM_COLS = new Set(['match_score','M_core','M_sec','F_exp','F_fit','skills_hard_match','experience_match']);

/* --- Render --- */
function render() {
  const minScore = parseInt(document.getElementById('filterScore').value) || 0;
  const fRec = document.getElementById('filterRec').value;
  const fSig = document.getElementById('filterSignal').value;
  const fRel = document.getElementById('filterRel').value;
  const includeBlocked = document.getElementById('filterBlocked').checked;

  let filtered = DATA.filter(d => {
    if ((d.match_score || 0) < minScore) return false;
    if (fRec && d.recommendation !== fRec) return false;
    if (fSig && d.llm_apply_signal !== fSig) return false;
    if (fRel && d.relevance_flag !== fRel) return false;
    if (!includeBlocked && d.apply_block) return false;
    return true;
  });

  filtered.sort((a,b) => {
    const col = sortCol;
    if (NUM_COLS.has(col)) {
      return ((a[col] ?? -1) - (b[col] ?? -1)) * sortDir;
    }
    if (SORT_ORDERS[col]) {
      const order = SORT_ORDERS[col];
      const ia = order.indexOf(a[col] ?? '');
      const ib = order.indexOf(b[col] ?? '');
      return (ia - ib) * sortDir;
    }
    const va = String(a[col] ?? '').toLowerCase();
    const vb = String(b[col] ?? '').toLowerCase();
    return va < vb ? -sortDir : va > vb ? sortDir : 0;
  });

  /* KPIs */
  let high = 0, mid = 0, low = 0, blocked = 0, sum = 0;
  DATA.forEach(d => {
    const s = d.match_score || 0;
    if (s >= 55) high++;
    else if (s >= 35) mid++;
    else low++;
    if (d.apply_block) blocked++;
    sum += s;
  });
  document.getElementById('kpiTotal').textContent = DATA.length;
  document.getElementById('kpiAvg').textContent = DATA.length ? (sum / DATA.length).toFixed(1) : '—';
  document.getElementById('kpiHigh').textContent = high;
  document.getElementById('kpiMid').textContent = mid;
  document.getElementById('kpiLow').textContent = low;
  document.getElementById('kpiBlocked').textContent = blocked;

  /* Table */
  document.getElementById('shownCount').textContent = filtered.length;
  document.getElementById('totalOffers').textContent = `· ${filtered.length} mostradas`;

  const tbody = document.getElementById('tbody');
  tbody.innerHTML = filtered.map(d => {
    const s = d.match_score || 0;
    const cls = scoreClass(s);
    const isSel = selectedId === d.id;
    return `<tr data-id="${d.id}" class="${isSel ? 'active' : ''}">
      <td><span class="cell-score ${cls}">${s}</span></td>
      <td><span class="cell-comp">${pct(d.M_core)}</span></td>
      <td><span class="cell-comp">${pct(d.M_sec)}</span></td>
      <td><span class="cell-comp">${pct(d.F_exp)}</span></td>
      <td><span class="cell-comp">${pct(d.F_fit)}</span></td>
      <td>${d.title || ''}</td>
      <td>${d.company_name || ''}</td>
      <td>${d.role_normalized || ''}</td>
      <td>${relTag(d.relevance_flag)}</td>
      <td><span class="cell-date">${dateFmt(d.published_at)}</span></td>
      <td>${d.location || ''}</td>
      <td>${signalTag(d.llm_apply_signal)}</td>
      <td>${recTag(d.recommendation)}</td>
      <td>${blockTag(d.apply_block)}</td>
    </tr>`;
  }).join('');

  tbody.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('click', () => {
      const id = parseInt(tr.dataset.id);
      const d = DATA.find(x => x.id === id);
      if (d) openPanel(d);
      tbody.querySelectorAll('tr').forEach(r => r.classList.remove('active'));
      tr.classList.add('active');
    });
  });
}

/* --- Charts --- */
function renderCharts() {
  /* Distribution doughnut */
  const labels = ['Aplicar', 'Con expectativas bajas', 'No aplicar'];
  const counts = [0, 0, 0];
  DATA.forEach(d => {
    const r = d.recommendation;
    if (r === 'Aplicar') counts[0]++;
    else if (r === 'Con expectativas bajas') counts[1]++;
    else counts[2]++;
  });

  const ctx1 = document.getElementById('chartDist').getContext('2d');
  chartDistInst = new Chart(ctx1, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: counts,
        backgroundColor: ['#3fb950', '#d29922', '#f85149'],
        borderColor: ['#2ea043', '#9e6a03', '#da3633'],
        borderWidth: 1.5,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#8b949e', font: { size: 10 }, padding: 10, boxWidth: 12 } },
        tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.parsed} ofertas (${(ctx.parsed/DATA.length*100).toFixed(1)}%)` } }
      },
      cutout: '60%',
    }
  });

  /* Grouped bar: recommendation × signal */
  const recOrder = ['Aplicar', 'Con expectativas bajas', 'No aplicar'];
  const sigOrder = ['yes', 'maybe', 'no'];
  const sigLabels = { yes: 'Sí', maybe: 'Quizás', no: 'No' };
  const sigColors = { yes: '#3fb950', maybe: '#d29922', no: '#f85149' };

  const matrix = {};
  recOrder.forEach(r => { matrix[r] = {}; sigOrder.forEach(s => { matrix[r][s] = 0; }); });
  DATA.forEach(d => {
    const r = d.recommendation || '';
    const s = (d.llm_apply_signal || '').toLowerCase();
    if (matrix[r] && matrix[r][s] !== undefined) matrix[r][s]++;
  });

  const ctx2 = document.getElementById('chartSignal').getContext('2d');
  chartSignalInst = new Chart(ctx2, {
    type: 'bar',
    data: {
      labels: recOrder,
      datasets: sigOrder.map(sig => ({
        label: sigLabels[sig],
        data: recOrder.map(r => matrix[r][sig]),
        backgroundColor: sigColors[sig],
        borderRadius: 3,
        maxBarThickness: 20,
      }))
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#8b949e', font: { size: 10 }, padding: 10, boxWidth: 12 } },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        x: { stacked: false, grid: { display: false }, ticks: { color: '#8b949e', font: { size: 9 } } },
        y: { beginAtZero: true, stacked: false, grid: { color: '#30363d' }, ticks: { color: '#8b949e', font: { size: 9 }, stepSize: 1 } }
      }
    }
  });
}

/* --- Panel --- */
function openPanel(d) {
  selectedId = d.id;

  document.getElementById('panelTitle').innerHTML = `${d.title || ''} <span style="font-size:13px;color:var(--text2);font-weight:400;">${d.match_score}</span>`;

  const meta = [];
  meta.push(d.company_name || '');
  if (d.city) meta.push(d.city);
  if (d.work_mode) meta.push(d.work_mode);
  if (d.salary_display) meta.push(d.salary_display);
  if (d.company_sector) meta.push(d.company_sector);
  if (d.company_size) meta.push(d.company_size);
  if (d.evaluated_at) meta.push(`✅ ${d.evaluated_at.slice(0,10)}`);
  let metaHtml = meta.join(' · ');
  metaHtml += ` · Score: <strong class="${scoreClass(d.match_score)}">${d.match_score}</strong>`;
  if (d.url) metaHtml += ` · <a href="${d.url}" target="_blank">Ver oferta ↗</a>`;
  document.getElementById('panelMeta').innerHTML = metaHtml;

  /* Formula */
  const w = d.weights || {W_CORE:0.45, W_SEC:0.15, W_EXP:0.25, W_FIT:0.15};
  const mc = d.M_core || 0;
  const ms = d.M_sec || 0;
  const fe = d.F_exp || 0;
  const ff = d.F_fit || 0;
  const calc = Math.round(((w.W_CORE||0)*mc + (w.W_SEC||0)*ms + (w.W_EXP||0)*fe + (w.W_FIT||0)*ff) * 10000) / 10000;
  const stored = (d.match_score || 0) / 100;
  const diff = Math.abs(calc - stored) < 0.001 ? '' : ` <span class="op">(diferencia: ${(stored - calc) >= 0 ? '+' : ''}${(stored - calc).toFixed(4)})</span>`;

  document.getElementById('panelFormula').innerHTML =
    `${pct(mc)} <span class="op">× ${w.W_CORE}</span> <span class="op">+</span> ` +
    `${pct(ms)} <span class="op">× ${w.W_SEC}</span> <span class="op">+</span> ` +
    `${pct(fe)} <span class="op">× ${w.W_EXP}</span> <span class="op">+</span> ` +
    `${pct(ff)} <span class="op">× ${w.W_FIT}</span> ` +
    `<span class="op">=</span> <span class="result">${(calc*100).toFixed(0)}</span>` +
    ` <span class="op">(DB: ${d.match_score})</span>${diff}`;

  /* Skill table */
  const sd = d.skill_detail || {};
  let skillRows = '';
  ['core', 'secondary'].forEach(cat => {
    const skills = sd[cat] || [];
    if (!skills.length) return;
    skillRows += `<tr><td class="cat-label" colspan="6">${cat === 'core' ? 'Core' : 'Secundarias'}</td></tr>`;
    skills.forEach(sk => {
      const present = sk.present ? '✓' : '✗';
      const pClass = sk.present ? 'green' : 'red';
      const lCls = sk.L >= 0.8 ? 'green' : sk.L >= 0.5 ? 'yellow' : 'red';
      skillRows += `<tr>
        <td></td>
        <td>${sk.skill || ''}</td>
        <td>${sk.level_required || '—'}</td>
        <td>${sk.candidate_level || '—'}</td>
        <td style="color:var(--${pClass});font-weight:600;text-align:center;">${present}</td>
        <td style="color:var(--${lCls});font-weight:600;text-align:center;">${sk.L != null ? sk.L.toFixed(2) : '—'}</td>
      </tr>`;
    });
  });
  if (!skillRows) skillRows = '<tr><td colspan="6" style="color:var(--text2);text-align:center;padding:8px;">Sin skills estructuradas</td></tr>';
  document.getElementById('skillTbody').innerHTML = skillRows;

  /* Verdict */
  document.getElementById('panelVerdict').textContent = d.gemma_verdict || 'No disponible';

  /* Lists */
  setList('panelStrengths', d.strengths);
  setList('panelRedFlags', d.red_flags);
  setList('panelHRConcerns', d.hr_concerns);
  setList('panelInterviewPrep', d.interview_prep);

  /* Block */
  const blockSec = document.getElementById('panelBlockSection');
  if (d.apply_block) {
    blockSec.style.display = 'block';
    document.getElementById('panelBlock').innerHTML = `<strong>${d.apply_block}</strong>${d.apply_block_reason ? ': ' + d.apply_block_reason : ''}`;
  } else {
    blockSec.style.display = 'none';
  }

  document.getElementById('panel').classList.add('open');
  document.getElementById('backdrop').style.display = 'block';
}

function setList(id, items) {
  const el = document.getElementById(id);
  const section = el.closest('.panel-section');
  if (!items || !items.length) {
    section.style.display = 'none';
    return;
  }
  section.style.display = 'block';
  el.innerHTML = items.map(s => `<li>${s}</li>`).join('');
}

function closePanel() {
  selectedId = null;
  document.getElementById('panel').classList.remove('open');
  document.getElementById('backdrop').style.display = 'none';
  document.querySelectorAll('#tbody tr').forEach(r => r.classList.remove('active'));
}

/* --- Sorting --- */
document.querySelectorAll('th[data-col]').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.col;
    if (col === sortCol) sortDir *= -1;
    else { sortCol = col; sortDir = col === 'match_score' ? -1 : 1; }
    document.querySelectorAll('th .arrow').forEach(a => a.textContent = '');
    th.querySelector('.arrow').textContent = sortDir === 1 ? '▲' : '▼';
    render();
  });
});

/* --- Filter events --- */
['filterScore','filterRec','filterSignal','filterRel','filterBlocked'].forEach(id => {
  document.getElementById(id).addEventListener('change', render);
  if (document.getElementById(id).type === 'number') {
    document.getElementById(id).addEventListener('input', render);
  }
});
document.getElementById('resetFilters').addEventListener('click', () => {
  document.getElementById('filterScore').value = 0;
  document.getElementById('filterRec').value = '';
  document.getElementById('filterSignal').value = '';
  document.getElementById('filterRel').value = '';
  document.getElementById('filterBlocked').checked = true;
  render();
});

/* --- Close panel --- */
document.getElementById('panelClose').addEventListener('click', closePanel);

/* --- Init --- */
render();
renderCharts();
</script>
</body>
</html>"""


def generate(records: list[dict], meta: dict) -> str:
    subtitle = (
        f"Job Intelligence Agent · {meta['n_offers']} ofertas evaluadas"
        f" · {meta['date_range_min']} – {meta['date_range_max']}"
        f" · Generado: {meta['generated_at']}"
    )
    html = HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", json.dumps(records, ensure_ascii=False, default=str))
    html = html.replace("__SUBTITLE_PLACEHOLDER__", subtitle)
    return html


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log.info("Fetching data from %s", DB)
    records, meta = fetch_data()
    log.info("Fetched %d evaluation records", meta["n_offers"])

    log.info("Generating dashboard HTML")
    html = generate(records, meta)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    log.info("Dashboard written to %s", OUT.resolve())


if __name__ == "__main__":
    main()
