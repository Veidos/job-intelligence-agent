"""Tests de ScraplingTransport y factoría create_scraper (ADR-023).

Sin red real: sesiones Scrapling simuladas con fixtures HTML del PoC.
"""

from __future__ import annotations

import gzip
import time
from pathlib import Path

import pytest

import src.pipeline.scrapling_transport as st
from src.pipeline.infojobs_scraper import InfoJobsScraper
from src.pipeline.scrapling_transport import (
    MAX_CONSECUTIVE_DECOYS,
    MAX_TOTAL_FAILURES,
    ScraperBlockedError,
    ScraplingTransport,
    create_scraper,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html_poc"

DECOY_HTML = (
    "<html><head><title>No podemos identificar tu navegador</title></head>"
    "<body>No podemos identificar tu navegador</body></html>"
)


def load_fixture(name: str) -> str:
    return gzip.open(FIXTURES / name, "rt", encoding="utf-8").read()


SEARCH_HTML = load_fixture("t1_search.html.gz")
DETAIL_1_HTML = load_fixture("t2_detail_1.html.gz")


class FakeResp:
    def __init__(self, status: int, html: str):
        self.status = status
        self.body = html.encode("utf-8")


class FakeHttpClient:
    """Cliente HTTP/browser simulado con cola de respuestas."""

    def __init__(self, responses: list[FakeResp]):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, url, headers=None, **kwargs):
        self.calls.append((url, headers))
        return self.responses.pop(0)

    def fetch(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class FakeCtx:
    def __init__(self, client: FakeHttpClient):
        self.client = client
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self.client

    def __exit__(self, *args):
        self.exited = True
        return False

def attach_http(transport: ScraplingTransport, client: FakeHttpClient) -> ScraplingTransport:
    """Inyecta un cliente HTTP simulado respetando el par (ctx, client)."""
    transport._session = FakeCtx(client)
    transport._client = client
    return transport


@pytest.fixture()
def no_sleep(monkeypatch):
    """Neutraliza los delays log-normal en tests."""
    monkeypatch.setattr(st, "human_delay", lambda prev: (time.monotonic(), 0.0))


@pytest.fixture()
def recorded():
    events: list[tuple] = []

    def hook(kind, url, status, html, offer_id=None):
        events.append((kind, url, status, html, offer_id))

    return hook, events


class TestSearchWarming:
    def test_search_parsea_stubs_del_fixture_real(self, no_sleep, recorded):
        hook, events = recorded
        client = FakeHttpClient([FakeResp(200, SEARCH_HTML)])
        t = ScraplingTransport(on_raw_html=hook)
        attach_http(t, client)

        stubs = t.search(query="data analyst", page_limit=1)

        assert len(stubs) > 0
        assert len(stubs[0].offer_id) >= 16  # hash hex de InfoJobs, sin prefijo
        # Hook bronze invocado ANTES de parsear, kind='search', offer_id=None
        assert events[0][0] == "search"
        assert events[0][2] == 200
        assert events[0][4] is None

    def test_primera_peticion_es_el_warm_request(self, no_sleep, recorded):
        """La búsqueda es la primera petición: gana cookies antes que ningún detail."""
        hook, _ = recorded
        http = FakeHttpClient([FakeResp(200, SEARCH_HTML)])
        t = ScraplingTransport(on_raw_html=hook)
        attach_http(t, http)

        stubs = t.search(query="data analyst", page_limit=1)
        t.detail(stubs[0].url, search_url=stubs[0].url.replace("list.xhtml", "list.xhtml"))

        urls_called = [u for u, _ in http.calls]
        assert urls_called[0].startswith(
            "https://www.infojobs.net/jobsearch/search-results/list.xhtml"
        )


class TestDetail:
    def test_detail_ok_con_referer_y_hook_bronze(self, no_sleep, recorded):
        hook, events = recorded
        detail_url = "https://www.infojobs.net/madrid/oferta/of-abc"
        http = FakeHttpClient([FakeResp(200, DETAIL_1_HTML)])
        t = ScraplingTransport(on_raw_html=hook)
        attach_http(t, http)

        d = t.detail(detail_url, search_url="https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword=x")

        assert d is not None
        assert d.title == "Analista de datos"
        _, headers = http.calls[0]
        assert headers["Referer"].startswith(
            "https://www.infojobs.net/jobsearch/search-results/list.xhtml"
        )
        assert headers["Sec-Fetch-Site"] == "same-origin"
        assert events[0][0] == "detail"
        assert events[0][4] is None  # offer_id se añade en fetch.py vía upsert, no aquí

    def test_decoy_devuelve_none_y_cuenta(self, no_sleep, recorded):
        hook, events = recorded
        http = FakeHttpClient([FakeResp(200, DECOY_HTML)])
        t = ScraplingTransport(on_raw_html=hook)
        attach_http(t, http)

        result = t.detail("https://x/of-1", search_url="https://s")

        assert result is None
        assert t._consecutive_decoys == 1
        assert t._total_failures == 1
        assert events[0][0] == "detail"  # el decoy TAMBIÉN se archiva en bronze

    def test_dos_decoys_consecutivos_escalan_a_stealth(self, no_sleep, recorded):
        hook, _ = recorded
        responses = [FakeResp(200, DECOY_HTML), FakeResp(200, DECOY_HTML)]
        stealth_client = FakeHttpClient([FakeResp(200, DETAIL_1_HTML)])
        t = ScraplingTransport(on_raw_html=hook, stealth_fallback=True)
        attach_http(t, FakeHttpClient(responses))
        monkey_target = t

        import src.pipeline.scrapling_transport as mod

        original_ensure = ScraplingTransport._ensure_stealth_session

        def fake_ensure_stealth(self):
            if self._stealth_ctx is None:
                self._stealth_ctx = FakeCtx(stealth_client)
                self._stealth_client = stealth_client
                self._detail_mode = "stealth"
                log_msg = "escalada simulada en test"
                del log_msg
            return self._stealth_client

        mod.ScraplingTransport._ensure_stealth_session = fake_ensure_stealth
        try:
            r1 = monkey_target.detail("https://x/of-1", search_url="https://s")
            r2 = monkey_target.detail("https://x/of-2", search_url="https://s")
            assert r1 is None and r2 is None
            assert monkey_target._detail_mode == "stealth"

            r3 = monkey_target.detail("https://x/of-3", search_url="https://s")
            assert r3 is not None  # servido por browser stealth
            assert monkey_target._consecutive_decoys == 0  # reset tras éxito
        finally:
            mod.ScraplingTransport._ensure_stealth_session = original_ensure

    def test_sin_stealth_fallback_no_escala(self, no_sleep, recorded):
        hook, _ = recorded
        responses = [FakeResp(200, DECOY_HTML)] * (MAX_CONSECUTIVE_DECOYS + 1)
        t = ScraplingTransport(on_raw_html=hook, stealth_fallback=False)
        attach_http(t, FakeHttpClient(responses))

        for i in range(MAX_CONSECUTIVE_DECOYS + 1):
            t.detail(f"https://x/of-{i}", search_url="https://s")

        assert t._detail_mode == "http"  # sin escalada si está desactivado


class TestCircuitBreaker:
    def test_ocho_fallos_totales_abortan_con_excepcion(self, no_sleep, recorded):
        hook, _ = recorded
        responses = [FakeResp(200, DECOY_HTML)] * MAX_TOTAL_FAILURES
        t = ScraplingTransport(on_raw_html=hook, stealth_fallback=False)
        attach_http(t, FakeHttpClient(responses))

        with pytest.raises(ScraperBlockedError):
            for i in range(MAX_TOTAL_FAILURES):
                t.detail(f"https://x/of-{i}", search_url="https://s")

    def test_exito_resetea_decoys_consecutivos(self, no_sleep, recorded):
        hook, _ = recorded
        http = FakeHttpClient([FakeResp(200, DECOY_HTML), FakeResp(200, DETAIL_1_HTML)])
        t = ScraplingTransport(on_raw_html=hook, stealth_fallback=False)
        attach_http(t, http)

        t.detail("https://x/of-1", search_url="https://s")
        assert t._consecutive_decoys == 1
        t.detail("https://x/of-2", search_url="https://s")
        assert t._consecutive_decoys == 0
        assert t._total_failures == 1  # el fallo anterior sigue contado


class TestFactory:
    def test_backend_scrapling_por_defecto(self, monkeypatch):
        monkeypatch.delenv("SCRAPER_BACKEND", raising=False)
        s = create_scraper()
        assert isinstance(s, ScraplingTransport)

    def test_backend_curl_cffi_para_rollback(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_BACKEND", "curl_cffi")
        s = create_scraper()
        assert isinstance(s, InfoJobsScraper)
        s.close()

    def test_backend_desconocido_caen_en_scrapling(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_BACKEND", "desconocido")
        s = create_scraper()
        assert isinstance(s, ScraplingTransport)

    def test_override_explicito_gana_al_env(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_BACKEND", "curl_cffi")
        s = create_scraper(backend="scrapling")
        assert isinstance(s, ScraplingTransport)


class TestClose:
    def test_close_cierra_contextos_abiertos(self, no_sleep):
        http_ctx = FakeCtx(FakeHttpClient([]))
        t = ScraplingTransport()
        t._session = http_ctx
        t.close()
        assert http_ctx.exited is True
        assert t._session is None

    def test_close_sin_sesiones_no_falla(self):
        t = ScraplingTransport()
        t.close()  # no debe lanzar
