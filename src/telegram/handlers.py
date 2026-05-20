"""Handlers para comandos de feedback de Telegram.

Procesa /f1, /f2, /f3, /dia y los guarda en user_feedback.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_reply(chat_id: int, text: str) -> bool:
    """Envía respuesta al usuario."""
    import requests

    try:
        r = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        log.error("Error enviando respuesta: %s", e)
        return False


def get_latest_daily_offers() -> list[int]:
    """Obtiene IDs de ofertas del último envío diario ordenados por daily_position."""
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT offer_id FROM offer_evaluations
        WHERE sent_via_telegram = 1
        ORDER BY daily_position ASC, sent_at DESC
        LIMIT 3
        """,
    ).fetchall()
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


def handle_command(
    command: str, args: str, chat_id: int, user_id: int | None = None
) -> str:
    """Procesa un comando y devuelve la respuesta."""
    cmd = command.lower().strip()

    if cmd == "/f1":
        return handle_fb_command("f1", args, 0, user_id, chat_id)
    if cmd == "/f2":
        return handle_fb_command("f2", args, 1, user_id, chat_id)
    if cmd == "/f3":
        return handle_fb_command("f3", args, 2, user_id, chat_id)
    if cmd == "/dia":
        return handle_dia_command(args, user_id)

    return "Comando desconocido. Usa /f1, /f2, /f3 o /dia"


def handle_fb_command(
    fb_type: str,
    text: str,
    position: int,
    user_id: int | None,
    chat_id: int,
) -> str:
    """Procesa comandos de feedback sobre ofertas."""
    if not text or not text.strip():
        return f"Usa /{fb_type} <tu feedback>\n\nEjemplo: /{fb_type} Me gusta esta oferta pero el salario es bajo"

    offer_ids = get_latest_daily_offers()

    if not offer_ids:
        return "No hay ofertas del día recientes. Ejecuta el pipeline primero."

    if position >= len(offer_ids):
        return f"No existe oferta en posición {position + 1}. El último daily tenía {len(offer_ids)} ofertas."

    offer_id = offer_ids[position]
    success = save_feedback(fb_type, text.strip(), offer_id, user_id)

    if success:
        return f"Feedback registrado para oferta {position + 1} ✓\n\nGracias por tu opinión."
    return "Error al guardar反馈. Intenta de nuevo."


def handle_dia_command(text: str, user_id: int | None) -> str:
    """Procesa comando de estado emocional del día."""
    if not text or not text.strip():
        return (
            "Usa /dia <tu estado>\n\nEjemplo: /dia Hoy me siento motivado pero cansado"
        )

    success = save_feedback("dia", text.strip(), None, user_id)

    if success:
        return "Estado del día registrado ✓\n\nGracias por compartir."
    return "Error al guardar. Intenta de nuevo."


def handle_update(update: dict[str, Any]) -> str | None:
    """Procesa un update de Telegram webhook."""
    if "message" not in update:
        return None

    message = update["message"]
    chat = message.get("chat", {})
    user = message.get("from", {})
    chat_id = chat.get("id")
    user_id = user.get("id")
    text = message.get("text", "")

    if not text or not text.startswith("/"):
        return None

    parts = text.split(" ", 1)
    command = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    response = handle_command(command, args, chat_id, user_id)
    send_reply(chat_id, response)
    return response


def run_webhook():
    """Run como webhook (para servidor)."""
    import json
    import sys

    data = json.load(sys.stdin)
    handle_update(data)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Handler de feedback Telegram")
    parser.add_argument(
        "--test", action="store_true", help="Probar con datos de ejemplo"
    )
    args = parser.parse_args()

    if args.test:
        test_update = {
            "message": {
                "chat": {"id": 123456},
                "from": {"id": 111},
                "text": "/f1 Esta oferta me interesa mucho",
            }
        }
        handle_update(test_update)
        print("Test ejecutado")
