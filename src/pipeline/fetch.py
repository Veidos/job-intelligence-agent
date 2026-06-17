"""
Pipeline: fetch de ofertas desde InfoJobs vía scraper propio (curl_cffi + BeautifulSoup).
Extrae campos estructurados (requisitos, salario, modalidad) del HTML directo.
3 fases: scraper_raw_responses (append-only) → upsert en offers → enrich con LLM.
"""

import dataclasses
import json
import logging
import re
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from src.db.init_db import get_connection
from src.utils.ollama_client import MODEL_TECHNICAL, ollama_call

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

    evaluate.py usa L binario (no level_required),
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
            result["skills_required"] = parse_skills_required(result.get("skills_required"))
            return result
        return {}
    except Exception as e:
        log.warning("gemma4:e4b falló extrayendo campos: %s", e)
        return {}


def _merge_scraper_skills_into_llm(
    detail_skills: list[str],
    llm_skills: dict,
) -> dict:
    """Post-merge: las skills del <dl> del scraper son siempre core.

    El LLM puede añadir secondary desde la descripción, pero no puede
    mover skills explícitas del scraper a secondary.

    Reglas:
    1. Skill del scraper en LLM secondary → mover a core
    2. Skill del scraper ausente en LLM → añadir a core
    3. Secondary del LLM sin coincidencia en scraper → conservar
    """
    def _norm(name: str) -> str:
        return re.sub(r"[\s\-_./]", "", name.strip().lower())

    scraper_normalized = {_norm(s): s.strip() for s in (detail_skills or []) if s}

    llm_core = list(llm_skills.get("core") or [])
    llm_secondary = list(llm_skills.get("secondary") or [])
    llm_core_norm = {_norm(s.get("name", "")) for s in llm_core if s}

    # Regla 1: mover de secondary a core si coincide con scraper
    kept_secondary = []
    for s in llm_secondary:
        if s:
            norm_name = _norm(s.get("name", ""))
            if norm_name in scraper_normalized:
                corrected = dict(s)
                corrected["name"] = scraper_normalized[norm_name]
                llm_core.append(corrected)
                llm_core_norm.add(norm_name)
            else:
                kept_secondary.append(s)

    # Regla 2: añadir skills del scraper no presentes en ninguna lista LLM
    llm_all_norm = llm_core_norm | {_norm(s.get("name", "")) for s in kept_secondary if s}
    for norm_name, original_name in scraper_normalized.items():
        if norm_name not in llm_all_norm:
            llm_core.append({"name": original_name, "level_required": None})

    return {"core": llm_core, "secondary": kept_secondary}


def _upsert_offer_from_scraper(detail: Any, conn) -> bool:
    """Persiste RawOfferDetail directamente en offers.

    Skills del scraper (del <dl> de Requisitos) van directamente a core.
    enriched_at se setea en el mismo upsert — no hay Fase 3 separada.

    Returns:
        True si fue inserción nueva, False si fue actualización.
    """
    source_id = detail.offer_id
    if not source_id:
        log.warning("source_id vacío en RawOfferDetail, saltando")
        return False

    # Skills del scraper (del <dl> de Requisitos) como base
    base_skills = {"core": [{"name": s} for s in (detail.skills or [])], "secondary": []}

    # Enriquecer con LLM + post-merge: skills del <dl> son siempre core
    try:
        llm_item = {"title": detail.title or "", "description": detail.description_text or ""}
        llm_result = extract_fields_with_llm(llm_item)
        llm_skills = llm_result.get("skills_required")
        if llm_skills and isinstance(llm_skills, dict):
            merged = _merge_scraper_skills_into_llm(detail.skills, llm_skills)
            skills_required = json.dumps(merged)
        else:
            skills_required = json.dumps(base_skills)
    except Exception:
        log.warning("LLM enrichment failed for %s, usando skills base", detail.title)
        skills_required = json.dumps(base_skills)
    raw_data = json.dumps(dataclasses.asdict(detail), ensure_ascii=False)
    now = datetime.now().isoformat()

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
                skills_required, fetched_at, is_active, raw_data, enriched_at,
                employer_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                now,
                detail.employer_id,
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
            enriched_at=COALESCE(enriched_at, ?),
            employer_id=COALESCE(employer_id, ?),
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
            now,
            detail.employer_id,
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

    Procesa TODAS las filas no procesadas, independientemente de run_id,
    para que ejecuciones abortadas no dejen filas huérfanas.

    Returns:
        Número de ofertas nuevas insertadas.
    """
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT id, offer_id, payload
        FROM scraper_raw_responses
        WHERE processed = 0
        """,
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


def run_fetch_scraper(
    search_config: dict | None = None,
    since_date: str | None = None,
    max_items: int = 30,
    dry_run: bool = False,
) -> int:
    """Fetch usando scraper propio (curl_cffi + BeautifulSoup).

    Fases:
      1. persist_scraper_raw — guarda RawOfferDetail en tabla append-only
      2. upsert_from_scraper_raw — escribe en offers desde raw (skills a core)

    Si dry_run=True, no persiste nada en DB. Útil para pruebas sin efectos laterales.

    El scraper construye sus propias URLs de búsqueda internamente.
    """
    from datetime import timezone

    from src.pipeline.infojobs_scraper import InfoJobsScraper

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
    conn = get_connection() if not dry_run else None
    scraper = InfoJobsScraper()

    total_raw = 0
    new_count = 0
    try:
        for keyword in keywords:
            stubs = scraper.search(
                query=keyword, page_limit=5, max_items=max_items, since_date=since_date
            )
            if not stubs:
                log.info("  Sin ofertas para '%s'", keyword)
                continue

            log.info("Procesando %d ofertas para '%s'...", len(stubs), keyword)
            for stub in stubs:
                detail = scraper.detail(stub.url)
                if not detail:
                    log.warning("  Falló detalle para %s, saltando", stub.offer_id)
                    continue
                if not dry_run:
                    _persist_scraper_raw(run_id, detail, conn)
                total_raw += 1

        if not dry_run:
            new_count = _upsert_from_scraper_raw(run_id, conn)
    except Exception as e:
        log.error("Error en scraper fetch: %s", e)
    finally:
        scraper.close()
        if not dry_run:
            conn.close()

    log.info(
        "Scraper fetch completado: %d raws, %d nuevas ofertas%s",
        total_raw,
        new_count,
        " (DRY RUN)" if dry_run else "",
    )
    return new_count


if __name__ == "__main__":
    import argparse

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Fetch offers from InfoJobs vía scraper propio")
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
        help="Filtro temporal: _24_HOURS, _7_DAYS, _15_DAYS, ANY. None = sin filtro.",
    )
    args = parser.parse_args()

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
