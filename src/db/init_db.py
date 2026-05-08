"""
Inicializa la base de datos SQLite aplicando migraciones en orden.
Uso: python src/db/init_db.py
"""

import logging
import os
from pathlib import Path
import sqlite3

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "src" / "db" / "migrations"
DB_PATH = PROJECT_ROOT / os.getenv("DB_PATH", "data/jobs.db")


def get_connection():
    """Devuelve una conexión sqlite3 a la DB configurada."""
    return sqlite3.connect(DB_PATH)


def ensure_migration_log(conn):
    """Crea la tabla migration_log si no existe."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS migration_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            applied_at DATETIME NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def get_applied_migrations(conn):
    """Devuelve un set con los nombres de migraciones ya aplicadas."""
    try:
        cursor = conn.execute("SELECT filename FROM migration_log")
        return {row[0] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return set()


def apply_migrations(conn):
    """Aplica todas las migraciones nuevas en orden."""
    if not MIGRATIONS_DIR.exists():
        log.warning("Directorio de migraciones no existe: %s", MIGRATIONS_DIR)
        return

    ensure_migration_log(conn)
    applied = get_applied_migrations(conn)

    migration_files = sorted(
        f.name for f in MIGRATIONS_DIR.iterdir() if f.suffix == ".sql"
    )

    for filename in migration_files:
        if filename in applied:
            log.debug("Migración ya aplicada, saltando: %s", filename)
            continue

        filepath = MIGRATIONS_DIR / filename
        log.info("Aplicando migración: %s", filename)
        sql = filepath.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute("INSERT INTO migration_log (filename) VALUES (?)", (filename,))
        conn.commit()
        log.info("Migración aplicada: %s", filename)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # Aplicar migraciones en orden
        apply_migrations(conn)

        # Verificar tablas
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
    log.info("Tablas en DB (%d): %s", len(tables), ", ".join(tables))


if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        log.error("Error inicializando DB: %s", e)
        raise SystemExit(1) from e
