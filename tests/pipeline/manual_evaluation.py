"""
Evaluación manual del pipeline — Test sin fetch.
Replica el flujo classify→evaluate completo sobre ofertas existentes en DB.

Uso:
    PYTHONPATH=. python tests/pipeline/manual_evaluation.py

No hace fetch nuevo ni llamadas a Apify.
Genera un report en la consola y opcionalmente en data/manual_eval_report.md
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection  # noqa: E402
from src.pipeline.role_classifier import classify_offer, get_role_catalog  # noqa: E402
from src.pipeline.evaluate import (  # noqa: E402
    check_impossible_requirements,
    evaluate_technical,
    evaluate_hr,
    load_perfil,
    load_skills_from_perfil,
    load_gap_from_perfil,
    _clamp,
    get_rating,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "jobs.db"
REPORT_DIR = PROJECT_ROOT / "data"
REPORT_DIR.mkdir(exist_ok=True)
REPORT_PATH = REPORT_DIR / "manual_eval_report.md"

SCORE_BREAKDOWN = {
    "skills_hard_match": (0, 30, "Match de skills pedidas"),
    "experience_match": (0, 20, "Match de experiencia"),
    "education_match": (0, 10, "Match educativo"),
    "location_match": (0, 5, "Match de modalidad/ubicación"),
    "trajectory_coherence": (0, 15, "Coherencia de trayectoria"),
    "recency_relevance": (0, 15, "Relevancia de experiencia reciente"),
    "market_competitiveness": (0, 5, "Competitividad en el mercado"),
    "penalty": (0, 25, "Penalización por gap/incoherencia"),
}


def get_offers_for_test(conn, limit: int = 5) -> list[dict]:
    """Selecciona ofertas variadas para test: las top evaluadas + algunas sin evaluar."""
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT o.id, o.source_id, o.title, o.company_name, o.city, o.province,
               o.work_mode, o.salary_min, o.salary_max, o.salary_period,
               o.contract_type, o.description_raw, o.description_clean,
               o.skills_required, o.experience_min, o.education_level, o.url,
               o.published_at, o.relevance_flag, o.role_normalized,
               e.match_score
        FROM offers o
        LEFT JOIN offer_evaluations e ON e.offer_id = o.id
        WHERE o.description_clean IS NOT NULL
          AND o.title IS NOT NULL
        ORDER BY CASE WHEN e.match_score IS NULL THEN 1 ELSE 0 END,
                 e.match_score DESC, o.fetched_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    cols = [d[0] for d in cur.description]
    offers = []
    for row in rows:
        offers.append(dict(zip(cols, row)))

    if len(offers) < limit:
        rows2 = cur.execute(
            """
            SELECT o.id, o.source_id, o.title, o.company_name, o.city, o.province,
                   o.work_mode, o.salary_min, o.salary_max, o.salary_period,
                   o.contract_type, o.description_raw, o.description_clean,
                   o.skills_required, o.experience_min, o.education_level, o.url,
o.published_at, o.relevance_flag, o.role_normalized,
                   e.match_score
            FROM offers o
            LEFT JOIN offer_evaluations e ON e.offer_id = o.id
            WHERE o.description_clean IS NOT NULL
              AND o.id NOT IN ({})
            ORDER BY CASE WHEN e.match_score IS NULL THEN 1 ELSE 0 END,
                     e.match_score DESC, o.fetched_at DESC
            LIMIT ?
            """.format(",".join("?" for _ in offers) if offers else "0"),
            ([o["id"] for o in offers] if offers else []) + [limit - len(offers)],
        ).fetchall()
        cols2 = [d[0] for d in cur.description]
        for row in rows2:
            offers.append(dict(zip(cols2, row)))

    return offers


def format_score_bar(score: int, max_score: int = 100) -> str:
    filled = int(score / max_score * 20)
    return "[" + "█" * filled + "░" * (20 - filled) + f"] {score}/{max_score}"


def format_field_score(name: str, value: int, lo: int, hi: int) -> str:
    pct = (value - lo) / (hi - lo) if hi > lo else 0
    bar = "█" * int(pct * 10) + "░" * (10 - int(pct * 10))
    return f"  {name:28s} {bar} {value}/{hi}"


def run_evaluation_report(limit: int = 5) -> dict[str, Any]:
    conn = get_connection()
    perfil = load_perfil()
    catalog = get_role_catalog(conn)
    employment_gap = load_gap_from_perfil(perfil)
    candidate_skills = load_skills_from_perfil(perfil)

    offers = get_offers_for_test(conn, limit)
    catalog = get_role_catalog(conn)
    conn.close()

    results = []
    report_lines = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_lines.append(
        dedent(f"""\
        # Evaluación Manual del Pipeline
        **Fecha:** {ts}
        **Ofertas evaluadas:** {len(offers)}

        ---

        ## Configuración del Test

        - **Perfil:** {perfil.split(chr(10))[2] if perfil else "N/A"}
        - **Employment Gap:** {employment_gap} años
        - **Skills del candidato:** {len(candidate_skills)}
        - **Modelo técnico:** gemma4:e4b
        - **Modelo HR:** gemma4:e4b

        ---

        ## Prompts Activos (versión resumida)

        ### Prompt Técnico (bloque A — 60 pts max)
        - Evalúa skills con NIVEL (básico/intermedio/avanzado)
        - Si oferta no pide experiencia → experience_match 18-20
        - Nivel requerido inferido desde título (senior/junior/nada)

        ### Prompt HR (bloque B — 40 pts max)
        - trajectory_coherence (0-15)
        - recency_relevance (0-15)
        - market_competitiveness (0-5)
        - penalty (0-25): SOLO gap laboral, incoherencia, requisitos no cumplidos
        - NO incluye salario mínimo viable en penalty

        ---

        ## Resultados

        """)
    )

    for i, offer in enumerate(offers, 1):
        log.info(f"[{i}/{len(offers)}] Evaluando: {offer['title']}")

        result = {
            "offer_id": offer["id"],
            "title": offer["title"],
            "company_name": offer["company_name"],
        }
        lines = []

        lines.append(
            dedent(f"""\
            ### [{i}] {offer["title"]}
            **Empresa:** {offer["company_name"]}
            **Ubicación:** {offer.get("city", "N/A")}, {offer.get("province", "")}
            **Modalidad:** {offer.get("work_mode", "N/A")}
            **Salario:** {offer.get("salary_min", "N/A")} – {offer.get("salary_max", "N/A")} €/año
            **URL:** {offer.get("url", "N/A")}
            **Rol actual en DB:** {offer.get("role_normalized", "N/A")} | {offer.get("relevance_flag", "N/A")}
            **Exp. mínima requerida:** {offer.get("experience_min", "N/A")} años

            **Skills requeridas:**
            ```json
            {offer.get("skills_required", "[]")}
            ```

            **Descripción (primeros 300 chars):**
            ```
            {str(offer.get("description_clean") or offer.get("description_raw") or "")[:300]}
            ```

            ---

            #### FASE 1 — Filtro de requisitos imposibles (gemma4)
            """)
        )

        filtro = check_impossible_requirements(offer, perfil)
        es_descartable = filtro.get("descartable", False)
        razon_descarte = filtro.get("razon", "")
        if es_descartable:
            lines.append(f"> **DESCARTADO POR PRE-FILTRO:** {razon_descarte}\n")
            result["status"] = "descartado_prefiltro"
            result["razon"] = razon_descarte
            result["score"] = 0
            result["recommendation"] = "Descartado"
        else:
            lines.append("> Ningún requisito imposible detectado\n")

            lines.append("#### FASE 2 — Clasificación\n")
            class_result = classify_offer(offer, catalog, perfil)
            if class_result:
                result["role_classified"] = class_result["role_normalized"]
                result["relevance_classified"] = class_result["relevance_flag"]
                result["classification_reasoning"] = class_result["reasoning"]
                lines.append(
                    dedent(f"""\
                    - **Rol asignado:** {class_result["role_normalized"]}
                    - **Relevance flag:** {class_result["relevance_flag"]}
                    - **Razonamiento:** {class_result["reasoning"]}
                    - **Rol nuevo:** {"Sí" if class_result["is_new_role"] else "No"}

                    """)
                )
            else:
                lines.append("> Clasificación falló (gemma4 no respondió)\n\n")
                result["role_classified"] = "ERROR"
                result["relevance_classified"] = "ERROR"

            lines.append("#### FASE 3 — Evaluación Técnica (Bloque A)\n")
            t0 = time.monotonic()
            technical = evaluate_technical(offer, perfil)
            t_tech = int((time.monotonic() - t0) * 1000)
            result["technical_ms"] = t_tech

            if technical:
                result["technical"] = technical
                lines.append("| Campo | Valor | Razonamiento |\n|---|---|---|")
                lines.append(
                    f"| skills_hard_match | {technical.get('skills_hard_match', '?')}/30 | {technical.get('nivel_match_reasoning', 'N/A')[:100]}... |"
                )
                lines.append(
                    f"| experience_match | {technical.get('experience_match', '?')}/20 | {technical.get('reasoning', 'N/A')[:100]}... |"
                )
                lines.append(
                    f"| education_match | {technical.get('education_match', '?')}/10 | |"
                )
                lines.append(
                    f"| location_match | {technical.get('location_match', '?')}/5 | |"
                )

                bloque_a = (
                    _clamp(technical.get("skills_hard_match", 0), 0, 30)
                    + _clamp(technical.get("experience_match", 0), 0, 20)
                    + _clamp(technical.get("education_match", 0), 0, 10)
                    + _clamp(technical.get("location_match", 0), 0, 5)
                )
                lines.append(f"\n**Bloque A = {bloque_a}/65 pts** ({t_tech}ms)\n")
                result["bloque_a"] = bloque_a
            else:
                lines.append("> Evaluación técnica falló\n\n")
                result["technical"] = {}
                result["bloque_a"] = 0

            lines.append("#### FASE 4 — Evaluación HR (Bloque B)\n")
            t0 = time.monotonic()
            hr = evaluate_hr(offer, perfil, technical or {}, employment_gap)
            t_hr = int((time.monotonic() - t0) * 1000)
            result["hr_ms"] = t_hr

            if hr:
                result["hr"] = hr
                penalty_breakdown = hr.get("penalty_breakdown", {})
                penalty_str = (
                    ", ".join(f"{k}: {v}" for k, v in penalty_breakdown.items())
                    if isinstance(penalty_breakdown, dict)
                    else str(penalty_breakdown)
                )

                lines.append("| Campo | Valor |\n|---|---|\n")
                lines.append(
                    f"| trajectory_coherence | {hr.get('trajectory_coherence', '?')}/15 |\n"
                )
                lines.append(
                    f"| recency_relevance | {hr.get('recency_relevance', '?')}/15 |\n"
                )
                lines.append(
                    f"| market_competitiveness | {hr.get('market_competitiveness', '?')}/5 |\n"
                )
                lines.append(f"| penalty | {hr.get('penalty', '?')}/25 |\n")
                lines.append(
                    f"| environment_compatibility | {hr.get('environment_compatibility', '?')} |\n"
                )
                if penalty_breakdown:
                    lines.append(f"\n**Penalty breakdown:** {penalty_str}\n")

                bloque_b = (
                    _clamp(hr.get("trajectory_coherence", 0), 0, 15)
                    + _clamp(hr.get("recency_relevance", 0), 0, 15)
                    + _clamp(hr.get("market_competitiveness", 0), 0, 5)
                )
                penalty = _clamp(hr.get("penalty", 0), 0, 25)
                lines.append(f"\n**Bloque B = {bloque_b}/35 pts** ({t_hr}ms)\n")
                result["bloque_b"] = bloque_b
                result["penalty"] = penalty

                lines.append("##### Factors HR\n")
                if hr.get("hr_concerns"):
                    lines.append(
                        "**Concerns:**\n- "
                        + "\n- ".join(hr.get("hr_concerns", [])[:3])
                        + "\n"
                    )
                if hr.get("strengths"):
                    lines.append(
                        "**Fortalezas:**\n- "
                        + "\n- ".join(hr.get("strengths", [])[:3])
                        + "\n"
                    )
                if hr.get("red_flags"):
                    lines.append(
                        "**Red flags:**\n- "
                        + "\n- ".join(hr.get("red_flags", [])[:3])
                        + "\n"
                    )
                if hr.get("interview_prep"):
                    lines.append(
                        "**Prep entrevista:**\n- "
                        + "\n- ".join(hr.get("interview_prep", [])[:3])
                        + "\n"
                    )
            else:
                lines.append("> Evaluación HR falló\n\n")
                result["hr"] = {}
                result["bloque_b"] = 0
                result["penalty"] = 0

            lines.append("#### FASE 5 — Score Final\n")
            raw_score = (
                result.get("bloque_a", 0)
                + result.get("bloque_b", 0)
                - result.get("penalty", 0)
            )
            score = max(0, min(100, raw_score))
            recommendation = get_rating(score)

            lines.append(
                dedent(f"""\
                **Cálculo:** {result.get("bloque_a", 0)} + {result.get("bloque_b", 0)} - {result.get("penalty", 0)} = **{score}**/100
                {format_score_bar(score)}
                **Recomendación:** {recommendation}
                **apply_signal (HR):** {hr.get("apply_signal", "N/A") if hr else "N/A"}
                **Verdict HR:**
                > {hr.get("verdict", "N/A") if hr else "N/A"}

                """)
            )

            result["score"] = score
            result["recommendation"] = recommendation
            result["apply_signal"] = hr.get("apply_signal") if hr else None

        lines.append("---\n")
        report_lines.append("\n".join(lines))
        results.append(result)

    report_lines.append("## Resumen de Scores\n")
    report_lines.append(
        "| # | Título | Empresa | Score | Recom. | apply_signal | Bloque A | Bloque B | Penalty | Compat. |\n"
    )
    report_lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        hr = r.get("hr", {})
        compat = hr.get("environment_compatibility", "-") if hr else "-"
        report_lines.append(
            f"| {results.index(r) + 1} | {r.get('title', '')[:30]} | {r.get('company_name', '')[:20]} "
            f"| {r.get('score', 0)} | {r.get('recommendation', '')} "
            f"| {r.get('apply_signal', '-')} "
            f"| {r.get('bloque_a', 0)} | {r.get('bloque_b', 0)} | {r.get('penalty', 0)} "
            f"| {compat} |"
        )

    report_lines.append(
        dedent("""

        ---

        ## Evaluación

        ### ¿Los scores son coherentes con el perfil del candidato?
        *(Responde: Sí / Parcialmente / No — explica por qué)*

        ### ¿Las recommendations son realistas?
        *(¿Alguna oferta merece mejor/peor score del asignado?)*

        ### ¿El penalty es justo o excesivo?
        *(¿El gap de 3.7 años está penalizando demasiado?)*

        ### ¿Los prompts necesitan ajuste?
        *(¿Algún prompt está siendo demasiado duro o demasiado blando?)*

        ### ¿Algún oferta debería haber sido descartada por pre-filtro?
        *(¿Falta algún patrón de requisito impossível?)*

        ### Notas adicionales

        """)
    )

    report = "\n".join(report_lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log.info(f"Report generado: {REPORT_PATH}")

    print("\n" + "=" * 70)
    print("EVALUACIÓN MANUAL DEL PIPELINE")
    print("=" * 70)
    print(report)

    return {"results": results, "report": report, "report_path": str(REPORT_PATH)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=5, help="Número de ofertas a evaluar"
    )
    args = parser.parse_args()
    result = run_evaluation_report(limit=args.limit)
    print(f"\nReport guardado en: {result['report_path']}")
    print(f"Resultados: {len(result['results'])} ofertas evaluadas")
