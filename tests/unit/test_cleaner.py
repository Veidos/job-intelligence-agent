"""Unit tests para utils/cleaner.py — funciones de limpieza de texto."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


class TestCleanText:
    """Tests para clean_text(text)."""

    def test_pasa_texto_normal(self):
        from src.utils.cleaner import clean_text

        result = clean_text("Texto normal sin problemas")

        assert result == "Texto normal sin problemas"

    def test_elimina_tabs(self):
        from src.utils.cleaner import clean_text

        result = clean_text("Texto\tcon\ttabs")

        assert result == "Texto con tabs"

    def test_elimina_newlines_multiples(self):
        from src.utils.cleaner import clean_text

        result = clean_text("Texto\n\n\n\n\ncon saltos")

        assert result == "Texto con saltos"

    def test_elimina_espacios_al_inicio(self):
        from src.utils.cleaner import clean_text

        result = clean_text("   Texto con espacios")

        assert result == "Texto con espacios"

    def test_elimina_espacios_al_final(self):
        from src.utils.cleaner import clean_text

        result = clean_text("Texto con espacios   ")

        assert result == "Texto con espacios"

    def test_elimina_espacios_intermedios_extras(self):
        from src.utils.cleaner import clean_text

        result = clean_text("Texto  con   muchos    espacios")

        assert result == "Texto con muchos espacios"

    def test_none_retorna_vacio(self):
        from src.utils.cleaner import clean_text

        result = clean_text(None)

        assert result == ""

    def test_string_vacio_retorna_vacio(self):
        from src.utils.cleaner import clean_text

        result = clean_text("")

        assert result == ""


class TestCleanDescription:
    """Tests para clean_description(raw)."""

    def test_pasa_descripcion_limpia(self):
        from src.utils.cleaner import clean_description

        result = clean_description("Descripción limpia y normal.")

        assert result == "Descripción limpia y normal."

    def test_elimina_tabs(self):
        from src.utils.cleaner import clean_description

        result = clean_description("Desc\tcon\ttabs")

        assert result == "Desc con tabs"

    def test_elimina_carriage_return(self):
        from src.utils.cleaner import clean_description

        result = clean_description("Desc\rcon\rpalabras")

        assert result == "Descconpalabras"

    def test_colapsa_newlines_triples(self):
        from src.utils.cleaner import clean_description

        result = clean_description("Línea uno\n\n\nLínea dos")

        assert result == "Línea uno\n\nLínea dos"

    def test_colapsa_newlines_cuadruples(self):
        from src.utils.cleaner import clean_description

        result = clean_description("Línea uno\n\n\n\nLínea dos")

        assert result == "Línea uno\n\nLínea dos"

    def test_no_colapsa_newlines_dobles(self):
        from src.utils.cleaner import clean_description

        result = clean_description("Línea uno\n\nLínea dos")

        assert result == "Línea uno\n\nLínea dos"

    def test_strip_al_final(self):
        from src.utils.cleaner import clean_description

        result = clean_description("Descripción   \n\n   ")

        assert result.endswith("Descripción")

    def test_none_retorna_vacio(self):
        from src.utils.cleaner import clean_description

        result = clean_description(None)

        assert result == ""

    def test_string_vacio_retorna_vacio(self):
        from src.utils.cleaner import clean_description

        result = clean_description("")

        assert result == ""
