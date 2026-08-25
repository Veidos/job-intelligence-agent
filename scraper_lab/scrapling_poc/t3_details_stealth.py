"""T3 — Warming + detail pages vía Scrapling StealthySession (patchright Chromium).

Mismo flujo que T2 pero con browser real: fingerprint JS completo, cookies de
navegación genuinas. 3 requests: 1 warm + 2 details.
Requiere: scrapling install (Chromium descargado).
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


def body_to_str(body) -> str:
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    if hasattr(body, "html_content"):
        return body.html_content
    return str(body)


def main() -> int:
    header("T3 · DETAILS STEALTH · StealthySession (headless)")
    from scrapling.fetchers import StealthySession

    results = []
    with StealthySession(headless=True) as session:
        # ── Paso 1: warming en browser real ──
        print(f"[warm] GET {SEARCH_URL}")
        resp = session.fetch(SEARCH_URL, network_idle=True, timeout=60000)
        warm_html = body_to_str(resp.body)
        save_result("t3_warm_search.html", warm_html)
        stubs = parse_search_cards(warm_html, limit=DETAILS_N)
        print(f"[warm] status={resp.status} bytes={len(warm_html):,} stubs={len(stubs)}")
        if not stubs:
            print("VEREDICTO T3: ❌ FAIL (sin stubs)")
            save_json(
                "t3_summary.json", {"test": "T3 stealth", "passed": False, "error": "no stubs"}
            )
            return 1

        # ── Paso 2: details navegados por el browser ──
        for i, stub in enumerate(stubs, 1):
            wait = human_delay()
            print(f"\n[delay {wait}s]")
            print(f"[detail {i}] GET {stub['url']}")
            d_resp = session.fetch(stub["url"], network_idle=True, timeout=60000)
            html = body_to_str(d_resp.body)
            fname = f"t3_detail_{i}.html"
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
    print(f"\nVEREDICTO T3: {'✅ PASS' if passed else '❌ FAIL'}")

    save_json(
        "t3_summary.json",
        {"test": "T3 details stealth", "passed": passed, "results": results},
    )
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print("\nVEREDICTO T3: ❌ FAIL (excepción)")
        sys.exit(2)
