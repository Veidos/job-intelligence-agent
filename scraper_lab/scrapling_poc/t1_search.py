"""T1 — Search page vía Scrapling FetcherSession (1 request a InfoJobs).

Valida: TLS impersonation de Scrapling contra la search page, conteo de
tarjetas orgánicas y extracción de stubs con el parser de Scrapling.
Guarda stubs para referencia, pero T2/T3 hacen su propio warming.
"""

import sys
import traceback

from poc_common import (
    SEARCH_URL,
    header,
    parse_search_cards,
    save_json,
    save_result,
)

STUBS_LIMIT = 3


def main() -> int:
    header("T1 · SEARCH · FetcherSession (impersonate=chrome131)")
    from scrapling.fetchers import FetcherSession

    with FetcherSession(impersonate="chrome131", timeout=30) as session:
        resp = session.get(SEARCH_URL)
        html = (
            resp.body.decode("utf-8", errors="replace")
            if isinstance(resp.body, bytes)
            else str(resp.body)
        )
        save_result("t1_search.html", html)

        print(f"status:  {resp.status}")
        print(f"bytes:   {len(html.encode('utf-8')):,}")

        decoy = any(
            p in html[:2000].lower()
            for p in ("no podemos identificar tu navegador", "acceso denegado")
        )
        cards = parse_search_cards(html, limit=STUBS_LIMIT)
        from scrapling import Selector

        total_cards = len(Selector(content=html).css("li.ij-OfferList-offerCardItem"))

        print(f"decoy:   {decoy}")
        print(f"cards:   {total_cards} totales (aprox), {len(cards)} orgánicas extraídas")
        for s in cards:
            print(f"  → {s['title'][:60]} | {s['url']}")

        passed = resp.status == 200 and not decoy and len(cards) >= 3
        print(f"\nVEREDICTO T1: {'✅ PASS' if passed else '❌ FAIL'}")

        save_json(
            "t1_summary.json",
            {
                "test": "T1 search",
                "status": resp.status,
                "bytes": len(html),
                "decoy": decoy,
                "organic_cards_extracted": len(cards),
                "passed": passed,
                "stubs": cards,
            },
        )
        return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print("\nVEREDICTO T1: ❌ FAIL (excepción)")
        sys.exit(2)
