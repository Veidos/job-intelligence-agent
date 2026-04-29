"""
Migración: crea la tabla user_settings si no existe
e inserta un registro con valores por defecto si está vacía.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.db.init_db import get_connection

log = logging.getLogger(__name__)


def migrate() -> None:
    conn = get_connection()
    cur = conn.cursor()

    # 1. Crear tabla si no existe
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
            send_time TEXT DEFAULT '09:00',
            max_offers_day INTEGER DEFAULT 3,
            send_mode TEXT DEFAULT 'morning',
            min_score_send INTEGER DEFAULT 35,
            weekly_summary INTEGER DEFAULT 1,
            strategic_alerts INTEGER DEFAULT 1
        )
    """)
    log.info("Tabla user_settings verificada/creada")

    # 2. Insertar registro por defecto si la tabla está vacía
    count = cur.execute("SELECT COUNT(*) FROM user_settings").fetchone()[0]
    if count == 0:
        cur.execute("""
            INSERT INTO user_settings (send_time, max_offers_day, send_mode, min_score_send, weekly_summary, strategic_alerts)
            VALUES ('09:00', 3, 'morning', 35, 1, 1)
        """)
        log.info("Registro por defecto insertado en user_settings")
    else:
        log.info("user_settings ya tiene %d registro(s)", count)

    conn.commit()
    conn.close()
    log.info("Migración completada")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    migrate()
