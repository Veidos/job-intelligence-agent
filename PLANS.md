# PLANS.md — Estado del Proyecto (Método Ledger)

> **Próximo paso:** Testing T-6 — send.py: mensaje Telegram correcto.
> T-2 ⏳ y T-3 ⏳ bloqueados por límite Apify (ADR-004). T-4 ✅, T-5 ✅ completado.
> Ver docs/TESTING.md para el checklist completo.

## FASE 1 — Cimientos
  [x] init_db.py + schema.sql completo
  [x] ollama_client.py con reintentos y validación JSON
  [x] Test de conexión Telegram
  [x] Test de conexión Ollama (gemma4:e4b)
  [x] Test de conexión InfoJobs API (vía Apify)

## FASE 2 — Onboarding
  [x] cv_extractor.py (gemma4 → datos estructurados)
  [x] interviewer.py (gemma4 → preguntas secuenciales)
  [x] Rediseño entrevista: preguntas positivas, salario opcional, contexto personal fusionado (ADR 003)
  [x] Generación de PERFIL.md (fuente única de verdad)
  [x] run.py orquesta el onboarding completo

## FASE 3 — Pipeline base
  [x] fetch.py (InfoJobs API → limpieza → upsert en DB)
  [x] evaluate.py (gemma4:e4b técnico + HR → offer_evaluations)
  [x] send.py (formato Telegram → envío)
  [x] run.py (orquestador del pipeline + CV freshness check vía SHA-256, ADR 002)
  [x] role_classifier.py (clasificación de ofertas y relevance_flag)
  [x] Añadir campos search_layer, role_level, relevance_flag a offers
  [x] Crear tabla search_config para configuración geográfica y de rol
  [x] Pre-filtro de requisitos impossibles (descartar 0/1)
  [x] fetch_company.py — enriquecimiento de companies desde ofertas (employer_id)
[x] Integrar fetch_company en pipeline (entre classify y evaluate)
[x] Añadir columna employer_id a offers en schema.sql
[x] Capturar author.id de API InfoJobs en fetch.py
  [x] apify_raw_responses — registro inmutable de raw data Apify
  [x] keyword_generator.py — generación y gestión de keywords desde PERFIL.md

## FASE 4 — Inteligencia
  [ ] role_discovery.py
  [ ] market_signals.py
  [ ] strategic_advisor.py con todos los triggers

## FASE 5 — Automatización
  [x] Listener de comandos Telegram (/f1, /f2, /f3, /dia) — handlers.py + bot.py
  [x] Persistencia de feedback con enlace a ofertas del día (get_latest_daily_offers corregido)
  [x] feedback_processor.py — procesa feedback acumulado a user_psychology
  [x] Scripts cron (setup_cron.sh, start_bot.sh, stop_bot.sh)
  [x] Logging persistente (RotatingFileHandler en run.py y bot.py)
  [x] Tests para feedback (test_feedback.py)

## TESTS
[x] tests/conftest.py con fixtures DB (temp file + rollback)
[x] Fixtures: sample_perfil_text, sample_offer (6 variants)
[x] Unit tests: test_evaluate.py, test_send.py, test_cleaner.py, test_fetch.py, test_models.py (107 tests)
[x] Integration tests: test_db_operations.py, test_db_evaluations.py (20 tests)
[x] Ollama cassettes (13 JSON en tests/fixtures/ollama/ + patch-based tests)
[x] Integration cassettes: test_evaluate_cassettes.py, test_classifier_cassettes.py, test_fetch_cassettes.py (30 tests cassette-based)
[x] Pipeline tests: test_pipeline.py (10 tests, flujo completo con cassettes)
[x] 171 tests passing total

## BUGS DETECTADOS (TESTS Y REVISIÓN)
  [x] save_evaluation: añadidas 7 columnas faltantes al INSERT (cv_version_id, company_fit_score, etc.)
  [x] pre_filtro_requisitos_imposibles: PROFILE_CHECK_PATTERNS comparaba regex vs string
  [x] test_phase1.py: eliminada (tabla candidate_profile ya no existe)
  [x] Reportes HTML: `<title>` de v5 y v6 copiado de v4 sin actualizar ("T-4 v4" en la pestaña del navegador)
  [x] Reportes HTML: falta `ORDER BY id ASC` en queries SQL — IDs 241/242 invertidos en las cards
  [x] Navegación entre reportes: v3–v5 no tenían enlaces a versiones posteriores (imposible volver a v6 desde v5)
  [x] APIFY_TOKEN leído en module-level: movido a dentro de run_fetch()

## Testing pendiente — Pipeline completo

Ver checklist completo en docs/TESTING.md

- [x] T-0 — Prerequisitos verificados (4/5 🤖 OK, pendiente revisión 👤 ítem T-0.5)
- [x] T-1 — Onboarding validado manualmente (extracción + entrevista + PERFIL.md)
- [ ] T-2 — fetch.py con sinceDate=_24_HOURS validado en producción ⏳ (bloqueado: Apify, ADR-004)
- [ ] T-3 — fetch_company.py sin errores ⏳ (bloqueado: depende de T-2, employer_id en ofertas)
- [x] T-4 — role_classifier.py coherente con las ofertas (v5/v6 validado, ADR-005 documenta evolución)
- [x] T-5 — evaluate.py — requisitos imposibles penalizados + scoring determinista 0-1
- [ ] T-6 — send.py — mensaje Telegram correcto
- [ ] T-7 — run.py ciclo completo real sin errores
- [ ] T-8 — Feedback bot funcional y natural
- [ ] T-9 — pytest 0 failed