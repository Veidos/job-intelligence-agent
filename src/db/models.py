"""
DB helpers for Job Intelligence Agent.
Schema source of truth: src/db/schema.sql
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from src.db.init_db import get_connection

log = logging.getLogger(__name__)


def json_serialize(data) -> str:
    if data is None:
        return json.dumps(None)
    return json.dumps(data, ensure_ascii=False)


def json_deserialize(text: str):
    if text is None or text == "":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.error("Error deserializando JSON: %s | texto: %.100s", e, text)
        return None


@dataclass
class UserSettings:
    id: int | None = None
    send_time: str = "09:00"
    max_offers_day: int = 3
    send_mode: str = "morning"
    min_score_send: int = 35
    weekly_summary: int = 1
    strategic_alerts: int = 1


def get_user_settings() -> UserSettings:
    """Devuelve el registro de user_settings, o crea uno con defaults.

    TODO: INSERT defaults si se necesita persistencia.
    Por ahora los defaults se devuelven en memoria sin tocar la DB.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        row = cur.execute(
            """SELECT send_time, max_offers_day, send_mode,
                      min_score_send, weekly_summary, strategic_alerts
               FROM user_settings ORDER BY id LIMIT 1"""
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return UserSettings()

    return UserSettings(
        send_time=row[0] or "09:00",
        max_offers_day=int(row[1] or 3),
        send_mode=row[2] or "morning",
        min_score_send=int(row[3] or 35),
        weekly_summary=int(row[4] or 1),
        strategic_alerts=int(row[5] or 1),
    )
