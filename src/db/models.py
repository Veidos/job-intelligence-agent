"""
SQLAlchemy models for Job Intelligence Agent.
Única fuente de verdad: PERFIL.md
"""

import json
import logging

from sqlalchemy import Column, DateTime, Integer, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker

log = logging.getLogger(__name__)

DB_PATH = "data/jobs.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def json_serialize(data) -> str:
    """Serializa un objeto Python a JSON string para almacenar en TEXT."""
    if data is None:
        return json.dumps(None)
    return json.dumps(data, ensure_ascii=False)


def json_deserialize(text: str):
    """Deserializa un JSON string desde TEXT a objeto Python."""
    if text is None or text == "":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.error("Error deserializando JSON: %s | texto: %.100s", e, text)
        return None


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    updated_at = Column(DateTime, default=func.datetime("now"))
    send_time = Column(String, default="09:00")
    max_offers_day = Column(Integer, default=3)
    send_mode = Column(String, default="morning")
    min_score_send = Column(Integer, default=35)
    weekly_summary = Column(Integer, default=1)
    strategic_alerts = Column(Integer, default=1)


def get_user_settings() -> UserSettings:
    """Devuelve el registro de user_settings, o crea uno con defaults."""
    with SessionLocal() as session:
        stmt = select(UserSettings).order_by(UserSettings.id).limit(1)
        record = session.scalar(stmt)
        if record is None:
            record = UserSettings()
            session.add(record)
            session.commit()
            session.refresh(record)
            log.info("user_settings creado con valores por defecto")
        return record
