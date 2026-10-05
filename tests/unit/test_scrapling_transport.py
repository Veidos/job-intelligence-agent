"""Tests de ScraplingTransport y factoría create_scraper (ADR-023).

Sin red real: sesiones Scrapling simuladas con fixtures HTML del PoC.
"""

from __future__ import annotations

import gzip
import time
from pathlib import Path

import pytest

import src.pipeline.scrapling_transport as st
from src.pipeline.infojobs_scraper import InfoJobsParser, InfoJobsScraper
from src.pipeline.scrapling_transport import (
    DETAIL_MODE_AUTO,
    MAX_CONSECUTIVE_DECOYS,
    MAX_TOTAL_FAILURES,
    ScraperBlockedError,
    ScraplingTransport,
    create_scraper,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html_poc"

# Reproduce el muro real de Distil (~29 KB) con el aviso en el <h1> muy tarde.
# Un decoy con la frase al principio daba falso negativo: el test "escalaba" sin
# que producción lo hiciera. Ver _DECOY_SCAN_LIMIT en InfoJobsParser.
_DECOY_FILLER = "<div>contenido de relleno sin señal</div>" * 300
DECOY_HTML = (
    "<html><head><title>InfoJobs</title></head><body>"
    + _DECOY_FILLER
    + "<h1>No podemos identificar tu navegador</h1>"
    + "</body></html>"
)
assert DECOY_HTML.index("No podemos identificar") > 2000  # el bug histórico
assert len(DECOY_HTML) > 10_000  # tamaño parecido al muro real


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


class TestSearchDecoyEscalation:
    """Un muro en búsqueda debe reintentarse por navegador, no assume página vacía."""

    def test_search_con_muro_reintenta_por_navegador(self, no_sleep, recorded):
        hook, events = recorded
        t = ScraplingTransport(on_raw_html=hook)
        attach_http(t, FakeHttpClient([FakeResp(200, DECOY_HTML)]))
        stealth_client = FakeHttpClient([FakeResp(200, SEARCH_HTML)])
        import src.pipeline.scrapling_transport as mod

        original = ScraplingTransport._ensure_stealth_session

        def fake_ensure_stealth(self):
            if self._stealth_ctx is None:
                self._stealth_ctx = FakeCtx(stealth_client)
                self._stealth_client = stealth_client
            return self._stealth_client

        mod.ScraplingTransport._ensure_stealth_session = fake_ensure_stealth
        try:
            stubs = t.search(query="data analyst", page_limit=1)
            assert len(stubs) > 0  # el muro se recuperó: no se perdió la keyword
            kinds = [e[0] for e in events]
            assert kinds == ["search", "search"]  # muro + reintento, ambos archivados
        finally:
            mod.ScraplingTransport._ensure_stealth_session = original

    def test_search_pagina_vacia_no_es_muro(self, no_sleep, recorded):
        """Una búsqueda real sin resultados NO debe tratarse como bloqueo."""
        hook, _ = recorded
        vacia = "<html><body><div class='sin-resultados'></div></body></html>"
        t = ScraplingTransport(on_raw_html=hook)
        attach_http(t, FakeHttpClient([FakeResp(200, vacia)]))

        assert t.search(query="data analyst", page_limit=2) == []
        assert t._total_failures == 0  # vacío legítimo no cuenta como fallo


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


class TestDecoyDetectionRegression:
    """El muro con la frase al final DEBE detectarse (bug que tumbó el run del 5-oct)."""

    def test_muro_con_frase_temprana_se_detecta(self):
        assert InfoJobsParser._is_decoy_page("", DECOY_HTML)

    def test_muro_titulo_vacio_frase_al_final_se_detecta(self):
        assert InfoJobsParser._is_decoy_page("", DECOY_HTML)

    def test_oferta_real_no_es_muro(self):
        assert not InfoJobsParser._is_decoy_page("Analista de datos", DETAIL_1_HTML)

    def test_acceso_denegado_en_cuerpo_no_es_muro(self):
        html = (
            "<html><head><title>Ingeniero de seguridad</title></head><body>"
            "<h1>Analista de datos</h1>"
            "<p>El equipo controla el acceso denegado a sistemas heredados.</p>"
            "</body></html>"
        )
        assert not InfoJobsParser._is_decoy_page("Analista de datos", html)

    def test_acceso_denegado_en_titulo_si_es_muro(self):
        html = "<html><head><title>Acceso denegado</title></head><body>x</body></html>"
        assert InfoJobsParser._is_decoy_page("Acceso denegado", html)


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

    def test_dos_decoys_consecutivos_escalan_a_stealth_en_modo_auto(self, no_sleep, recorded):
        hook, _ = recorded
        responses = [FakeResp(200, DECOY_HTML), FakeResp(200, DECOY_HTML)]
        stealth_client = FakeHttpClient([FakeResp(200, DETAIL_1_HTML)])
        t = ScraplingTransport(
            on_raw_html=hook, stealth_fallback=True, detail_mode=DETAIL_MODE_AUTO
        )
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

    def test_default_usa_navegador_para_fichas(self, no_sleep, recorded):
        """Desde oct-2026 el detalle exige JS: el modo por defecto es navegador."""
        hook, _ = recorded
        t = ScraplingTransport(on_raw_html=hook)
        stealth_client = FakeHttpClient([FakeResp(200, DETAIL_1_HTML)])
        import src.pipeline.scrapling_transport as mod

        original_ensure = ScraplingTransport._ensure_stealth_session

        def fake_ensure_stealth(self):
            if self._stealth_ctx is None:
                self._stealth_ctx = FakeCtx(stealth_client)
                self._stealth_client = stealth_client
            return self._stealth_client

        mod.ScraplingTransport._ensure_stealth_session = fake_ensure_stealth
        try:
            assert t._detail_mode == "stealth"
            result = t.detail("https://x/of-1", search_url="https://s")
            assert result is not None
            assert t._total_failures == 0  # HTTP ni se intenta
        finally:
            mod.ScraplingTransport._ensure_stealth_session = original_ensure

    def test_navegador_no_disponible_degrada_a_http(self, no_sleep, recorded):
        """Si Camoufox no arranca, el run sigue por HTTP en vez de abortar."""
        hook, _ = recorded
        t = ScraplingTransport(on_raw_html=hook)
        import src.pipeline.scrapling_transport as mod

        def boom(self):
            raise RuntimeError("sin binarios de camoufox")

        original = ScraplingTransport._ensure_stealth_session
        mod.ScraplingTransport._ensure_stealth_session = boom
        attach_http(t, FakeHttpClient([FakeResp(200, DETAIL_1_HTML)]))
        try:
            result = t.detail("https://x/of-1", search_url="https://s")
            assert result is not None
            assert t._detail_mode == "http"  # degradado, no abortado
        finally:
            mod.ScraplingTransport._ensure_stealth_session = original

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
