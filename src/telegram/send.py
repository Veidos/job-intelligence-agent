"""
Telegram: envío diario de top ofertas evaluadas.
Lee user_settings para hora y número de ofertas.
Escucha comandos /f1 /f2 /f3 /dia para feedback.
"""
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
import requests
from src.db.init_db import get_connection
from src.db.models import get_user_settings

load_dotenv()

log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    try:
        r = requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.error("Error enviando mensaje Telegram: %s", e)
        return False


def get_top_offers(max_offers: int = 3) -> list[dict]:
    """Selecciona top ofertas evaluadas no enviadas, priorizando score."""
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT
            o.id, o.title, o.company_name, o.city, o.work_mode,
            o.salary_min, o.salary_max, o.url,
            e.id as eval_id, e.match_score, e.recommendation,
            e.hr_concerns, e.strengths, e.interview_prep,
            o.relevance_flag, o.role_normalized
        FROM offer_evaluations e
        JOIN offers o ON o.id = e.offer_id
        WHERE e.sent_via_telegram = 0
          AND e.match_score >= 35
        ORDER BY e.match_score DESC
        LIMIT ?
    """,
        (max_offers,),
    ).fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def format_offer(offer: dict, position: int) -> str:
    score = offer["match_score"]
    if score >= 75:
        emoji = "🟢"
    elif score >= 55:
        emoji = "🟡"
    else:
        emoji = "🟠"

    salary = ""
    if offer.get("salary_min") and offer.get("salary_max"):
        salary = f" | {int(offer['salary_min']):,}–{int(offer['salary_max']):,}€"
    elif offer.get("salary_min"):
        salary = f" | desde {int(offer['salary_min']):,}€"

    url = offer.get("url") or ""
    if url and not url.startswith("http"):
        url = f"https://www.infojobs.net{url}"

    concerns = json.loads(offer.get("hr_concerns") or "[]")
    first_concern = f"\n⚠️ {concerns[0]}" if concerns else ""

    interview = json.loads(offer.get("interview_prep") or "[]")
    first_prep = f"\n🎯 {interview[0]}" if interview else ""

    low_score_note = ""
    if score < 55:
        low_score_note = "\n<i>Incluida por falta de opciones superiores</i>"

    return (
        f"[{position}] {emoji} <b>{offer['title']}</b> | {offer['company_name']}\n"
        f"📍 {offer.get('work_mode', 'N/A')} | {offer.get('city', 'N/A')}{salary}\n"
        f"✅ Match: {score}/100 — {offer['recommendation']}"
        f"{first_concern}"
        f"{first_prep}"
        f"{low_score_note}\n"
        f"🔗 {url}"
    )


def mark_sent(eval_ids: list[int], positions: list[int]) -> None:
    conn = get_connection()
    cur = conn.cursor()
    for eval_id, pos in zip(eval_ids, positions):
        cur.execute(
            """
            UPDATE offer_evaluations
            SET sent_via_telegram = 1,
                sent_at = datetime('now'),
                daily_position = ?
            WHERE id = ?
        """,
            (pos, eval_id),
        )
    conn.commit()
    conn.close()


def save_feedback(position: int, text: str, feedback_type: str = "offer") -> None:
    conn = get_connection()
    cur = conn.cursor()
    offer_id = None
    if feedback_type == "offer":
        row = cur.execute(
            """
            SELECT offer_id FROM offer_evaluations
            WHERE sent_via_telegram = 1
              AND daily_position = ?
              AND date(sent_at) = date('now')
            ORDER BY sent_at DESC LIMIT 1
        """,
            (position,),
        ).fetchone()
        if row:
            offer_id = row[0]
    cur.execute(
        """
        INSERT INTO user_feedback (offer_id, feedback_type, raw_text)
        VALUES (?, ?, ?)
    """,
        (offer_id, feedback_type, text),
    )
    conn.commit()
    conn.close()


def send_daily() -> None:
    settings = get_user_settings()
    max_offers = settings.max_offers_day if settings else 3

    offers = get_top_offers(max_offers)
    today = date.today().strftime("%d %b %Y")

    if not offers:
        send_message(
            f"📋 <b>OFERTAS DEL DÍA — {today}</b>\n\nSin ofertas relevantes hoy."
        )
        return

    header = f"📋 <b>OFERTAS DEL DÍA — {today}</b>\n\n"
    blocks = []
    eval_ids = []
    positions = []

    for i, offer in enumerate(offers, 1):
        blocks.append(format_offer(offer, i))
        eval_ids.append(offer["eval_id"])
        positions.append(i)

    footer = (
        "\n───\n💬 <i>Feedback opcional:</i>\n"
        "/f1 [comentario] → sobre oferta 1\n"
        "/f2 [comentario] → sobre oferta 2\n"
        "/f3 [comentario] → sobre oferta 3\n"
        "/dia [comentario] → cómo te sientes hoy"
    )

    message = header + "\n\n".join(blocks) + footer
    if send_message(message):
        mark_sent(eval_ids, positions)
        log.info("Mensaje diario enviado con %d ofertas", len(offers))
    else:
        log.error("Fallo enviando mensaje diario")


def process_feedback(text: str) -> str:
    text = text.strip()
    if text.startswith("/dia "):
        content = text[5:].strip()
        save_feedback(0, content, feedback_type="daily")
        return "Entendido, lo tengo en cuenta 🧠"
    for i in range(1, 6):
        prefix = f"/f{i} "
        if text.startswith(prefix):
            content = text[len(prefix):].strip()
            save_feedback(i, content, feedback_type="offer")
            return "Anotado 📝"
    return ""


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="daily", choices=["daily", "feedback"])
    parser.add_argument("--text", default="")
    args = parser.parse_args()

    if args.mode == "daily":
        send_daily()
    elif args.mode == "feedback" and args.text:
        response = process_feedback(args.text)
        print(response)
