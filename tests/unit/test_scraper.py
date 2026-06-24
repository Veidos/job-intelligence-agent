"""Tests para infojobs_scraper.py con snapshots HTML reales.

TDD: los asserts se escribieron antes que el parser.
Fallan si el parser no captura los campos correctamente.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = PROJECT_ROOT / "scraper_lab" / "snapshots"


class TestParseSearch:
    """Tests contra search_result.html (senior python, province=28)."""

    @classmethod
    def setup_class(cls):
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = (SNAPSHOTS / "search_result.html").read_text(encoding="utf-8")
        cls.stubs = InfoJobsParser.parse_search_html(html)
        cls.total = InfoJobsParser.extract_total_results(html)

    def test_filtra_anuncios(self):
        assert all(not s.is_promoted for s in self.stubs), "Hay anuncios en los stubs"

    def test_solo_ofertas_reales(self):
        assert len(self.stubs) > 0, "No se encontraron ofertas reales"
        assert len(self.stubs) <= 10, "Esperaba máximo 10 ofertas por página"

    def test_total_resultados(self):
        assert self.total > 0, "No se pudo extraer el total de resultados"

    def test_cada_stub_tiene_campos_obligatorios(self):
        for s in self.stubs:
            assert s.title, f"Stub sin título: {s}"
            assert s.url, f"Stub sin URL: {s}"
            assert s.offer_id, f"Stub sin offer_id: {s}"
            assert s.company, f"Stub sin company: {s}"

    def test_offer_id_tiene_formato_correcto(self):
        import re

        for s in self.stubs:
            assert re.match(r"^[a-zA-Z0-9]{30,}$", s.offer_id), (
                f"offer_id inválido: {s.offer_id}"
            )

    def test_url_contiene_of_code(self):
        for s in self.stubs:
            assert s.offer_id in s.url, f"URL no contiene offer_id: {s.url}"


class TestParseDetailBeca:
    """Tests contra offer_detail.html (Beca Java, campos mínimos)."""

    @classmethod
    def setup_class(cls):
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = (SNAPSHOTS / "offer_detail.html").read_text(encoding="utf-8")
        cls.detail = InfoJobsParser.parse_detail_html(html)

    def test_titulo(self):
        assert "Beca Java" in self.detail.title

    def test_company(self):
        assert self.detail.company == "MINSAIT (Indra Producción de Software)"

    def test_city(self):
        assert self.detail.city == "A Coruña"

    def test_work_mode(self):
        assert self.detail.work_mode in ("Híbrido", "Presencial", "Remoto")

    def test_salary_none(self):
        assert self.detail.salary_min is None
        assert self.detail.salary_max is None

    def test_skills_vacio(self):
        assert self.detail.skills == []

    def test_languages_vacio(self):
        assert self.detail.languages == []

    def test_education_min(self):
        assert self.detail.education_min is not None

    def test_experiencia_none(self):
        assert self.detail.experience_min_years is not None
        assert self.detail.experience_min_years == 0

    def test_offer_id(self):
        assert len(self.detail.offer_id) >= 30

    def test_description_not_empty(self):
        assert len(self.detail.description_text) > 0

    def test_to_db_dict(self):
        from src.pipeline.infojobs_scraper import InfoJobsParser

        d = InfoJobsParser.to_db_dict(self.detail)
        assert d["source_id"] == self.detail.offer_id
        assert d["title"] == self.detail.title
        assert d["company_name"] == self.detail.company


class TestParseDetailSenior:
    """Tests contra offer_senior_detail.html (Senior Python, campos completos)."""

    @classmethod
    def setup_class(cls):
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = (SNAPSHOTS / "offer_senior_detail.html").read_text(encoding="utf-8")
        cls.detail = InfoJobsParser.parse_detail_html(html)

    def test_titulo(self):
        assert "Senior Python" in self.detail.title

    def test_company(self):
        assert self.detail.company == "Mensoft Consultores, S.L"

    def test_city(self):
        assert self.detail.city == "Barcelona"

    def test_work_mode(self):
        assert self.detail.work_mode == "Híbrido"

    def test_salary_min(self):
        assert self.detail.salary_min == 30000.0

    def test_salary_max(self):
        assert self.detail.salary_max == 40000.0

    def test_salary_period(self):
        assert self.detail.salary_period == "año"

    def test_experiencia(self):
        assert self.detail.experience_min_years == 4

    def test_skills_not_empty(self):
        assert len(self.detail.skills) > 0, (
            "Skills debería tener al menos un conocimiento"
        )

    def test_education_min_not_none(self):
        assert self.detail.education_min is not None

    def test_contract_type(self):
        assert self.detail.contract_type is not None

    def test_workday(self):
        assert self.detail.workday is not None

    def test_offer_id(self):
        assert len(self.detail.offer_id) >= 30

    def test_description_not_empty(self):
        assert len(self.detail.description_text) > 0

    def test_to_db_dict(self):
        from src.pipeline.infojobs_scraper import InfoJobsParser

        d = InfoJobsParser.to_db_dict(self.detail)
        assert d["source_id"] == self.detail.offer_id
        assert d["title"] == self.detail.title
        assert d["company_name"] == self.detail.company
        assert d["salary_min"] == 30000.0
        assert d["salary_max"] == 40000.0


class TestParserUtils:
    """Tests unitarios para métodos auxiliares del parser."""

    def test_parse_skills_dedup(self):
        from bs4 import BeautifulSoup
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = "<dd><ul><li>Python</li><li>Python</li><li>SQL</li><li>SQL</li><li>ML</li></ul></dd>"
        dd = BeautifulSoup(html, "lxml").find("dd")
        skills = InfoJobsParser._parse_skills(dd)
        assert skills == ["Python", "SQL", "ML"]

    def test_parse_skills_no_duplicates(self):
        from bs4 import BeautifulSoup
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = "<dd><ul><li>Python</li><li>SQL</li></ul></dd>"
        dd = BeautifulSoup(html, "lxml").find("dd")
        skills = InfoJobsParser._parse_skills(dd)
        assert skills == ["Python", "SQL"]

    def test_extract_published_at_days_ago(self):
        from datetime import datetime, timedelta, timezone
        from bs4 import BeautifulSoup
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = '<span class="ij-FormatterSincedate">Hace 4d</span>'
        dt = InfoJobsParser._extract_published_at(BeautifulSoup(html, "lxml"))
        expected = (datetime.now(timezone.utc) - timedelta(days=4)).strftime("%Y-%m-%d")
        assert dt == expected

    def test_extract_published_at_hours_ago(self):
        from datetime import datetime, timezone
        from bs4 import BeautifulSoup
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = '<span data-testid="sincedate-tag">Hace 4h</span>'
        dt = InfoJobsParser._extract_published_at(BeautifulSoup(html, "lxml"))
        assert dt == datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def test_extract_published_at_literal_date(self):
        from bs4 import BeautifulSoup
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = '<span data-testid="sincedate-tag">29 may</span>'
        dt = InfoJobsParser._extract_published_at(BeautifulSoup(html, "lxml"))
        assert dt == "2026-05-29"

    def test_extract_published_at_hoy(self):
        from datetime import datetime, timezone
        from bs4 import BeautifulSoup
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = '<span class="ij-FormatterSincedate">Hoy</span>'
        dt = InfoJobsParser._extract_published_at(BeautifulSoup(html, "lxml"))
        assert dt == datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def test_extract_published_at_ayer(self):
        from datetime import datetime, timedelta, timezone
        from bs4 import BeautifulSoup
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = '<span class="ij-FormatterSincedate">Ayer</span>'
        dt = InfoJobsParser._extract_published_at(BeautifulSoup(html, "lxml"))
        expected = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        assert dt == expected

    def test_extract_published_at_no_date(self):
        from bs4 import BeautifulSoup
        from src.pipeline.infojobs_scraper import InfoJobsParser

        html = "<div>Sin fecha</div>"
        dt = InfoJobsParser._extract_published_at(BeautifulSoup(html, "lxml"))
        assert dt is None


class TestBotBlocked:
    """Tests para is_bot_blocked contra snapshots real y sintético."""

    @classmethod
    def setup_class(cls):
        from src.pipeline.infojobs_scraper import InfoJobsParser

        cls.parser = InfoJobsParser

    def test_bot_blocked_true(self):
        html = (SNAPSHOTS / "detail_bot_blocked.html").read_text(encoding="utf-8")
        assert self.parser.is_bot_blocked(html)

    def test_bot_blocked_false_valid(self):
        html = (SNAPSHOTS / "offer_detail.html").read_text(encoding="utf-8")
        assert not self.parser.is_bot_blocked(html)

    def test_bot_blocked_false_senior(self):
        html = (SNAPSHOTS / "offer_senior_detail.html").read_text(encoding="utf-8")
        assert not self.parser.is_bot_blocked(html)


class TestValidDetail:
    """Tests para is_valid_detail contra ofertas reales y bot-blocked."""

    @classmethod
    def setup_class(cls):
        from src.pipeline.infojobs_scraper import InfoJobsParser

        cls.parser = InfoJobsParser

    def test_valid_detail_normal(self):
        html = (SNAPSHOTS / "offer_detail.html").read_text(encoding="utf-8")
        detail = self.parser.parse_detail_html(html)
        assert self.parser.is_valid_detail(detail)

    def test_valid_detail_senior(self):
        html = (SNAPSHOTS / "offer_senior_detail.html").read_text(encoding="utf-8")
        detail = self.parser.parse_detail_html(html)
        assert self.parser.is_valid_detail(detail)

    def test_valid_detail_bot_blocked(self):
        html = (SNAPSHOTS / "detail_bot_blocked.html").read_text(encoding="utf-8")
        detail = self.parser.parse_detail_html(html)
        # El título "No podemos identificar tu navegador" tiene 44 chars > _MIN_TITLE_LENGTH=5
        # El rechazo viene de description_text vacío y offer_id vacío
        assert not self.parser.is_valid_detail(detail)
        assert len(detail.description_text or "") < self.parser._MIN_DESC_LENGTH
        assert not detail.offer_id
