# PLANS.md — Estado del Proyecto (Método Ledger)

## FASE 1 — Cimientos
  [x] init_db.py + schema.sql completo
  [x] ollama_client.py con reintentos y validación JSON
  [x] Test de conexión Telegram
  [x] Test de conexión Ollama (qwen2.5-coder:7b y gemma4:e4b)
  [x] Test de conexión InfoJobs API (vía Apify)

## FASE 2 — Onboarding
  [x] cv_extractor.py (qwen2.5 → datos estructurados)
  [x] interviewer.py (gemma4 → preguntas secuenciales)
  [x] Generación de PERFIL.md
  [x] Guardado en candidate_profile (DB)
  [x] run.py orquesta el onboarding completo

## FASE 3 — Pipeline base
  [x] fetch.py (InfoJobs API → limpieza → upsert en DB)
  [x] evaluate.py (qwen2.5 técnico + gemma4 HR → offer_evaluations)
  [x] send.py (formato Telegram → envío)
  [x] run.py (orquestador del pipeline completo)
  [x] role_classifier.py (clasificación de ofertas y relevance_flag)
  [x] Añadir campos search_layer, role_level, relevance_flag a offers
  [x] Crear tabla search_config para configuración geográfica y de rol
  [x] Pre-filtro de requisitos impossibles (descartar 0/1)
  [ ] fetch_company.py (datos empresa → DB)

## FASE 4 — Inteligencia
  [ ] role_discovery.py
  [ ] market_signals.py
  [ ] strategic_advisor.py con todos los triggers

## FASE 5 — Automatización
  [ ] Configuración cron
  [ ] Logging y monitorización

## TESTS — Infrastructure
  [x] tests/conftest.py con fixtures DB (temp file + rollback)
  [x] Fixtures: sample_perfil_text, sample_offer (+ variants)
  [x] Unit tests: test_evaluate.py, test_send.py, test_cleaner.py, test_fetch.py, test_models.py
  [x] Integration tests: test_db_operations.py, test_db_evaluations.py
  [ ] Ollama cassettes (grabados) + tests con patches
  [ ] Pipeline tests (flujo completo con cassettes)
  [ ] Depreciar/reemplazar test_phase1.py (tabla candidate_profile eliminada)