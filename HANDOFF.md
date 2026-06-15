# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-15 (v2)
**Fase activa:** Dashboard work_mode canonical fix + doc updates

## Cambios de la sesión actual (2026-06-15)

### Reseteo de DB
- `data/jobs.db` respaldado como `data/jobs.db.v1` (8.7 MB)
- Tablas reseteadas: offers, offer_evaluations, scraper_raw_responses, apify_raw_responses, applications, user_feedback, search_runs
- Companies, search_config, user_settings, user_psychology preservados

### Fixes de scraper (403 Forbidden)
- `delay` aumentado de 2.0s → 4.0s + jitter aleatorio 2.0s
- Fingerprint rotado: `chrome131`/`safari17`/`chrome124` (random)
- `random` import añadido a `infojobs_scraper.py`

### Fix: `_upsert_from_scraper_raw()` filtraba por `run_id`
- `WHERE run_id = ? AND processed = 0` → `WHERE processed = 0`
- Ejecuciones abortadas ya no dejan filas huérfanas

### Fix: `--dry-run` no llegaba a fetch.py
- `run_fetch_scraper()` ahora acepta `dry_run: bool = False`
- En dry_run: no abre conexión, no persiste raw, no upsert
- `run.py` pasa `dry_run` correctamente

### Fix: `--limit-eval 0` y `--limit-enrich 0` como "sin límite"
- `evaluate.py:get_pending_offers()`: `limit=0` → `-1` (SQLite LIMIT -1 = sin límite)
- `fetch_company.py:run()`: batch slice `companies_to_enrich[:limit if limit > 0 else None]`
- `run.py`: help actualizado documentando que `0` = sin límite

### Fix: `published_at` nulo en scraper
- Fallback: si `_extract_published_at()` devuelve `None`, usar `datetime.now().strftime("%Y-%m-%d")`
- Previene acumulación de ofertas sin fecha en dashboard

### Pipeline resultados
- **65 ofertas** fetch + classify (5 core, 20 adjacent, 38 stretch, 2 temporal)
- **14 empresas enriquecidas** → 176 total, 100% pobladas
- **65/65 evaluadas**, 0 errores
- **3 "Aplicar"**: CONSULTOR DATA SCIENCE @ Management Solutions (0.70), Ingeniero/a procesos @ CADE (0.67), Data Scientist/ML Analyst @ Solutia (0.61)
- **Avg score**: 0.253 | 197 LLM calls, 0 fallos JSON
- **Pipeline**: ~3h45min total (ambos runs), Telegram enviado con 3 ofertas

### Dashboard
- Servidor Flask en `http://localhost:8080`
- Todos los endpoints API verificados: stats, offers, companies, runs
- Sin regresiones por zombie columns (ninguna referenciada en dashboard)
- skill_detail, scoring breakdown (M_core, F_exp, etc.) poblados correctamente

### Fix: work_mode desde título (fallback)
- `_parse_header_details()`: si el header no da modalidad, prueba chips/tags alternativos
- Si tampoco, fallback desde el título con `log.warning()` para monitoreo
- 3/8 ofertas sin work_mode corregidas vía re-scrape (scraper_lab/reparse_work_mode.py)

### Fix: skills gap empty state
- `renderSkillsGap()` ahora muestra mensaje informativo cuando gap está vacío
- En vez de return silencioso que dejaba el contenedor gris vacío

### Fix: mapa canónico WORK_MODE_CANONICAL + normalización de variantes scraper
- **Bug #1 (vuelta 1):** `work_mode=""` (6 ofertas) filtrado porque `""` no está en `allowedModes`. **Fix:** guardia `d.work_mode &&`
- **Bug #2 (vuelta 2):** `work_mode="Teletrabajo"` (2 ofertas, IDs 34, 38) filtrado porque `"Teletrabajo"` no está en `allowedModes` (solo `"Solo teletrabajo"`). Causa: el scraper produce `"Teletrabajo"` como variante.
- **Bug #3:** chart `Modalidad de trabajo` mostraba categorías `-` (6 vacías) y `Teletrabajo` (2) mezcladas con Presencial/Híbrido/Remoto
- **Causa raíz:** fragmentación de la normalización de `work_mode`: `workModeLabel()` y `workModeValue()` tenían mapas paralelos e incompletos
- **Fix estructural:** constante única `WORK_MODE_CANONICAL` que mapea las 4 variantes del scraper (`Solo teletrabajo`, `Teletrabajo`, `Híbrido`, `Presencial`) a 3 categorías (`Remoto`, `Híbrido`, `Presencial`). `workModeLabel()`, `workModeValue()` y `allowedModes` comparten el mismo namespace canónico.
- **Fix chart:** `renderWorkModeChart()` filtra solo categorías conocidas via `WORK_MODE_COLORS`, excluye vacíos y variantes no mapeadas
- **Tests:** `test_api_offers_work_mode_null` + `test_api_offers_work_mode_teletrabajo`

### Tests
- **223 tests passing** (20 dashboard + 203 resto) — 2 tests nuevos, 0 regresiones

### 🔴 Fix: models.py — DB_PATH ahora lee variable de entorno
- **Problema:** `DB_PATH = "data/jobs.db"` hardcodeado, engine instanciado al importar el módulo, antes de cualquier `load_dotenv()`. Ignoraba `DB_PATH` del `.env`.
- **Fix:** `_get_engine()` perezoso dentro de `load_dotenv()`, `DB_PATH` leído con `os.getenv("DB_PATH", "data/jobs.db")`
- **Tests:** `pytest tests/ -q` → 223 passed

### 🔴 Fix: evaluate.py — elimina duplicación de CandidateProfile
- **Problema:** `load_skills_from_perfil()`, `load_gap_from_perfil()`, `load_location_from_perfil()`, `load_experience_years_from_perfil()`, `MONTH_NAMES`, `_month_from_name()` — código idéntico al que ya existe en `CandidateProfile`. Dos implementaciones paralelas que pueden divergir.
- **Fix:** eliminadas las 6 definiciones (~164 líneas). `run_evaluate()` ya usaba `CandidateProfile.from_perfil()` desde el refactor anterior. Tests actualizados para importar desde `CandidateProfile`.
- **Tests:** 223 passed, 0 regresiones

### 🔴 Fix: server.py — conexiones con context manager
- **Problema:** 8 endpoints usaban `conn = get_connection()` + `conn.close()` manual. Cualquier excepción no capturada dejaba la conexión abierta (leak).
- **Fix:** `with contextlib.closing(get_connection()) as conn:` en los 8 endpoints (`api_stats`, `api_offers`, `api_offer_detail`, `api_companies`, `api_feedback`, `api_applications`, `api_delete_application`, `api_runs`). Eliminados todos los `conn.close()` manuales. Los early returns dentro del `with` son seguros.
- **Tests:** 223 passed, 0 regresiones

### 🔴 Fix: ollama_client.py — OLLAMA_BASE_URL lee de variable de entorno
- **Problema:** `OLLAMA_BASE_URL = "http://localhost:11434"` hardcodeado, ignoraba el `.env`. Imposible apuntar a Ollama remoto sin tocar código.
- **Fix:** `OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")`. Añadido `import os`. `.env.example` actualizado con la variable.
- **Tests:** 223 passed, 0 regresiones

---

## Auditoría intensiva completa (2026-06-15)

He leído y analizado metódicamente cada archivo del repositorio. Auditoría completa ordenada por severidad:

### 🔴 Críticos — Bugs o riesgos reales

1. **src/db/models.py** — `DB_PATH` hardcodeado, engine creado antes de `load_dotenv()` → **✅ FIXED (parcial)**
   - Engine se instancia al importar, antes de que `load_dotenv()` se ejecute.
   - Fix: `_get_engine()` perezoso + `load_dotenv()` dentro del módulo.
   - **⚠️ Limitación:** `load_dotenv()` en models.py es redundante si otro módulo ya lo llamó. El engine sigue creándose al importar, pero ahora respeta `DB_PATH` del `.env`. El `load_dotenv()` extra es ruido inofensivo. Se eliminará naturalmente al abordar el ítem #8 (pyproject.toml + punto de entrada único).

2. **src/pipeline/evaluate.py** — Duplicación total de lógica de parseo ya refactorizada
   - `load_skills_from_perfil()`, `load_gap_from_perfil()`, `load_experience_years_from_perfil()`, `MONTH_NAMES` — código idéntico al que ya existe en `CandidateProfile` (`src/utils/candidate_profile.py`).
   - `evaluate.py` debería simplemente: `from src.utils.candidate_profile import CandidateProfile; profile = CandidateProfile.from_perfil(perfil_text)` y usar `profile.skills_map`, `profile.employment_gap`, etc.

3. **src/dashboard/server.py** — Conexiones SQLite sin context manager (leak garantizado en error)
   - 6 endpoints usan `conn = get_connection()` + `conn.close()` manual. Si hay una excepción, `conn` nunca se cierra.
   - Fix: `with get_connection() as conn:` (requiere que `get_connection()` devuelva context manager, o usar `contextlib.closing()`).

4. **src/utils/ollama_client.py** — `OLLAMA_BASE_URL` hardcodeado
   - `OLLAMA_BASE_URL = "http://localhost:11434"` ignora el `.env`. Hace imposible apuntar a Ollama remoto sin tocar el código.

5. **src/telegram/send.py** — Sin validación de tokens vacíos
   - Si `.env` no existe o los tokens están vacíos, la URL queda como `.../bot/sendMessage` y el error llega tarde (en el request HTTP), con mensaje críptico.
   - Fix: `if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: raise EnvironmentError(...)`

6. **Schema SQL** — `match_score INTEGER` vs float 0-1
   - Schema define `match_score INTEGER`, pero `evaluate.py` calcula scores como float en rango `0.0–1.0`. En `send.py` se compara con `>= 35` y en el dashboard se muestra como porcentaje `/100`. La conversión `*100` implícita hace el código frágil: si se cambia en un sitio, el resto falla silenciosamente.

7. **src/telegram/send.py** — `process_feedback` hardcodea `range(1, 6)` pero el docstring documenta `/f1–/f3`
   - `for i in range(1, 6):` acepta `/f1` a `/f5`, pero el mensaje enviado a Telegram solo lista `/f1 /f2 /f3`. Inconsistencia de contrato.

### 🟠 Mayores — Deuda técnica real

8. **`sys.path.insert(0, ...)` en 8+ módulos** — ausencia de packaging
   - Aparece en `evaluate.py`, `fetch.py`, `run.py`, `server.py`, `handlers.py`, `send.py`...
   - Solución: `pyproject.toml` con `[tool.setuptools.packages.find]` + `pip install -e .` elimina todos los `sys.path.insert`.

9. **src/db/migrate.py** — Segunda fuente de verdad del schema
   - `SCHEMA_DEFINITIONS` en `migrate.py` duplica exactamente `schema.sql`. Si añades una columna en `schema.sql` y olvidas `migrate.py` (o viceversa), las instalaciones nuevas y las existentes tienen schemas distintos.

10. **src/db/models.py** — SQLAlchemy solo para `UserSettings`, raw `sqlite3` para todo lo demás
    - El proyecto mezcla ORM y raw en el mismo codebase. Decisión: eliminar SQLAlchemy completamente y quedarse con `sqlite3` raw (más simple, ya tienes el schema), o modelar todas las tablas en ORM.

11. **src/dashboard/server.py** — SQL dinámico con f-string en `api_offers`
    - `where_sql = " AND ".join(wheres)` construido desde `request.args`. Los valores van parametrizados, pero si alguien añade `request.args.get("order_by")` directamente abre inyección SQL. Usar allowlist explícito de columnas filtrables.

12. **src/pipeline/run.py** — `setup_logging()` añade handlers duplicados
    - Si `run_pipeline()` se llama más de una vez (ej. tests), los handlers se acumulan y cada log se emite N veces. Fix: `logging.getLogger().handlers = []` antes de añadir, o comprobar `if not root_logger.handlers`.

13. **`_extract_offer_id`** — Regex sobre el HTML completo (O(n) innecesario)
    - Se pasa el HTML completo de la oferta (>100KB) cuando el ID ya está disponible en la URL que se pasó al scraper.

### 🟡 Menores — Calidad y limpieza

14. **requirements.txt** — `ruff` en producción
    - `ruff==0.6.9` es herramienta de desarrollo. No debería estar en el mismo archivo que las dependencias de runtime. Lo correcto: `requirements-dev.txt` o `pyproject.toml` con `[project.optional-dependencies] dev = ["ruff"]`.

15. **`MONTH_NAMES` definido en 3 sitios**
    - `evaluate.py`, `candidate_profile.py`, e `infojobs_scraper.py` definen el mismo diccionario. Debería vivir en `src/utils/` como constante compartida.

16. **`scripts/`** — Versiones muertas `reporte_v1` a `reporte_v6`
    - Seis versiones acumuladas de scripts de reporte. Si no se usan, deben eliminarse (están en git, siempre recuperables).

17. **`scraper_lab/`** — Scripts de fix one-off
    - `fix_published_at.py`, `reparse_*.py` ya cumplieron su función. Mover a un branch de historia o eliminar del main.

18. **src/db/models.py** — Docstring incorrecto
    - `Única fuente de verdad: PERFIL.md` → incorrecto. La fuente de verdad del schema es `schema.sql`, no `PERFIL.md`.

19. **requirements.txt** — Sin `uv.lock` o `requirements.lock`
    - Pins con `==` dan reproducibilidad, pero sin lock file con hashes hay riesgo de supply chain. Aceptable para proyecto personal.

### ✅ Lo que está bien — Reconocimiento explícito

- **`CandidateProfile`** — el refactor es correcto: dataclass, single-pass parsing, `from_perfil`/`from_perfil_path`, `excerpt()`. Falta solo que `evaluate.py` lo use.
- **`schema.sql`** — excelente: comentarios de diseño, FK dependency order explícito, `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`, índices bien colocados, `UNIQUE(offer_id)` en scraper_raw para idempotencia.
- **`ollama_client.py`** — tenacity para reintentos, `_extract_json` con múltiples estrategias de extracción, métricas en `_metrics`, separación clara entre `_call_ollama_raw` y `ollama_call`.
- **`InfoJobsParser`** — dataclasses `frozen=True` para `SearchStub` y `RawOfferDetail`. Parseable sin HTTP (testeable con snapshots HTML).
- **`GAP_MULTIPLIER` y `RATING` como tablas fijas** — determinismo correcto. No usar LLM para umbrales numéricos es la decisión correcta.
- **`WORK_MODE_CANONICAL`** — el fix estructural es la solución correcta: una sola constante, todos los consumers la comparten.
- **Tests** — estructura unit/integration/manual, fixtures JSON como cassettes, 223 tests passing. Para un proyecto personal esto es excepcional.
- **AGENTS.md + HANDOFF.md** — documentación de sesión de nivel profesional. El sistema de "fuente de verdad del candidato" y las reglas de cierre de sesión son prácticas maduras.

### Tabla resumen de prioridades

| # | Archivo | Problema | Prioridad |
|---|---------|----------|-----------|
| 1 | `models.py` | DB_PATH hardcodeado + engine global pre-env | 🔴 **✅ FIXED** |
| 2 | `evaluate.py` | Duplica todo CandidateProfile | 🔴 |
| 3 | `server.py` | Conexiones sin context manager | 🔴 |
| 4 | `ollama_client.py` | OLLAMA_BASE_URL hardcodeado | 🔴 |
| 5 | `send.py` | Sin validación de tokens vacíos | 🔴 |
| 6 | Schema | match_score INTEGER vs float 0-1 | 🔴 |
| 7 | `send.py` | range(1,6) vs /f1–/f3 docs | 🔴 |
| 8 | Todo | sys.path.insert x8 | 🟠 |
| 9 | `migrate.py` | Duplica schema.sql | 🟠 |
| 10 | `models.py` | ORM parcial (solo UserSettings) | 🟠 |
| 11 | `server.py` | SQL dinámico sin allowlist | 🟠 |
| 12 | `run.py` | Handler logging duplicado | 🟠 |
| 13 | scraper | Regex HTML completo O(n) | 🟠 |
| 14 | requirements.txt | ruff en producción | 🟡 |
| 15 | Global | MONTH_NAMES x3 | 🟡 |
| 16 | scripts/ | Versiones muertas v1–v6 | 🟡 |
| 17 | scraper_lab/ | Scripts one-off | 🟡 |
| 18 | models.py | Docstring incorrecto | 🟡 |
| 19 | requirements.txt | Sin lock file | 🟡 |
