"""Generate T-4 v3 report: classifier results with seniority prompt fix."""

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
REPORT_PATH = PROJECT_ROOT / "reports" / "testing" / "04-classifier-v3.html"


def esc(text: str) -> str:
    return html.escape(text or "")


FLAG_COLORS = {
    "core": {"bg": "#e8f5e9", "text": "#2e7d32", "border": "#2e7d32"},
    "adjacent": {"bg": "#fff8e1", "text": "#f57f17", "border": "#f57f17"},
    "stretch": {"bg": "#fce4ec", "text": "#c62828", "border": "#c62828"},
    "temporal": {"bg": "#f3e5f5", "text": "#7b1fa2", "border": "#7b1fa2"},
}


def flag_badge(flag: str) -> str:
    fc = FLAG_COLORS.get(flag, FLAG_COLORS["stretch"])
    return f'<span class="fl" style="background:{fc["bg"]};color:{fc["text"]};border-color:{fc["border"]}">{flag}</span>'


def gap_badge(gap: str, flag: str) -> str:
    if gap == "seniority":
        return f'<span class="gb gb-s">{gap}</span>'
    elif gap == "dominio":
        return f'<span class="gb gb-d">{gap}</span>'
    elif gap == "herramienta":
        return f'<span class="gb gb-h">{gap}</span>'
    elif gap == "none" or not gap:
        return f'<span class="gb gb-n">{gap or "none"}</span>'
    return f'<span class="gb">{gap}</span>'


def build_report() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, title, role_normalized, relevance_flag, gap_type, role_reasoning, classification_reasoning
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
        role_r = row["role_reasoning"] or ""
        reasoning = row["classification_reasoning"] or ""

        fc = FLAG_COLORS.get(flag, FLAG_COLORS["stretch"])

        cards_html += f"""
<div class="card" style="border-left:4px solid #{fc['border']};">
  <div class="card-h" onclick="toggleCard({oid})">
    <div class="num">{i}</div>
    <div class="info">
      <div class="ti">{esc(row['title'])}</div>
      <div class="me">{esc(role)}</div>
    </div>
    <div class="bads">
      {flag_badge(flag)}
      {gap_badge(gap, flag)}
      <span class="ar" id="ar-{oid}">&#9660;</span>
    </div>
  </div>
  <div class="card-b" id="b-{oid}">
    <div class="sec">
      <h4>gap_type: {esc(gap)} &middot; role_reasoning</h4>
      <div class="df">{esc(role_r)}</div>
      <h4 style="margin-top:8px;">classification_reasoning</h4>
      <div class="rea">{esc(reasoning)}</div>
    </div>
  </div>
</div>"""

    html_out = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>T-4 v3 &mdash; Classifier con ajuste seniority</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',-apple-system,sans-serif;max-width:1200px;margin:2em auto;padding:0 1em;background:#f5f5f5;color:#222;font-size:15px}}
h1{{font-size:1.4em;margin-bottom:.2em}}
.sub{{color:#888;font-size:.85em;margin-bottom:1.2em}}
.stats{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:1em}}
.st{{background:#fff;border-radius:8px;padding:12px 16px;box-shadow:0 1px 3px rgba(0,0,0,.06);flex:1;min-width:80px;text-align:center}}
.st .n{{font-size:1.6em;font-weight:700}}
.st .l{{font-size:.75em;color:#888;margin-top:2px}}
.card{{background:#fff;border-radius:8px;margin-bottom:6px;box-shadow:0 1px 3px rgba(0,0,0,.05);overflow:hidden}}
.card-h{{display:flex;align-items:center;padding:10px 14px;cursor:pointer;gap:10px;transition:background .12s}}
.card-h:hover{{background:#fafafa}}
.num{{background:#37474f;color:#fff;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.75em;font-weight:700;flex-shrink:0}}
.info{{flex:1;min-width:0}}
.ti{{font-weight:600;font-size:.93em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.me{{font-size:.78em;color:#888}}
.bads{{display:flex;align-items:center;gap:6px;flex-shrink:0}}
.fl{{padding:2px 8px;border-radius:8px;font-size:.76em;font-weight:600;border:1px solid}}
.gb{{padding:2px 8px;border-radius:8px;font-size:.76em;font-weight:600;color:#fff}}
.gb-s{{background:#c62828}}
.gb-d{{background:#f57f17}}
.gb-h{{background:#1565c0}}
.gb-n{{background:#888}}
.ar{{font-size:.75em;color:#aaa;transition:transform .2s}}
.card-b{{padding:0 14px 14px;border-top:1px solid #eee;display:none}}
.sec{{margin:10px 0}}
.sec h4{{font-size:.8em;color:#555;margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px}}
.dt{{width:100%;font-size:.85em}}
.dt td{{padding:2px 0}}
.dt td:first-child{{color:#888;width:85px}}
.rea{{background:#fff8e1;border-left:3px solid #ffb300;border-radius:4px;padding:10px 12px;font-size:.85em;line-height:1.5;max-height:200px;overflow-y:auto}}
.df{{background:#f9f9f9;border:1px solid #eee;border-radius:6px;padding:10px;font-size:.85em;line-height:1.45;max-height:240px;overflow-y:auto;white-space:pre-wrap}}
.note{{background:#e3f2fd;border:1px solid #90caf9;border-radius:6px;padding:10px 14px;font-size:.85em;margin-bottom:1em}}
</style>
</head>
<body>
<h1>T-4 v3 &mdash; Classifier con ajuste de seniority</h1>
<p class="sub">{datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; 17 ofertas &middot; gemma4:e4b
&middot; <a href="04-classifier.html">v1 original</a> &middot; <a href="04-classifier-v2.html">v2</a></p>

<div class="note">
<strong>Cambio respecto a v2:</strong> Se añadió definición explícita de cada gap_type en QE,
ancorando <code>seniority</code> a la oferta: "la oferta exige explícitamente ≥2 años de experiencia,
liderazgo de equipos o autonomía senior (no lo infieras del perfil)".
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
  <div class="st"><div class="n">{gap_dist.get('none', 0)}</div><div class="l">Sin gap</div></div>
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
    print(f"Reporte v3 generado: {REPORT_PATH}")
    print(f"  Distribución: {dict(dist)}")
    print(f"  Gap types: {dict(gap_dist)}")


if __name__ == "__main__":
    build_report()
