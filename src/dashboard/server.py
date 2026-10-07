#!/usr/bin/env python3
"""Servidor web del dashboard de Job Intelligence Agent.

Uso:
    python src/dashboard/server.py          # localhost:8080
    python src/dashboard/server.py --port 9090
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

from src.db.init_db import get_connection  # noqa: E402

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIVE_LOG = PROJECT_ROOT / "logs" / "pipeline_live.log"

app = Flask(__name__, static_folder=None)


# ── helpers ──────────────────────────────────────────────────────────
def _json(val):
    if not val:
        return None
    try:
        return json.loads(val) if isinstance(val, str) else val
    except (json.JSONDecodeError, TypeError):
        return None


def _rows(cursor):
    return [dict(r) for r in cursor.fetchall()]


# ── API routes ────────────────────────────────────────────────────────
@app.route("/api/stats")
def api_stats():
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        total_offers = cur.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
        evaluated = cur.execute(
            "SELECT COUNT(*) FROM offer_evaluations WHERE match_score IS NOT NULL"
        ).fetchone()[0]
        pending_eval = cur.execute(
            "SELECT COUNT(*) FROM offers WHERE is_evaluated=0 AND relevance_flag IS NOT NULL"
        ).fetchone()[0]
        classified = cur.execute(
            "SELECT COUNT(*) FROM offers WHERE relevance_flag IS NOT NULL"
        ).fetchone()[0]
        companies = cur.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        apps = cur.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        feedbacks = cur.execute("SELECT COUNT(*) FROM user_feedback").fetchone()[0]

        avg_score = cur.execute(
            "SELECT ROUND(AVG(match_score), 1) FROM offer_evaluations WHERE match_score IS NOT NULL"
        ).fetchone()[0]
        max_score = cur.execute("SELECT MAX(match_score) FROM offer_evaluations").fetchone()[0]

        rec_counts = _rows(
            cur.execute(
                """SELECT recommendation, COUNT(*) as cnt
                   FROM offer_evaluations WHERE match_score IS NOT NULL
                   GROUP BY recommendation ORDER BY cnt DESC"""
            )
        )

        last_run = cur.execute("SELECT MAX(fetched_at) FROM offers").fetchone()[0]

    return jsonify(
        total_offers=total_offers,
        evaluated=evaluated,
        pending_eval=pending_eval,
        classified=classified,
        companies=companies,
        applications=apps,
        feedbacks=feedbacks,
        avg_score=avg_score,
        max_score=max_score,
        rec_counts=rec_counts,
        last_run=last_run,
    )


# Columnas filtrables en api_offers — allowlist explícito.
# Siempre usar placeholders ? con params, nunca interpolación directa.
_OFFER_FILTER_COLUMNS = frozenset(
    {
        "match_score",
        "recommendation",
        "llm_apply_signal",
        "relevance_flag",
        "title",
        "company_name",
        "company_id",
    }
)


@app.route("/api/offers")
def api_offers():
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        min_score = request.args.get("min_score", type=int)
        rec = request.args.get("rec")
        signal = request.args.get("signal")
        rel = request.args.get("rel")
        search = request.args.get("search")
        company_id = request.args.get("company_id", type=int)
        limit = request.args.get("limit", type=int)

        wheres = ["e.match_score IS NOT NULL"]
        params = []
        if min_score:
            wheres.append("e.match_score >= ?")
            params.append(min_score)
        if rec:
            wheres.append("e.recommendation = ?")
            params.append(rec)
        if signal:
            wheres.append("e.llm_apply_signal = ?")
            params.append(signal)
        if rel:
            wheres.append("o.relevance_flag = ?")
            params.append(rel)
        if search:
            wheres.append("(o.title LIKE ? OR o.company_name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if company_id:
            wheres.append("o.company_id = ?")
            params.append(company_id)

        where_sql = " AND ".join(wheres)

        sql = f"""
            SELECT o.id, o.source_id, o.title, o.company_name, o.company_id,
                   o.city, o.work_mode, o.url, o.salary_min, o.salary_max,
                   o.published_at, o.relevance_flag, o.role_normalized,
                   e.match_score, e.recommendation, e.llm_apply_signal,
                   e.skills_hard_match, e.experience_match,
                   e.scoring_detail, e.gemma_verdict, e.hr_concerns,
                   e.strengths, e.red_flags, e.interview_prep,
                   e.apply_block, e.apply_block_reason,
                   e.environment_compatibility,
                   e.evaluated_at,
                   c.sector AS company_sector, c.size_range AS company_size
            FROM offers o
            JOIN offer_evaluations e ON o.id = e.offer_id
            LEFT JOIN companies c ON o.company_id = c.id
            WHERE {where_sql}
            ORDER BY e.match_score DESC
        """
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

        cols = [d[0] for d in cur.description]
        offers = []
        for row in rows:
            r = dict(zip(cols, row))
            pb = _json(r["scoring_detail"]) or {}
            smin = r["salary_min"]
            smax = r["salary_max"]
            if smin is not None and smax is not None:
                salary_display = f"{round(smin / 1000)}k–{round(smax / 1000)}k"
            elif smin is not None:
                salary_display = f"{round(smin / 1000)}k"
            else:
                salary_display = None

            offers.append(
                dict(
                    id=r["id"],
                    source_id=r["source_id"],
                    title=r["title"] or "",
                    company_name=r["company_name"] or "",
                    company_id=r["company_id"],
                    city=r["city"] or "",
                    work_mode=r["work_mode"] or "",
                    url=r["url"],
                    salary_display=salary_display,
                    salary_min=r["salary_min"],
                    salary_max=r["salary_max"],
                    skill_detail=pb.get("skill_detail", {}),
                    published_at=r["published_at"],
                    evaluated_at=r["evaluated_at"],
                    relevance_flag=r["relevance_flag"] or "",
                    role_normalized=r["role_normalized"] or "",
                    match_score=r["match_score"] or 0,
                    recommendation=r["recommendation"] or "",
                    llm_apply_signal=r["llm_apply_signal"] or "",
                    M_core=pb.get("M_core"),
                    M_sec=pb.get("M_sec"),
                    F_exp=pb.get("F_exp"),
                    F_fit=pb.get("F_fit"),
                    apply_block=r["apply_block"],
                    apply_block_reason=r["apply_block_reason"],
                    gemma_verdict=r["gemma_verdict"] or "",
                    environment_compatibility=r["environment_compatibility"] or "",
                    strengths=_json(r["strengths"]) or [],
                    red_flags=_json(r["red_flags"]) or [],
                    hr_concerns=_json(r["hr_concerns"]) or [],
                    interview_prep=_json(r["interview_prep"]) or [],
                    skills_hard_match=r["skills_hard_match"],
                    experience_match=r["experience_match"],
                    company_sector=r["company_sector"] or "",
                    company_size=r["company_size"] or "",
                )
            )

    return jsonify(offers)


@app.route("/api/offers/<int:offer_id>")
def api_offer_detail(offer_id):
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """SELECT o.*, e.match_score, e.recommendation, e.scoring_detail,
                      e.gemma_verdict, e.hr_concerns, e.strengths, e.red_flags,
                      e.interview_prep, e.apply_block, e.apply_block_reason,
                      e.llm_apply_signal, e.environment_compatibility,
                      e.skills_hard_match, e.experience_match, e.evaluated_at,
                      c.sector AS company_sector, c.size_range AS company_size
               FROM offers o
               LEFT JOIN offer_evaluations e ON o.id = e.offer_id
               LEFT JOIN companies c ON o.company_id = c.id
               WHERE o.id = ?""",
            (offer_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify(error="Not found"), 404

        cols = [d[0] for d in cur.description]
        r = dict(zip(cols, row))

        feedback = _rows(
            cur.execute(
                "SELECT * FROM user_feedback WHERE offer_id = ? ORDER BY created_at DESC",
                (offer_id,),
            )
        )

        app_row = cur.execute(
            "SELECT * FROM applications WHERE offer_id = ? ORDER BY applied_at DESC LIMIT 1",
            (offer_id,),
        ).fetchone()
        application = dict(zip([d[0] for d in cur.description], app_row)) if app_row else None

    return jsonify(offer=r, feedback=feedback, application=application)


@app.route("/api/companies")
def api_companies():
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = _rows(
            cur.execute(
                """SELECT c.*,
                          (SELECT COUNT(*) FROM offers o WHERE o.company_id = c.id) AS offer_count,
                          (SELECT ROUND(AVG(e.match_score), 1) FROM offer_evaluations e
                           JOIN offers o ON o.id = e.offer_id WHERE o.company_id = c.id) AS avg_score
                   FROM companies c
                   ORDER BY offer_count DESC"""
            )
        )
    return jsonify(rows)


@app.route("/api/feedback", methods=["GET", "POST"])
def api_feedback():
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if request.method == "POST":
            data = request.get_json()
            offer_id = data.get("offer_id")
            raw_text = data.get("raw_text", "").strip()
            if not offer_id or not raw_text:
                return jsonify(error="offer_id and raw_text required"), 400
            cur.execute(
                """INSERT INTO user_feedback (offer_id, feedback_type, raw_text)
                   VALUES (?, 'dashboard', ?)""",
                (offer_id, raw_text),
            )
            conn.commit()
            return jsonify(status="ok", id=cur.lastrowid)

        rows = _rows(
            cur.execute(
                """SELECT f.*, o.title AS offer_title, o.company_name
                   FROM user_feedback f
                   LEFT JOIN offers o ON o.id = f.offer_id
                   ORDER BY f.created_at DESC LIMIT 200"""
            )
        )
    return jsonify(rows)


@app.route("/api/applications", methods=["GET", "POST"])
def api_applications():
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if request.method == "POST":
            data = request.get_json()
            offer_id = data.get("offer_id")
            if not offer_id:
                return jsonify(error="offer_id required"), 400
            status = data.get("status", "applied")
            notes = data.get("notes", "")
            contact_name = data.get("contact_name", "")
            next_action = data.get("next_action_date", "")

            existing = cur.execute(
                "SELECT id FROM applications WHERE offer_id = ?", (offer_id,)
            ).fetchone()
            if existing:
                cur.execute(
                    """UPDATE applications SET status=?, notes=?, contact_name=?,
                              next_action_date=?, updated_at=datetime('now')
                       WHERE offer_id=?""",
                    (status, notes, contact_name, next_action, offer_id),
                )
            else:
                cur.execute(
                    """INSERT INTO applications (offer_id, status, notes, contact_name, next_action_date)
                       VALUES (?, ?, ?, ?, ?)""",
                    (offer_id, status, notes, contact_name, next_action),
                )
            conn.commit()
            app_id = existing[0] if existing else cur.lastrowid
            return jsonify(status="ok", id=app_id)

        limit = request.args.get("limit", type=int) or 500
        rows = _rows(
            cur.execute(
                """SELECT a.*, o.title AS offer_title, o.company_name, o.url,
                          e.match_score, e.recommendation
                   FROM applications a
                   LEFT JOIN offers o ON o.id = a.offer_id
                   LEFT JOIN offer_evaluations e ON o.id = e.offer_id
                   ORDER BY a.applied_at DESC LIMIT ?""",
                (limit,),
            )
        )
    return jsonify(rows)


@app.route("/api/applications/<int:app_id>", methods=["DELETE"])
def api_delete_application(app_id):
    with contextlib.closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        conn.commit()
    return jsonify(status="ok")


@app.route("/api/runs")
def api_runs():
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = _rows(cur.execute("""SELECT * FROM search_runs ORDER BY ran_at DESC LIMIT 50"""))
    return jsonify(rows)


@app.route("/api/pipeline-runs")
def api_pipeline_runs():
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # --- aggregated stats per run date ---
        rows = _rows(
            cur.execute("""
            SELECT
                date(o.fetched_at) as run_date,
                COUNT(*)                                          AS fetched,
                SUM(CASE WHEN o.relevance_flag IS NOT NULL
                    THEN 1 ELSE 0 END)                            AS classified,
                SUM(o.is_evaluated)                               AS evaluated,
                SUM(CASE WHEN e.match_score >= 35
                    THEN 1 ELSE 0 END)                            AS score_ge_35,
                SUM(CASE WHEN e.match_score >= 50
                    THEN 1 ELSE 0 END)                            AS score_ge_50,
                SUM(COALESCE(e.sent_via_telegram, 0))               AS sent,
                ROUND(AVG(e.match_score), 1)                      AS avg_score,
                ROUND(AVG(e.skills_hard_match), 1)                AS avg_m_core,
                ROUND(AVG(e.experience_match), 1)                 AS avg_f_exp,
                ROUND(AVG(e.location_match), 1)                   AS avg_location,
                ROUND(AVG(e.market_competitiveness), 1)           AS avg_market
            FROM offers o
            JOIN offer_evaluations e ON o.id = e.offer_id
            WHERE e.match_score IS NOT NULL
            GROUP BY run_date
            ORDER BY run_date DESC
        """)
        )

        # --- environment_compatibility breakdown per run ---
        env_rows = _rows(
            cur.execute("""
            SELECT
                date(o.fetched_at) as run_date,
                e.environment_compatibility as env,
                COUNT(*) as cnt
            FROM offer_evaluations e
            JOIN offers o ON o.id = e.offer_id
            WHERE e.match_score IS NOT NULL
              AND e.environment_compatibility IS NOT NULL
            GROUP BY run_date, env
            ORDER BY run_date DESC, env
        """)
        )
        env_by_run: dict[str, dict[str, int]] = {}
        for r in env_rows:
            env_by_run.setdefault(r["run_date"], {})[r["env"]] = r["cnt"]

        # --- component bands per run ---
        band_rows = _rows(
            cur.execute("""
            SELECT
                date(o.fetched_at) as run_date,
                CASE
                    WHEN e.match_score < 30  THEN 'lt_30'
                    WHEN e.match_score < 50  THEN 'grey'
                    ELSE                          'gt_50'
                END as band,
                COUNT(*)                                     AS n,
                ROUND(AVG(e.skills_hard_match), 1)           AS m_core,
                ROUND(AVG(json_extract(e.scoring_detail, '$.M_sec')) * 100, 1) AS m_sec,
                ROUND(AVG(e.experience_match), 1)            AS f_exp,
                ROUND(AVG(e.location_match), 1)              AS loc,
                ROUND(AVG(e.market_competitiveness), 1)      AS market
            FROM offer_evaluations e
            JOIN offers o ON o.id = e.offer_id
            WHERE e.match_score IS NOT NULL
            GROUP BY run_date, band
            ORDER BY run_date DESC, band
        """)
        )
        bands_by_run: dict[str, list] = {}
        for r in band_rows:
            bands_by_run.setdefault(r["run_date"], []).append(
                {
                    "band": r["band"],
                    "n": r["n"],
                    "m_core": r["m_core"],
                    "m_sec": r["m_sec"],
                    "f_exp": r["f_exp"],
                    "loc": r["loc"],
                    "market": r["market"],
                }
            )

        # --- actionable offers (score >= 50, no block) per run ---
        act_rows = _rows(
            cur.execute("""
            SELECT
                o.id, o.title, o.company_name, o.city, o.work_mode,
                e.match_score, e.recommendation, e.llm_apply_signal,
                date(o.fetched_at) as run_date
            FROM offer_evaluations e
            JOIN offers o ON o.id = e.offer_id
            WHERE e.match_score >= 50
              AND (e.apply_block IS NULL OR e.apply_block = '')
            ORDER BY o.fetched_at DESC, e.match_score DESC
        """)
        )
        actionable_by_run: dict[str, list] = {}
        for r in act_rows:
            actionable_by_run.setdefault(r["run_date"], []).append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "company_name": r["company_name"],
                    "city": r["city"],
                    "work_mode": r["work_mode"],
                    "match_score": r["match_score"],
                    "recommendation": r["recommendation"],
                    "llm_apply_signal": r["llm_apply_signal"],
                }
            )

    result = []
    for r in rows:
        rd = r["run_date"]
        result.append(
            {
                "run_date": rd,
                "fetched": r["fetched"],
                "classified": r["classified"],
                "evaluated": r["evaluated"],
                "score_ge_35": r["score_ge_35"],
                "score_ge_50": r["score_ge_50"],
                "sent": r["sent"],
                "avg_score": r["avg_score"],
                "avg_m_core": r["avg_m_core"],
                "avg_f_exp": r["avg_f_exp"],
                "avg_location": r["avg_location"],
                "avg_market": r["avg_market"],
                "env_compat": env_by_run.get(rd, {}),
                "bands": bands_by_run.get(rd, []),
                "actionable": actionable_by_run.get(rd, []),
            }
        )
    return jsonify(result)


# ── Pipeline execution ────────────────────────────────────────────────


def _watch_process(proc: subprocess.Popen, log_file, run_id: int) -> None:
    proc.wait()
    log_file.close()
    if proc.returncode != 0:
        try:
            conn = get_connection()
            conn.execute(
                "UPDATE search_runs SET status='error' WHERE id=? AND status='running'",
                (run_id,),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.error("Error actualizando status del run %d: %s", run_id, e)


@app.route("/api/scraper/cooldown")
def api_scraper_cooldown():
    """Lee el lockfile del scraper (20h mínimo entre runs)."""
    lockfile = Path("data/.last_infojobs_run")
    if not lockfile.exists():
        return jsonify(ready=True, seconds_remaining=0)
    try:
        last_run = float(lockfile.read_text().strip())
    except (ValueError, OSError):
        return jsonify(ready=True, seconds_remaining=0)
    elapsed = time.time() - last_run
    remaining = max(0, int(20 * 3600 - elapsed))
    return jsonify(ready=remaining <= 0, seconds_remaining=remaining)


@app.route("/api/pipeline/run", methods=["POST"])
def api_pipeline_run():
    data = request.get_json(silent=True) or {}
    with contextlib.closing(get_connection()) as conn:
        cur = conn.cursor()
        running = cur.execute("SELECT id FROM search_runs WHERE status='running'").fetchone()
        if running:
            return jsonify(error="Pipeline ya en ejecución", run_id=running[0]), 409

        params = json.dumps(
            {
                "skip_fetch": data.get("skip_fetch", False),
                "dry_run": data.get("dry_run", False),
                "since_date": data.get("since_date", "_24_HOURS"),
                "limit_eval": data.get("limit_eval", 30),
                "limit_enrich": data.get("limit_enrich", 50),
            }
        )
        cur.execute(
            "INSERT INTO search_runs (status, query_params) VALUES ('running', ?)",
            (params,),
        )
        run_id = cur.lastrowid
        conn.commit()

    LIVE_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(LIVE_LOG, "w")
    cmd = [
        sys.executable,
        "-m",
        "src.pipeline.run",
        "--run-id",
        str(run_id),
    ]
    if data.get("skip_fetch"):
        cmd.append("--skip-fetch")
    if data.get("dry_run"):
        cmd.append("--dry-run")
    if data.get("since_date"):
        cmd.extend(["--since-date", data["since_date"]])
    if data.get("limit_eval") is not None:
        cmd.extend(["--limit-eval", str(data["limit_eval"])])

    proc_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=proc_env,
    )
    conn = get_connection()
    conn.execute("UPDATE search_runs SET pid=? WHERE id=?", (proc.pid, run_id))
    conn.commit()
    conn.close()
    t = threading.Thread(target=_watch_process, args=(proc, log_file, run_id), daemon=True)
    t.start()

    log.info("Pipeline lanzado: run_id=%d, cmd=%s", run_id, cmd)
    return jsonify(status="started", run_id=run_id)


@app.route("/api/pipeline/status")
def api_pipeline_status():
    """Consulta si hay un pipeline en ejecución (reconexión post‑restart).

    El offset se envía a 0 para que al reconectar se vea el log completo
    desde el inicio, no solo líneas nuevas.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, pid FROM search_runs WHERE status='running' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return jsonify(running=False)
        return jsonify(running=True, run_id=row[0], pid=row[1], offset=0)
    finally:
        conn.close()


@app.route("/api/pipeline/stop", methods=["POST"])
def api_pipeline_stop():
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, pid FROM search_runs WHERE status='running' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return jsonify(error="No hay pipeline en ejecución"), 404
        if not row[1]:
            return jsonify(error="PID desconocido (pipeline lanzado antes de esta versión)"), 404
        run_id, pid = row[0], row[1]
        try:
            os.kill(pid, signal.SIGTERM)
            log.info("Pipeline detenido: run_id=%d, pid=%d", run_id, pid)
            return jsonify(status="stopped", run_id=run_id)
        except ProcessLookupError:
            return jsonify(status="already_finished", run_id=run_id)
    except Exception as e:
        log.error("Error deteniendo pipeline: %s", e)
        return jsonify(error=str(e)), 500
    finally:
        conn.close()


@app.route("/api/pipeline/log")
def api_pipeline_log():
    offset = request.args.get("offset", 0, type=int)
    run_id = request.args.get("run_id", type=int)

    lines = []
    finished = False
    try:
        if LIVE_LOG.exists():
            size = LIVE_LOG.stat().st_size
            with open(LIVE_LOG) as f:
                f.seek(offset)
                new_data = f.read()
            if new_data:
                lines = new_data.splitlines(keepends=True)
            new_offset = size
        else:
            new_offset = offset
    except OSError:
        new_offset = offset

    if any(
        "Pipeline completado" in line
        or "Pipeline abortado" in line
        or "Pipeline interrumpido" in line
        for line in lines
    ):
        finished = True
    elif run_id:
        try:
            conn = get_connection()
            row = conn.execute("SELECT status FROM search_runs WHERE id=?", (run_id,)).fetchone()
            conn.close()
            if row and row[0] != "running":
                finished = True
        except Exception:
            pass

    return jsonify(lines=lines, offset=new_offset, finished=finished)


# ── Serve static files & SPA ──────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"


@app.route("/static/<path:filename>")
def static_files(filename):
    response = send_from_directory(str(STATIC_DIR), filename)
    if filename.endswith((".js", ".css")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/")
def index():
    html = (TEMPLATE_DIR / "dashboard.html").read_text(encoding="utf-8")
    return html


# ── Main ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Job Intelligence Dashboard")
    parser.add_argument("--port", type=int, default=8080, help="Puerto (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", help="Modo debug Flask")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    log.info("Dashboard arrancando en http://%s:%d", args.host, args.port)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
