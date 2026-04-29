"""
Pipeline: fetch de ofertas desde InfoJobs vía Apify.
Construye searchUrls desde search_config, limpia datos y hace upsert en DB.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from apify_client import ApifyClient

# Asegurar que src/ está en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.init_db import get_connection
from src.db.models import get_active_candidate_profile
from src.utils.ollama_client import ollama_call
from src.utils.cleaner import clean_description

log = logging.getLogger(__name__)

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")

MAX_RETRIES = 3


def build_search_urls(search_config: dict, profile: dict) -> list[str]:
    """Construye searchUrls válidas de InfoJobs."""
    base = "https://www.infojobs.net/ofertas-trabajo/espana"
    urls: list[str] = []

    geo_level = search_config.get("active_geo_level", 0)

    # Provincias: 5=Cádiz, 40=Sevilla (según InfoJobs)
    province_map = {1: "5", 2: "40"}
    province_id = province_map.get(geo_level, "")

    # Roles desde role_hierarchy o defaults
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
        url = f"{base}?keyword={query}&sinceDate=LAST_DAY"
        if province_id:
            url += f"&provinceIds={province_id}"
        urls.append(url)

    log.info("searchUrls generadas (%d): %s", len(urls), urls)
    return urls


def ensure_search_config() -> dict:
    """
    Verifica que exista search_config activo.
    Si no, lo genera con qwen2.5 desde PERFIL.md.
    """
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT * FROM search_config ORDER BY last_updated DESC LIMIT 1"
    ).fetchone()

    if row:
        cols = [d[0] for d in cur.description]
        cfg = dict(zip(cols, row))
        conn.close()
        return cfg

    # Generar desde PERFIL.md
    log.info("search_config no existe, generando desde PERFIL.md...")
    perfil_text = Path("PERFIL.md").read_text(encoding="utf-8")

    prompt = f"""Lee este perfil y genera la jerarquía geográfica y de roles para búsqueda de empleo.
Responde SOLO con JSON válido (sin markdown) con este esquema:
{{
  "geo_hierarchy": ["nacional", "provincia_X", "ciudad_Y"],
  "role_hierarchy": ["data-analyst", "analista-de-datos", "business-intelligence"],
  "active_geo_level": 0,
  "active_role_level": 0
}}

PERFIL:
{perfil_text}
"""

    result = ollama_call(
        model="qwen2.5-coder:7b",
        prompt=prompt,
        expect_json=True,
    )

    if not result or "error" in str(result).lower():
        log.error("Fallo generando search_config desde qwen2.5")
        conn.close()
        return {
            "geo_hierarchy": "[]",
            "role_hierarchy": "[]",
            "active_geo_level": 0,
            "active_role_level": 0,
        }

    cur.execute(
        """INSERT INTO search_config
           (geo_hierarchy, role_hierarchy, active_geo_level, active_role_level)
           VALUES (?, ?, ?, ?)""",
        (
            json.dumps(result.get("geo_hierarchy", [])),
            json.dumps(result.get("role_hierarchy", [])),
            result.get("active_geo_level", 0),
            result.get("active_role_level", 0),
        ),
    )
    conn.commit()
    row = cur.execute(
        "SELECT * FROM search_config ORDER BY last_updated DESC LIMIT 1"
    ).fetchone()
    cols = [d[0] for d in cur.description]
    cfg = dict(zip(cols, row))
    conn.close()
    log.info("search_config generado (id=%d)", cfg["id"])
    return cfg


def call_apify(urls: list[str]) -> list[dict]:
    """Llama a Apify usando ApifyClient y devuelve la lista de ofertas."""
    if not APIFY_TOKEN:
        log.error("APIFY_TOKEN no configurado")
        return []

    client = ApifyClient(APIFY_TOKEN)
    run_input = {
        "searchUrls": urls,
        "maxItems": 30,
        "proxyConfiguration": {"useApifyProxy": False},
    }

    try:
        run = client.actor("easyapi~infojobs-job-scraper").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        log.info(
            "Apify OK: %d items, coste $%.5f",
            len(items),
            run.get("usageTotalUsd", 0),
        )
        return items
    except Exception as e:
        log.error("Error Apify: %s", e)
        return []


def extract_fields_with_qwen(offer: dict) -> dict:
    """Usa qwen2.5 para extraer/normalizar campos de la oferta."""
    title = offer.get("title", "")
    description = offer.get("description", "")

    prompt = f"""Analiza esta oferta de empleo y extrae campos normalizados.
Responde SOLO con JSON válido (sin markdown):
{{
  "sector_norm": "string (sector normalizado)",
  "sector_tags": ["string"],
  "relevance_flag": "core|adjacent|stretch|temporal",
  "skills_required": ["string"],
  "work_mode_norm": "remote|hybrid|onsite|unknown"
}}

TÍTULO: {title}
DESCRIPCIÓN: {description[:3000]}
"""

    result = ollama_call(
        model="qwen2.5-coder:7b",
        prompt=prompt,
        expect_json=True,
    )
    if not result or "error" in str(result).lower():
        return {
            "sector_norm": None,
            "sector_tags": [],
            "relevance_flag": "stretch",
            "skills_required": [],
            "work_mode_norm": "unknown",
        }
    return result


def upsert_offer(cur, offer: dict, search_layer: int, role_level: int) -> bool:
    """
    Hace upsert de una oferta en la tabla offers.
    Devuelve True si es nueva (insertada), False si ya existía.
    """
    source_id = offer.get("id") or offer.get("sourceId") or str(offer.get("url", ""))
    if not source_id:
        return False

    # Verificar si ya existe
    existing = cur.execute(
        "SELECT id FROM offers WHERE source_id = ?", (source_id,)
    ).fetchone()
    if existing:
        return False

    # Limpiar descripción
    raw_desc = offer.get("description", "")
    clean_desc = clean_description(raw_desc)

    # Extraer campos con qwen2.5
    extracted = extract_fields_with_qwen(offer)

    # Construir dict de inserción
    cur.execute(
        """INSERT INTO offers (
            source_id, source, url, title, company_name,
            province, city, salary_min, salary_max, salary_period,
            contract_type, work_mode, experience_min, experience_max,
            education_level, skills_required, description_raw, description_clean,
            applications_count, published_at, search_layer, role_level,
            relevance_flag
        ) VALUES (?, 'infojobs', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            source_id,
            offer.get("url"),
            offer.get("title"),
            offer.get("companyName") or offer.get("company_name"),
            offer.get("province") or offer.get("provinceName"),
            offer.get("city") or offer.get("cityName"),
            offer.get("salaryMin") or offer.get("salary_min"),
            offer.get("salaryMax") or offer.get("salary_max"),
            offer.get("salaryPeriod") or offer.get("salary_period"),
            offer.get("contractType") or offer.get("contract_type"),
            extracted.get("work_mode_norm", offer.get("workMode")),
            offer.get("experienceMin") or offer.get("experience_min"),
            offer.get("experienceMax") or offer.get("experience_max"),
            offer.get("educationLevel") or offer.get("education_level"),
            json.dumps(extracted.get("skills_required", [])),
            raw_desc,
            clean_desc,
            offer.get("applicationsCount") or offer.get("applications_count", 0),
            offer.get("publishedAt") or offer.get("published_at"),
            search_layer,
            role_level,
            extracted.get("relevance_flag", "stretch"),
        ),
    )
    return True


def run_fetch() -> dict:
    """Ejecuta el fetch completo. Devuelve stats para search_runs."""
    t0 = time.monotonic()
    stats: dict[str, Any] = {
        "offers_fetched": 0,
        "new_offers": 0,
        "errors": None,
        "status": "ok",
    }

    try:
        cfg = ensure_search_config()
        profile = get_active_candidate_profile()
        if not profile:
            log.warning("No hay perfil activo, usando PERFIL.md")

        urls = build_search_urls(cfg, {})
        if not urls:
            stats["status"] = "no_urls"
            return stats

        raw_offers = call_apify(urls)
        stats["offers_fetched"] = len(raw_offers)

        conn = get_connection()
        cur = conn.cursor()
        new_count = 0
        for offer in raw_offers:
            try:
                is_new = upsert_offer(
                    cur,
                    offer,
                    cfg.get("active_geo_level", 0),
                    cfg.get("active_role_level", 0),
                )
                if is_new:
                    new_count += 1
            except Exception as e:
                log.error("Error procesando oferta: %s", e)
                if not stats["errors"]:
                    stats["errors"] = str(e)
        conn.commit()
        conn.close()

        stats["new_offers"] = new_count
        log.info(
            "Fetch completado: %d nuevas de %d total",
            new_count,
            len(raw_offers),
        )

    except Exception as e:
        log.error("Error en fetch: %s", e)
        stats["status"] = "error"
        stats["errors"] = str(e)

    stats["duration_ms"] = int((time.monotonic() - t0) * 1000)
    return stats


def log_search_run(stats: dict) -> None:
    """Registra el run en search_runs."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO search_runs
           (offers_fetched, new_offers, errors, duration_ms, status)
           VALUES (?, ?, ?, ?, ?)""",
        (
            stats.get("offers_fetched", 0),
            stats.get("new_offers", 0),
            stats.get("errors"),
            stats.get("duration_ms"),
            stats.get("status", "ok"),
        ),
    )
    conn.commit()
    conn.close()
    log.info("search_runs registrado")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = run_fetch()
    log_search_run(stats)
    print(f"Stats: {stats}")
