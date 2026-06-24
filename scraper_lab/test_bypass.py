"""Valida qué motor supera el anti-bot de InfoJobs. Ejecutar en venv actual."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from curl_cffi import requests as curl_requests

SEARCH_URL = "https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword=python+developer&province=28&sortBy=PUBLICATION_DATE"

BLOCK_SIGNALS = [
    "No podemos identificar",
    "Comprueba que eres humano",
    "Enable JavaScript",
    "cf-challenge",
    "datadome",
    "__ddg",
]

SUCCESS_SIGNALS = [
    "ij-OfferList",
    "data-job-id",
    "oferta-trabajo",
]

CHROME_VERSIONS = ["chrome124", "chrome120", "chrome131"]

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


def try_bypass(impersonate: str) -> bool:
    session = curl_requests.Session()
    print(f"\n--- Probando {impersonate} ---")
    try:
        r = session.get(SEARCH_URL, impersonate=impersonate, timeout=30)
        body = r.text
        print(f"  [{r.status_code}] {len(r.text):,} chars")

        # Signals de bloqueo
        if any(s.lower() in body.lower() for s in BLOCK_SIGNALS):
            print(f"  ⚠️  BLOQUEADO | Server: {r.headers.get('server','?')}")
            return False

        # Signals de éxito
        if any(s.lower() in body.lower() for s in SUCCESS_SIGNALS):
            print(f"  ✅ OFERTAS REALES — Server: {r.headers.get('server','?')}")
            # Guardar snapshot
            SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            (SNAPSHOT_DIR / "search_result.html").write_text(body, encoding="utf-8")
            print(f"  💾 Snapshot guardado: snapshots/search_result.html")
            return True

        print(f"  🔍 Indeterminado | Server: {r.headers.get('server','?')}")
        print(f"  Muestra: {body[:300]}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    for version in CHROME_VERSIONS:
        if try_bypass(version):
            print(f"\n✅ Motor viable: curl_cffi ({version})")
            return
    print("\n❌ Ningún motor bypass. Escalar a Camoufox.")


if __name__ == "__main__":
    main()
