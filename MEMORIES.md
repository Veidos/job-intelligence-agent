# MEMORIES.md — Aprendizajes del Sistema

## Configuración del proyecto
- Python 3.14+ requerido
- pypdf 6.10.2 instalado (usado para extracción de texto del CV)
- Ollama ejecutándose localmente en http://localhost:11434
- qwen2.5-coder:7b y gemma4:e4b confirmados disponibles

## Extracción de CV (cv_extractor.py)
- Limite de texto enviado a qwen2.5: 12000 caracteres (primeras páginas)
- qwen2.5 responde en JSON estructurado validado por ollama_client.py
- Campos extraídos: full_name, location_current, skills_technical, education, experience, languages, projects
- Si el modelo falla en devolver JSON, ollama_client reintenta con instrucción adicional

## Prompts efectivos
- qwen2.5-coder:7b: instrucción explícita "responde UNICAMENTE con JSON valido" + esquema de campos
- Temperatura baja (0.1) para extracción determinista

## Fetch y extracción de campos
- `fetch.py` usa Apify (actor XkZvxV7rJbKjXh8NA) para scrapear InfoJobs.
- Estructura del actor: `item["offer"]["code"]`, `item["offer"]["teleworking"]`, etc.
- `upsert_offer` debe usar nombres exactos del schema.sql: `description_raw` (no `description`), `experience_min` (no `experience_years`), `fetched_at` (no `scraped_at`).
- Salarios: el schema tiene `salary_min` (REAL) y `salary_max` (REAL). Parsear desde texto con regex o desde qwen2.5.
- `search_url` NO existe en la tabla `offers`; no incluir en INSERT.
- `source_id` puede ser None si el actor falla; validar siempre antes de upsert.
- qwen2.5 enriquece campos pasando el item completo (no solo `offer_data`) para contexto.
- `cleaner.py` limpia descripciones eliminando exceso de saltos de línea y espacios.

## URLs de InfoJobs
- `sinceDate=LAST_DAY` no funciona en URLs de InfoJobs (parámetro no soportado).
- Deduplicación se hace exclusivamente por `source_id` en DB (ya implementado).
- Usar `sortBy=PUBLICATION_DATE` para priorizar ofertas recientes en los resultados.

## Arquitectura de búsqueda y escalabilidad
- El sistema usa **source_adapter pattern** para escalabilidad multi-país.
  Ahora solo InfoJobs (España). Diseñado para añadir Indeed, LinkedIn etc
  sin reescribir fetch.py.
- La expansión geográfica y de rol es genérica: se infiere desde PERFIL.md
  vía qwen2.5, nunca hardcodeada.

## Configuración del usuario (user_settings)
- `user_settings` controla hora de envío, número de ofertas y modo
  (morning/night). En Fase 5 se gestiona vía comandos de Telegram.
  `fetch.py` y `send.py` leen siempre desde esta tabla, nunca hardcodean.
- Apify MCP se implementa en Fase 5. `fetch.py` usa REST API ahora.
  El adaptador será intercambiable sin cambiar la lógica del pipeline.
