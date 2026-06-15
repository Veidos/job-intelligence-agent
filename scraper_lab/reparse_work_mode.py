"""Re-scrapea ofertas sin work_mode con el parser corregido (chips + título)."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from src.db.init_db import get_connection
from src.pipeline.fetch import _upsert_offer_from_scraper
from src.pipeline.infojobs_scraper import InfoJobsScraper

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("reparse_wm")


def main():
    conn = get_connection()
    scraper = InfoJobsScraper()

    rows = conn.execute(
        "SELECT source_id, url FROM offers WHERE work_mode IS NULL OR work_mode = ''"
    ).fetchall()

    log.info("Re-scrapeando %d ofertas...", len(rows))
    for i, (sid, url) in enumerate(rows, 1):
        detail = scraper.detail(url)
        if not detail:
            log.warning("  [%d/%d] Falló %s", i, len(rows), sid)
            continue
        _upsert_offer_from_scraper(detail, conn)
        log.info(
            "  [%d/%d] %s → work_mode=%s",
            i,
            len(rows),
            sid,
            detail.work_mode,
        )

    scraper.close()
    conn.close()
    log.info("Completado.")


if __name__ == "__main__":
    main()
