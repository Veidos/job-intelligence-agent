"""
POC: verificar que extract_fields_with_llm produce secondary no vacío
sobre ofertas reales de InfoJobs ya almacenadas en DB.

Criterio de éxito: >=3 de 5 ofertas con secondary no vacío.
Criterio de fallo: secondary siempre vacío -> problema de datos fuente,
                   no del prompt. Documentar en ADR.

Uso: python scraper_lab/poc_secondary_skills.py
"""

import json
import logging

from src.db.init_db import get_connection
from src.pipeline.fetch import extract_fields_with_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

conn = get_connection()
rows = conn.execute("""
    SELECT id, title, description_clean, skills_required
    FROM offers
    WHERE length(description_clean) > 800
      AND is_evaluated = 1
    ORDER BY RANDOM()
    LIMIT 5
""").fetchall()
conn.close()

success = 0
for row in rows:
    offer_id, title, description, skills_raw = row
    log.info("Procesando: %s (id=%d)", title, offer_id)

    item = {"title": title, "description": description}
    result = extract_fields_with_llm(item)
    skills = result.get("skills_required", {})
    core = skills.get("core", [])
    secondary = skills.get("secondary", [])

    has_secondary = len(secondary) > 0
    if has_secondary:
        success += 1

    # Skills originales en DB para comparar
    original = json.loads(skills_raw or "{}")
    original_core = [s["name"] for s in original.get("core", [])]

    print(f"\n--- [{offer_id}] {title} ---")
    print(f"  DB core:       {original_core}")
    print(f"  LLM core:      {[s['name'] for s in core]}")
    print(f"  LLM secondary: {[s['name'] for s in secondary]}")
    print(f"  {'✓ secondary poblado' if has_secondary else '✗ secondary vacío'}")

print(f"\n{'=' * 50}")
print(f"RESULTADO: {success}/5 ofertas con secondary no vacío")
if success >= 3:
    print("-> Fix 2 VIABLE: integrar extract_fields_with_llm en _upsert_offer_from_scraper")
else:
    print("-> Fix 2 NO VIABLE: secondary vacío es limitación de datos fuente, documentar en ADR")
