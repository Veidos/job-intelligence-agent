"""
Cliente para OpenRouter API (compatible con interfaz de ollama_client).
Usa chat completions endpoint en lugar de /api/generate de Ollama.
"""

import json
import logging
import os
import time
from typing import Any

import requests

from src.utils.json_utils import _extract_json

log = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_TIMEOUT = 180

MODEL_TECHNICAL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
MODEL_HR = os.getenv("OPENROUTER_MODEL", "openrouter/free")

MODEL_TEMPERATURES: dict[str, float] = {
    MODEL_TECHNICAL: 0.1,
    MODEL_HR: 0.0,
}


class OpenRouterError(Exception):
    """Error en llamada a OpenRouter."""


def _call_openrouter_raw(
    model: str,
    prompt: str,
    temperature: float | None = None,
) -> str:
    """Llamada directa a la API de OpenRouter. Sin reintentos."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY no configurada en entorno")

    temp = temperature if temperature is not None else MODEL_TEMPERATURES.get(model, 0.1)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temp,
        "max_tokens": 4096,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Veidos/job-intelligence-agent",
    }
    try:
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=OPENROUTER_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except requests.exceptions.ConnectionError as e:
        raise OpenRouterError(f"OpenRouter no disponible: {e}") from e
    except requests.exceptions.Timeout:
        raise OpenRouterError(f"Timeout ({OPENROUTER_TIMEOUT}s) en {model}")
    except requests.exceptions.HTTPError as e:
        raise OpenRouterError(f"HTTP {e.response.status_code}: {e}") from e
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise OpenRouterError(f"Respuesta inesperada de OpenRouter: {e}") from e


def ollama_call(
    model: str,
    prompt: str,
    expect_json: bool = False,
    temperature: float | None = None,
    think: bool = False,
    json_retry_instruction: str = "\n\nResponde UNICAMENTE con JSON valido, sin texto adicional.",
) -> str | Any:
    """
    Llama a OpenRouter con reintentos y validacion JSON opcional.
    Compatible con interfaz de ollama_client.ollama_call.

    think se ignora (no aplica a OpenRouter).
    """
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            text = _call_openrouter_raw(model, prompt, temperature)
            if not expect_json:
                return text

            return _extract_json(text)
        except (OpenRouterError, ValueError) as e:
            last_error = e
            log.warning(
                "Intento %d/3 fallo para %s: %s",
                attempt + 1,
                model,
                e,
            )
            if attempt < 2:
                time.sleep(2)

    if expect_json and isinstance(last_error, ValueError):
        log.warning("Respuesta no-JSON de %s, reintentando con instruccion extra...", model)
        try:
            text = _call_openrouter_raw(model, prompt + json_retry_instruction, temperature)
            return _extract_json(text)
        except (OpenRouterError, ValueError) as e:
            raise OpenRouterError(f"Modelo {model} no devolvio JSON valido") from e

    raise OpenRouterError(f"Fallo tras 3 intentos: {last_error}") from last_error


def check_openrouter_connection() -> dict[str, bool]:
    """Verifica que OPENROUTER_API_KEY este configurada."""
    status: dict[str, bool] = {MODEL_TECHNICAL: False, MODEL_HR: False}
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        log.error("OPENROUTER_API_KEY no configurada")
        return status
    try:
        r = requests.get(
            f"{OPENROUTER_BASE_URL}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        r.raise_for_status()
        for model in status:
            status[model] = True
            log.info("[%s] OK (model configurado: %s)", model, model)
    except requests.exceptions.RequestException as e:
        log.error("OpenRouter no disponible: %s", e)
    return status


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    status = check_openrouter_connection()
    if all(status.values()):
        result = ollama_call(
            model=MODEL_TECHNICAL,
            prompt='Responde con este JSON exacto: {"status": "ok", "test": true}',
            expect_json=True,
        )
        log.info("Test exitoso: %s", result)
    else:
        log.error("OpenRouter no disponible")
