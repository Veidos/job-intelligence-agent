"""
Pipeline: fetch de ofertas desde InfoJobs vía Apify.
Construye searchUrls desde search_config, limpia datos y hace upsert en DB.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from typing import Any
from urllib.parse import quote

from apify_client import ApifyClient

# Asegurar que la raíz del proyecto está en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.db.init_db import get_connection
from src.utils.ollama_client import ollama_call
from src.utils.cleaner import clean_description

log = logging.getLogger(__name__)

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")

MAX_RETRIES = 3


def ensure_search_config(conn=None) -> dict:
    """Lee la configuración de búsqueda desde la DB.

    Devuelve el registro más reciente de search_config.
    Si no existe ninguno, devuelve un dict vacío (el caller decide el fallback).
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, geo_hierarchy, role_hierarchy, active_geo_level, active_role_level "
            "FROM search_config ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "geo_hierarchy": row[1],
                "role_hierarchy": row[2],
                "active_geo_level": row[3],
                "active_role_level": row[4],
            }
        return {}
    finally:
        if own_conn:
            conn.close()


def build_search_urls(
    search_config: dict, profile: dict, since_date: str | None = None
) -> list[str]:
    """Construye searchUrls válidas de InfoJobs.

    Args:
        search_config: Configuración de búsqueda (debe venir de ensure_search_config)
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

    # Parse role_hierarchy (viene de DB, no usar fallback hardcodeado)
    roles_raw = search_config.get("role_hierarchy")
    if roles_raw:
        try:
            roles = json.loads(roles_raw) if isinstance(roles_raw, str) else roles_raw
        except (json.JSONDecodeError, TypeError):
            roles = []
    else:
        roles = []

    for query in roles:
        url = f"{base}?keyword={quote(query)}&sortBy=PUBLICATION_DATE"
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


def parse_salary(text: str) -> tuple[float | None, float | None]:
    """Extrae salary_min y salary_max de un texto de salario."""
    if not text or text in ("No especificado", "No especificada"):
        return None, None
    # Buscar patrones como "20.000 - 25.000", "20000€", "20k-25k"
    text = text.lower().replace(".", "").replace("€", "").replace("k", "000")
    numbers = re.findall(r"\d+", text)
    if len(numbers) >= 2:
        return float(numbers[0]), float(numbers[1])
    if len(numbers) == 1:
        return float(numbers[0]), None
    return None, None


def extract_fields_with_qwen(item: dict) -> dict[str, Any]:
    """Usa qwen2.5 para extraer campos estructurados de una oferta."""
    prompt = f"""
Extrae los siguientes campos de esta oferta de InfoJobs en JSON válido:
- description_clean: descripción limpia (sin HTML)
- skills_required: lista de skills técnicas requeridas (array de strings)
- experience_min: años mínimos de experiencia requeridos (int, 0 si no se menciona)
- education_level: nivel educativo requerido (string)
- salary_min: salario mínimo anual en número (float o null)
- salary_max: salario máximo anual en número (float o null)

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


def upsert_offer(item: dict, conn) -> bool:
    """Inserta o actualiza una oferta en la base de datos.

    Returns:
        True si fue inserción nueva, False si fue actualización.
    """
    offer_data = item.get("offer", {})

    source_id = offer_data.get("code")
    if not source_id:
        log.warning(
            "source_id es None, saltando oferta: %s",
            offer_data.get("title", "sin título"),
        )
        return False

    title = offer_data.get("title")
    city = offer_data.get("city")
    company_name = offer_data.get("companyName")
    url = offer_data.get("link")
    contract_type = offer_data.get("contractType")
    work_mode_raw = offer_data.get("teleworking")
    published_at = offer_data.get("publishedAt")
    description_raw = offer_data.get("description", "")

    # Enriquecer con qwen2.5 usando el item completo
    enriched = extract_fields_with_qwen(item)
    description_clean = enriched.get(
        "description_clean", clean_description(description_raw)
    )
    skills_required = json.dumps(enriched.get("skills_required", []))
    experience_min = enriched.get("experience_min", 0)
    education_level = enriched.get("education_level", "")

    # Parsear salario
    salary_min = enriched.get("salary_min")
    salary_max = enriched.get("salary_max")
    salary_text = enriched.get("salary_text", "")
    if (salary_min is None or salary_max is None) and salary_text:
        salary_min, salary_max = parse_salary(salary_text)

    work_mode = work_mode_raw or "Presencial"
    fetched_at = item.get("scrapedAt") or datetime.now().isoformat()

    cursor = conn.cursor()

    # 1. Comprobar si source_id ya existe
    cursor.execute("SELECT COUNT(*) FROM offers WHERE source_id = ?", (source_id,))
    count = cursor.fetchone()[0]

    if count == 0:
        # No existe → INSERT completo
        cursor.execute(
            """
            INSERT INTO offers (
                source_id, title, city, company_name, url, contract_type,
                work_mode, published_at, description_raw, description_clean,
                skills_required, experience_min, education_level,
                salary_min, salary_max, fetched_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                description_raw,
                description_clean,
                skills_required,
                experience_min,
                education_level,
                salary_min,
                salary_max,
                fetched_at,
                True,
            ),
        )
        conn.commit()
        log.debug("Inserción nueva oferta %s: %s", source_id, title)
        return True
    else:
        # Ya existe → UPDATE sin tocar fetched_at ni source_id
        cursor.execute(
            """
            UPDATE offers SET
                title=?,
                city=?,
                company_name=?,
                url=?,
                contract_type=?,
                work_mode=?,
                published_at=?,
                description_raw=?,
                description_clean=?,
                skills_required=?,
                experience_min=?,
                education_level=?,
                salary_min=?,
                salary_max=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE source_id=?
            """,
            (
                title,
                city,
                company_name,
                url,
                contract_type,
                work_mode,
                published_at,
                description_raw,
                description_clean,
                skills_required,
                experience_min,
                education_level,
                salary_min,
                salary_max,
                source_id,
            ),
        )
        conn.commit()
        log.debug("Actualización oferta %s: %s", source_id, title)
        return False


def run_fetch(
    search_config: dict | None = None,
    profile: dict | None = None,
    since_date: str | None = None,
    max_items: int = 30,
) -> int:
    """Ejecuta el fetch completo desde Apify y guarda en DB."""
    if not APIFY_TOKEN:
        log.error("APIFY_TOKEN no configurado")
        return 0

    # Leer search_config desde DB si no se pasa explícitamente
    if not search_config:
        search_config = ensure_search_config()
    if not search_config:
        log.error("No hay search_config en DB y no se proporcionó uno")
        return 0

    if not profile:
        profile = {}

    client = ApifyClient(APIFY_TOKEN)
    search_urls = build_search_urls(search_config, profile, since_date)

    if not search_urls:
        log.warning("No hay searchUrls para procesar")
        return 0

    log.info("Iniciando Apify actor para %d URLs", len(search_urls))

    run_input = {
        "searchUrls": search_urls,
        "maxItems": max_items,
    }

    try:
        actor_client = client.actor("lRxJmbuhggr0LU3uj")
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
    new_count = 0
    for item in items:
        try:
            is_new = upsert_offer(item, conn)
            if is_new:
                new_count += 1
        except Exception as e:
            log.warning("Error procesando oferta: %s", e)

    conn.close()
    log.info(
        "Fetch completado: %d ofertas nuevas guardadas (de %d total)",
        new_count,
        len(items),
    )
    return new_count


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    search_config = None  # lee desde DB via ensure_search_config()
    profile = {}
    inserted = run_fetch(search_config, profile, since_date=None, max_items=30)
    print(f"Ofertas insertadas: {inserted}")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT source_id, title, city, company_name FROM offers LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()
