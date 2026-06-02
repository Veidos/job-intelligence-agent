# Base de Datos

## Motor

- **Motor:** SQLite en `data/jobs.db`
- **Driver:** `sqlite3` estándar (raw SQL, sin ORM)
- **Convenciones:** `snake_case` para todas las columnas

## Tablas Principales

| Tabla | Descripción |
|-------|-------------|
| `apify_raw_responses` | Registro inmutable de items Apify (append-only) |
| `offers` | Ofertas crudas de InfoJobs (source_id UNIQUE) |
| `companies` | Datos e inteligencia de empresa |
| `offer_evaluations` | Scoring técnico + HR (ambos gemma4:e4b, temperaturas 0.1 y 0.0) |
| `applications` | Seguimiento de candidaturas del usuario (estados, contacto, próxima acción) |
| `cv_versions` | Historial de versiones del CV |
| `search_runs` | Historial de ejecuciones del pipeline |
| `market_signals` | Señales semanales del mercado |
| `strategic_insights` | Consejos del Strategic Advisor |
| `user_settings` | Configuración del usuario |
| `user_feedback` | Feedback diario del candidato |
| `user_psychology` | Resumen semanal evolutivo |
| `search_config` | Configuración geográfica y de roles |

### `applications`

Estado controlado por el usuario (no por el pipeline). El dashboard permite crear, actualizar y eliminar.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `offer_id` | INTEGER FK→offers | Oferta asociada |
| `applied_at` | DATETIME | Cuándo se aplicó |
| `status` | TEXT | applied / interviewing / rejected / offer / accepted / archived |
| `notes` | TEXT | Notas libres |
| `contact_name` | TEXT | Reclutador o hiring manager |
| `next_action_date` | TEXT | Fecha ISO de próximo seguimiento |

## Reglas de Datos

### Offers
- **Upsert** por `source_id` (nunca duplicar ofertas)
- Usar `is_active = False` para desactivar (no borrar)
- `fetched_at` no se actualiza en updates (solo en insert)

### Apify Raw Responses
- **Append-only:** nunca se actualiza un payload, solo se marca `processed=1`
- `INSERT OR IGNORE` por (run_id, item_index) — idempotente
- `error` registra fallos de procesado sin bloquear el batch

### Campos JSON
- Almacenados como TEXT serializado
- Usar helpers en `src/db/models.py`:
  - `json_serialize(data)` → str
  - `json_deserialize(text)` → dict/list

## Índices Principales

```sql
idx_offers_source_id ON offers(source_id)
idx_offers_fetched_at ON offers(fetched_at)
idx_offers_is_active ON offers(is_active)
idx_offers_employer_id ON offers(employer_id)
idx_evaluations_offer_id ON offer_evaluations(offer_id)
idx_evaluations_match_score ON offer_evaluations(match_score)
idx_companies_name ON companies(name)
idx_apify_raw_run_id ON apify_raw_responses(run_id)
idx_apify_raw_source_id ON apify_raw_responses(source_id)
idx_apify_raw_processed ON apify_raw_responses(processed)
```

## Schema

El schema completo está en `src/db/schema.sql`. Consultar siempre antes de modificar modelos o consultas.
