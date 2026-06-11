"""Re-scrapea ofertas del scraper que quedaron con descripciones rotas.

Las 21 ofertas del scraper tienen description_clean inválida porque el
parser original capturaba el toggle "Ofertas de empleo similares" en vez
de la descripción real. El fix en _parse_description() ahora usa selectores
semánticos + guard len>100, pero solo aplica a ofertas nuevas.

Este script re-scrapea las 21 ofertas existentes, actualiza la DB y guarda
el HTML crudo en scraper_raw_responses para futura inmutabilidad.
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataclasses import asdict
from datetime import datetime, timezone

from dotenv import load_dotenv

from src.db.init_db import get_connection


load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("reparse")


def main():
    from src.pipeline.infojobs_scraper import InfoJobsScraper

    conn = get_connection()
    scraper = InfoJobsScraper(delay=2.0)

    # Leer ofertas del scraper que necesitan re-scrapeo
    rows = conn.execute(
        """
        SELECT id, source_id, title, raw_data
        FROM offers
        WHERE raw_data LIKE '{%"offer_id"%}'
        ORDER BY source_id
        """
    ).fetchall()

    log.info("Re-scrapeando %d ofertas...", len(rows))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    updated = 0
    failed = 0

    try:
        for offer_id, source_id, title, raw_str in rows:
            raw = json.loads(raw_str)
            url = raw.get("url")
            if not url:
                log.warning("  Sin URL para %s (%s), saltando", source_id, title)
                failed += 1
                continue

            detail = scraper.detail(url)
            if not detail:
                log.warning("  Falló scrapeo de %s (%s)", source_id, title)
                failed += 1
                continue

            desc_len = len(detail.description_text)
            if desc_len <= 100:
                log.warning(
                    "  Descripción sigue siendo corta para %s (%s): %d chars",
                    source_id, title, desc_len,
                )
                failed += 1
                continue

            # Guardar raw en scraper_raw_responses
            raw_payload = json.dumps(asdict(detail), ensure_ascii=False)
            conn.execute(
                """
                INSERT OR IGNORE INTO scraper_raw_responses
                    (run_id, offer_id, payload, processed)
                VALUES (?, ?, ?, 0)
                """,
                (run_id, detail.offer_id, raw_payload),
            )

            # Actualizar offers
            conn.execute(
                """
                UPDATE offers SET
                    description_raw = ?,
                    description_clean = ?,
                    raw_data = ?,
                    published_at = COALESCE(published_at, ?),
                    enriched_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    detail.description_html,
                    detail.description_text,
                    raw_payload,
                    detail.published_at,
                    offer_id,
                ),
            )
            conn.commit()
            updated += 1
            log.info(
                "  ✓ %s — %s (%d chars desc, %d skills, pub=%s)",
                source_id,
                title,
                desc_len,
                len(detail.skills or []),
                detail.published_at or "—",
            )
    finally:
        scraper.close()

    log.info("Re-scrapeo completado: %d actualizadas, %d fallos", updated, failed)

    conn.close()


if __name__ == "__main__":
    main()
