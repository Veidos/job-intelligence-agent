"""
Pipeline: fetch de ofertas desde InfoJobs vía Apify.
Construye searchUrls desde search_config, limpia datos y hace upsert en DB.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from apify_client import ApifyClient

# Asegurar que src/ está en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.init_db import get_connection
from src.utils.ollama_client import ollama_call
from src.utils.cleaner import clean_description

log = logging.getLogger(__name__)

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")

MAX_RETRIES = 3


def build_search_urls(
    search_config: dict, profile: dict, since_date: str | None = None
) -> list[str]:
    """Construye searchUrls válidas de InfoJobs.

    Args:
        search_config: Configuración de búsqueda
        profile: Perfil del candidato
        since_date: Filtro de fecha (ej: "LAST_WEEK"). None = sin filtro.
    """
    base = "https://www.infojobs.net/ofertas-trabajo/espana"
    urls: list[str] = []

    # Parse geo_hierarchy
    geo_raw = search_config.get("geo_hierarchy")
    if geo_raw:
        try:
            geo_hierarchy = json.loads(geo_raw) if isinstance(geo_raw, str) else geo_raw
        except (json.JSONDecodeError, TypeError):
            geo_hierarchy = ["nacional"]
    else:
        geo_hierarchy = ["nacional"]

    active_geo_level = search_config.get("active_geo_level", 0)
    current_geo = (
        geo_hierarchy[active_geo_level]
        if active_geo_level < len(geo_hierarchy)
        else None
    )

    # Parse role_hierarchy
    roles_raw = search_config.get("role_hierarchy")
    if roles_raw:
        try:
            roles = json.loads(roles_raw) if isinstance(roles_raw, str) else roles_raw
        except (json.JSONDecodeError, TypeError):
            roles = []
    else:
        roles = [
            "data analyst",
            "analista de datos",
            "business intelligence",
            "cientifico de datos junior",
        ]

    for query in roles[:5]:
        url = f"{base}?keyword={query}&sortBy=PUBLICATION_DATE"
        if since_date:
            url += f"&sinceDate={since_date}"
        if current_geo and current_geo != "nacional":
            if current_geo.isdigit():
                url += f"&provinceIds={current_geo}"
            else:
                url += f"+{current_geo}"
        urls.append(url)

    log.info("searchUrls generadas (%d): %s", len(urls), urls)
    return urls


def extract_fields_with_qwen(item: dict) -> dict[str, Any]:
    """Usa qwen2.5 para extraer campos estructurados de una oferta."""
    prompt = f"""
Extrae los siguientes campos de esta oferta de InfoJobs en JSON válido:
- description_clean: descripción limpia (sin HTML)
- skills_required: lista de skills técnicas requeridas
- experience_years: años de experiencia requeridos (int, 0 si no se menciona)
- education_level: nivel educativo requerido
- salary_range: rango salarial o "No especificado"

Oferta:
{json.dumps(item, ensure_ascii=False)}

Responde SOLO con el JSON, sin markdown.
"""
    try:
        result = ollama_call(
            model="qwen2.5-coder:7b",
            prompt=prompt,
            expect_json=True,
        )
        return result if isinstance(result, dict) else {}
    except Exception as e:
        log.warning("qwen2.5 falló extrayendo campos: %s", e)
        return {}


def upsert_offer(item: dict, conn) -> None:
    """Inserta o actualiza una oferta en la base de datos."""
    offer_data = item.get("offer", {})

    source_id = offer_data.get("code")
    if not source_id:
        log.warning(
            "source_id es None, saltando oferta: %s",
            offer_data.get("title", "sin título"),
        )
        return

    title = offer_data.get("title")
    city = offer_data.get("city")
    company_name = offer_data.get("companyName")
    url = offer_data.get("link")
    contract_type = offer_data.get("contractType")
    work_mode_raw = offer_data.get("teleworking")
    published_at = offer_data.get("publishedAt")
    description = offer_data.get("description", "")

    # Enriquecer con qwen2.5 usando el item completo
    enriched = extract_fields_with_qwen(item)
    description_clean = enriched.get(
        "description_clean", clean_description(description)
    )
    skills_required = json.dumps(enriched.get("skills_required", []))
    experience_years = enriched.get("experience_years", 0)
    education_level = enriched.get("education_level", "")
    salary_range = enriched.get("salary_range", "")

    work_mode = work_mode_raw or "Presencial"

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO offers (
            source_id, title, city, company_name, url, contract_type,
            work_mode, published_at, description, description_clean,
            skills_required, experience_years, education_level, salary_range,
            scraped_at, search_url, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            title=excluded.title,
            city=excluded.city,
            company_name=excluded.company_name,
            url=excluded.url,
            contract_type=excluded.contract_type,
            work_mode=excluded.work_mode,
            published_at=excluded.published_at,
            description=excluded.description,
            description_clean=excluded.description_clean,
            skills_required=excluded.skills_required,
            experience_years=excluded.experience_years,
            education_level=excluded.education_level,
            salary_range=excluded.salary_range,
            scraped_at=excluded.scraped_at,
            search_url=excluded.search_url,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            source_id,
            title,
            city,
            company_name,
            url,
            contract_type,
            work_mode,
            published_at,
            description,
            description_clean,
            skills_required,
            experience_years,
            education_level,
            salary_range,
            item.get("scrapedAt"),
            item.get("searchUrl"),
            True,
        ),
    )
    conn.commit()
    log.debug("Upsert oferta %s: %s", source_id, title)


def run_fetch(search_config: dict, profile: dict, since_date: str | None = None) -> int:
    """Ejecuta el fetch completo desde Apify y guarda en DB."""
    if not APIFY_TOKEN:
        log.error("APIFY_TOKEN no configurado")
        return 0

    client = ApifyClient(APIFY_TOKEN)
    search_urls = build_search_urls(search_config, profile, since_date)

    if not search_urls:
        log.warning("No hay searchUrls para procesar")
        return 0

    log.info("Iniciando Apify actor para %d URLs", len(search_urls))

    run_input = {
        "startUrls": [{"url": u} for u in search_urls],
        "maxItems": 100,
    }

    try:
        actor_client = client.actor("XkZvxV7rJbKjXh8NA")
        run_result = actor_client.call(run_input=run_input)
    except Exception as e:
        log.error("Error ejecutando Apify actor: %s", e)
        return 0

    if not run_result or "defaultDatasetId" not in run_result:
        log.error("Apify no devolvió dataset válido")
        return 0

    dataset = client.dataset(run_result["defaultDatasetId"])
    items = list(dataset.iterate_items())
    log.info("Apify devolvió %d items", len(items))

    conn = get_connection()
    count = 0
    for item in items:
        try:
            upsert_offer(item, conn)
            count += 1
        except Exception as e:
            log.warning("Error procesando oferta: %s", e)

    conn.close()
    log.info("Fetch completado: %d ofertas guardadas", count)
    return count
