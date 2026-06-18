"""Módulo de lógica para feedback de Telegram.

Funciones puras de acceso a DB para el bot de Telegram.
No contiene HTTP ni lógica de Telegram (eso está en bot.py).
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)


def get_latest_daily_offers() -> list[int]:
    """Obtiene IDs de ofertas del último envío diario ordenados por daily_position.

    Filtra por la fecha del último envío real, no por las últimas 3 evaluaciones.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT offer_id FROM offer_evaluations
            WHERE sent_via_telegram = 1
              AND date(sent_at) = (
                  SELECT date(MAX(sent_at))
                  FROM offer_evaluations
                  WHERE sent_via_telegram = 1
              )
            ORDER BY daily_position ASC
            LIMIT 3
            """,
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def save_feedback(
    feedback_type: str,
    raw_text: str,
    offer_id: int | None = None,
    user_id: int | None = None,
) -> bool:
    """Guarda feedback en la tabla user_feedback."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO user_feedback (offer_id, feedback_type, raw_text, processed)
            VALUES (?, ?, ?, 0)
            """,
            (offer_id, feedback_type, raw_text),
        )
        conn.commit()
        log.info(
            "Feedback guardado: tipo=%s, offer_id=%s, texto=%s",
            feedback_type,
            offer_id,
            raw_text[:50],
        )
        return True
    except Exception as e:
        log.error("Error guardando feedback: %s", e)
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("Módulo de lógica de feedback. Usa bot.py para ejecutar el bot.")
    print("Funciones disponibles: get_latest_daily_offers(), save_feedback()")
