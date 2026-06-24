"""Scraper backend con Camoufox (Firefox headless modificado) para bypass de Distil/Imperva.

Requiere: pip install 'camoufox[geoip]' && camoufox fetch
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.pipeline.infojobs_scraper import (
    BotBlockedError,
    InfoJobsParser,
    RawOfferDetail,
    SearchStub,
)

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_USER_DATA = PROJECT_ROOT / "scraper_lab" / "user_data"


class CamoufoxScraper:
    """Backend que usa Camoufox (Firefox patched) para scrapear InfoJobs.

    Camoufox ejecuta JS y pasa los checks de Distil/Imperva.
    El HTML resultante se delega a InfoJobsParser (mismo parser que curl_cffi).
    """

    BASE_URL = "https://www.infojobs.net"
    SEARCH_PATH = "/jobsearch/search-results/list.xhtml"

    def __init__(
        self,
        user_data_dir: str | Path | None = None,
        headless: bool = True,
        timeout: int = 30000,
    ):
        self.user_data_dir = Path(user_data_dir or DEFAULT_USER_DATA)
        self.headless = headless
        self.timeout = timeout
        self._camoufox = None
        self._browser = None

    def warmup(self) -> None:
        """Camoufox no necesita warmup — la sesión se establece en el primer search()."""

    def _get_browser(self):
        """Lazy init — abre el browser solo una vez.

        Camoufox es un context manager (PlaywrightContextManager).
        Lo entramos manualmente para mantenerlo vivo hasta close().
        """
        if self._browser is None:
            from camoufox.sync_api import Camoufox

            self._camoufox = Camoufox(
                headless=self.headless,
                persistent_context=True,
                user_data_dir=str(self.user_data_dir),
                geoip=True,
                humanize=True,
            )
            self._browser = self._camoufox.__enter__()
        return self._browser

    def _reset_browser(self):
        """Resetea el browser tras un crash para que se recree en el próximo fetch."""
        try:
            if self._camoufox is not None:
                self._camoufox.__exit__(None, None, None)
        except Exception:
            pass
        self._camoufox = None
        self._browser = None

    def _fetch(self, url: str) -> str | None:
        """Usa Camoufox para obtener el HTML de una URL."""
        page = None
        try:
            browser = self._get_browser()
            page = browser.new_page()
            page.on("pageerror", lambda err: log.debug("Page error ignorado: %s", err))
            page.goto(
                url,
                timeout=self.timeout,
                wait_until="domcontentloaded",
                referer="https://www.infojobs.net/jobsearch/search-results/list.xhtml",
            )
            return page.content()
        except Exception as e:
            log.warning("Camoufox fetch falló para %s: %s", url[:80], e)
            if "Connection closed" in str(e):
                log.warning("Browser crash detectado — reseteando")
                self._reset_browser()
            return None
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass

    def search(
        self,
        query: str = "",
        location: str = "",
        page_limit: int = 1,
        max_items: int = 0,
        since_date: str | None = None,
    ) -> list[SearchStub]:
        """Busca ofertas y devuelve stubs."""
        from urllib.parse import urlencode

        all_stubs: list[SearchStub] = []

        for page in range(1, page_limit + 1):
            params: dict[str, Any] = {"page": page, "sortBy": "PUBLICATION_DATE"}
            if since_date:
                params["sinceDate"] = since_date
            if query:
                params["keyword"] = query
            if location:
                params["location"] = location

            qs = urlencode(params)
            url = f"{self.BASE_URL}{self.SEARCH_PATH}?{qs}"
            html = self._fetch(url)
            if not html:
                break

            stubs = InfoJobsParser.parse_search_html(html)
            if not stubs:
                log.info("Sin más ofertas en página %d — fin", page)
                break

            all_stubs.extend(stubs)
            if max_items > 0 and len(all_stubs) >= max_items:
                all_stubs = all_stubs[:max_items]
                break

            log.info("Página %d: %d ofertas (total: %d)", page, len(stubs), len(all_stubs))

        return all_stubs

    def detail(self, url: str) -> RawOfferDetail | None:
        """Obtiene y parsea una oferta individual vía Camoufox.

        Limpia parámetros de tracking (?applicationOrigin=...) que Distil
        usa como señal de bot antes de fetchear.
        """
        clean_url = url.split("?")[0]
        html = self._fetch(clean_url)
        if not html:
            return None
        if InfoJobsParser.is_bot_blocked(html):
            log.warning("Bot-blocking detectado en %s", clean_url)
            raise BotBlockedError(clean_url)
        parsed = InfoJobsParser.parse_detail_html(html, url=clean_url)
        if not InfoJobsParser.is_valid_detail(parsed):
            log.warning(
                "Oferta descartada por datos insuficientes: "
                "title=%r, offer_id=%r, desc_len=%d, company=%r, url=%s",
                parsed.title,
                parsed.offer_id,
                len(parsed.description_text or ""),
                parsed.company,
                clean_url,
            )
            return None
        return parsed

    def close(self) -> None:
        """Cierra el navegador si está abierto."""
        self._reset_browser()

    def __del__(self):
        self.close()
