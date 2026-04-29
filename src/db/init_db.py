"""
Inicializa la base de datos SQLite desde schema.sql.
Uso: python src/db/init_db.py
"""
import logging
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "src" / "db" / "schema.sql"
DB_PATH = PROJECT_ROOT / os.getenv("DB_PATH", "data/jobs.db")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema no encontrado: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(schema_sql)
        conn.commit()

    log.info("Base de datos inicializada en: %s", DB_PATH)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
    log.info("Tablas creadas (%d): %s", len(tables), ", ".join(tables))


if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        log.error("Error inicializando DB: %s", e)
        raise SystemExit(1) from e
