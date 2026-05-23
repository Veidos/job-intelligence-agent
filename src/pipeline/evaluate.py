"""
Pipeline: evaluación de ofertas con gemma4:e4b (técnico y HR).
Procesa ofertas clasificadas (relevance_flag NOT NULL, is_evaluated=0).
Incluye evaluación técnica, HR y validación final (relevance + bloqueos).
PERFIL.md es la única fuente de verdad del candidato.
"""

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection  # noqa: E402
from src.utils.ollama_client import MODEL_HR, MODEL_TECHNICAL, ollama_call  # noqa: E402

log = logging.getLogger(__name__)


def _clamp(val, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(val or 0)))


def load_skills_from_perfil(perfil: str) -> list[dict]:
    """Parsea skills con nivel desde PERFIL.md.

    Formato esperado:
    ## Skills técnicas
    - **Python (básico)**: Bootcamp IE University 2023
    - **SQL (intermedio)**: Proyectos freelance
    """
    import re

    skills = []

    # Buscar sección de skills técnicas
    match = re.search(r"## Skills técnicas\s*\n((?:- .*\n?)+)", perfil, re.IGNORECASE)
    if not match:
        return skills

    skills_block = match.group(1)

    # Parsear cada línea de skill
    # Patrón: - **SkillName (nivel)**: evidencia
    skill_pattern = re.compile(r"- \*\*([^(]+)\((\w+)\)\*\*:?\s*(.+)?", re.IGNORECASE)

    for line in skills_block.strip().split("\n"):
        line = line.strip()
        if not line.startswith("-"):
            continue

        # Intentar parsear con formato estructurado
        m = skill_pattern.match(line)
        if m:
            name = m.group(1).strip()
            level = m.group(2).strip().lower()
            evidence = m.group(3).strip() if m.group(3) else ""
            skills.append({"name": name, "level": level, "evidence": evidence})
        else:
            # Fallback: solo nombre sin nivel
            clean = line.lstrip("- ").strip()
            if clean:
                skills.append(
                    {
                        "name": clean,
                        "level": "básico",
                        "evidence": "sin información de nivel",
                    }
                )

    return skills


def load_gap_from_perfil(perfil: str) -> float | None:
    """Extrae employment_gap_years desde PERFIL.md.

    Formato esperado:
    ## Gap de empleo
    - **Años:** 3.5
    """
    import re

    # Buscar sección de gap
    gap_match = re.search(r"## Gap de empleo\s*\n((?:.+\n?)+)", perfil, re.IGNORECASE)
    if not gap_match:
        return None

    gap_block = gap_match.group(1)

    # Buscar patrón: - **Años:** 3.5
    years_match = re.search(r"- \*\*Años:\*\*\s*([\d.]+)", gap_block)
    if years_match:
        try:
            return float(years_match.group(1))
        except ValueError:
            pass
    return None


RATING = {
    (75, 101): "Prioritario",
    (55, 75): "Aplicar",
    (35, 55): "Con expectativas bajas",
    (0, 35): "No aplicar",
}


def get_rating(score: int) -> str:
    for (low, high), label in RATING.items():
        if low <= score < high:
            return label
    return "No aplicar"


def load_perfil() -> str:
    perfil_path = Path(__file__).resolve().parent.parent.parent / "PERFIL.md"
    return perfil_path.read_text(encoding="utf-8")


def get_pending_offers(limit: int = 10) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT id, title, company_name, city, work_mode,
               description_clean, skills_required,
               relevance_flag, role_normalized,
               salary_min, salary_max, published_at
        FROM offers
        WHERE relevance_flag IS NOT NULL
          AND is_evaluated = 0
        ORDER BY published_at DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def evaluate_technical(offer: dict, perfil: str) -> dict:
    """Evalúa bloque técnico (60 pts) con lógica de niveles usando gemma4:e4b."""
    skills = offer.get("skills_required") or "[]"
    description = (offer.get("description_clean") or "")[:1500]

    # Cargar skills desde PERFIL.md
    candidate_skills = load_skills_from_perfil(perfil)

    # Formatear skills del candidato con nivel
    skills_info = (
        "\n".join(
            [
                f"- {s['name']}: {s['level']} ({s.get('evidence', 'sin evidencia')[:80]})"
                for s in candidate_skills
            ]
        )
        if candidate_skills
        else "Sin skills registradas en el perfil"
    )

    prompt = f"""Eres un evaluador técnico de ofertas de trabajo. Analiza el match entre el perfil y la oferta.

REGLAS CRÍTICAS (obligatorias):

1. EVALUACIÓN DE SKILLS CON NIVEL:
   - Solo evalúa las skills que la OFERTA explícitamente pide
   - Las skills del candidato que la oferta NO pide = IGNORAR (no cuentan, no restan)
   - El nivel importa: si la oferta pide "avanzado" y el candidato tiene "básico" → reducir puntuación
   - Si la oferta NO especifica nivel → cualquier nivel del candidato es válido (100%)

2. INFERIR NIVEL DESDE LA OFERTA:
   - "senior", "lead", "experto", "experienced" → nivel avanzado/experto requerido
   - "junior", "entry", "sin experiencia" → nivel básico es suficiente
   - Sin especificación → cualquier nivel es válido

3. EXPERIENCIA:
   - Si la oferta NO pide experiencia previa → experience_match = 18-20
   - Si pide experiencia y el candidato tiene gap de +3 años → evaluar si es relevante

4. LOCATION:
   - remoto=5, híbrido=3, presencial-otra-ciudad=1, presencial-sin-posibilidad-remoto=0

CANDIDATO SKILLS (con nivel):
{skills_info}

PERFIL:
{perfil[:2500]}

OFERTA:
Título: {offer["title"]}
Empresa: {offer["company_name"]}
Skills requeridas: {skills}
Descripción: {description}

NIVEL REQUERIDO DE LA OFERTA: (inferir desde el título y descripción)
- Si dice "senior/experto/lead" → nivel requerido: avanzado
- Si dice "junior/básico/sin experiencia" → nivel requerido: básico
- Si no especifica → nivel requerido: cualquiera

EVALÚA y responde SOLO este JSON:
{{
  "skills_hard_match": <int 0-30>,
  "experience_match": <int 0-20>,
  "education_match": <int 0-10>,
  "location_match": <int 0-5>,
  "nivel_match_reasoning": "<explica cómo evaluaste el nivel de cada skill>",
  "reasoning": "<frase honesta que justifique el score>"
}}"""
    result = ollama_call(
        model=MODEL_TECHNICAL,
        prompt=prompt,
        expect_json=True,
        temperature=0.1,
        think=True,
    )
    return result if isinstance(result, dict) else {}


def evaluate_hr(
    offer: dict, perfil: str, technical: dict, employment_gap: float | None = None
) -> dict:
    """gemma4 evalúa bloque HR (40 pts). Con think=True para razonamiento."""
    gap_info = f"\n- **Gap de empleo:** {employment_gap} años" if employment_gap else ""

    prompt = f"""Eres un recruiter senior con criterio real. Evalúa honestamente.
NO suavices la realidad. Evalúa como si tuvieras que defender tu decisión.

PERFIL DEL CANDIDATO (resumen):{gap_info}
{perfil[:2800]}

OFERTA:
Título: {offer["title"]} | Empresa: {offer["company_name"]}
Ubicación: {offer.get("city")} | Modalidad: {offer.get("work_mode")}
Descripción: {(offer.get("description_clean") or "")[:1500]}

EVALUACIÓN TÉCNICA PREVIA:
{json.dumps(technical, ensure_ascii=False)}

IMPORTANTE: El salario mínimo viable del candidato NO es un factor de
penalización. No lo incluyas en penalty_breakdown bajo ningún concepto.
La penalty es SOLO para: gap laboral injustificado, incoherencia grave
de trayectoria, requisitos obligatorios no cumplidos.

EVALÚA:
1. ¿El trayecto profesional tiene sentido para este puesto?
2. ¿El gap laboral es descalificante para esta oferta concreta?
3. ¿La empresa/cultura presentan factores relevantes?
   IMPORTANTE: los factores de entorno NO son filtros, son contexto
   de priorización y preparación para entrevista.
4. ¿Qué haría un recruiter real con este CV en el primer filtro?
5. Dado el contexto personal, ¿vale la pena invertir energía aquí?

6. Considerando la edad del candidato y que es un cambio de carrera:
   ¿La empresa típicamente contrata perfiles de reconversión en esta franja de edad?
   ¿Es la edad un factor descalificante, neutro o positivo para ESTE puesto concreto?
   IMPORTANTE: la edad NO es un filtro absoluto, es contexto de probabilidad real.

Devuelve SOLO este JSON:
{{
  "trajectory_coherence": <int 0-15>,
  "recency_relevance": <int 0-15>,
  "market_competitiveness": <int 0-5>,
  "penalty": <int 0-25>,
  "penalty_breakdown": {{"motivo": <puntos>}},
  "environment_compatibility": "<alta|media|baja>",
  "hr_concerns": ["<string>"],
  "strengths": ["<string>"],
  "red_flags": ["<string>"],
  "interview_prep": ["<consejo concreto>"],
  "apply_signal": "<yes|no|maybe>",
  "verdict": "<párrafo libre honesto>"
}}"""
    result = ollama_call(
        model=MODEL_HR,
        prompt=prompt,
        expect_json=True,
        temperature=0.0,
        think=True,
    )
    return result if isinstance(result, dict) else {}


def evaluate_final(
    offer: dict,
    perfil: str,
    technical: dict,
    hr: dict,
    raw_score: int,
) -> dict:
    """Tercer prompt: valida el relevance_flag del classifier y detecta
    bloqueos reales de aplicación. No altera el score numérico.

    Retorna:
    {
      "relevance_validation": "confirmed|corrected",
      "relevance_corrected": "core|adjacent|stretch|temporal|null",
      "relevance_reasoning": str,
      "apply_block": null | "requisito_imposible|practicas|otro",
      "apply_block_reason": str | null,
      "apply_recommendation": "yes|maybe|no",
      "verdict": str
    }
    """
    prompt = f"""Eres un evaluador senior de ofertas de trabajo. Tienes ya la evaluación técnica y HR de esta oferta.

PERFIL DEL CANDIDATO:
{perfil[:2500]}

OFERTA:
Título: {offer["title"]}
Empresa: {offer.get("company_name", "")}
Ciudad: {offer.get("city", "")} | Modalidad: {offer.get("work_mode", "")}
Descripción: {(offer.get("description_clean") or "")[:2000]}

CLASIFICACIÓN PREVIA (role_classifier):
relevance_flag: {offer.get("relevance_flag")}
role_normalized: {offer.get("role_normalized")}

EVALUACIÓN TÉCNICA:
{json.dumps(technical, ensure_ascii=False)}

EVALUACIÓN HR:
{json.dumps(hr, ensure_ascii=False)}

SCORE CALCULADO: {raw_score}/100

---

TU TAREA TIENE DOS PARTES INDEPENDIENTES:

PARTE 1 — VALIDAR EL RELEVANCE_FLAG:
El classifier asignó "{offer.get("relevance_flag")}" a esta oferta basándose
en el título y skills. Tú tienes ahora la descripción completa y las evaluaciones.
¿Confirmas esa clasificación o la corriges? Razona brevemente.
- "confirmed": la clasificación es correcta
- "corrected": propón una corrección (core/adjacent/stretch/temporal) y explica por qué

PARTE 2 — DETECTAR BLOQUEOS DE APLICACIÓN:
Evalúa si la oferta tiene algún requisito que haga inviable la candidatura
independientemente del score. Razona desde la descripción completa, no desde reglas.
Ejemplos de bloqueo real: convenio de prácticas universitarias, certificado de
discapacidad obligatorio, requisito legal de nacionalidad.
NO son bloqueos: falta de experiencia, skills no dominadas, gap laboral.

Si hay bloqueo: apply_block = "requisito_imposible" | "practicas" | "otro"
Si no hay bloqueo: apply_block = null

Responde SOLO este JSON:
{{
  "relevance_validation": "<confirmed|corrected>",
  "relevance_corrected": <"core"|"adjacent"|"stretch"|"temporal"|null>,
  "relevance_reasoning": "<una frase>",
  "apply_block": <"requisito_imposible"|"practicas"|"otro"|null>,
  "apply_block_reason": <"<texto>"|null>,
  "apply_recommendation": "<yes|maybe|no>",
  "verdict": "<síntesis ejecutiva honesta en 2-3 frases>"
}}"""

    result = ollama_call(
        model=MODEL_HR,
        prompt=prompt,
        expect_json=True,
        temperature=0.0,
        think=True,
    )
    return result if isinstance(result, dict) else {}


def save_evaluation(
    offer_id: int,
    technical: dict,
    hr: dict,
    final: dict,
    match_score: int,
    recommendation: str,
    processing_ms: int,
) -> None:
    conn = get_connection()
    cur = conn.cursor()
    verdict_final = hr.get("verdict", "") if hr else ""

    technical_data = technical if technical else {}
    hr_data = hr if hr else {}
    final_data = final if final else {}

    cur.execute(
        """
        INSERT INTO offer_evaluations (
            offer_id, cv_version_id,
            skills_hard_match, experience_match,
            education_match, location_match,
            trajectory_coherence, recency_relevance,
            market_competitiveness, penalty, penalty_breakdown,
            match_score, recommendation,
            environment_compatibility, hr_concerns,
            strengths, red_flags, gemma_verdict,
            apply_recommendation, processing_ms,
            model_technical, model_hr,
            company_fit_score, company_green_flags, company_red_flags,
            interview_prep,
            relevance_validation, relevance_corrected, relevance_reasoning,
            apply_block, apply_block_reason, llm_apply_signal
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            offer_id,
            None,
            technical_data.get("skills_hard_match", 0),
            technical_data.get("experience_match", 0),
            technical_data.get("education_match", 0),
            technical_data.get("location_match", 0),
            hr_data.get("trajectory_coherence", 0),
            hr_data.get("recency_relevance", 0),
            hr_data.get("market_competitiveness", 0),
            hr_data.get("penalty", 0),
            json.dumps(hr_data.get("penalty_breakdown", {}), ensure_ascii=False),
            match_score,
            recommendation,
            hr_data.get("environment_compatibility"),
            json.dumps(hr_data.get("hr_concerns", []), ensure_ascii=False),
            json.dumps(hr_data.get("strengths", []), ensure_ascii=False),
            json.dumps(hr_data.get("red_flags", []), ensure_ascii=False),
            verdict_final,
            recommendation,
            processing_ms,
            MODEL_TECHNICAL,
            MODEL_HR,
            hr_data.get("company_fit_score"),
            json.dumps(hr_data.get("company_green_flags", []), ensure_ascii=False),
            json.dumps(hr_data.get("company_red_flags", []), ensure_ascii=False),
            json.dumps(hr_data.get("interview_prep", []), ensure_ascii=False),
            final_data.get("relevance_validation"),
            final_data.get("relevance_corrected"),
            final_data.get("relevance_reasoning"),
            final_data.get("apply_block"),
            final_data.get("apply_block_reason"),
            final_data.get("apply_recommendation"),
        ),
    )
    cur.execute("UPDATE offers SET is_evaluated=1 WHERE id=?", (offer_id,))
    conn.commit()
    conn.close()


def run_evaluate(limit: int = 10) -> dict:
    perfil = load_perfil()
    offers = get_pending_offers(limit)
    candidate_skills = load_skills_from_perfil(perfil)
    employment_gap = load_gap_from_perfil(perfil)
    log.info("Ofertas pendientes de evaluar: %d", len(offers))
    log.info("Skills del candidato cargadas: %d", len(candidate_skills))
    if employment_gap:
        log.info("Employment gap: %.1f años", employment_gap)

    stats = {"evaluated": 0, "errors": 0, "scores": []}

    for offer in offers:
        t0 = time.monotonic()
        try:
            log.info("Evaluando: %s", offer["title"])

            technical = evaluate_technical(offer, perfil)
            if not technical:
                log.warning(f"gemma4 no devolvió resultado para: {offer['title']}")
                stats["errors"] += 1
                continue

            hr = evaluate_hr(offer, perfil, technical, employment_gap)
            if not hr:
                log.warning("gemma4 no devolvió resultado para: %s", offer["title"])
                stats["errors"] += 1
                continue

            bloque_a = (
                _clamp(technical.get("skills_hard_match", 0), 0, 30)
                + _clamp(technical.get("experience_match", 0), 0, 20)
                + _clamp(technical.get("education_match", 0), 0, 10)
                + _clamp(technical.get("location_match", 0), 0, 5)
            )
            bloque_b = (
                _clamp(hr.get("trajectory_coherence", 0), 0, 15)
                + _clamp(hr.get("recency_relevance", 0), 0, 15)
                + _clamp(hr.get("market_competitiveness", 0), 0, 5)
            )
            penalty = _clamp(hr.get("penalty", 0), 0, 25)
            match_score = max(0, min(100, bloque_a + bloque_b - penalty))
            recommendation = get_rating(match_score)

            final = evaluate_final(offer, perfil, technical, hr, match_score)
            if not final:
                log.warning("Sin resultado final: %s", offer["title"])
                stats["errors"] += 1
                continue

            ms = int((time.monotonic() - t0) * 1000)
            save_evaluation(
                offer["id"],
                technical,
                hr,
                final,
                match_score,
                recommendation,
                ms,
            )

            block = final.get("apply_block")
            log.info(
                "✓ %s → %d/100 (%s)%s",
                offer["title"],
                match_score,
                recommendation,
                f" [BLOQUEADO: {block}]" if block else "",
            )
            stats["evaluated"] += 1
            stats["scores"].append(match_score)

        except Exception as e:
            log.error("Error evaluando %s: %s", offer["title"], e)
            stats["errors"] += 1

    if stats["scores"]:
        stats["avg_score"] = sum(stats["scores"]) // len(stats["scores"])

    return stats


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    stats = run_evaluate(limit=3)
    log.info("Completado: %s", stats)
