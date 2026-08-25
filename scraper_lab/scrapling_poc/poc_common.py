"""Utilidades compartidas del PoC de Scrapling contra InfoJobs.

Standalone: no importa nada de src/, no toca data/jobs.db.
Patrones replicados de producción:
- DECOY_PATTERNS: idénticos a InfoJobsParser._is_decoy_page() (infojobs_scraper.py:252)
- Delay log-normal: idéntico a InfoJobsScraper._rate_limit() (ADR-022)
"""

import json
import random
import time
from pathlib import Path
from urllib.parse import urljoin

RESULTS_DIR = Path(__file__).parent / "results"

BASE_URL = "https://www.infojobs.net"
SEARCH_PATH = "/jobsearch/search-results/list.xhtml"
KEYWORD = "data analyst"
SEARCH_URL = f"{BASE_URL}{SEARCH_PATH}?keyword={KEYWORD.replace(' ', '%20')}"

# Idéntico a producción (infojobs_scraper.py:252-256)
DECOY_PATTERNS = [
    "no podemos identificar tu navegador",
    "no podemos identificar su navegador",
    "acceso denegado",
]

# Guard de producción para descripción válida (_parse_description)
MIN_DESC_CHARS = 100
# Una detail page real de InfoJobs pesa >100KB; una decoy es un template pequeño
MIN_REAL_BODY_BYTES = 50_000

CARD_SELECTOR = "li.ij-OfferList-offerCardItem"
PROMOTED_LABEL = "Publicidad"
TITLE_LINK_SELECTOR = "a.ij-OfferCardContent-description-link"

DETAIL_MARKERS = ["ij-OfferDetail", "ij-OfferDetailPage-mainContent"]


def human_delay() -> float:
    """Sleep log-normal clamp [8,45]s. Igual que ADR-022."""
    wait = max(8.0, min(random.lognormvariate(mu=2.5, sigma=0.6), 45.0))
    time.sleep(wait)
    return round(wait, 1)


def is_decoy(html: str) -> bool:
    """Detección de decoy: mismos marcadores textuales que producción,
    sobre título implícito y primeros 2000 chars del HTML."""
    head = html[:2000].lower()
    return any(p in head for p in DECOY_PATTERNS)


def looks_real_detail(html: str) -> tuple[bool, str]:
    """(es_real, razón) — más estricto que is_decoy: exige estructura de detail."""
    if is_decoy(html):
        return False, "decoy-marker"
    if len(html.encode("utf-8")) < MIN_REAL_BODY_BYTES:
        return False, f"body<{MIN_REAL_BODY_BYTES}B"
    if not any(m in html for m in DETAIL_MARKERS):
        return False, "sin-selectores-detail"
    return True, "ok"


def extract_description_text_len(html: str) -> int:
    """Longitud del texto de descripción vía selectores estructurales.

    Nota PoC 2026-08-25: la clase .ij-OfferDetailDescription ya NO aparece
    en el DOM actual de InfoJobs (cambió desde los snapshots de producción).
    Se usa el contenedor mainContent + get_all_text() de Scrapling.
    """
    try:
        from scrapling import Selector

        sel = Selector(content=html)
        for css in (
            "section[class*='ij-OfferDetailPage-mainContent']",
            "[class*='ij-OfferDetailDescription']",
            "[class*='OfferDetail']",
        ):
            found = sel.css(css)
            if not found:
                continue
            el = found[0]
            try:
                return len(el.get_all_text(strip=True))
            except TypeError:
                return len(el.get_all_text())
            except Exception:
                continue
        return 0
    except Exception:
        return 0


def parse_search_cards(search_html: str, limit: int = 3) -> list[dict]:
    """Extrae stubs orgánicos (excluye aria-label='Publicidad') con la API de Scrapling."""
    from scrapling import Selector

    sel = Selector(content=search_html)
    cards = sel.css(CARD_SELECTOR)
    stubs: list[dict] = []
    for card in cards:
        if card.attrib.get("aria-label") == PROMOTED_LABEL:
            continue
        links = card.css(TITLE_LINK_SELECTOR)
        if not links:
            continue
        href = links[0].attrib.get("href", "")
        if not href:
            continue
        title = (links[0].text or "").strip()
        stubs.append(
            {
                "title": title,
                "url": urljoin(BASE_URL, href),
                "referer": SEARCH_URL,
            }
        )
        if len(stubs) >= limit:
            break
    return stubs


def save_result(filename: str, content: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


def save_json(filename: str, data: dict | list) -> Path:
    return save_result(filename, json.dumps(data, ensure_ascii=False, indent=2))


def header(title: str) -> None:
    print(f"\n{'=' * 62}\n{title}\n{'=' * 62}")
