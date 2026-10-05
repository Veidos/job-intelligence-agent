"""Backfill: recalcula match_score usando los pesos efectivos versionados.

Uso:
    python -m src.pipeline.backfill_scores

Lee `scoring_detail`, reaplica la redistribución `W_SEC→W_CORE` cuando secondary
está vacío y renormaliza los componentes disponibles cuando F_exp es desconocido.
Actualiza `match_score`, `recommendation` y el desglose de pesos en DB.
"""

import contextlib
import json
import sqlite3

from src.db.init_db import get_connection
from src.pipeline.evaluate import compute_effective_weights, get_rating


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
        F_exp = sd.get("F_exp")
        F_fit = sd.get("F_fit", 0)
        weights = compute_effective_weights(has_secondary=has_sec, has_exp=F_exp is not None)

        new_score = round(
            min(
                max(
                    sum(
                        weights[name] * value
                        for name, value in {
                            "W_CORE": M_core,
                            "W_SEC": M_sec,
                            "W_EXP": F_exp,
                            "W_FIT": F_fit,
                        }.items()
                        if value is not None
                    ),
                    0.0,
                ),
                1.0,
            ),
            4,
        )
        new_score_int = round(new_score * 100)
        old_score_int = row["match_score"]

        current_weights = sd.get("weights", {})
        flags_current = current_weights.get("secondary_redistributed") is not None and sd.get(
            "exp_redistributed"
        ) == (F_exp is None)
        if new_score_int == old_score_int and flags_current:
            continue

        new_rec = get_rating(new_score)

        sd["weights"] = {
            **weights,
            "secondary_redistributed": weights["W_SEC"] == 0.0,
        }
        sd["exp_redistributed"] = F_exp is None

        with contextlib.closing(get_connection()) as conn:
            conn.execute(
                "UPDATE offer_evaluations SET match_score=?, recommendation=?, scoring_detail=? WHERE id=?",
                (new_score_int, new_rec, json.dumps(sd, ensure_ascii=False), row["id"]),
            )
            conn.commit()

        updated += 1
        print(
            f"  ✓ offer_id={row['offer_id']:>5}  {old_score_int:>3} → {new_score_int:>3}  {new_rec}"
        )

    print(f"\nActualizadas: {updated} ofertas")


if __name__ == "__main__":
    main()
