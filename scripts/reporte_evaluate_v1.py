"""Generate T-5 v1 report: evaluate results with technical, HR and final prompts."""

from __future__ import annotations

import html
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "jobs.db"
REPORT_PATH = PROJECT_ROOT / "reports" / "testing" / "05-evaluate-v1.html"


def esc(text: str) -> str:
    return html.escape(text or "")


def fmt_json(raw: str) -> str:
    if not raw:
        return ""
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(obj, dict):
            return " ".join(
                f'<span class="kv"><b>{esc(k)}:</b> {esc(str(v))}</span>'
                for k, v in obj.items()
            )
        if isinstance(obj, list):
            return " ".join(f'<span class="kv">{esc(str(i))}</span>' for i in obj)
        return esc(str(obj))
    except (json.JSONDecodeError, TypeError):
        return esc(raw)


FLAG_COLORS = {
    "core": {"bg": "#e8f5e9", "text": "#2e7d32", "border": "#2e7d32"},
    "adjacent": {"bg": "#fff8e1", "text": "#f57f17", "border": "#f57f17"},
    "stretch": {"bg": "#fce4ec", "text": "#c62828", "border": "#c62828"},
    "temporal": {"bg": "#f3e5f5", "text": "#7b1fa2", "border": "#7b1fa2"},
}

BLOCK_COLORS = {
    "requisito_imposible": {"bg": "#d32f2f", "text": "#fff"},
    "practicas": {"bg": "#f57c00", "text": "#fff"},
    "otro": {"bg": "#757575", "text": "#fff"},
}

SCORE_BG = [
    (75, "#e8f5e9"),
    (55, "#fff8e1"),
    (35, "#fff3e0"),
    (0, "#fce4ec"),
]


def score_color(score: int) -> str:
    for threshold, color in SCORE_BG:
        if score >= threshold:
            return color
    return "#fce4ec"


def flag_badge(flag: str) -> str:
    fc = FLAG_COLORS.get(flag, FLAG_COLORS["stretch"])
    return f'<span class="fl" style="background:{fc["bg"]};color:{fc["text"]};border-color:{fc["border"]}">{flag}</span>'


def block_badge(block: str | None) -> str:
    if not block:
        return ""
    bc = BLOCK_COLORS.get(block, BLOCK_COLORS["otro"])
    return f'<span class="bl" style="background:{bc["bg"]};color:{bc["text"]}">{block}</span>'


def build_report() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT o.id, o.title, o.company_name, o.city, o.work_mode,
                  o.description_clean, o.skills_required,
                  o.relevance_flag, o.role_normalized,
                  e.match_score, e.recommendation,
                  e.skills_hard_match, e.experience_match,
                  e.education_match, e.location_match,
                  e.trajectory_coherence, e.recency_relevance,
                  e.market_competitiveness, e.penalty, e.penalty_breakdown,
                  e.environment_compatibility, e.hr_concerns,
                  e.strengths, e.red_flags, e.gemma_verdict, e.interview_prep,
                  e.relevance_validation, e.relevance_corrected,
                  e.relevance_reasoning, e.apply_block, e.apply_block_reason,
                  e.llm_apply_signal, e.evaluated_at
           FROM offers o
           JOIN offer_evaluations e ON e.offer_id = o.id
           WHERE o.id BETWEEN 226 AND 242
             AND e.id = (SELECT MAX(e2.id) FROM offer_evaluations e2 WHERE e2.offer_id = o.id)
           ORDER BY e.match_score DESC"""
    ).fetchall()
    conn.close()

    scores = [r["match_score"] or 0 for r in rows]
    total = len(rows)
    avg_score = sum(scores) // total if total else 0
    rec_dist = Counter(r["recommendation"] or "unknown" for r in rows)

    cards_html = ""
    for i, row in enumerate(rows, 1):
        oid = row["id"]
        score = row["match_score"] or 0
        rec = row["recommendation"] or ""
        sc = score_color(score)
        org_flag = row["relevance_flag"] or ""
        rev_val = row["relevance_validation"] or ""
        rev_cor = row["relevance_corrected"] or ""
        rev_rea = row["relevance_reasoning"] or ""
        block = row["apply_block"]
        block_reason = row["apply_block_reason"] or ""
        verdict = row["gemma_verdict"] or ""
        strengths = row["strengths"] or ""
        red_flags = row["red_flags"] or ""
        hr_concerns = row["hr_concerns"] or ""
        interview_prep = row["interview_prep"] or ""
        env_comp = row["environment_compatibility"] or ""
        penalty_bd = row["penalty_breakdown"] or ""
        company = row["company_name"] or ""
        city = row["city"] or ""
        role = row["role_normalized"] or ""

        skills_hard = row["skills_hard_match"] or 0
        exp_match = row["experience_match"] or 0
        edu_match = row["education_match"] or 0
        loc_match = row["location_match"] or 0
        traj = row["trajectory_coherence"] or 0
        recency = row["recency_relevance"] or 0
        market = row["market_competitiveness"] or 0
        penalty = row["penalty"] or 0

        bloque_a = skills_hard + exp_match + edu_match + loc_match
        bloque_b = traj + recency + market

        flag_display = flag_badge(org_flag)
        if rev_val == "corrected" and rev_cor:
            flag_display += f' → {flag_badge(rev_cor)}'
        elif rev_val == "corrected":
            flag_display += f' <span class="rv">(corregido)</span>'

        cards_html += f"""
<article class="card" style="border-left:4px solid {sc};">
  <header class="card-h" onclick="toggleCard({oid})">
    <span class="num">{i}</span>
    <div class="info">
      <div class="ti">{esc(row["title"])}</div>
      <div class="meta">{esc(company)} &middot; {esc(city)} &middot; <strong>{esc(role)}</strong></div>
    </div>
    <div class="tags">
      <span class="sc" style="background:{sc}"><b>{score}</b>/100</span>
      <span class="rec">{esc(rec)}</span>
      {block_badge(block)}
      <span class="arr" id="ar-{oid}">&#9660;</span>
    </div>
  </header>
  <div class="body" id="b-{oid}">
    <div class="split">
      <section>
        <h4>Bloque A — Técnico (60 pts)</h4>
        <table class="dt">
          <tr><td>Skills hard match</td><td class="r">{skills_hard}/30</td></tr>
          <tr><td>Experience match</td><td class="r">{exp_match}/20</td></tr>
          <tr><td>Education match</td><td class="r">{edu_match}/10</td></tr>
          <tr><td>Location match</td><td class="r">{loc_match}/5</td></tr>
          <tr class="total"><td>Total bloque A</td><td class="r">{bloque_a}/65</td></tr>
        </table>
      </section>
      <section>
        <h4>Bloque B — HR (40 pts)</h4>
        <table class="dt">
          <tr><td>Trajectory coherence</td><td class="r">{traj}/15</td></tr>
          <tr><td>Recency relevance</td><td class="r">{recency}/15</td></tr>
          <tr><td>Market competitiveness</td><td class="r">{market}/5</td></tr>
          <tr class="total"><td>Total bloque B</td><td class="r">{bloque_b}/35</td></tr>
        </table>
      </section>
    </div>
    <section>
      <h4>Penalty</h4>
      <div class="dt-line"><span class="pv">-{penalty}</span> / 25 &middot; {fmt_json(penalty_bd)}</div>
    </section>
    <section>
      <h4>Score final: <span class="sc" style="background:{sc};padding:2px 10px;border-radius:12px;"><b>{score}</b>/100 &middot; {esc(rec)}</span></h4>
      <div class="dt-line">A + B - penalty = {bloque_a} + {bloque_b} - {penalty} = {bloque_a + bloque_b - penalty} → clamp(0,100) = {score}</div>
    </section>
    <section>
      <h4>Relevance flag</h4>
      <div class="dt-line">
        Original: {flag_badge(org_flag)}
        &middot; Validación: <span class="rv">{esc(rev_val)}</span>
        {f'→ {flag_badge(rev_cor)}' if rev_cor else ''}
        {f'<br><em>{esc(rev_rea)}</em>' if rev_rea else ''}
      </div>
    </section>
    {'<section><h4>Bloqueo de aplicación</h4><div class="dt-line">' + block_badge(block) + ' ' + esc(block_reason) + '</div></section>' if block else ''}
    <section>
      <h4>Entorno</h4>
      <div class="dt-line">Compatibilidad: <strong>{esc(env_comp)}</strong></div>
    </section>
    <section>
      <h4>Strengths</h4>
      <div class="list">{fmt_json(strengths) if strengths else '—'}</div>
    </section>
    <section>
      <h4>Red flags</h4>
      <div class="list">{fmt_json(red_flags) if red_flags else '—'}</div>
    </section>
    <section>
      <h4>HR concerns</h4>
      <div class="list">{fmt_json(hr_concerns) if hr_concerns else '—'}</div>
    </section>
    <section>
      <h4>Interview prep</h4>
      <div class="list">{fmt_json(interview_prep) if interview_prep else '—'}</div>
    </section>
    <section>
      <h4>Veredicto final</h4>
      <div class="ver">{esc(verdict)}</div>
    </section>
  </div>
</article>"""

    dist_html = "".join(
        f'<div class="st"><div class="n">{rec_dist.get(label, 0)}</div><div class="l">{label}</div></div>'
        for label in ["Prioritario", "Aplicar", "Con expectativas bajas", "No aplicar"]
    )

    evaluated_at = (rows[0]["evaluated_at"] if rows else datetime.now().strftime("%Y-%m-%d %H:%M")).split(".")[0]

    html_out = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>T-5 v1 — Evaluate con evaluate_final</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0 }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  max-width: 1100px; margin: 2em auto; padding: 0 1.5em;
  background: #f0f2f5; color: #1a1a2e; font-size: 15px; line-height: 1.5
}}
h1 {{ font-size: 1.3rem; font-weight: 700; margin-bottom: 0.15em }}
.sub {{ color: #666; font-size: 0.85rem; margin-bottom: 1em }}
a {{ color: #1565c0; text-decoration: none }}
a:hover {{ text-decoration: underline }}

.stats {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 1em }}
.st {{
  background: #fff; border-radius: 10px; padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); flex: 1; min-width: 90px; text-align: center
}}
.st .n {{ font-size: 1.5rem; font-weight: 800; color: #1a1a2e }}
.st .l {{ font-size: 0.7rem; color: #888; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.5px }}

.card {{
  background: #fff; border-radius: 10px; margin-bottom: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06); overflow: hidden
}}
.card-h {{
  display: flex; align-items: center; padding: 12px 16px;
  cursor: pointer; gap: 12px; transition: background 0.12s
}}
.card-h:hover {{ background: #fafafa }}
.num {{
  background: #37474f; color: #fff; width: 28px; height: 28px;
  border-radius: 50%; display: flex; align-items: center;
  justify-content: center; font-size: 0.75rem; font-weight: 700; flex-shrink: 0
}}
.info {{ flex: 1; min-width: 0 }}
.ti {{ font-weight: 600; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis }}
.meta {{ font-size: 0.78rem; color: #888; margin-top: 1px }}
.tags {{ display: flex; align-items: center; gap: 6px; flex-shrink: 0 }}
.arr {{ font-size: 0.7rem; color: #bbb; transition: transform 0.2s; margin-left: 2px }}

.sc {{
  padding: 3px 10px; border-radius: 20px; font-size: 0.78rem;
  font-weight: 700; letter-spacing: 0.3px
}}
.rec {{
  padding: 3px 10px; border-radius: 20px; font-size: 0.7rem;
  background: #37474f; color: #fff; font-weight: 600; letter-spacing: 0.3px
}}
.fl {{
  padding: 3px 10px; border-radius: 20px; font-size: 0.72rem;
  font-weight: 700; border: 1.5px solid; letter-spacing: 0.3px
}}
.bl {{
  padding: 3px 10px; border-radius: 20px; font-size: 0.72rem;
  font-weight: 700; letter-spacing: 0.3px
}}
.rv {{ font-size: 0.78rem; color: #555; font-style: italic }}

.body {{ padding: 0 16px 16px; border-top: 1px solid #eee; display: none }}
.body section {{ margin-top: 12px }}
.body h4 {{
  font-size: 0.68rem; color: #888; text-transform: uppercase;
  letter-spacing: 0.6px; margin-bottom: 4px; font-weight: 600
}}

.split {{ display: flex; gap: 12px; flex-wrap: wrap }}
.split section {{ flex: 1; min-width: 200px }}

.dt {{ width: 100%; font-size: 0.82rem; border-collapse: collapse }}
.dt td {{ padding: 3px 6px }}
.dt .r {{ text-align: right; font-weight: 600 }}
.dt .total {{ border-top: 1px solid #ddd; font-weight: 700 }}

.dt-line {{
  background: #f9f9f9; border: 1px solid #eee; border-radius: 6px;
  padding: 8px 12px; font-size: 0.85rem; line-height: 1.5
}}
.pv {{ font-weight: 700; color: #c62828 }}

.list {{
  display: flex; flex-wrap: wrap; gap: 5px
}}
.kv {{
  background: #e8eaf6; color: #283593; border-radius: 14px;
  padding: 3px 11px; font-size: 0.78rem; font-weight: 500
}}

.ver {{
  background: #fff8e1; border-left: 3px solid #ffb300; border-radius: 4px;
  padding: 10px 12px; font-size: 0.85rem; line-height: 1.5;
  max-height: 240px; overflow-y: auto
}}
</style>
</head>
<body>
<h1>T-5 v1 — Evaluate con evaluate_final</h1>
<p class="sub">{evaluated_at} &middot; {total} ofertas &middot; gemma4:e4b &middot; score medio: {avg_score}/100
&middot; <a href="04-classifier-v6.html">T-4 v6 classifier</a> &middot; <b>v1</b></p>

<div class="stats">
  <div class="st"><div class="n">{total}</div><div class="l">Evaluadas</div></div>
  <div class="st"><div class="n">{avg_score}</div><div class="l">Score medio</div></div>
  {dist_html}
</div>

{cards_html}

<script>
function toggleCard(id) {{
  var b = document.getElementById('b-' + id);
  var ar = document.getElementById('ar-' + id);
  if (b.style.display === 'block') {{
    b.style.display = 'none';
    ar.innerHTML = '&#9660;';
  }} else {{
    b.style.display = 'block';
    ar.innerHTML = '&#9650;';
  }}
}}
</script>
</body>
</html>"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html_out, encoding="utf-8")
    print(f"Reporte v1 generado: {REPORT_PATH}")
    print(f"  Total: {total}, Score medio: {avg_score}")
    print(f"  Distribución: {dict(rec_dist)}")


if __name__ == "__main__":
    build_report()
