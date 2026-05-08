"""Unit tests para pipeline/fetch.py — parsers y lógica de URLs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


class TestParseSalary:
    """Tests para parse_salary(text)."""

    def test_rango_con_puntos_y_euro(self):
        from src.pipeline.fetch import parse_salary

        result = parse_salary("20.000 - 25.000 €")

        assert result == (20000.0, 25000.0)

    def test_solo_minimo(self):
        from src.pipeline.fetch import parse_salary

        result = parse_salary("Desde 18.000 €")

        assert result == (18000.0, None)

    def test_formato_k_minuscula(self):
        from src.pipeline.fetch import parse_salary

        result = parse_salary("20k-25k")

        assert result == (20000.0, 25000.0)

    def test_sin_separadores(self):
        from src.pipeline.fetch import parse_salary

        result = parse_salary("35000€")

        assert result == (35000.0, None)

    def test_no_especificado(self):
        from src.pipeline.fetch import parse_salary

        assert parse_salary("No especificado") == (None, None)
        assert parse_salary("No especificada") == (None, None)

    def test_none(self):
        from src.pipeline.fetch import parse_salary

        result = parse_salary(None)

        assert result == (None, None)

    def test_vacio(self):
        from src.pipeline.fetch import parse_salary

        result = parse_salary("")

        assert result == (None, None)

    def test_solo_maximo(self):
        from src.pipeline.fetch import parse_salary

        result = parse_salary("hasta 40.000")

        assert result == (40000.0, None)


class TestBuildSearchUrls:
    """Tests para build_search_urls(search_config, profile, since_date)."""

    def test_url_simple_sin_geografia(self):
        from src.pipeline.fetch import build_search_urls

        search_config = {
            "geo_hierarchy": json.dumps(["nacional"]),
            "role_hierarchy": json.dumps(["data analyst"]),
            "active_geo_level": 0,
        }

        urls = build_search_urls(search_config, {}, since_date=None)

        assert len(urls) == 1
        assert "data%20analyst" in urls[0]
        assert "PUBLICATION_DATE" in urls[0]

    def test_url_con_provincia_por_id(self):
        from src.pipeline.fetch import build_search_urls

        search_config = {
            "geo_hierarchy": json.dumps(["nacional", "28", "41"]),
            "role_hierarchy": json.dumps(["data scientist"]),
            "active_geo_level": 1,
        }

        urls = build_search_urls(search_config, {}, since_date=None)

        assert len(urls) == 1
        assert "provinceIds=28" in urls[0]

    def test_url_con_geografia_nacional(self):
        from src.pipeline.fetch import build_search_urls

        search_config = {
            "geo_hierarchy": json.dumps(["nacional"]),
            "role_hierarchy": json.dumps(["ml engineer"]),
            "active_geo_level": 0,
        }

        urls = build_search_urls(search_config, {}, since_date=None)

        assert "provincia" not in urls[0]
        assert "nacional" not in urls[0]

    def test_url_con_since_date(self):
        from src.pipeline.fetch import build_search_urls

        search_config = {
            "geo_hierarchy": json.dumps(["nacional"]),
            "role_hierarchy": json.dumps(["data analyst"]),
            "active_geo_level": 0,
        }

        urls = build_search_urls(search_config, {}, since_date="LAST_WEEK")

        assert "sinceDate=LAST_WEEK" in urls[0]

    def test_multiple_roles(self):
        from src.pipeline.fetch import build_search_urls

        search_config = {
            "geo_hierarchy": json.dumps(["nacional"]),
            "role_hierarchy": json.dumps(
                ["data analyst", "data scientist", "bi analyst"]
            ),
            "active_geo_level": 0,
        }

        urls = build_search_urls(search_config, {}, since_date=None)

        assert len(urls) == 3
        roles = ["data%20analyst", "data%20scientist", "bi%20analyst"]
        for url in urls:
            assert any(r in url for r in roles)

    def test_config_vacia_devuelve_lista_vacia(self):
        from src.pipeline.fetch import build_search_urls

        urls = build_search_urls({}, {}, since_date=None)

        assert urls == []

    def test_role_hierarchy_mal_formado_json(self):
        from src.pipeline.fetch import build_search_urls

        search_config = {
            "geo_hierarchy": json.dumps(["nacional"]),
            "role_hierarchy": "no es json valido [",
            "active_geo_level": 0,
        }

        urls = build_search_urls(search_config, {}, since_date=None)

        assert urls == []

    def test_geo_hierarchy_mal_formado_json_fallback_nacional(self):
        from src.pipeline.fetch import build_search_urls

        search_config = {
            "geo_hierarchy": "mal[formado",
            "role_hierarchy": json.dumps(["data analyst"]),
            "active_geo_level": 0,
        }

        urls = build_search_urls(search_config, {}, since_date=None)

        assert len(urls) == 1

    def test_active_geo_level_fuera_de_rango(self):
        from src.pipeline.fetch import build_search_urls

        search_config = {
            "geo_hierarchy": json.dumps(["nacional", "28"]),
            "role_hierarchy": json.dumps(["data analyst"]),
            "active_geo_level": 99,
        }

        urls = build_search_urls(search_config, {}, since_date=None)

        assert len(urls) == 1
        assert "provincia" not in urls[0]
