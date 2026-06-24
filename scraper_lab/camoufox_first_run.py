"""Primera ejecución: abre Camoufox en modo GUI para resolver el challenge de Distil.

Uso: PYTHONPATH=. python scraper_lab/camoufox_first_run.py

Resuelve el JS challenge manualmente una vez.
Las cookies quedan guardadas en scraper_lab/user_data/ para uso headless posterior.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.scraper.camoufox_scraper import CamoufoxScraper

print("Abriendo Camoufox en modo GUI para resolver challenge de Distil...")
print("Resuelve el challenge manualmente y cierra el navegador.")
print("Las cookies se guardarán en scraper_lab/user_data/ para uso futuro.\n")

s = CamoufoxScraper(headless=False)
stubs = s.search(query="Data Analyst", page_limit=1, max_items=1)
s.close()

if stubs:
    print(f"\n✅ Challenge resuelto — {len(stubs)} ofertas encontradas")
    print(f"   Primera: {stubs[0].title} @ {stubs[0].company}")
elif stubs is not None:
    print("\n⚠️  Sin ofertas en las últimas 24h. El challenge puede estar resuelto.")
    print("   Prueba con since_date='_7_DAYS' para confirmar.")
else:
    print("\n❌ Distil sigue bloqueando incluso en GUI. Reintenta o usa otro IP.")
