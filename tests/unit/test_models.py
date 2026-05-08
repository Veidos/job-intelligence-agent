"""Unit tests para db/models.py — helpers de serialización JSON."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


class TestJsonSerialize:
    """Tests para json_serialize(data)."""

    def test_dict_a_json_string(self):
        from src.db.models import json_serialize

        result = json_serialize({"key": "value", "num": 42})

        assert result == '{"key": "value", "num": 42}'

    def test_lista_a_json_string(self):
        from src.db.models import json_serialize

        result = json_serialize([1, 2, 3])

        assert result == "[1, 2, 3]"

    def test_none_devuelve_null(self):
        from src.db.models import json_serialize

        result = json_serialize(None)

        assert result == "null"

    def test_lista_vacia(self):
        from src.db.models import json_serialize

        result = json_serialize([])

        assert result == "[]"

    def test_dict_vacio(self):
        from src.db.models import json_serialize

        result = json_serialize({})

        assert result == "{}"

    def test_nested_object(self):
        from src.db.models import json_serialize

        data = {
            "skills": [{"name": "Python", "level": "básico"}],
            "count": 2,
        }
        result = json_serialize(data)

        assert "skills" in result
        assert "Python" in result

    def test_unicode_chars(self):
        from src.db.models import json_serialize

        result = json_serialize({"nombre": "José", "emoji": "🎯"})

        assert "José" in result
        assert "🎯" in result


class TestJsonDeserialize:
    """Tests para json_deserialize(text)."""

    def test_json_string_a_dict(self):
        from src.db.models import json_deserialize

        result = json_deserialize('{"key": "value", "num": 42}')

        assert result == {"key": "value", "num": 42}

    def test_json_string_a_lista(self):
        from src.db.models import json_deserialize

        result = json_deserialize("[1, 2, 3]")

        assert result == [1, 2, 3]

    def test_null_string_a_none(self):
        from src.db.models import json_deserialize

        assert json_deserialize("null") is None

    def test_none_input_retorna_none(self):
        from src.db.models import json_deserialize

        assert json_deserialize(None) is None

    def test_string_vacio_retorna_none(self):
        from src.db.models import json_deserialize

        assert json_deserialize("") is None

    def test_mal_formado_retorna_none(self):
        from src.db.models import json_deserialize

        assert json_deserialize("{esto no es json") is None

    def test_nested_object(self):
        from src.db.models import json_deserialize

        result = json_deserialize('{"skills": [{"name": "Python"}]}')

        assert result["skills"][0]["name"] == "Python"
