"""
Fixtures de respuestas pre-grabadas de Ollama (cassettes).
Cada cassette es un JSON con la respuesta "raw" del modelo.

Uso:
    from tests.fixtures.ollama.cassettes import CASSETTES

    def test_con_ollama_mock(ollama_mock):
        ollama_mock.return_value = CASSETTES["evaluate_technical_core"]
"""

from pathlib import Path
import json

CASSETTES_DIR = Path(__file__).parent

CASSETTES = {}


def _load_all():
    for fpath in CASSETTES_DIR.glob("*.json"):
        name = fpath.stem
        with open(fpath, encoding="utf-8") as fh:
            CASSETTES[name] = json.load(fh)


_load_all()

__all__ = ["CASSETTES", "CASSETTES_DIR"]
