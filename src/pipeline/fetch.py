"""
Pipeline: fetch de ofertas desde InfoJobs vía scraper propio (curl_cffi + BeautifulSoup).
Extrae campos estructurados (requisitos, salario, modalidad) del HTML directo.
3 fases: scraper_raw_responses (append-only) → upsert en offers → enrich con LLM.
"""

import dataclasses
import json
import logging
import re
import sys
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from typing import Any
from urllib.parse import quote

# Asegurar que la raíz del proyecto está en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.db.init_db import get_connection
from src.utils.ollama_client import MODEL_TECHNICAL, ollama_call
from src.utils.cleaner import clean_description

log = logging.getLogger(__name__)

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


def _extract_keywords_from_config(search_config: dict) -> list[str]:
    """Extrae keywords de role_hierarchy sin construir URLs."""
    roles_raw = search_config.get("role_hierarchy")
    if not roles_raw:
        return []
    try:
        return json.loads(roles_raw) if isinstance(roles_raw, str) else roles_raw
    except (json.JSONDecodeError, TypeError):
        return []


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

    for query in _extract_keywords_from_config(search_config):
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


def parse_salary(salary_data: Any) -> tuple[float | None, float | None]:
    """Extrae salary_min y salary_max del campo salary de InfoJobs.

    Acepta tanto string legacy ("20.000€ - 25.000€") como el nuevo formato
    dict estructurado: {"range": {"min": 30000, "max": 33000}, "period": "YEAR"}
    """
    if not salary_data:
        return None, None

    if isinstance(salary_data, dict):
        rng = salary_data.get("range") or {}
        return rng.get("min"), rng.get("max")

    text = str(salary_data)
    if text in ("No especificado", "No especificada"):
        return None, None
    text = text.lower().replace(".", "").replace("€", "").replace("k", "000")
    numbers = re.findall(r"\d+", text)
    if len(numbers) >= 2:
        return float(numbers[0]), float(numbers[1])
    if len(numbers) == 1:
        return float(numbers[0]), None
    return None, None


def _extract_employer_id(offer_data: dict) -> str | None:
    """Extrae employer_id del companyLink de InfoJobs."""
    link = offer_data.get("companyLink")
    if not link:
        return None
    m = re.search(r"/em-i([a-zA-Z0-9_]+)", link)
    if m:
        return m.group(1)
    m = re.match(r"https?://([^.]+)\.", link)
    if m and m.group(1) != "www":
        return m.group(1)
    return None


def _ensure_skill_obj(s: Any) -> dict:
    """Asegura que una skill sea dict con name; level_required opcional."""
    if isinstance(s, dict):
        return {
            "name": s.get("name", str(s)),
            "level_required": s.get("level_required"),
        }
    return {"name": str(s), "level_required": None}


def parse_skills_required(raw: Any) -> dict:
    """Normaliza skills_required al schema {core: [{name, level_required}], secondary: [...]}.

    Acepta:
    - dict con keys 'core' y 'secondary' (objetos con/sin level_required)
    - list de strings (schema legacy) -> convierte a objetos sin nivel
    - string JSON -> deserializa y reintenta
    - None / vacío -> estructura vacía

    level_required se resuelve en evaluate.py desde role_level_label,
    no se persiste por skill desde fetch.
    """
    if raw is None:
        return {"core": [], "secondary": []}

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {"core": [], "secondary": []}

    if isinstance(raw, dict) and "core" in raw:
        core = [_ensure_skill_obj(s) for s in raw.get("core", []) if s]
        secondary = [_ensure_skill_obj(s) for s in raw.get("secondary", []) if s]
        return {"core": core, "secondary": secondary}

    if isinstance(raw, list):
        return {
            "core": [_ensure_skill_obj(s) for s in raw if isinstance(s, str)],
            "secondary": [],
        }

    return {"core": [], "secondary": []}


def extract_fields_with_llm(item: dict) -> dict[str, Any]:
    """Usa gemma4:e4b para extraer campos estructurados de una oferta.

    skills_required se extrae con schema estructurado:
    {
      "core": [{"name": "Python", "level_required": "intermedio"}, ...],
      "secondary": [{"name": "Git", "level_required": null}, ...]
    }

    Niveles válidos: "basico", "intermedio", "avanzado", null.
    Core = skills explícitamente marcadas como requisito o mencionadas múltiples veces.
    Secondary = deseables, valorables o mencionadas una vez sin énfasis.
    """
    prompt = f"""Extrae los siguientes campos de esta oferta de InfoJobs en JSON válido:

- description_clean: descripción limpia sin HTML, máximo 2000 caracteres
- role_level: nivel de seniority del puesto. Valores: "junior", "mid", "senior", null si no se puede inferir.
  Inferir de: título del puesto, años de experiencia pedidos, lenguaje de la descripción.
- skills_required: objeto con dos listas de objetos:
    - core: skills sin las que no se puede optar al puesto.
      Cada elemento: {{"name": "<nombre>"}}
    - secondary: skills deseables, valorables o mencionadas sin énfasis.
      Mismo formato que core.
- experience_min: años mínimos de experiencia requeridos (int, 0 si no se menciona)
- education_level: nivel educativo requerido (string, null si no se menciona)
- salary_min: salario mínimo anual en número (float o null)
- salary_max: salario máximo anual en número (float o null)

Reglas para clasificar skills:
- "imprescindible", "requisito", "obligatorio", "must have" → core
- "valorable", "deseable", "se valorará", "plus" → secondary
- Sin distinción explícita: las 3-5 skills más centrales al rol → core, el resto → secondary

Oferta:
{json.dumps(item, ensure_ascii=False)[:3000]}

Responde SOLO con el JSON, sin markdown."""

    try:
        result = ollama_call(
            model=MODEL_TECHNICAL,
            prompt=prompt,
            expect_json=True,
            temperature=0.0,
            think=True,
            num_ctx=8192,
        )
        if isinstance(result, dict):
            result["skills_required"] = parse_skills_required(
                result.get("skills_required")
            )
            return result
        return {}
    except Exception as e:
        log.warning("gemma4:e4b falló extrayendo campos: %s", e)
        return {}


def persist_raw_responses(run_id: str, items: list, conn) -> int:
    """Persiste cada item de Apify de forma inmutable antes de cualquier procesado.

    append-only: el payload nunca se modifica tras la inserción.
    Si el source_id ya existe para este run_id, se salta (idempotente).

    Returns:
        Número de items guardados.
    """
    cursor = conn.cursor()
    saved = 0
    for idx, item in enumerate(items):
        source_id = (item.get("offer") or {}).get("code")
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO apify_raw_responses
                    (run_id, item_index, source_id, payload, processed)
                VALUES (?, ?, ?, ?, 0)
                """,
                (run_id, idx, source_id, json.dumps(item, ensure_ascii=False)),
            )
            saved += cursor.rowcount
        except Exception as e:
            log.warning(
                "Error persistiendo raw item %d (run_id=%s): %s", idx, run_id, e
            )
    conn.commit()
    log.info("Raw responses persistidas: %d/%d (run_id=%s)", saved, len(items), run_id)
    return saved


def _upsert_offer(item: dict, conn) -> bool:
    """Persiste raw de Apify sin llamar a Ollama.

    Guarda raw_data completo + campos estructurales directos de Apify.
    Los campos que requieren LLM se rellenan en enrich_pending().

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
    employer_id = _extract_employer_id(offer_data)
    url = offer_data.get("link")
    contract_type = offer_data.get("contractType")
    work_mode_raw = offer_data.get("teleworking")
    published_at = offer_data.get("publishedAt")
    description_raw = offer_data.get("description", "")
    work_mode = work_mode_raw or "Presencial"
    fetched_at = item.get("scrapedAt") or datetime.now().isoformat()
    raw_data = json.dumps(item, ensure_ascii=False)

    salary_min, salary_max = parse_salary(offer_data.get("salary", "") or "")

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM offers WHERE source_id = ?", (source_id,))
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute(
            """
            INSERT INTO offers (
                source_id, title, city, company_name, employer_id, url, contract_type,
                work_mode, published_at, description_raw, salary_min, salary_max,
                fetched_at, is_active, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                title,
                city,
                company_name,
                employer_id,
                url,
                contract_type,
                work_mode,
                published_at,
                description_raw,
                salary_min,
                salary_max,
                fetched_at,
                True,
                raw_data,
            ),
        )
        conn.commit()
        log.debug("Inserción nueva oferta %s: %s", source_id, title)
        return True

    cursor.execute(
        """
        UPDATE offers SET
            title=?, city=?, company_name=?, employer_id=?, url=?,
            contract_type=?, work_mode=?, published_at=?, description_raw=?,
            salary_min=?, salary_max=?, raw_data=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE source_id=?
        """,
        (
            title,
            city,
            company_name,
            employer_id,
            url,
            contract_type,
            work_mode,
            published_at,
            description_raw,
            salary_min,
            salary_max,
            raw_data,
            source_id,
        ),
    )
    conn.commit()
    log.debug("Actualización oferta %s: %s", source_id, title)
    return False


def _upsert_offer_from_scraper(detail: Any, conn) -> bool:
    """Persiste RawOfferDetail directamente en offers.

    Salta apify_raw_responses — no es un item Apify.
    Skills del scraper van todas a secondary hasta que el LLM
    las reclasifique (core vs secondary) en enrich_pending().

    Returns:
        True si fue inserción nueva, False si fue actualización.
    """
    source_id = detail.offer_id
    if not source_id:
        log.warning("source_id vacío en RawOfferDetail, saltando")
        return False

    skills_required = json.dumps(
        {
            "core": [],
            "secondary": [{"name": s} for s in (detail.skills or [])],
        }
    )
    raw_data = json.dumps(dataclasses.asdict(detail), ensure_ascii=False)

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM offers WHERE source_id = ?", (source_id,))
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute(
            """
            INSERT INTO offers (
                source_id, title, city, company_name, url, contract_type,
                work_mode, published_at, description_raw, description_clean,
                salary_min, salary_max, experience_min, education_level,
                skills_required, fetched_at, is_active, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                detail.title,
                detail.city,
                detail.company,
                detail.url,
                detail.contract_type,
                detail.work_mode,
                detail.published_at,
                detail.description_html,
                detail.description_text,
                detail.salary_min,
                detail.salary_max,
                detail.experience_min_years,
                detail.education_min,
                skills_required,
                detail.scraped_at,
                True,
                raw_data,
            ),
        )
        conn.commit()
        log.debug("Inserción nueva oferta (scraper) %s: %s", source_id, detail.title)
        return True

    cursor.execute(
        """
        UPDATE offers SET
            title=?, city=?, company_name=?, url=?,
            contract_type=?, work_mode=?, published_at=?,
            description_raw=?, description_clean=?,
            salary_min=?, salary_max=?,
            experience_min=COALESCE(experience_min, ?),
            education_level=COALESCE(education_level, ?),
            skills_required=?, raw_data=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE source_id=?
        """,
        (
            detail.title,
            detail.city,
            detail.company,
            detail.url,
            detail.contract_type,
            detail.work_mode,
            detail.published_at,
            detail.description_html,
            detail.description_text,
            detail.salary_min,
            detail.salary_max,
            detail.experience_min_years,
            detail.education_min,
            skills_required,
            raw_data,
            source_id,
        ),
    )
    conn.commit()
    log.debug("Actualización oferta (scraper) %s: %s", source_id, detail.title)
    return False


def _persist_scraper_raw(run_id: str, detail: Any, conn) -> None:
    """Persiste RawOfferDetail en scraper_raw_responses (append-only).

    INSERT OR IGNORE con UNIQUE(offer_id): la primera vez que se scrapea
    una oferta queda como canónica. Ejecuciones posteriores se ignoran.
    """
    import dataclasses

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO scraper_raw_responses
            (run_id, offer_id, payload)
        VALUES (?, ?, ?)
        """,
        (
            run_id,
            detail.offer_id,
            json.dumps(dataclasses.asdict(detail), ensure_ascii=False),
        ),
    )
    if cursor.rowcount:
        conn.commit()
        log.debug("Raw scraper guardado: %s", detail.offer_id)


def _upsert_from_scraper_raw(run_id: str, conn) -> int:
    """Lee scraper_raw_responses pendientes y hace upsert en offers.

    Returns:
        Número de ofertas nuevas insertadas.
    """
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT id, offer_id, payload
        FROM scraper_raw_responses
        WHERE run_id = ? AND processed = 0
        """,
        (run_id,),
    ).fetchall()

    if not rows:
        log.info("No hay scraper raw pendientes para run_id=%s", run_id)
        return 0

    new_count = 0
    for raw_id, offer_id, payload_str in rows:
        try:
            from src.pipeline.infojobs_scraper import RawOfferDetail

            data = json.loads(payload_str)
            # Reconstruir RawOfferDetail desde dict
            detail = RawOfferDetail(**data)
            is_new = _upsert_offer_from_scraper(detail, conn)
            if is_new:
                new_count += 1
            cursor.execute(
                "UPDATE scraper_raw_responses SET processed=1 WHERE id=?",
                (raw_id,),
            )
        except Exception as e:
            cursor.execute(
                "UPDATE scraper_raw_responses SET error=? WHERE id=?",
                (str(e), raw_id),
            )
            log.warning(
                "Error procesando scraper_raw_id=%d (offer_id=%s): %s",
                raw_id,
                offer_id,
                e,
            )
    conn.commit()
    return new_count


def upsert_from_raw(run_id: str, conn) -> int:
    """Lee apify_raw_responses no procesadas de este run y hace upsert en offers.

    Marca cada raw como processed=1 si el upsert fue exitoso,
    o guarda el error en la columna error si falló.

    Returns:
        Número de ofertas nuevas insertadas.
    """
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT id, source_id, payload
        FROM apify_raw_responses
        WHERE run_id = ? AND processed = 0
        """,
        (run_id,),
    ).fetchall()

    if not rows:
        log.info("No hay raw responses pendientes para run_id=%s", run_id)
        return 0

    new_count = 0
    for raw_id, source_id, payload_str in rows:
        try:
            item = json.loads(payload_str)
            is_new = _upsert_offer(item, conn)
            if is_new:
                new_count += 1
            cursor.execute(
                "UPDATE apify_raw_responses SET processed=1 WHERE id=?",
                (raw_id,),
            )
        except Exception as e:
            cursor.execute(
                "UPDATE apify_raw_responses SET error=? WHERE id=?",
                (str(e), raw_id),
            )
            log.warning(
                "Error procesando raw_id=%d (source_id=%s): %s",
                raw_id,
                source_id,
                e,
            )
    conn.commit()
    return new_count


def enrich_pending(conn, limit: int = 0) -> int:
    """Fase 2: enriquece con LLM ofertas con raw_data pero sin enriched_at.

    Llama a extract_fields_with_llm() para cada oferta pendiente y actualiza
    description_clean, skills_required, experience_min, education_level,
    role_level_label, salary_min/max y enriched_at.

    Si el LLM falla -> enriched_at queda NULL -> reintento automático.
    """
    query = """
        SELECT id, source_id, raw_data
        FROM offers
        WHERE raw_data IS NOT NULL AND enriched_at IS NULL
    """
    params: tuple = ()
    if limit > 0:
        query += " LIMIT ?"
        params = (limit,)

    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        log.info("No hay ofertas pendientes de enriquecimiento")
        return 0

    log.info("Enriqueciendo %d ofertas con LLM...", len(rows))
    enriched_count = 0

    for offer_id, source_id, raw_data_str in rows:
        try:
            item = json.loads(raw_data_str)
        except (json.JSONDecodeError, TypeError):
            log.warning("raw_data inválido para oferta %s, saltando", source_id)
            continue

        enriched = extract_fields_with_llm(item)
        if not enriched:
            log.warning(
                "LLM no devolvió datos para oferta %s, se reintentará", source_id
            )
            continue

        description_clean = enriched.get(
            "description_clean",
            clean_description(item.get("offer", {}).get("description", "")),
        )
        skills_raw = enriched.get("skills_required", {"core": [], "secondary": []})
        skills_required = json.dumps(
            parse_skills_required(skills_raw), ensure_ascii=False
        )
        experience_min = enriched.get("experience_min", 0)
        education_level = enriched.get("education_level", "")
        role_level = enriched.get("role_level")

        salary_min = enriched.get("salary_min")
        salary_max = enriched.get("salary_max")
        if salary_min is None and salary_max is None:
            salary_text = enriched.get("salary_text", "")
            if salary_text:
                salary_min, salary_max = parse_salary(salary_text)

        # Trazabilidad COALESCE: loguear cuándo el scraper proveyó valores
        # que el LLM no va a sobrescribir.
        row_current = cursor.execute(
            "SELECT experience_min, education_level FROM offers WHERE id = ?",
            (offer_id,),
        ).fetchone()
        current_exp, current_edu = row_current if row_current else (None, None)
        if current_exp is not None:
            log.debug(
                "COALESCE exp: manteniendo %s del scraper para %s (LLM propuso %s)",
                current_exp,
                source_id,
                experience_min,
            )
        if current_edu is not None:
            log.debug(
                "COALESCE edu: manteniendo '%s' del scraper para %s (LLM propuso '%s')",
                current_edu,
                source_id,
                education_level,
            )

        cursor.execute(
            """
            UPDATE offers SET
                description_clean = ?,
                skills_required   = ?,
                experience_min    = COALESCE(experience_min, ?),
                education_level   = COALESCE(education_level, ?),
                role_level_label  = ?,
                salary_min        = COALESCE(?, salary_min),
                salary_max        = COALESCE(?, salary_max),
                enriched_at       = datetime('now'),
                updated_at        = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                description_clean,
                skills_required,
                experience_min,
                education_level,
                role_level,
                salary_min,
                salary_max,
                offer_id,
            ),
        )
        conn.commit()
        enriched_count += 1
        log.info(
            "  ✓ [%d/%d] %s — enriquecida",
            enriched_count,
            len(rows),
            source_id,
        )

    log.info("Enriquecimiento completado: %d/%d ofertas", enriched_count, len(rows))
    return enriched_count


def run_fetch_scraper(
    search_config: dict | None = None,
    since_date: str | None = None,
    max_items: int = 30,
) -> int:
    """Fetch usando scraper propio. No requiere APIFY_TOKEN.

    Fases:
      1. persist_scraper_raw — guarda RawOfferDetail en tabla append-only
      2. upsert_from_scraper_raw — escribe en offers desde raw
      3. enrich_pending — LLM reclasifica skills (core vs secondary)

    El scraper construye sus propias URLs de búsqueda internamente.
    """
    from src.pipeline.infojobs_scraper import InfoJobsScraper
    from datetime import timezone

    # Leer search_config desde DB si no se pasa explícitamente
    if not search_config:
        search_config = ensure_search_config()
    if not search_config:
        log.error("No hay search_config en DB y no se proporcionó uno")
        return 0

    keywords = _extract_keywords_from_config(search_config)
    if not keywords:
        log.warning("No hay keywords en role_hierarchy para buscar")
        return 0

    # Generar run_id una sola vez al inicio
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    conn = get_connection()
    scraper = InfoJobsScraper()

    total_raw = 0
    try:
        for keyword in keywords:
            stubs = scraper.search(query=keyword, page_limit=5, max_items=max_items)
            if not stubs:
                log.info("  Sin ofertas para '%s'", keyword)
                continue

            log.info("Procesando %d ofertas para '%s'...", len(stubs), keyword)
            for stub in stubs:
                detail = scraper.detail(stub.url)
                if not detail:
                    log.warning("  Falló detalle para %s, saltando", stub.offer_id)
                    continue
                # Fase 1: raw inmutable
                _persist_scraper_raw(run_id, detail, conn)
                total_raw += 1

        # Fase 2: upsert desde raw
        new_count = _upsert_from_scraper_raw(run_id, conn)

        # Fase 3: enriquecer con LLM
        enriched = enrich_pending(conn)
        log.info("Ofertas enriquecidas con LLM: %d", enriched)
    except Exception as e:
        log.error("Error en scraper fetch: %s", e)
    finally:
        scraper.close()
        conn.close()

    log.info(
        "Scraper fetch completado: %d raws, %d nuevas ofertas",
        total_raw,
        new_count,
    )
    return new_count


if __name__ == "__main__":
    import argparse

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Fetch offers from InfoJobs vía scraper propio"
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=30,
        help="Máximo de ofertas a obtener por keyword (default: 30). 0 = sin límite.",
    )
    parser.add_argument(
        "--since-date",
        choices=["_24_HOURS", "_7_DAYS", "_15_DAYS", "ANY"],
        default=None,
        help="Sin efecto en scraper propio (reservado para compatibilidad).",
    )
    parser.add_argument(
        "--enrich-only",
        action="store_true",
        help="Solo enriquecer ofertas pendientes con LLM, sin fetch",
    )
    args = parser.parse_args()

    if args.enrich_only:
        conn = get_connection()
        enriched = enrich_pending(conn)
        conn.close()
        print(f"Ofertas enriquecidas: {enriched}")
        sys.exit(0)

    inserted = run_fetch_scraper(
        search_config=None,
        since_date=args.since_date,
        max_items=args.max_items,
    )
    print(f"Ofertas insertadas: {inserted}")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT source_id, title, city, company_name FROM offers LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()
