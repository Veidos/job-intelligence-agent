"""Tests de frescura del parser contra el DOM REAL de InfoJobs (ADR-023).

Fixtures: snapshots HTML capturados 2026-08-25 durante el PoC de Scrapling
(scraper_lab/scrapling_poc). Si estos tests fallan, InfoJobs cambió su DOM
y hay que revisar InfoJobsParser ANTES de scrapear en producción.

Ventaja de la capa bronze: cuando esto pase, se pueden generar fixtures
nuevos desde scraper_raw_html sin gastar requests.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from src.pipeline.infojobs_scraper import InfoJobsParser

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html_poc"

DETAIL_FIXTURES = ["t2_detail_1.html.gz", "t2_detail_2.html.gz"]


def load(name: str) -> str:
    return gzip.open(FIXTURES / name, "rt", encoding="utf-8").read()


@pytest.fixture(scope="module", params=DETAIL_FIXTURES)
def detail(request):
    html = load(request.param)
    return request.param, InfoJobsParser.parse_detail_html(html, url=f"https://poc/{request.param}")


class TestDomActualDetalles:
    """El parser extrae contenido completo del DOM actual (ago-2026)."""

    def test_titulo_presente(self, detail):
        name, d = detail
        assert len(d.title) > 5, f"{name}: título vacío — DOM cambió"

    def test_company_presente(self, detail):
        name, d = detail
        assert len(d.company) > 2, f"{name}: empresa vacía — DOM cambió"

    def test_descripcion_completa(self, detail):
        """Guard de producción: descripción >100 chars (sin truncado)."""
        name, d = detail
        assert len(d.description_text) > 100, f"{name}: descripción corta/truncada"
        assert len(d.description_html) > 1000, f"{name}: desc_html sospechosamente pequeño"
        # El texto debe ser sustancialmente más corto que el HTML (markup stripped)
        assert len(d.description_text) < len(d.description_html)

    def test_skills_estructurados_del_dl(self, detail):
        """Skills del <dl> Conocimientos van a core (requisitos explícitos)."""
        name, d = detail
        assert len(d.skills) >= 5, f"{name}: pocas skills ({len(d.skills)}) — dl cambió?"

    def test_campos_estructurados_header(self, detail):
        name, d = detail
        assert d.city, f"{name}: city vacía"
        assert d.work_mode in ("Presencial", "Híbrido", "Remoto", "", None) or d.work_mode

    def test_sin_marcadores_decoy(self, detail):
        name = detail[0]
        html = load(name)
        assert not InfoJobsParser._is_decoy_page("", html)


class TestDomActualSearch:
    def test_search_extrae_stubs_organicos(self):
        html = load("t1_search.html.gz")
        stubs = InfoJobsParser.parse_search_html(html)
        assert len(stubs) >= 3
        for s in stubs:
            assert s.offer_id and not s.is_promoted
            assert s.url.startswith("https://www.infojobs.net/")
