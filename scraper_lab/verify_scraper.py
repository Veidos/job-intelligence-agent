"""Verifica que el scraper obtiene datos reales post-mitigación Distil.
Ejecutar: PYTHONPATH=. python scraper_lab/verify_scraper.py
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.infojobs_scraper import BotBlockedError, InfoJobsParser, InfoJobsScraper


def main():
    scraper = InfoJobsScraper(delay=6.0, jitter=4.0)

    print("\n1. Warmup...")
    scraper.warmup()

    print("\n2. Search (1 keyword, 1 página, max 3 stubs)...")
    stubs = scraper.search(
        query="python developer",
        page_limit=1,
        max_items=3,
        since_date="_24_HOURS",
    )
    print(f"   Stubs obtenidos: {len(stubs)}")
    if not stubs:
        print("   ❌ Search bloqueada o sin resultados — abortar")
        scraper.close()
        return

    print("\n3. Detail (primer stub)...")
    stub = stubs[0]
    print(f"   URL: {stub.url[:80]}...")
    try:
        detail = scraper.detail(stub.url)
        if detail:
            print(f"   ✅ OK — title={detail.title!r}")
            print(f"      company={detail.company!r}, city={detail.city!r}")
            print(f"      desc_len={len(detail.description_text)}, skills={detail.skills[:3]}")
            print(f"      is_valid_detail={InfoJobsParser.is_valid_detail(detail)}")
        else:
            print("   ⚠️  detail() → None (is_valid_detail falló — datos corruptos)")
    except BotBlockedError as e:
        print("   ❌ BotBlockedError — Distil sigue bloqueando detail pages")
        print(f"      {e}")

    scraper.close()


if __name__ == "__main__":
    main()
