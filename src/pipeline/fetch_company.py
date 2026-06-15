"""Enriquecimiento de datos de empresas via LLM.

Agrupa ofertas por employer_id, infiere sector, tamaño y descripción
de la empresa usando qwen2.5:7b, y persiste en la tabla companies.

Stale rule: solo enriquece empresas cuyo sector IS NULL
(empresa nueva o nunca enriquecida).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection  # noqa: E402
from src.utils.ollama_client import MODEL_COMPANY, ollama_call  # noqa: E402

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"

COMPANY_PROMPT_TEMPLATE = """Eres un analizador de empresas. A partir de las ofertas de empleo de una empresa, infieres su sector, tamaño y señales relevantes.

Datos agregados de la empresa "{company_name}":
- Ofertas publicadas: {offer_count}
- Títulos más representativos:
{titles_bullets}
{extra_fields}
Responde UNICAMENTE con JSON valido. Sin markdown, sin explicaciones, sin texto adicional.
{{
  "sector": "string (solo un valor, ej: 'Tecnologia', 'Medio ambiente', 'Consultoria', 'Marketing', 'Industrial', 'Salud', 'Educacion', 'Financiero', 'Automocion', 'Logistica', 'Construccion', 'Comercial')",
  "size_range": "string (solo UN valor: startup | pequeña | mediana | grande | gran_empresa | multinacional)",
  "description": "string (1-2 frases descriptivas de la empresa inferidas de sus ofertas)",
  "green_flags": ["string (aspectos positivos visibles en sus ofertas, ej: contrato indefinido, formacion, plan de carrera, teletrabajo)"],
  "red_flags": ["string (posibles senales de alerta en sus ofertas, ej: salario no especificado, alta rotacion, requisitos vagos)"],
  "confidence": "alta | media | baja"
}}"""


def get_companies_to_enrich(conn) -> list[dict[str, Any]]:
    """Obtiene employer_ids únicos que necesitan enriquecimiento.

    Solo empresas cuyo sector es NULL (nuevas o nunca enriquecidas).
    """
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT DISTINCT o.employer_id, o.company_name
        FROM offers o
        LEFT JOIN companies c ON c.infojobs_company_id = o.employer_id
        WHERE o.employer_id IS NOT NULL
          AND (c.id IS NULL OR c.sector IS NULL)
        ORDER BY o.employer_id
        """,
    ).fetchall()
    return [{"employer_id": r[0], "company_name": r[1] or "Empresa Desconocida"} for r in rows]


def get_aggregated_offers(conn, employer_id: str) -> dict[str, Any]:
    """Agrupa todas las ofertas de un employer_id para el prompt."""
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT title, description_clean, work_mode, contract_type,
               salary_min, salary_max, city
        FROM offers
        WHERE employer_id = ?
        ORDER BY fetched_at DESC
        """,
        (employer_id,),
    ).fetchall()

    titles = []
    descriptions = []
    work_modes: set[str] = set()
    contract_types: set[str] = set()
    salary_mins: list[float] = []
    salary_maxs: list[float] = []
    cities: set[str] = set()

    for r in rows:
        title, desc, wm, ct, smin, smax, city = r
        titles.append(title or "")
        if desc:
            descriptions.append(desc[:300])
        if wm:
            work_modes.add(wm)
        if ct:
            contract_types.add(ct)
        if smin is not None:
            salary_mins.append(smin)
        if smax is not None:
            salary_maxs.append(smax)
        if city:
            cities.add(city)

    return {
        "titles": titles,
        "descriptions": descriptions,
        "work_modes": sorted(work_modes),
        "contract_types": sorted(contract_types),
        "salary_min": min(salary_mins) if salary_mins else None,
        "salary_max": max(salary_maxs) if salary_maxs else None,
        "cities": sorted(cities),
    }


def build_company_prompt(company_name: str, agg: dict[str, Any]) -> str:
    """Construye el prompt para qwen2.5:7b con datos agregados."""
    titles_bullets = "\n".join(f"  * {t}" for t in agg["titles"][:10])

    extras = []
    if agg["work_modes"]:
        extras.append(f"- Modalidades: {', '.join(agg['work_modes'])}")
    if agg["contract_types"]:
        extras.append(f"- Tipos de contrato: {', '.join(agg['contract_types'])}")
    if agg["salary_min"] is not None or agg["salary_max"] is not None:
        smin = agg["salary_min"] or ""
        smax = agg["salary_max"] or ""
        extras.append(f"- Rango salarial: {smin} - {smax} EUR")
    if agg["cities"]:
        extras.append(f"- Ciudades: {', '.join(agg['cities'][:5])}")

    descriptions_snippet = ""
    if agg["descriptions"]:
        combined = " ".join(agg["descriptions"][:3])
        descriptions_snippet = f"\n- Descripciones (resumidas): {combined[:500]}"

    extra_str = "\n".join(extras) + descriptions_snippet

    return COMPANY_PROMPT_TEMPLATE.format(
        company_name=company_name,
        offer_count=len(agg["titles"]),
        titles_bullets=titles_bullets,
        extra_fields=extra_str,
    )


def enrich_company(conn, employer_id: str, company_name: str) -> dict[str, Any]:
    """Ejecuta el LLM para una empresa y persiste el resultado."""
    log.info("[Enrich] Procesando empresa: %s (%s)", company_name, employer_id)

    agg = get_aggregated_offers(conn, employer_id)
    if not agg["titles"]:
        log.warning("[Enrich] Sin ofertas para %s, saltando", employer_id)
        return {"status": "skipped", "reason": "no_offers"}

    prompt = build_company_prompt(company_name, agg)

    try:
        result = ollama_call(
            model=MODEL_COMPANY,
            prompt=prompt,
            expect_json=True,
            temperature=0.0,
            think=False,
            num_ctx=4096,
        )
    except Exception as e:
        log.warning("[Enrich] LLM fallo para %s: %s", employer_id, e)
        return {"status": "error", "reason": str(e)}

    sector = result.get("sector")
    if not sector:
        log.warning("[Enrich] Sector nulo para %s, saltando", employer_id)
        return {"status": "skipped", "reason": "sector_null"}

    now = datetime.now().isoformat()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO companies (
            infojobs_company_id, name, sector, size_range,
            llm_description, green_flags, red_flags, llm_confidence,
            enriched_by_llm_at, llm_model, last_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(infojobs_company_id) DO UPDATE SET
            name = excluded.name,
            sector = excluded.sector,
            size_range = excluded.size_range,
            llm_description = excluded.llm_description,
            green_flags = excluded.green_flags,
            red_flags = excluded.red_flags,
            llm_confidence = excluded.llm_confidence,
            enriched_by_llm_at = excluded.enriched_by_llm_at,
            llm_model = excluded.llm_model,
            last_updated_at = excluded.last_updated_at
        """,
        (
            employer_id,
            company_name,
            sector,
            result.get("size_range"),
            result.get("description"),
            json.dumps(result.get("green_flags", []), ensure_ascii=False),
            json.dumps(result.get("red_flags", []), ensure_ascii=False),
            result.get("confidence", "media"),
            now,
            MODEL_COMPANY,
            now,
        ),
    )
    conn.commit()

    log.info(
        "[Enrich] %s -> sector=%s, tamano=%s, confianza=%s",
        employer_id,
        sector,
        result.get("size_range"),
        result.get("confidence"),
    )

    return {"status": "enriched", "sector": sector}


def link_offers_to_companies(conn) -> int:
    """Asocia ofertas con companies basándose en employer_id."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE OR IGNORE offers
        SET company_id = (
            SELECT c.id FROM companies c
            WHERE c.infojobs_company_id = offers.employer_id
        )
        WHERE employer_id IS NOT NULL
          AND (company_id IS NULL OR company_id = 0)
        """,
    )
    conn.commit()
    return cur.rowcount


def run(limit: int = 50) -> dict[str, Any]:
    """Función principal: enriquece companies desde ofertas via LLM."""
    conn = get_connection()

    companies_to_enrich = get_companies_to_enrich(conn)
    total_pending = len(companies_to_enrich)
    log.info("[Enrich] Empresas pendientes de enriquecimiento: %d", total_pending)

    if total_pending == 0:
        linked = link_offers_to_companies(conn)
        conn.close()
        return {"enriched": 0, "linked": linked, "errors": 0, "pending": 0}

    batch = companies_to_enrich[: limit if limit > 0 else None]
    enriched_count = 0
    error_count = 0
    skipped_count = 0

    for i, data in enumerate(batch, 1):
        try:
            result = enrich_company(conn, data["employer_id"], data["company_name"])
            if result["status"] == "enriched":
                enriched_count += 1
            elif result["status"] == "error":
                error_count += 1
            else:
                skipped_count += 1
            log.info(
                "[Enrich] [%d/%d] %s — %s",
                i,
                len(batch),
                data["employer_id"],
                result["status"],
            )
        except Exception as e:
            error_count += 1
            log.warning("[Enrich] Error procesando %s: %s", data["employer_id"], e)

    linked_count = link_offers_to_companies(conn)

    remaining = len(get_companies_to_enrich(conn))

    conn.close()

    log.info(
        "[Enrich] Completado: %d enriquecidas, %d enlazadas, "
        "%d saltadas, %d errores, %d pendientes",
        enriched_count,
        linked_count,
        skipped_count,
        error_count,
        remaining,
    )

    return {
        "enriched": enriched_count,
        "linked": linked_count,
        "skipped": skipped_count,
        "errors": error_count,
        "pending": remaining,
    }


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Enriquecer datos de empresas via LLM")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Limite de empresas a procesar",
    )
    args = parser.parse_args()

    result = run(args.limit)
    print(f"Resultado: {result}")
