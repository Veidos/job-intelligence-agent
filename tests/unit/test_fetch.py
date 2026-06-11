"""Unit tests para pipeline/fetch.py — parsers y lógica de URLs."""

from __future__ import annotations

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
