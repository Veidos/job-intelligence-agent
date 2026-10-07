"""Transporte HTTP vía Scrapling con patrón warming (ADR-023).

Sustituye/acompaña a InfoJobsScraper (curl_cffi) como capa de transporte,
delegando TODO el parseo en InfoJobsParser (fuente única del parser).

Diseño validado empíricamente en scraper_lab/scrapling_poc (T1-T3 PASS):
- FetcherSession(impersonate=chrome131) con cookie jar persistente
- La primera búsqueda actúa de warm request (gana cookies Distil)
- Los detalles llevan Referer de la búsqueda que los generó
- Ante 2 decoys consecutivos: escalada automática a StealthySession
  (solo los detalles van por browser; las búsquedas siguen en HTTP barato)
- Tras 8 fallos totales: ScraperBlockedError sin tormentas de reintentos

Variables .env:
- SCRAPER_BACKEND=scrapling|curl_cffi  (rollback instantáneo)
- SCRAPER_STEALTH_FALLBACK=1|0         (escalada automática, default 1)

Rollback documentado en docs/adr/ADR-023-scrapling-transport-bronze-layer.md
"""

from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from src.pipeline.infojobs_scraper import (
    InfoJobsParser,
    InfoJobsScraper,
    RawOfferDetail,
    SearchStub,
)

# El logging interno de Scrapling ensuciaría los logs de cron (RotatingFileHandler)
logging.getLogger("scrapling").setLevel(logging.WARNING)

log = logging.getLogger(__name__)

# Umbrales del circuito anti-bloqueo (revisión de calidad ADR-023)
MAX_CONSECUTIVE_DECOYS = 2
MAX_TOTAL_FAILURES = 8

STEALTH_TIMEOUT_MS = 60_000

# Firma del hook bronze: (kind, url, http_status, html, offer_id)
RawHtmlCallback = Callable[[str, str, int | None, str, str | None], None]


class ScraperBlockedError(RuntimeError):
    """Distil bloquea incluso tras la escalada stealth — abortar el run."""


class TransportProtocol(Protocol):
    """Contrato común de los backends de transporte."""

    def search(
        self,
        query: str = "",
        location: str = "",
        page_limit: int = 1,
        max_items: int = 0,
        since_date: str | None = None,
    ) -> list[SearchStub]: ...

    def detail(self, url: str, search_url: str | None = None) -> RawOfferDetail | None: ...

    def close(self) -> None: ...


@dataclass
class FetchResult:
    """Respuesta cruda antes de parsear."""

    status: int | None
    html: str


def human_delay(previous_ts: float) -> tuple[float, float]:
    """Espera log-normal clamp [8,45]s respecto a previous_ts (ADR-022).

    Returns:
        (nuevo_timestamp, segundos_esperados)
    """
    base = random.lognormvariate(mu=2.5, sigma=0.6)
    wait = max(8.0, min(base, 45.0))
    now = time.monotonic()
    elapsed = now - previous_ts
    if elapsed < wait:
        time.sleep(wait - elapsed)
    return time.monotonic(), round(wait, 1)


class ScraplingTransport:
    """Transporte principal: Scrapling HTTP + warming + escalada stealth."""

    BASE_URL = "https://www.infojobs.net"
    SEARCH_PATH = "/jobsearch/search-results/list.xhtml"
    IMPERSONATE = "chrome131"

    def __init__(
        self,
        on_raw_html: RawHtmlCallback | None = None,
        stealth_fallback: bool | None = None,
    ):
        self._on_raw_html = on_raw_html
        if stealth_fallback is None:
            stealth_fallback = os.getenv("SCRAPER_STEALTH_FALLBACK", "1") != "0"
        self._stealth_enabled = stealth_fallback
        self._session = None  # contexto FetcherSession activo (lazy)
        self._stealth_ctx = None  # contexto StealthySession activo (lazy)
        self._detail_mode = "http"  # 'http' | 'stealth' — las búsquedas SIEMPRE http
        self._consecutive_decoys = 0
        self._total_failures = 0
        self._last_request = 0.0

    # ── infraestructura de sesión ──────────────────────────────────────

    def _ensure_http_session(self):
        if self._session is None:
            from scrapling.fetchers import FetcherSession

            self._session = FetcherSession(impersonate=self.IMPERSONATE, timeout=30)
            self._client = self._session.__enter__()
        return self._client

    def _ensure_stealth_session(self):
        if self._stealth_ctx is None:
            from scrapling.fetchers import StealthySession

            self._stealth_ctx = StealthySession(headless=True)
            self._stealth_client = self._stealth_ctx.__enter__()
            log.warning("Escalada a browser stealth activada para detail pages")
        return self._stealth_client

    @staticmethod
    def _resp_to_html(resp) -> str:
        body = resp.body
        if isinstance(body, bytes):
            return body.decode("utf-8", errors="replace")
        if hasattr(body, "html_content"):
            return body.html_content
        return str(body)

    def _emit_raw(
        self, kind: str, url: str, status: int | None, html: str, offer_id: str | None = None
    ) -> None:
        """Entrega el HTML al hook bronze ANTES de parsearlo."""
        if self._on_raw_html is None:
            return
        try:
            self._on_raw_html(kind, url, status, html, offer_id)
        except Exception as e:
            # Un fallo de archivo nunca debe romper el scraping
            log.warning("Hook bronze falló para %s: %s", url[:80], e)

    def _count_failure(self, what: str) -> None:
        self._total_failures += 1
        if self._total_failures >= MAX_TOTAL_FAILURES:
            raise ScraperBlockedError(
                f"{self._total_failures} fallos totales ({what}): "
                "IP/protección bloqueando — abortando run"
            )

    # ── fetching de páginas ────────────────────────────────────────────

    def _fetch_http(self, url: str, headers: dict | None = None) -> FetchResult:
        client = self._ensure_http_session()
        self._last_request, waited = human_delay(self._last_request)
        resp = client.get(url, headers=headers)
        html = self._resp_to_html(resp)
        log.info(
            "HTTP %s %s (%s, %d chars, +%gs)",
            resp.status,
            url[:80],
            self.IMPERSONATE,
            len(html),
            waited,
        )
        return FetchResult(status=resp.status, html=html)

    def _fetch_stealth(self, url: str) -> FetchResult:
        client = self._ensure_stealth_session()
        self._last_request, waited = human_delay(self._last_request)
        resp = client.fetch(url, network_idle=True, timeout=STEALTH_TIMEOUT_MS)
        html = self._resp_to_html(resp)
        log.info("STEALTH %s %s (%d chars, +%gs)", resp.status, url[:80], len(html), waited)
        return FetchResult(status=resp.status, html=html)

    # ── interfaz TransportProtocol ─────────────────────────────────────

    def search(
        self,
        query: str = "",
        location: str = "",
        page_limit: int = 1,
        max_items: int = 0,
        since_date: str | None = None,
    ) -> list[SearchStub]:
        """Búsqueda paginada. La primera petición hace de warm request."""
        from urllib.parse import urlencode

        all_stubs: list[SearchStub] = []
        for page in range(1, page_limit + 1):
            params: dict = {"page": page, "sortBy": "PUBLICATION_DATE"}
            if since_date:
                params["sinceDate"] = since_date
            if query:
                params["keyword"] = query
            if location:
                params["location"] = location

            url = f"{self.BASE_URL}{self.SEARCH_PATH}?{urlencode(params)}"
            try:
                result = self._fetch_http(url)  # búsquedas siempre por HTTP barato
            except Exception as e:
                self._count_failure(f"search '{query}' p{page}")
                log.warning("Fallo en search '%s' página %d: %s", query, page, e)
                break

            self._emit_raw("search", url, result.status, result.html)
            stubs = InfoJobsParser.parse_search_html(result.html)
            if not stubs:
                log.info("Sin más ofertas en página %d — fin", page)
                break
            all_stubs.extend(stubs)

            if max_items > 0 and len(all_stubs) >= max_items:
                all_stubs = all_stubs[:max_items]
                log.info("Alcanzado max_items=%d en página %d", max_items, page)
                break
        return all_stubs

    def detail(self, url: str, search_url: str | None = None) -> RawOfferDetail | None:
        """Obtiene y parsea una oferta individual, con escalada anti-decoy."""
        headers = None
        if search_url:
            headers = {
                "Referer": search_url,
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "navigate",
            }
        try:
            if self._detail_mode == "stealth":
                result = self._fetch_stealth(url)
            else:
                result = self._fetch_http(url, headers=headers)
        except ScraperBlockedError:
            raise
        except Exception as e:
            self._count_failure("detail excepción")
            log.warning("Fallo en detail %s: %s", url[:80], e)
            return None

        self._emit_raw("detail", url, result.status, result.html)

        if InfoJobsParser._is_decoy_page("", result.html):
            self._consecutive_decoys += 1
            self._count_failure("detail decoy")
            log.warning(
                "Decoy detectado (%d consecutivos): %s",
                self._consecutive_decoys,
                url[:80],
            )
            if (
                self._consecutive_decoys >= MAX_CONSECUTIVE_DECOYS
                and self._detail_mode == "http"
                and self._stealth_enabled
            ):
                self._escalate()
            return None

        self._consecutive_decoys = 0
        return InfoJobsParser.parse_detail_html(result.html, url=url)

    def _escalate(self) -> None:
        """Activa el modo stealth para los próximos detalles."""
        if not self._stealth_enabled:
            return
        self._detail_mode = "stealth"
        log.warning(
            "%d decoys consecutivos — próximos details irán por browser stealth",
            self._consecutive_decoys,
        )

    def close(self) -> None:
        """Cierra ambas sesiones si están abiertas."""
        for ctx_attr in ("_session", "_stealth_ctx"):
            ctx = getattr(self, ctx_attr, None)
            if ctx is not None:
                try:
                    ctx.__exit__(None, None, None)
                except Exception:
                    pass
                setattr(self, ctx_attr, None)


def create_scraper(
    on_raw_html: RawHtmlCallback | None = None,
    backend: str | None = None,
) -> TransportProtocol:
    """Factoría de transporte según SCRAPER_BACKEND (.env).

    Args:
        on_raw_html: Hook bronze (solo consumido por ScraplingTransport;
                     el rollback curl_cffi conserva su comportamiento legacy).
        backend: Override explícito del env (útil en tests).

    Returns:
        Transporte conforme a TransportProtocol.
    """
    backend = backend or os.getenv("SCRAPER_BACKEND", "scrapling")
    if backend == "curl_cffi":
        log.info("Transporte: curl_cffi legacy (rollback)")
        return InfoJobsScraper()
    if backend != "scrapling":
        log.warning("SCRAPER_BACKEND=%r desconocido — usando 'scrapling'", backend)
    log.info("Transporte: Scrapling (warming + escalada stealth)")
    return ScraplingTransport(on_raw_html=on_raw_html)
