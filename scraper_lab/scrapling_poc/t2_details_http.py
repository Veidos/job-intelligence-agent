"""T2 — Warming + detail pages vía Scrapling HTTP (FetcherSession).

Hipótesis Distil: ganar cookies en la search page primero (mismo cookie jar),
dwell log-normal, y luego pedir 2 detail pages con Referer de la navegación.
3 requests: 1 warm + 2 details.
"""

import sys
import traceback

from poc_common import (
    SEARCH_URL,
    extract_description_text_len,
    header,
    human_delay,
    looks_real_detail,
    parse_search_cards,
    save_json,
    save_result,
)

DETAILS_N = 2


def main() -> int:
    header("T2 · DETAILS HTTP · FetcherSession warmed (chrome131)")
    from scrapling.fetchers import FetcherSession

    results = []
    with FetcherSession(impersonate="chrome131", timeout=30) as session:
        # ── Paso 1: warming (gana cookies de fingerprint) ──
        print(f"[warm] GET {SEARCH_URL}")
        resp = session.get(SEARCH_URL)
        warm_html = (
            resp.body.decode("utf-8", errors="replace")
            if isinstance(resp.body, bytes)
            else str(resp.body)
        )
        save_result("t2_warm_search.html", warm_html)
        stubs = parse_search_cards(warm_html, limit=DETAILS_N)
        print(f"[warm] status={resp.status} stubs={len(stubs)}")
        if not stubs:
            print("VEREDICTO T2: ❌ FAIL (sin stubs para testear details)")
            save_json("t2_summary.json", {"test": "T2 http", "passed": False, "error": "no stubs"})
            return 1

        # ── Paso 2: details con Referer de la navegación real ──
        for i, stub in enumerate(stubs, 1):
            wait = human_delay()
            print(f"\n[delay {wait}s]")
            print(f"[detail {i}] GET {stub['url']}")
            headers = {
                "Referer": stub["referer"],
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
            }
            d_resp = session.get(stub["url"], headers=headers)
            html = (
                d_resp.body.decode("utf-8", errors="replace")
                if isinstance(d_resp.body, bytes)
                else str(d_resp.body)
            )
            fname = f"t2_detail_{i}.html"
            save_result(fname, html)
            real, reason = looks_real_detail(html)
            desc_len = extract_description_text_len(html)
            entry = {
                "url": stub["url"],
                "status": d_resp.status,
                "bytes": len(html.encode("utf-8")),
                "real": real and desc_len > 100,
                "reason": reason,
                "description_chars": desc_len,
            }
            results.append(entry)
            print(
                f"[detail {i}] status={entry['status']} bytes={entry['bytes']:,} "
                f"real={entry['real']} ({reason}) desc={desc_len} chars"
            )

    passed = any(r["real"] for r in results)
    print("\n" + "-" * 62)
    for r in results:
        mark = "✅ REAL" if r["real"] else f"❌ DECOY ({r['reason']})"
        print(f"  {r['url'][:70]} → {mark}")
    print(f"\nVEREDICTO T2: {'✅ PASS' if passed else '❌ FAIL'}")

    save_json(
        "t2_summary.json",
        {"test": "T2 details http warmed", "passed": passed, "results": results},
    )
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print("\nVEREDICTO T2: ❌ FAIL (excepción)")
        sys.exit(2)
