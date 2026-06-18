"""Backfill: recalcula match_score con pesos redistribuidos si secondary está vacío.

Uso:
    python -m src.pipeline.backfill_scores

Lee scoring_detail existente, detecta secondary vacío, recalcula con
w_core=W_CORE+W_SEC (0.60) en lugar de W_CORE (0.45), y actualiza
match_score, recommendation y scoring_detail.weights en DB.
"""

import contextlib
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.db.init_db import get_connection

W_CORE, W_SEC, W_EXP, W_FIT = 0.45, 0.15, 0.25, 0.15


def get_rating(score: float) -> str:
    if score >= 0.75:
        return "Prioritario"
    if score >= 0.55:
        return "Aplicar"
    if score >= 0.35:
        return "Con expectativas bajas"
    return "No aplicar"


def main():
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, offer_id, match_score, scoring_detail
            FROM offer_evaluations
            WHERE scoring_detail IS NOT NULL
        """).fetchall()

    updated = 0
    for row in rows:
        sd = json.loads(row["scoring_detail"])
        sk = sd.get("skill_detail", {})
        sec = sk.get("secondary", []) or []
        has_sec = len(sec) > 0

        M_core = sd.get("M_core", 0)
        M_sec = sd.get("M_sec", 0)
        F_exp = sd.get("F_exp", 0)
        F_fit = sd.get("F_fit", 0)

        if not has_sec and M_sec == 0:
            w_core = W_CORE + W_SEC
            w_sec = 0.0
        else:
            w_core = W_CORE
            w_sec = W_SEC

        new_score = round(
            min(max(w_core * M_core + w_sec * M_sec + W_EXP * F_exp + W_FIT * F_fit, 0.0), 1.0), 4
        )
        new_score_int = round(new_score * 100)
        old_score_int = row["match_score"]

        has_flag = sd.get("weights", {}).get("secondary_redistributed") is not None
        if new_score_int == old_score_int and has_flag:
            continue

        new_rec = get_rating(new_score)

        sd["weights"] = {
            "W_CORE": w_core,
            "W_SEC": w_sec,
            "W_EXP": W_EXP,
            "W_FIT": W_FIT,
            "secondary_redistributed": w_sec == 0.0,
        }

        with contextlib.closing(get_connection()) as conn:
            conn.execute(
                "UPDATE offer_evaluations SET match_score=?, recommendation=?, scoring_detail=? WHERE id=?",
                (new_score_int, new_rec, json.dumps(sd, ensure_ascii=False), row["id"]),
            )
            conn.commit()

        updated += 1
        print(f"  ✓ offer_id={row['offer_id']:>5}  {old_score_int:>3} → {new_score_int:>3}  {new_rec}")

    print(f"\nActualizadas: {updated} ofertas")


if __name__ == "__main__":
    main()
