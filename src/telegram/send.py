"""
Telegram: envío diario de top ofertas evaluadas.
Lee user_settings para hora y número de ofertas.
Escucha comandos /f1 /f2 /f3 /dia para feedback.
"""

import json
import logging
import os
from datetime import date

import requests
from dotenv import load_dotenv

from src.db.init_db import get_connection
from src.db.models import get_user_settings
from src.utils.eligibility import (
    eligibility_order_sql,
    eligibility_status,
    is_eligible,
    recommendation_label,
    sendable_sql_predicate,
)

load_dotenv()

log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def _validate_config() -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise EnvironmentError(
            "TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID son obligatorios. Revisa tu archivo .env"
        )


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    _validate_config()
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


def get_send_candidates(
    date_scope: str = "latest",
    min_score: int | None = None,
    connection=None,
) -> list[dict]:
    """Return all sendable candidates, ordered eligible-first then review.

    Args:
        date_scope: 'latest' → solo ofertas del día más reciente,
                    'all'    → cualquier fecha (fallback histórico).
        min_score: Umbral de envío. If omitted, read user_settings (default 35).
        connection: Optional connection for read-only audits and tests.

    The eligibility ordering and decision use the shared eligibility policy.
    """
    date_filter = ""
    if date_scope == "latest":
        date_filter = "AND date(o.fetched_at) = (SELECT MAX(date(fetched_at)) FROM offers)"

    owns_connection = connection is None
    conn = connection or get_connection()
    try:
        cur = conn.cursor()
        if min_score is None:
            settings_row = cur.execute(
                "SELECT min_score_send FROM user_settings ORDER BY id LIMIT 1"
            ).fetchone()
            min_score = int(settings_row[0]) if settings_row and settings_row[0] is not None else 35

        sendable_predicate, sendable_params = sendable_sql_predicate("e")
        eligibility_order, eligibility_order_params = eligibility_order_sql("e")
        rows = cur.execute(
            f"""SELECT
                o.id, o.title, o.company_name, o.city, o.work_mode,
                o.salary_min, o.salary_max, o.url, o.fetched_at,
                e.id AS eval_id, e.match_score, e.recommendation,
                e.hr_concerns, e.strengths, e.interview_prep,
                e.apply_block, e.apply_block_reason, e.llm_apply_signal,
                o.relevance_flag, o.role_normalized, e.sent_at
            FROM offer_evaluations e
            JOIN offers o ON o.id = e.offer_id
            WHERE e.sent_via_telegram = 0
              AND e.match_score >= ?
              AND {sendable_predicate}
              {date_filter}
            ORDER BY
              {eligibility_order},
              CASE e.recommendation
                WHEN 'Aplicar'                THEN 0
                WHEN 'Con expectativas bajas' THEN 1
                WHEN 'No aplicar'             THEN 2
                ELSE 3
              END,
              CASE e.llm_apply_signal
                WHEN 'yes'   THEN 0
                WHEN 'maybe' THEN 1
                WHEN 'no'    THEN 2
                ELSE 3
              END,
              e.match_score DESC
        """,
            (min_score, *sendable_params, *eligibility_order_params),
        ).fetchall()
        cols = [d[0] for d in cur.description]
        candidates = []
        for row in rows:
            offer = dict(zip(cols, row))
            status = eligibility_status(offer)
            offer["eligibility_status"] = status.value
            offer["eligible_for_send"] = is_eligible(offer, status)
            if offer["eligible_for_send"]:
                candidates.append(offer)
        return candidates
    finally:
        if owns_connection:
            conn.close()


def get_top_offers(
    max_offers: int = 3,
    date_scope: str = "latest",
    min_score: int | None = None,
) -> list[dict]:
    """Return the top offers after applying the shared eligibility policy."""
    return get_send_candidates(date_scope=date_scope, min_score=min_score)[:max_offers]


def format_offer(offer: dict, position: int, is_historical: bool = False) -> str:
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

    date_note = ""
    if is_historical and offer.get("fetched_at"):
        fetched = offer["fetched_at"][:10] if len(offer["fetched_at"]) > 10 else offer["fetched_at"]
        date_note = f" | 📅 {fetched}"

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

    action_label = recommendation_label(offer)
    review_reason = ""
    if offer.get("eligibility_status") == "review" and offer.get("apply_block_reason"):
        review_reason = f"\n🔎 Revisar: {offer['apply_block_reason']}"

    return (
        f"[{position}] {emoji} <b>{offer['title']}</b> | {offer['company_name']}\n"
        f"📍 {offer.get('work_mode', 'N/A')} | {offer.get('city', 'N/A')}{salary}{date_note}\n"
        f"✅ Match: {score}/100 — {action_label}"
        f"{review_reason}"
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
    try:
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
    finally:
        conn.close()


def send_daily() -> None:
    _validate_config()
    settings = get_user_settings()
    max_offers = settings.max_offers_day if settings else 3
    min_score = settings.min_score_send if settings else 35
    today = date.today().strftime("%d %b %Y")

    offers = get_top_offers(max_offers, date_scope="latest", min_score=min_score)
    is_historical = False

    if not offers:
        offers = get_top_offers(max_offers, date_scope="all", min_score=min_score)
        if offers:
            is_historical = True
        else:
            send_message(
                f"📋 <b>OFERTAS DEL DÍA — {today}</b>\n\nSin ofertas relevantes disponibles."
            )
            return

    header = (
        f"📋 <b>OFERTAS DEL DÍA — {today}</b>\n\n"
        if not is_historical
        else f"📋 <b>OFERTAS DEL DÍA — {today}</b>\n\n"
        "Hoy no hay ofertas nuevas que encajen, "
        "pero estas de días anteriores merecen un vistazo:\n\n"
    )
    blocks = []
    eval_ids = []
    positions = []

    for i, offer in enumerate(offers, 1):
        blocks.append(format_offer(offer, i, is_historical=is_historical))
        eval_ids.append(offer["eval_id"])
        positions.append(i)

    feedback_lines = "\n".join(
        f"/f{i} [comentario] → sobre oferta {i}" for i in range(1, len(offers) + 1)
    )
    footer = (
        "\n───\n💬 <i>Feedback opcional:</i>\n"
        f"{feedback_lines}\n"
        "/dia [comentario] → cómo te sientes hoy"
    )

    message = header + "\n\n".join(blocks) + footer
    if send_message(message):
        mark_sent(eval_ids, positions)
        prefix = "históricas" if is_historical else ""
        log.info("Mensaje diario enviado con %d ofertas %s", len(offers), prefix)
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
            content = text[len(prefix) :].strip()
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
