# Convenciones de Código

## Python

- **Versión:** 3.14+
- **Type hints:** Obligatorios en todas las funciones públicas
- **Imports:** Absolutos desde `src/`. No imports relativos

## Estilo y Nomenclatura

| Tipo | Convención |
|------|------------|
| Variables, columnas | snake_case |
| Clases | PascalCase |
| Constantes | UPPER_CASE |
| Booleanos | is_*, has_*, enable_* |

## Linter y Formato

```bash
ruff check src/
ruff format src/
```

Ejecutar siempre antes de dar una tarea por terminada.

## Logging

- Usar `logging` estándar de Python
- No usar `print()` salvo en scripts de onboarding interactivos
- Incluir contexto en errores (no solo el mensaje)

## Manejo de Errores

### Ollama
- Reintentar máximo 3 veces con backoff exponencial
- Si falla: loguear y continuar con la siguiente oferta
- Usar excepciones personalizadas: `OllamaError`, `OllamaJSONError`

### InfoJobs API
- Loguear error con contexto completo en `search_runs`
- No abortar el pipeline por error parcial
- Continuar con las ofertas que pudieron procesarse

### JSON desde Modelos
- Validar siempre el schema antes de insertar en DB
- Si el JSON es inválido, reintentar el prompt una vez con instrucción adicional de formato
- Usar helpers `json_serialize` / `json_deserialize`

## Variables de Entorno

- Todas en `.env` (NO commitear)
- Cargar con `python-dotenv`
- No hardcodear credenciales nunca

## Método Ledger

Este proyecto usa el Método Ledger para seguimiento:

- **PLANS.md:** Mantener actualizado con estado de cada fase, tareas completadas, pendientes y blockers
- **MEMORIES.md:** Registrar aprendizajes no obvios (prompts efectivos, campos fiables, rendimiento de modelos)

Actualizar ambos al completar cada módulo o tarea significativa.

## Fases de Implementación

```
FASE 1 — Cimientos
  init_db.py + schema.sql completo
  ollama_client.py con reintentos y validación JSON
  Test de conexión Telegram, Ollama, InfoJobs API

FASE 2 — Onboarding
  cv_extractor.py (qwen2.5 → datos estructurados)
  interviewer.py (gemma4 → preguntas secuenciales)
  Generación de PERFIL.md
  Guardado en candidate_profile (DB)

FASE 3 — Pipeline base
  fetch.py, evaluate.py, send.py, run.py
  role_classifier.py

FASE 4 — Inteligencia
  role_discovery.py, market_signals.py, strategic_advisor.py

FASE 5 — Automatización
  Configuración cron, logging y monitorización, tests end-to-end
```

No avanzar a la siguiente fase sin que la anterior esté testeada y funcionando.