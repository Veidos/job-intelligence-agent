"""Read-only audit of blocked offers and Telegram sends.

Run with ``python -m src.pipeline.audit_blocked_sends [--since YYYY-MM-DD]``.
The cutoff should be set to the effective fix date before committing.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import date
from pathlib import Path

from src.db.init_db import DB_PATH
from src.telegram.send import get_send_candidates
from src.utils.eligibility import HARD_BLOCK_CODES

log = logging.getLogger(__name__)

# Provisional: confirm/update to the effective fix date before committing.
FIX_DATE = date(2026, 10, 5)


def _parse_iso_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("usa una fecha ISO YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("usa una fecha ISO YYYY-MM-DD")
    return parsed


def _date_part(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _is_hard_block(value: object) -> bool:
    return str(value or "").strip().lower() in HARD_BLOCK_CODES


def _display(value: object) -> str:
    """Keep scraped control characters from affecting terminal output."""
    text = str(value or "")
    return "".join(char if char.isprintable() else " " for char in text).strip()


def open_readonly_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _get_min_score(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT min_score_send FROM user_settings ORDER BY id LIMIT 1").fetchone()
    return int(row[0]) if row and row[0] is not None else 35


def audit_records(
    conn: sqlite3.Connection,
    since: date | None = None,
    fix_date: date = FIX_DATE,
) -> dict:
    """Collect audit findings from an already-open read-only connection."""
    min_score = _get_min_score(conn)
    clauses = [
        "e.apply_block IS NOT NULL",
        "TRIM(e.apply_block) <> ''",
        "LOWER(TRIM(e.apply_block)) NOT IN ('none', 'null')",
    ]
    params: list[object] = []
    if since:
        clauses.append("date(COALESCE(e.sent_at, o.fetched_at)) >= ?")
        params.append(since.isoformat())

    where = " AND ".join(clauses)
    cursor = conn.execute(
        f"""SELECT o.id, o.title, o.company_name, o.fetched_at,
                   e.match_score, e.recommendation, e.apply_block,
                   e.apply_block_reason, e.llm_apply_signal,
                   e.sent_via_telegram, e.sent_at
            FROM offer_evaluations e
            JOIN offers o ON o.id = e.offer_id
            WHERE {where}
            ORDER BY e.match_score DESC, o.id""",
        params,
    )
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    blockers = [dict(zip(columns, row)) for row in rows]

    hard_sent_after_fix = []
    hard_sent_missing_timestamp = []
    for row in blockers:
        if not _is_hard_block(row["apply_block"]) or not row["sent_via_telegram"]:
            continue
        sent_date = _date_part(row["sent_at"])
        if sent_date is None:
            hard_sent_missing_timestamp.append(row)
        elif sent_date >= fix_date:
            hard_sent_after_fix.append(row)

    send_candidates = get_send_candidates(
        date_scope="all",
        min_score=min_score,
        connection=conn,
    )
    if since:
        send_candidates = [
            row
            for row in send_candidates
            if (_date_part(row.get("fetched_at")) or date.min) >= since
        ]
    selectable_hard = [row for row in send_candidates if _is_hard_block(row.get("apply_block"))]

    sent_blockers = [row for row in blockers if row["sent_via_telegram"]]
    unsent_hard = [
        row
        for row in blockers
        if not row["sent_via_telegram"] and _is_hard_block(row["apply_block"])
    ]
    over_threshold = [row for row in blockers if (row["match_score"] or 0) >= min_score]

    failed = bool(selectable_hard or hard_sent_after_fix)
    return {
        "min_score": min_score,
        "fix_date": fix_date,
        "sent_blockers": sent_blockers,
        "unsent_hard": unsent_hard,
        "over_threshold": over_threshold,
        "selectable_hard": selectable_hard,
        "hard_sent_after_fix": hard_sent_after_fix,
        "hard_sent_missing_timestamp": hard_sent_missing_timestamp,
        "incomplete": bool(hard_sent_missing_timestamp),
        "failed": failed,
    }


def print_audit(report: dict, output=None) -> None:
    output = output or sys.stdout
    print(f"Umbral de envío: {report['min_score']} | FIX_DATE: {report['fix_date']}", file=output)

    print("\nBloqueos con apply_block ya enviados:", file=output)
    if not report["sent_blockers"]:
        print("  (ninguno)", file=output)
    for row in report["sent_blockers"]:
        sent_date = _date_part(row["sent_at"])
        if _is_hard_block(row["apply_block"]):
            if sent_date is None:
                label = "sent_at no verificable"
            elif sent_date < report["fix_date"]:
                label = "histórico previo al fix"
            else:
                label = "ERROR: bloqueo duro enviado tras el fix"
        else:
            label = "REVISAR enviado"
        print(
            f"  [{label}] id={row['id']} score={row['match_score']} "
            f"bloqueo={_display(row['apply_block'])} enviado={row['sent_at']} "
            f"{_display(row['title'])} — {_display(row['company_name'])}",
            file=output,
        )

    print("\nBloqueos pendientes y sobre el umbral:", file=output)
    print("  Bloqueos duros sin enviar (bloqueadas correctamente):", file=output)
    if not report["unsent_hard"]:
        print("  (ninguna)", file=output)
    for row in report["unsent_hard"]:
        print(
            f"  id={row['id']} score={row['match_score']} "
            f"bloqueo={_display(row['apply_block'])} "
            f"{_display(row['title'])} — {_display(row['company_name'])}",
            file=output,
        )

    print(f"  Bloqueadas con match_score >= {report['min_score']}:", file=output)
    if not report["over_threshold"]:
        print("  (ninguna)", file=output)
    for row in report["over_threshold"]:
        sent = "sí" if row["sent_via_telegram"] else "no"
        print(
            f"  id={row['id']} score={row['match_score']} "
            f"bloqueo={_display(row['apply_block'])} enviado={sent} "
            f"{_display(row['title'])} — {_display(row['company_name'])}",
            file=output,
        )

    if report["selectable_hard"]:
        print("\nERROR: hay bloqueos duros seleccionables por send.py.", file=output)
    if report["hard_sent_after_fix"]:
        print("\nERROR: hay bloqueos duros enviados después de FIX_DATE.", file=output)
    if report["hard_sent_missing_timestamp"]:
        print("\nAUDITORÍA INCOMPLETA: bloqueo duro enviado sin sent_at verificable.", file=output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auditoría de solo lectura de bloqueos y envíos")
    parser.add_argument(
        "--since",
        type=_parse_iso_date,
        help=(
            "Incluir ofertas cuyo envío (o captura si siguen sin enviar) sea desde "
            "esa fecha ISO YYYY-MM-DD"
        ),
    )
    args = parser.parse_args(argv)

    try:
        conn = open_readonly_connection()
    except sqlite3.Error as exc:
        log.error("No se pudo abrir la base en modo solo lectura: %s", exc)
        return 2
    try:
        report = audit_records(conn, since=args.since)
    except sqlite3.Error as exc:
        log.error("Error consultando la auditoría: %s", exc)
        return 2
    finally:
        conn.close()

    print_audit(report)
    if report["failed"]:
        return 1
    if report["incomplete"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
