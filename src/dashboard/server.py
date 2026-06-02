#!/usr/bin/env python3
"""Servidor web del dashboard de Job Intelligence Agent.

Uso:
    python src/dashboard/server.py          # localhost:8080
    python src/dashboard/server.py --port 9090
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request, send_from_directory

from src.db.init_db import get_connection

log = logging.getLogger(__name__)

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
    conn = get_connection()
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
    max_score = cur.execute(
        "SELECT MAX(match_score) FROM offer_evaluations"
    ).fetchone()[0]

    rec_counts = _rows(
        cur.execute(
            """SELECT recommendation, COUNT(*) as cnt
               FROM offer_evaluations WHERE match_score IS NOT NULL
               GROUP BY recommendation ORDER BY cnt DESC"""
        )
    )

    last_run = cur.execute("SELECT MAX(fetched_at) FROM offers").fetchone()[0]

    conn.close()
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


@app.route("/api/offers")
def api_offers():
    conn = get_connection()
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
        sql += f" LIMIT {limit}"

    cur.execute(sql, params)
    rows = cur.fetchall()

    conn.close()

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
    conn = get_connection()
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
        conn.close()
        return jsonify(error="Not found"), 404

    cols = [d[0] for d in cur.description]
    r = dict(zip(cols, row))

    # feedback for this offer
    feedback = _rows(
        cur.execute(
            "SELECT * FROM user_feedback WHERE offer_id = ? ORDER BY created_at DESC",
            (offer_id,),
        )
    )

    # application for this offer
    app_row = cur.execute(
        "SELECT * FROM applications WHERE offer_id = ? ORDER BY applied_at DESC LIMIT 1",
        (offer_id,),
    ).fetchone()
    application = (
        dict(zip([d[0] for d in cur.description], app_row)) if app_row else None
    )

    conn.close()
    return jsonify(offer=r, feedback=feedback, application=application)


@app.route("/api/companies")
def api_companies():
    conn = get_connection()
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
    conn.close()
    return jsonify(rows)


@app.route("/api/feedback", methods=["GET", "POST"])
def api_feedback():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == "POST":
        data = request.get_json()
        offer_id = data.get("offer_id")
        raw_text = data.get("raw_text", "").strip()
        if not offer_id or not raw_text:
            conn.close()
            return jsonify(error="offer_id and raw_text required"), 400
        cur.execute(
            """INSERT INTO user_feedback (offer_id, feedback_type, raw_text)
               VALUES (?, 'dashboard', ?)""",
            (offer_id, raw_text),
        )
        conn.commit()
        conn.close()
        return jsonify(status="ok", id=cur.lastrowid)

    rows = _rows(
        cur.execute(
            """SELECT f.*, o.title AS offer_title, o.company_name
               FROM user_feedback f
               LEFT JOIN offers o ON o.id = f.offer_id
               ORDER BY f.created_at DESC LIMIT 200"""
        )
    )
    conn.close()
    return jsonify(rows)


@app.route("/api/applications", methods=["GET", "POST"])
def api_applications():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == "POST":
        data = request.get_json()
        offer_id = data.get("offer_id")
        if not offer_id:
            conn.close()
            return jsonify(error="offer_id required"), 400
        status = data.get("status", "applied")
        notes = data.get("notes", "")
        contact_name = data.get("contact_name", "")
        next_action = data.get("next_action_date", "")

        # upsert: si ya existe aplicación para esta oferta, actualizar
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
        conn.close()
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
    conn.close()
    return jsonify(rows)


@app.route("/api/applications/<int:app_id>", methods=["DELETE"])
def api_delete_application(app_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    conn.commit()
    conn.close()
    return jsonify(status="ok")


@app.route("/api/runs")
def api_runs():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = _rows(
        cur.execute("""SELECT * FROM search_runs ORDER BY ran_at DESC LIMIT 50""")
    )
    conn.close()
    return jsonify(rows)


# ── Serve static files & SPA ──────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(STATIC_DIR), filename)


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
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
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
