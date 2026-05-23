"""Reporte T-5 v2 — Comparativa Ollama vs OpenRouter (17 ofertas T-4)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "testing"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.db"

FLAG_COLORS = {
    "core": {"bg": "#e8f5e9", "text": "#2e7d32", "border": "#a5d6a7"},
    "adjacent": {"bg": "#fff3e0", "text": "#e65100", "border": "#ffcc80"},
    "stretch": {"bg": "#fce4ec", "text": "#c62828", "border": "#ef9a9a"},
    "temporal": {"bg": "#e3f2fd", "text": "#1565c0", "border": "#90caf9"},
}

GAP_COLORS = {
    "none": {"bg": "#e8f5e9", "text": "#2e7d32"},
    "herramienta": {"bg": "#fff3e0", "text": "#e65100"},
    "dominio": {"bg": "#fce4ec", "text": "#c62828"},
    "seniority": {"bg": "#f3e5f5", "text": "#6a1b9a"},
    "estructural": {"bg": "#ffebee", "text": "#b71c1c"},
}


def flag_badge(flag: str) -> str:
    fc = FLAG_COLORS.get(flag, FLAG_COLORS["stretch"])
    return f'<span class="fl" style="background:{fc["bg"]};color:{fc["text"]};border-color:{fc["border"]}">{flag}</span>'


def gap_badge(gap: str | None) -> str:
    if not gap:
        return ""
    gc = GAP_COLORS.get(gap, {"bg": "#eee", "text": "#666"})
    return f'<span class="gb" style="background:{gc["bg"]};color:{gc["text"]}">{gap}</span>'


def build_report() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """WITH ranked AS (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY offer_id ORDER BY id DESC) AS rn
            FROM offer_evaluations
            WHERE offer_id BETWEEN 226 AND 242
        )
        SELECT o.id, o.title, o.company_name, o.city, o.work_mode,
               o.description_clean, o.skills_required,
               o.relevance_flag, o.role_normalized, o.gap_type, o.role_reasoning,
               MAX(CASE WHEN r.rn = 1 THEN r.match_score END) AS or_score,
               MAX(CASE WHEN r.rn = 1 THEN r.recommendation END) AS or_rec,
               MAX(CASE WHEN r.rn = 1 THEN r.skills_hard_match END) AS or_skills,
               MAX(CASE WHEN r.rn = 1 THEN r.experience_match END) AS or_exp,
               MAX(CASE WHEN r.rn = 1 THEN r.education_match END) AS or_edu,
               MAX(CASE WHEN r.rn = 1 THEN r.location_match END) AS or_loc,
               MAX(CASE WHEN r.rn = 1 THEN r.trajectory_coherence END) AS or_traj,
               MAX(CASE WHEN r.rn = 1 THEN r.recency_relevance END) AS or_recency,
               MAX(CASE WHEN r.rn = 1 THEN r.market_competitiveness END) AS or_market,
               MAX(CASE WHEN r.rn = 1 THEN r.penalty END) AS or_penalty,
               MAX(CASE WHEN r.rn = 1 THEN r.environment_compatibility END) AS or_env,
               MAX(CASE WHEN r.rn = 1 THEN r.apply_block END) AS or_block,
               MAX(CASE WHEN r.rn = 1 THEN r.apply_block_reason END) AS or_block_reason,
               MAX(CASE WHEN r.rn = 1 THEN r.relevance_validation END) AS or_relval,
               MAX(CASE WHEN r.rn = 1 THEN r.relevance_corrected END) AS or_relcor,
               MAX(CASE WHEN r.rn = 1 THEN r.strengths END) AS or_strengths,
               MAX(CASE WHEN r.rn = 1 THEN r.red_flags END) AS or_redflags,
               MAX(CASE WHEN r.rn = 1 THEN r.gemma_verdict END) AS or_verdict,
               MAX(CASE WHEN r.rn = 1 THEN r.hr_concerns END) AS or_concerns,
               MAX(CASE WHEN r.rn = 1 THEN r.llm_apply_signal END) AS or_signal,
               MAX(CASE WHEN r.rn = 2 THEN r.match_score END) AS ol_score,
               MAX(CASE WHEN r.rn = 2 THEN r.recommendation END) AS ol_rec,
               MAX(CASE WHEN r.rn = 2 THEN r.skills_hard_match END) AS ol_skills,
               MAX(CASE WHEN r.rn = 2 THEN r.experience_match END) AS ol_exp,
               MAX(CASE WHEN r.rn = 2 THEN r.education_match END) AS ol_edu,
               MAX(CASE WHEN r.rn = 2 THEN r.location_match END) AS ol_loc,
               MAX(CASE WHEN r.rn = 2 THEN r.trajectory_coherence END) AS ol_traj,
               MAX(CASE WHEN r.rn = 2 THEN r.recency_relevance END) AS ol_recency,
               MAX(CASE WHEN r.rn = 2 THEN r.market_competitiveness END) AS ol_market,
               MAX(CASE WHEN r.rn = 2 THEN r.penalty END) AS ol_penalty,
               MAX(CASE WHEN r.rn = 2 THEN r.environment_compatibility END) AS ol_env,
               MAX(CASE WHEN r.rn = 2 THEN r.apply_block END) AS ol_block,
               MAX(CASE WHEN r.rn = 2 THEN r.apply_block_reason END) AS ol_block_reason,
               MAX(CASE WHEN r.rn = 2 THEN r.relevance_validation END) AS ol_relval,
               MAX(CASE WHEN r.rn = 2 THEN r.relevance_corrected END) AS ol_relcor,
               MAX(CASE WHEN r.rn = 2 THEN r.strengths END) AS ol_strengths,
               MAX(CASE WHEN r.rn = 2 THEN r.red_flags END) AS ol_redflags,
               MAX(CASE WHEN r.rn = 2 THEN r.gemma_verdict END) AS ol_verdict,
               MAX(CASE WHEN r.rn = 2 THEN r.hr_concerns END) AS ol_concerns,
               MAX(CASE WHEN r.rn = 2 THEN r.llm_apply_signal END) AS ol_signal
        FROM ranked r
        JOIN offers o ON o.id = r.offer_id
        GROUP BY r.offer_id
        ORDER BY COALESCE(or_score, 0) DESC"""
    ).fetchall()

    conn.close()

    cards_html = ""
    ol_scores: list[int] = []
    or_scores: list[int] = []

    for idx, r in enumerate(rows, 1):
        ol_score = r["ol_score"] if r["ol_score"] is not None else 0
        or_score = r["or_score"] if r["or_score"] is not None else 0
        has_both = r["ol_score"] is not None and r["or_score"] is not None
        delta = or_score - ol_score if has_both else 0

        if r["ol_score"] is not None:
            ol_scores.append(r["ol_score"])
        or_scores.append(or_score)

        if has_both:
            if delta > 0:
                delta_cls = "delta-up"
                delta_sign = "+"
            elif delta < 0:
                delta_cls = "delta-down"
                delta_sign = ""
            else:
                delta_cls = "delta-eq"
                delta_sign = "±"
        else:
            delta_cls = "delta-eq"
            delta_sign = "~"

        ol_rec = r["ol_rec"] or ""
        or_rec = r["or_rec"] or ""
        relevance_flag = r["relevance_flag"] or ""
        gap_type = r["gap_type"] or ""
        role_normalized = r["role_normalized"] or ""
        role_reasoning = r["role_reasoning"] or ""

        ol_block = r["ol_block"]
        or_block = r["or_block"]

        def fmt_list(val: str | None) -> str:
            if not val:
                return ""
            try:
                items = json.loads(val)
                if isinstance(items, list):
                    return ", ".join(items)
                return str(items)
            except (json.JSONDecodeError, TypeError):
                return val or ""

        def block_badge(block: str | None) -> str:
            if not block:
                return ""
            colors = {
                "requisito_imposible": {"bg": "#ffebee", "text": "#c62828"},
                "practicas": {"bg": "#e3f2fd", "text": "#1565c0"},
            }
            bc = colors.get(block, {"bg": "#fff3e0", "text": "#e65100"})
            return f'<span class="bl" style="background:{bc["bg"]};color:{bc["text"]}">{block}</span>'

        cards_html += f"""<div class="card">
  <div class="card-h" onclick="this.nextElementSibling.classList.toggle('open')">
    <span class="num">{idx}</span>
    <div class="info">
      <div class="ti">{r["title"]} {flag_badge(relevance_flag)} {gap_badge(gap_type)}</div>
      <div class="meta">{r["company_name"] or ""} &middot; {r["city"] or ""} &middot; {r["work_mode"] or ""}</div>
      <div class="meta" style="font-size:0.72rem;color:#999">{role_normalized}</div>
    </div>
    <div class="tags" style="gap:4px">
      <span class="sc" style="background:#e3f2fd"><b>{ol_score}</b>/100</span>
      <span class="sc" style="background:#fce4ec">Ollama</span>
      <span class="sc {delta_cls}">{delta_sign}{delta if has_both else ""}</span>
      <span class="sc" style="background:#e8f5e9">OpenRouter</span>
      <span class="sc" style="background:#e8f5e9"><b>{or_score}</b>/100</span>
    </div>
    <span class="arr">&#9660;</span>
  </div>
  <div class="card-b">
    <table class="ct">
      <tr>
        <th>Bloque A</th>
        <th class="ot">Ollama</th>
        <th class="nt">OpenRouter</th>
      </tr>
      <tr><td>Skills</td><td class="ot">{r["ol_skills"] or "-"}/30</td><td class="nt">{r["or_skills"] or "-"}/30</td></tr>
      <tr><td>Experiencia</td><td class="ot">{r["ol_exp"] or "-"}/20</td><td class="nt">{r["or_exp"] or "-"}/20</td></tr>
      <tr><td>Educación</td><td class="ot">{r["ol_edu"] or "-"}/10</td><td class="nt">{r["or_edu"] or "-"}/10</td></tr>
      <tr><td>Ubicación</td><td class="ot">{r["ol_loc"] or "-"}/5</td><td class="nt">{r["or_loc"] or "-"}/5</td></tr>
    </table>
    <table class="ct">
      <tr><th>Bloque B</th><th class="ot">Ollama</th><th class="nt">OpenRouter</th></tr>
      <tr><td>Trayectoria</td><td class="ot">{r["ol_traj"] or "-"}/15</td><td class="nt">{r["or_traj"] or "-"}/15</td></tr>
      <tr><td>Recencia</td><td class="ot">{r["ol_recency"] or "-"}/15</td><td class="nt">{r["or_recency"] or "-"}/15</td></tr>
      <tr><td>Mercado</td><td class="ot">{r["ol_market"] or "-"}/5</td><td class="nt">{r["or_market"] or "-"}/5</td></tr>
      <tr><td>Penalización</td><td class="ot">{r["ol_penalty"] or "-"}/25</td><td class="nt">{r["or_penalty"] or "-"}/25</td></tr>
    </table>
    <table class="ct">
      <tr><th>Resultado</th><th class="ot">{ol_rec}</th><th class="nt">{or_rec}</th></tr>
      <tr><td>Entorno</td><td class="ot">{r["ol_env"] or "-"}</td><td class="nt">{r["or_env"] or "-"}</td></tr>
      <tr><td>Bloqueo</td><td class="ot">{block_badge(r["ol_block"])}</td><td class="nt">{block_badge(r["or_block"])}</td></tr>
      <tr><td>LLM Apply</td><td class="ot">{r["ol_signal"] or "-"}</td><td class="nt">{r["or_signal"] or "-"}</td></tr>
    </table>
    <div class="sec">
      <strong>Fortalezas (Ollama)</strong> {fmt_list(r["ol_strengths"])}<br>
      <strong>Fortalezas (OpenRouter)</strong> {fmt_list(r["or_strengths"])}
    </div>
    <div class="sec">
      <strong>Red flags (Ollama)</strong> {fmt_list(r["ol_redflags"])}<br>
      <strong>Red flags (OpenRouter)</strong> {fmt_list(r["or_redflags"])}
    </div>
    <div class="sec">
      <strong>Veredicto Ollama:</strong> {r["ol_verdict"] or ""}<br>
      <strong>Veredicto OpenRouter:</strong> {r["or_verdict"] or ""}
    </div>
    <div class="sec" style="background:#fafafa;border-radius:6px;padding:8px;font-size:0.78rem;color:#555">
      <strong>classifier:</strong> {role_normalized} &middot; gap: {gap_type}<br>
      <details><summary>role_reasoning</summary>{role_reasoning}</details>
    </div>
  </div>
</div>"""

    avg_ol = sum(ol_scores) // len(ol_scores) if ol_scores else 0
    avg_or = sum(or_scores) // len(or_scores) if or_scores else 0
    delta_avg = avg_or - avg_ol
    ol_count = len(ol_scores)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>T-5 v2 — Compare Ollama vs OpenRouter</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0 }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  max-width: 1100px; margin: 2em auto; padding: 0 1.5em;
  background: #f0f2f5; color: #1a1a2e; font-size: 15px; line-height: 1.5
}}
h1 {{ font-size: 1.3rem; font-weight: 700; margin-bottom: 0.1em }}
.sub {{ color: #666; font-size: 0.82rem; margin-bottom: 1em }}
h2 {{ font-size: 1rem; margin: 1.2em 0 0.4em }}
.stats {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 1em }}
.st {{
  background: #fff; border-radius: 10px; padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); flex: 1; min-width: 90px; text-align: center
}}
.st .n {{ font-size: 1.5rem; font-weight: 800 }}
.st .l {{ font-size: 0.68rem; color: #888; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.4px }}
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
.tags {{ display: flex; align-items: center; gap: 8px; flex-shrink: 0 }}
.arr {{ font-size: 0.7rem; color: #bbb; transition: transform 0.2s; margin-left: 2px }}
.sc {{
  padding: 3px 10px; border-radius: 20px; font-size: 0.78rem;
  font-weight: 700; letter-spacing: 0.3px
}}
.card-b {{ display: none; padding: 12px 16px 16px; border-top: 1px solid #eee }}
.card-b.open {{ display: block }}
.ct {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 0.82rem }}
.ct th {{ text-align: left; padding: 4px 6px; background: #f5f5f5; font-weight: 600 }}
.ct td {{ padding: 3px 6px; border-bottom: 1px solid #f0f0f0 }}
.ot {{ color: #1565c0 }}
.nt {{ color: #2e7d32 }}
.fl {{
  display: inline-block; padding: 1px 8px; border-radius: 12px;
  font-size: 0.65rem; font-weight: 600; border: 1px solid;
  text-transform: uppercase; letter-spacing: 0.3px; margin-left: 4px; vertical-align: middle
}}
.gb {{
  display: inline-block; padding: 1px 8px; border-radius: 12px;
  font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.3px; margin-left: 4px; vertical-align: middle
}}
.bl {{
  display: inline-block; padding: 1px 8px; border-radius: 10px;
  font-size: 0.65rem; font-weight: 600; text-transform: uppercase
}}
.delta-up {{ background: #e8f5e9; color: #2e7d32 }}
.delta-down {{ background: #ffebee; color: #c62828 }}
.delta-eq {{ background: #f5f5f5; color: #888 }}
.sec {{ margin: 6px 0; font-size: 0.82rem; color: #444 }}
summary {{ cursor: pointer; color: #1565c0; font-size:0.78rem }}
</style>
</head>
<body>
<h1>T-5 v2 — Ollama vs OpenRouter</h1>
<div class="sub">{len(rows)} ofertas · Generado {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>

<div class="stats">
  <div class="st"><div class="n">{avg_ol}</div><div class="l">Ollama avg ({ol_count} ofertas)</div></div>
  <div class="st"><div class="n">{delta_avg:+d}</div><div class="l">Delta</div></div>
  <div class="st"><div class="n">{avg_or}</div><div class="l">OpenRouter avg (17 ofertas)</div></div>
</div>

{cards_html}
</body>
</html>"""

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "06-evaluate-openrouter.html"
    out.write_text(html, encoding="utf-8")
    print(f"Reporte generado: {out}")
    print(f"  Total: {len(rows)}, Ollama avg: {avg_ol}, OpenRouter avg: {avg_or}")


if __name__ == "__main__":
    build_report()
