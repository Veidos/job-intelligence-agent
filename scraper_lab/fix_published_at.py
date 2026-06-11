"""Re-scrapea ofertas con published_at=null para poblarlas con el parser corregido.

InfoJobs no usa time[datetime]. El fix en _extract_published_at() ahora parsea
el texto plano ("Hace 4d", "29 may", "Hoy", etc.). Este script re-scrapea las
44 ofertas existentes para aplicar el fix retroactivamente.
"""

import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from src.db.init_db import get_connection
from src.pipeline.infojobs_scraper import InfoJobsScraper

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fix_pub")


def main():
    conn = get_connection()
    scraper = InfoJobsScraper(delay=2.0)

    # Leer ofertas con published_at null desde scraper_raw_responses
    rows = conn.execute(
        """
        SELECT r.id AS raw_id, r.offer_id, r.payload, o.id AS offer_id_int
        FROM scraper_raw_responses r
        JOIN offers o ON o.source_id = r.offer_id
        WHERE o.published_at IS NULL
        ORDER BY r.offer_id
        """
    ).fetchall()

    log.info("Re-scrapeando %d ofertas para published_at...", len(rows))
    updated = 0
    skipped = 0
    failed = 0

    try:
        for raw_id, offer_id, payload_str, offer_int_id in rows:
            payload = json.loads(payload_str)
            url = payload.get("url")
            if not url:
                log.warning("  Sin URL para %s, saltando", offer_id)
                skipped += 1
                continue

            detail = scraper.detail(url)
            if not detail:
                log.warning("  Falló scrapeo de %s, saltando", offer_id)
                skipped += 1
                continue

            pub = detail.published_at
            if not pub:
                log.info("  %s — fecha no disponible (ofertas expirada?)", offer_id)
                skipped += 1
                continue

            # Actualizar offers.published_at
            conn.execute(
                "UPDATE offers SET published_at = ? WHERE id = ?",
                (pub, offer_int_id),
            )

            # Actualizar scraper_raw_responses.payload con la nueva fecha
            payload["published_at"] = pub
            conn.execute(
                "UPDATE scraper_raw_responses SET payload = ? WHERE id = ?",
                (json.dumps(payload, ensure_ascii=False), raw_id),
            )

            conn.commit()
            updated += 1
            log.info(
                "  ✓ %s — %s → %s",
                offer_id,
                payload.get("title", "?")[:50],
                pub,
            )

    finally:
        scraper.close()

    log.info(
        "Completado: %d actualizadas, %d saltadas, %d fallos",
        updated, skipped, failed,
    )
    conn.close()


if __name__ == "__main__":
    main()
