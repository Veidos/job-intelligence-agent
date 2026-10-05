"""Backfill: recalcula match_score usando los pesos efectivos versionados.

Uso:
    python -m src.pipeline.backfill_scores

Lee `scoring_detail` junto a `offers.experience_min`, reaplica la redistribución
`W_SEC→W_CORE` cuando secondary está vacío y renormaliza los componentes disponibles
cuando `experience_min` es NULL. Actualiza scores, `experience_match` y metadatos.
"""

import contextlib
import json
import sqlite3

from src.db.init_db import get_connection
from src.pipeline.evaluate import compute_effective_weights, get_rating


def recalculate_evaluation(scoring_detail: dict, experience_min: int | None) -> tuple:
    """Recalculate one historical evaluation from its stored components.

    The offer column is authoritative: NULL means its experience requirement
    was unknown, while 0 means no minimum requirement was stated.
    """
    details = dict(scoring_detail)
    if experience_min is None:
        F_exp = None
    elif experience_min == 0:
        F_exp = 1.0
    else:
        F_exp = details.get("F_exp")

    M_core = details.get("M_core", 0)
    M_sec = details.get("M_sec", 0)
    F_fit = details.get("F_fit", 0)
    skill_detail = details.get("skill_detail") or {}
    has_secondary = bool(skill_detail.get("secondary"))
    weights = compute_effective_weights(has_secondary=has_secondary, has_exp=F_exp is not None)
    components = {
        "W_CORE": M_core,
        "W_SEC": M_sec,
        "W_EXP": F_exp,
        "W_FIT": F_fit,
    }
    new_score = round(
        min(
            max(
                sum(
                    weights[name] * value for name, value in components.items() if value is not None
                ),
                0.0,
            ),
            1.0,
        ),
        4,
    )

    details["F_exp"] = F_exp
    details["weights"] = {
        **weights,
        "secondary_redistributed": weights["W_SEC"] == 0.0,
    }
    details["exp_redistributed"] = F_exp is None
    experience_match = round(F_exp * 100) if F_exp is not None else None
    return round(new_score * 100), get_rating(new_score), details, experience_match


def main():
    with contextlib.closing(get_connection()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT e.id, e.offer_id, e.match_score, e.experience_match,
                   e.scoring_detail, o.experience_min
            FROM offer_evaluations e
            JOIN offers o ON o.id = e.offer_id
            WHERE e.scoring_detail IS NOT NULL
        """).fetchall()

    updated = 0
    for row in rows:
        sd = json.loads(row["scoring_detail"])
        new_score_int, new_rec, updated_details, experience_match = recalculate_evaluation(
            sd, row["experience_min"]
        )
        old_score_int = row["match_score"]
        current_weights = sd.get("weights", {})
        expected_weights = updated_details["weights"]
        weights_current = all(
            current_weights.get(name) == value for name, value in expected_weights.items()
        )
        details_current = sd.get("exp_redistributed") == updated_details["exp_redistributed"]
        if (
            new_score_int == old_score_int
            and row["experience_match"] == experience_match
            and weights_current
            and details_current
        ):
            continue

        with contextlib.closing(get_connection()) as conn:
            conn.execute(
                """UPDATE offer_evaluations
                   SET match_score=?, recommendation=?, experience_match=?, scoring_detail=?
                   WHERE id=?""",
                (
                    new_score_int,
                    new_rec,
                    experience_match,
                    json.dumps(updated_details, ensure_ascii=False),
                    row["id"],
                ),
            )
            conn.commit()

        updated += 1
        print(
            f"  ✓ offer_id={row['offer_id']:>5}  {old_score_int:>3} → {new_score_int:>3}  {new_rec}"
        )

    print(f"\nActualizadas: {updated} ofertas")


if __name__ == "__main__":
    main()
