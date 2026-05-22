"""Generate T-4 v6 report: classifier results with directive FASE 2 prompt."""

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
REPORT_PATH = PROJECT_ROOT / "reports" / "testing" / "04-classifier-v6.html"


def esc(text: str) -> str:
    return html.escape(text or "")


def fmt_skills(raw: str) -> str:
    if not raw:
        return ""
    try:
        skills = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        skills = [raw]
    if not isinstance(skills, list):
        skills = [str(skills)]
    return " ".join(f'<span class="sk">{esc(s)}</span>' for s in skills if s)


FLAG_COLORS = {
    "core": {"bg": "#e8f5e9", "text": "#2e7d32", "border": "#2e7d32"},
    "adjacent": {"bg": "#fff8e1", "text": "#f57f17", "border": "#f57f17"},
    "stretch": {"bg": "#fce4ec", "text": "#c62828", "border": "#c62828"},
    "temporal": {"bg": "#f3e5f5", "text": "#7b1fa2", "border": "#7b1fa2"},
}

GAP_COLORS = {
    "seniority": {"bg": "#c62828"},
    "dominio": {"bg": "#e65100"},
    "herramienta": {"bg": "#1565c0"},
    "none": {"bg": "#757575"},
    "": {"bg": "#757575"},
}


def flag_badge(flag: str) -> str:
    fc = FLAG_COLORS.get(flag, FLAG_COLORS["stretch"])
    return f'<span class="fl" style="background:{fc["bg"]};color:{fc["text"]};border-color:{fc["border"]}">{flag}</span>'


def gap_badge(gap: str) -> str:
    gc = GAP_COLORS.get(gap, {"bg": "#757575"})
    return f'<span class="gb" style="background:{gc["bg"]}">{gap or "none"}</span>'


def build_report() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, title, company_name, city, experience_min, description_clean, skills_required,
                  role_normalized, relevance_flag, gap_type, role_reasoning, classification_reasoning
           FROM offers WHERE id BETWEEN 226 AND 242 ORDER BY id"""
    ).fetchall()
    conn.close()

    dist = Counter(r["relevance_flag"] or "unknown" for r in rows)
    gap_dist = Counter(r["gap_type"] or "none" for r in rows)

    cards_html = ""
    for i, row in enumerate(rows, 1):
        oid = row["id"]
        flag = row["relevance_flag"] or ""
        gap = row["gap_type"] or ""
        role = row["role_normalized"] or ""
        role_r = (row["role_reasoning"] or "").strip()
        reasoning = (row["classification_reasoning"] or "").strip()
        company = row["company_name"] or ""
        city = row["city"] or ""
        exp = row["experience_min"]
        if exp is None:
            exp_str = "No especificada"
        elif exp == 0:
            exp_str = "0 años (Junior)"
        else:
            exp_str = f"{exp}+ años"

        desc = (row["description_clean"] or "").strip()
        skills = row["skills_required"] or ""

        fc = FLAG_COLORS.get(flag, FLAG_COLORS["stretch"])

        cards_html += f"""
<article class="card" style="border-left:4px solid {fc['border']};">
  <header class="card-h" onclick="toggleCard({oid})">
    <span class="num">{i}</span>
    <div class="info">
      <div class="ti">{esc(row['title'])}</div>
      <div class="meta">{esc(company)} &middot; {esc(city)} &middot; {exp_str} &middot; <strong>{esc(role)}</strong></div>
    </div>
    <div class="tags">
      {flag_badge(flag)}
      {gap_badge(gap)}
      <span class="arr" id="ar-{oid}">&#9660;</span>
    </div>
  </header>
  <div class="body" id="b-{oid}">
    <section>
      <h4>Skills requeridas</h4>
      <div class="skill-list">{fmt_skills(skills)}</div>
    </section>
    <section>
      <h4>Descripción</h4>
      <div class="desc">{esc(desc)}</div>
    </section>
    <section>
      <h4>role_reasoning</h4>
      <div class="df">{esc(role_r)}</div>
    </section>
    <section>
      <h4>classification_reasoning</h4>
      <div class="rea">{esc(reasoning)}</div>
    </section>
  </div>
</article>"""

    html_out = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>T-4 v4 — Classifier con prompt refactorizado</title>
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

.note {{
  background: #e8eaf6; border: 1px solid #c5cae9;
  border-radius: 8px; padding: 12px 16px; font-size: 0.88rem;
  margin-bottom: 1.2em; line-height: 1.5
}}

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

.fl {{
  padding: 3px 10px; border-radius: 20px; font-size: 0.72rem;
  font-weight: 700; border: 1.5px solid; letter-spacing: 0.3px
}}
.gb {{
  padding: 3px 10px; border-radius: 20px; font-size: 0.72rem;
  font-weight: 600; color: #fff; letter-spacing: 0.3px
}}

.body {{ padding: 0 16px 16px; border-top: 1px solid #eee; display: none }}
.body section {{ margin-top: 12px }}
.body h4 {{
  font-size: 0.68rem; color: #888; text-transform: uppercase;
  letter-spacing: 0.6px; margin-bottom: 4px; font-weight: 600
}}

.skill-list {{ display: flex; flex-wrap: wrap; gap: 5px }}
.sk {{
  background: #e8eaf6; color: #283593; border-radius: 14px;
  padding: 3px 11px; font-size: 0.78rem; font-weight: 500
}}

.desc {{
  background: #f5f5f5; border: 1px solid #e0e0e0; border-radius: 6px;
  padding: 10px 12px; font-size: 0.85rem; line-height: 1.5;
  max-height: 280px; overflow-y: auto; white-space: pre-wrap
}}
.df {{
  background: #f9f9f9; border: 1px solid #eee; border-radius: 6px;
  padding: 10px 12px; font-size: 0.85rem; line-height: 1.5;
  max-height: 240px; overflow-y: auto
}}
.rea {{
  background: #fff8e1; border-left: 3px solid #ffb300; border-radius: 4px;
  padding: 10px 12px; font-size: 0.85rem; line-height: 1.5;
  max-height: 200px; overflow-y: auto
}}
</style>
</head>
<body>
<h1>T-4 v6 — Classifier con is_new_role determinista</h1>
<p class="sub">{datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; 17 ofertas &middot; gemma4:e4b &middot; 18 roles en catálogo
&middot; <a href="04-classifier.html">v1</a> &middot; <a href="04-classifier-v2.html">v2</a> &middot; <a href="04-classifier-v3.html">v3</a> &middot; <a href="04-classifier-v4.html">v4</a> &middot; <a href="04-classifier-v5.html">v5</a></p>

<div class="note">
<strong>Cambios en v6:</strong> <code>is_new_role</code> ahora es determinista en Python
(<code>role_normalized not in catalog</code>) en vez de venir del LLM.
Columna <code>is_new_role INTEGER DEFAULT 0</code> añadida a <code>offers</code>.
<code>trade_compliance_specialist</code> detectado como nuevo rol automáticamente.
</div>

<div class="stats">
  <div class="st"><div class="n">{len(rows)}</div><div class="l">Ofertas</div></div>
  <div class="st"><div class="n">{dist.get('adjacent', 0)}</div><div class="l">Adjacent</div></div>
  <div class="st"><div class="n">{dist.get('stretch', 0)}</div><div class="l">Stretch</div></div>
  <div class="st"><div class="n">{dist.get('core', 0)}</div><div class="l">Core</div></div>
  <div class="st"><div class="n">{dist.get('temporal', 0)}</div><div class="l">Temporal</div></div>
</div>

<div class="stats">
  <div class="st"><div class="n">{gap_dist.get('herramienta', 0)}</div><div class="l">Gap herramienta</div></div>
  <div class="st"><div class="n">{gap_dist.get('dominio', 0)}</div><div class="l">Gap dominio</div></div>
  <div class="st"><div class="n">{gap_dist.get('seniority', 0)}</div><div class="l">Gap seniority</div></div>
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
    print(f"Reporte v6 generado: {REPORT_PATH}")
    print(f"  Distribución: {dict(dist)}")
    print(f"  Gap types: {dict(gap_dist)}")


if __name__ == "__main__":
    build_report()
