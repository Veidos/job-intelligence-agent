"""Generate v1 vs v2 classifier comparison report (HTML)."""

from __future__ import annotations

import html
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "jobs.db"
REPORT_PATH = PROJECT_ROOT / "reports" / "testing" / "04-classifier-v2.html"
V1_REPORT = PROJECT_ROOT / "reports" / "testing" / "04-classifier.html"

OFFER_IDS = list(range(226, 243))

V1_DATA: dict[int, dict] = {}

if V1_REPORT.exists():
    content = V1_REPORT.read_text(encoding="utf-8")
    import re
    sections = re.findall(
        r'<div class="card[^>]*>\s*<div class="card-h[^>]*>\s*<div class="num">(\d+)</div>.*?<div class="ti">([^<]+)</div>.*?<span class="rp">([^<]+)</span>.*?<span class="fl[^"]*"[^>]*>([^<]+)</span>.*?<div class="rea">([^<]*)</div>',
        content,
        re.DOTALL,
    )
    for i, (num_str, title, role, flag, reasoning) in enumerate(sections):
        oid = OFFER_IDS[i] if i < len(OFFER_IDS) else 0
        V1_DATA[oid] = {
            "title": title.strip(),
            "role": role.strip(),
            "flag": flag.strip().replace("\U0001f7e2", "core").replace("\U0001f7e1", "adjacent").replace("\U0001f534", "stretch").replace("\U0001f7e0", "temporal"),
            "reasoning": reasoning.strip(),
        }


def esc(text: str) -> str:
    return html.escape(text or "")


FLAG_COLORS = {
    "core": {"bg": "#e8f5e9", "text": "#2e7d32", "border": "#2e7d32", "label": "core"},
    "adjacent": {"bg": "#fff8e1", "text": "#f57f17", "border": "#f57f17", "label": "adjacent"},
    "stretch": {"bg": "#fce4ec", "text": "#c62828", "border": "#c62828", "label": "stretch"},
    "temporal": {"bg": "#f3e5f5", "text": "#7b1fa2", "border": "#7b1fa2", "label": "temporal"},
}


def flag_badge(flag: str) -> str:
    fc = FLAG_COLORS.get(flag, FLAG_COLORS["stretch"])
    return f'<span class="fl" style="background:{fc["bg"]};color:{fc["text"]};border-color:{fc["border"]}">{fc["label"]}</span>'


def diff_class(v1_val: str, v2_val: str) -> str:
    return ' style="font-weight:700;color:#e65100"' if v1_val != v2_val else ""


def build_report() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, title, role_normalized, relevance_flag, gap_type, role_reasoning, classification_reasoning
           FROM offers WHERE id BETWEEN 226 AND 242 ORDER BY id"""
    ).fetchall()
    conn.close()

    cards_html = ""
    changes = 0
    total = 0

    for i, row in enumerate(rows, 1):
        oid = row["id"]
        v2_role = row["role_normalized"] or ""
        v2_flag = row["relevance_flag"] or ""
        v2_gap = row["gap_type"] or ""
        v2_role_r = row["role_reasoning"] or ""
        v2_reasoning = row["classification_reasoning"] or ""

        v1 = V1_DATA.get(oid, {})
        v1_role = v1.get("role", "-")
        v1_flag_raw = v1.get("flag", "-")
        v1_reasoning = v1.get("reasoning", "")

        role_diff = v1_role != v2_role
        flag_diff = v1_flag_raw != v2_flag
        if role_diff or flag_diff:
            changes += 1
        total += 1

        fc = FLAG_COLORS.get(v2_flag, FLAG_COLORS["stretch"])
        border = fc.get("border", "#2e7d32")

        cards_html += f"""
<div class="card" style="border-left:4px solid #{border};">
  <div class="card-h" onclick="toggleCard({oid})">
    <div class="num">{i}</div>
    <div class="info">
      <div class="ti">{esc(row['title'])}</div>
      <div class="me">{esc(v2_role)}{' (' + esc(v2_gap) + ')' if v2_gap else ''}</div>
    </div>
    <div class="bads">
      {flag_badge(v2_flag)}
      <span class="rp">{esc(v2_role)}</span>
      <span class="ar" id="ar-{oid}">&#9660;</span>
    </div>
  </div>
  <div class="card-b" id="b-{oid}">
    <div class="g2">
      <div>
        <h4>V2 — gap_type: {esc(v2_gap)}</h4>
        <div class="df"><strong>role_reasoning:</strong> {esc(v2_role_r)}</div>
        <div class="rea">{esc(v2_reasoning)}</div>
      </div>
      <div>
        <h4>V1<span style="font-weight:400;font-size:.85em;color:#888"> (reporte anterior)</span></h4>
        <div class="df"><strong>role:</strong> {esc(v1_role)} <strong>flag:</strong> {esc(v1_flag_raw)}</div>
        <div class="rea">{esc(v1_reasoning)}</div>
      </div>
    </div>
  </div>
</div>"""

    diff_pct = round(changes / total * 100) if total else 0

    html_out = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>T-4 v2 &mdash; Comparativa Classifier</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',-apple-system,sans-serif;max-width:1200px;margin:2em auto;padding:0 1em;background:#f5f5f5;color:#222;font-size:15px}}
h1{{font-size:1.4em;margin-bottom:.2em}}
.sub{{color:#888;font-size:.85em;margin-bottom:1.2em}}
.stats{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:1em}}
.st{{background:#fff;border-radius:8px;padding:12px 16px;box-shadow:0 1px 3px rgba(0,0,0,.06);flex:1;min-width:80px;text-align:center}}
.st .n{{font-size:1.6em;font-weight:700}}
.st .l{{font-size:.75em;color:#888;margin-top:2px}}
.tag{{display:inline-block;background:#e8eaf6;color:#283593;padding:2px 9px;border-radius:10px;font-size:.8em;margin:1px}}
.card{{background:#fff;border-radius:8px;margin-bottom:6px;box-shadow:0 1px 3px rgba(0,0,0,.05);overflow:hidden}}
.card-h{{display:flex;align-items:center;padding:10px 14px;cursor:pointer;gap:10px;transition:background .12s}}
.card-h:hover{{background:#fafafa}}
.num{{background:#37474f;color:#fff;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.75em;font-weight:700;flex-shrink:0}}
.info{{flex:1;min-width:0}}
.ti{{font-weight:600;font-size:.93em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.me{{font-size:.78em;color:#888}}
.bads{{display:flex;align-items:center;gap:6px;flex-shrink:0}}
.rp{{background:#e3f2fd;color:#1565c0;padding:2px 8px;border-radius:8px;font-size:.76em;font-weight:600}}
.fl{{padding:2px 8px;border-radius:8px;font-size:.76em;font-weight:600;border:1px solid}}
.ar{{font-size:.75em;color:#aaa;transition:transform .2s}}
.card-b{{padding:0 14px 14px;border-top:1px solid #eee;display:none}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:10px 0}}
.sec{{margin:10px 0}}
.sec h4{{font-size:.8em;color:#555;margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px;display:flex;align-items:center;gap:6px}}
.dt{{width:100%;font-size:.85em}}
.dt td{{padding:2px 0}}
.dt td:first-child{{color:#888;width:85px}}
.rea{{background:#fff8e1;border-left:3px solid #ffb300;border-radius:4px;padding:10px 12px;font-size:.85em;line-height:1.5;max-height:200px;overflow-y:auto}}
.df{{background:#f9f9f9;border:1px solid #eee;border-radius:6px;padding:10px;font-size:.85em;line-height:1.45;max-height:240px;overflow-y:auto;white-space:pre-wrap}}
@media(max-width:700px){{.g2{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>T-4 v2 &mdash; Clasificador reformado: comparativa v1 vs v2</h1>
<p class="sub">{datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; 17 ofertas &middot; gemma4:e4b &middot; <a href="04-classifier.html">Ver reporte v1</a></p>

<div class="stats">
  <div class="st"><div class="n">{total}</div><div class="l">Ofertas</div></div>
  <div class="st"><div class="n">{changes}</div><div class="l">Cambios v1&rarr;v2</div></div>
  <div class="st"><div class="n" style="color:#e65100">{diff_pct}%</div><div class="l">Diferencias</div></div>
</div>

<p><strong>Leyenda:</strong> V2 aplica Paso 1 (rol sin perfil) + Paso 2 (gap_type jerárquico). 
V1 usaba prompt único con bandas porcentuales.
Cada oferta muestra V2 (izquierda) y V1 (derecha) lado a lado.</p>

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
    print(f"Reporte generado: {REPORT_PATH}")
    print(f"  {total} ofertas, {changes} con cambios v1→v2 ({diff_pct}%)")


if __name__ == "__main__":
    build_report()
