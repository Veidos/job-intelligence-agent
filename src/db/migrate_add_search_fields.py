"""
Migración: añade campos search_layer, role_level, relevance_flag a offers
y crea la tabla search_config si no existe.
"""

import logging
import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto está en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.db.init_db import get_connection

log = logging.getLogger(__name__)


def migrate() -> None:
    conn = get_connection()
    cur = conn.cursor()

    # 1. Añadir columnas a offers (SQLite no soporta múltiples ADD COLUMN en un ALTER)
    existing_cols = {
        row[1] for row in cur.execute("PRAGMA table_info(offers)").fetchall()
    }

    alters = []
    if "search_layer" not in existing_cols:
        alters.append("ALTER TABLE offers ADD COLUMN search_layer INTEGER")
    if "role_level" not in existing_cols:
        alters.append("ALTER TABLE offers ADD COLUMN role_level INTEGER")
    if "relevance_flag" not in existing_cols:
        alters.append("ALTER TABLE offers ADD COLUMN relevance_flag TEXT")

    for sql in alters:
        log.info("Ejecutando: %s", sql)
        cur.execute(sql)

    # 2. Crear tabla search_config si no existe
    cur.execute("""
        CREATE TABLE IF NOT EXISTS search_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at DATETIME NOT NULL DEFAULT (datetime('now')),
            profile_id INTEGER REFERENCES candidate_profile(id),
            geo_hierarchy TEXT,
            role_hierarchy TEXT,
            active_geo_level INTEGER,
            active_role_level INTEGER,
            last_updated DATETIME NOT NULL DEFAULT (datetime('now'))
        )
    """)
    log.info("Tabla search_config verificada/creada")

    conn.commit()
    conn.close()
    log.info("Migración completada")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    migrate()
