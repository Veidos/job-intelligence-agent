"""Backfill tests run entirely against a temporary SQLite database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def test_backfill_uses_offer_null_experience_over_stored_legacy_f_exp(
    tmp_path: Path, schema_sql: str, monkeypatch, capsys
):
    from src.pipeline import backfill_scores

    db_path = tmp_path / "backfill-copy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.execute(
        "INSERT INTO offers (source_id, title, experience_min) VALUES (?, ?, NULL)",
        ("BACKFILL-NULL-EXP", "Historical role"),
    )
    offer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    scoring_detail = {
        "M_core": 0.5,
        "M_sec": 0.0,
        "F_exp": 1.0,
        "F_fit": 0.5,
        "weights": {
            "W_CORE": 0.6,
            "W_SEC": 0.0,
            "W_EXP": 0.25,
            "W_FIT": 0.15,
            "secondary_redistributed": True,
        },
        "skill_detail": {"core": [], "secondary": []},
    }
    conn.execute(
        """INSERT INTO offer_evaluations
           (offer_id, experience_match, scoring_detail, match_score, recommendation)
           VALUES (?, 100, ?, 62, 'Aplicar')""",
        (
            offer_id,
            json.dumps(scoring_detail),
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        backfill_scores,
        "get_connection",
        lambda: sqlite3.connect(db_path),
    )
    backfill_scores.main()
    assert "Actualizadas: 1 ofertas" in capsys.readouterr().out

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """SELECT e.match_score, e.recommendation, e.experience_match, e.scoring_detail
           FROM offer_evaluations e WHERE e.offer_id=?""",
        (offer_id,),
    ).fetchone()
    conn.close()

    assert row[0] == 50
    assert row[1] == "Con expectativas bajas"
    assert row[2] is None
    updated_detail = json.loads(row[3])
    assert updated_detail["F_exp"] is None
    assert updated_detail["exp_redistributed"] is True
