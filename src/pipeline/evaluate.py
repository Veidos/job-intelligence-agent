"""
Pipeline: evaluación de ofertas con gemma4:e4b (técnico y HR).
Procesa ofertas clasificadas (relevance_flag NOT NULL, is_evaluated=0).
Incluye pre-filtro de requisitos impossibles y evaluación de skills con nivel.
PERFIL.md es la única fuente de verdad del candidato.
"""

import json
import logging
import re
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


# Patrones de requisitos impossibles (requieren condición que NO se puede cambiar)
IMPOSSIBLE_PATTERNS = [
    (r"estudiante.*\búltimo año\b", "No es estudiante de último año"),
    (
        r"firma.*convenio.*prácticas",
        "No puede firmar convenio de prácticas (no es estudiante)",
    ),
    (r"ser.*estudiante", "No es estudiante activo"),
    (r"certificado.*discapacidad", "No posee certificado de discapacidad"),
    (r"minusvalía", "No tiene minusvalía"),
    (r"discapacitado", "No tiene discapacidad"),
    (r"ser.*menor de \d+", "No cumple requisito de edad"),
    (r"tener.*\d+ años", "No cumple requisito de edad"),
]

# Patrones de requisitos que requieren verificar el perfil
PROFILE_CHECK_PATTERNS = [
    (r"carné de conducir", "carnet"),
    (r"coche propio", "coche"),
    (r"vehículo propio", "coche"),
]


def pre_filtro_requisitos_imposibles(offer: dict, perfil: str) -> tuple[bool, str]:
    """
    Analiza la oferta antes de llamar a los modelos para detectar requisitos impossibles.

    Un requisito es IMPOSIBLE si requiere volver a un estado anterior:
    - Ser estudiante (no lo es)
    - Tener certificado de discapacidad (no lo tiene)
    - Ser menor de X años (no lo es)

    Retorna: (es_descartable, razon)
    - Si es_descartable=True: NO se evalúa con modelos, score=0
    """
    description = (offer.get("description_clean") or "").lower()
    title = (offer.get("title") or "").lower()
    full_text = f"{title} {description}"

    # Buscar patrones impossibles
    for pattern, razon in IMPOSSIBLE_PATTERNS:
        if re.search(pattern, full_text, re.IGNORECASE):
            log.info(f"Descarte por requisito imposible: {razon}")
            return True, razon

    # Verificar requisitos del perfil
    perfil_lower = perfil.lower()
    for pattern, kw in PROFILE_CHECK_PATTERNS:
        if re.search(pattern, full_text, re.IGNORECASE):
            if kw == "carnet" and "carné de conducir" in full_text:
                if "carné" not in perfil_lower and "carnet" not in perfil_lower:
                    return True, "No tiene carné de conducir"
            elif kw == "coche" and (
                "coche propio" in full_text or "vehículo propio" in full_text
            ):
                if "coche" not in perfil_lower and "vehículo" not in perfil_lower:
                    return True, "No tiene vehículo propio"

    return False, ""


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


def save_evaluation(
    offer_id: int,
    technical: dict,
    hr: dict,
    match_score: int,
    recommendation: str,
    processing_ms: int,
    coherence_note: str | None = None,
    descarte_tipo: str = "ninguno",
    descarte_razon: str | None = None,
) -> None:
    conn = get_connection()
    cur = conn.cursor()
    verdict_final = hr.get("verdict", "") if hr else ""
    if coherence_note:
        verdict_final += f"\n\n[COHERENCIA]: {coherence_note}"

    technical_data = technical if technical else {}
    hr_data = hr if hr else {}

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
            descarte_tipo, descarte_razon
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            descarte_tipo,
            descarte_razon,
        ),
    )
    cur.execute("UPDATE offers SET is_evaluated=1 WHERE id=?", (offer_id,))
    conn.commit()
    conn.close()


def coherence_check(
    offer: dict,
    perfil: str,
    technical: dict,
    hr: dict,
    raw_score: int,
) -> tuple[int, str | None]:
    pass


def run_evaluate(limit: int = 10) -> dict:
    perfil = load_perfil()
    offers = get_pending_offers(limit)
    candidate_skills = load_skills_from_perfil(perfil)
    employment_gap = load_gap_from_perfil(perfil)
    log.info("Ofertas pendientes de evaluar: %d", len(offers))
    log.info("Skills del candidato cargadas: %d", len(candidate_skills))
    if employment_gap:
        log.info("Employment gap: %.1f años", employment_gap)

    stats = {"evaluated": 0, "errors": 0, "scores": [], "descarte": 0}

    for offer in offers:
        t0 = time.monotonic()
        try:
            log.info("Evaluando: %s", offer["title"])

            # PRE-FILTRO: Verificar requisitos impossibles
            es_descartable, razon_descarte = pre_filtro_requisitos_imposibles(
                offer, perfil
            )

            if es_descartable:
                log.warning(f"⚠️ DESCARTE: {offer['title']} - {razon_descarte}")
                ms = int((time.monotonic() - t0) * 1000)
                save_evaluation(
                    offer_id=offer["id"],
                    technical={},
                    hr={},
                    match_score=0,
                    recommendation="Descartado",
                    processing_ms=ms,
                    descarte_tipo="requisito_imposible",
                    descarte_razon=razon_descarte,
                )
                stats["descarte"] += 1
                stats["evaluated"] += 1
                log.info("✓ %s → DESCARTADO (%s)", offer["title"], razon_descarte)
                continue

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

            ms = int((time.monotonic() - t0) * 1000)
            save_evaluation(
                offer["id"],
                technical,
                hr,
                match_score,
                recommendation,
                ms,
            )

            log.info("✓ %s → %d/100 (%s)", offer["title"], match_score, recommendation)
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
