# Base de Datos

## Motor y ORM

- **Motor:** SQLite en `data/jobs.db`
- **ORM:** SQLAlchemy (usar siempre, no SQL raw salvo en `init_db.py`)
- **Convenciones:** `snake_case` para todas las columnas

## Tablas Principales

| Tabla | Descripción |
|-------|-------------|
| `offers` | Ofertas crudas de InfoJobs (source_id UNIQUE) |
| `companies` | Datos e inteligencia de empresa |
| `offer_evaluations` | Scoring técnico + HR (ambos gemma4:e4b, temperaturas 0.1 y 0.0) |
| `candidate_profile` | Perfil estructurado (generado desde PERFIL.md) |
| `cv_versions` | Historial de versiones del CV |
| `search_runs` | Historial de ejecuciones del pipeline |
| `market_signals` | Señales semanales del mercado |
| `strategic_insights` | Consejos del Strategic Advisor |
| `user_settings` | Configuración del usuario |
| `user_feedback` | Feedback diario del candidato |
| `user_psychology` | Resumen semanal evolutivo |
| `search_config` | Configuración geográfica y de roles |

## Reglas de Datos

### Offers
- **Upsert** por `source_id` (nunca duplicar ofertas)
- Usar `is_active = False` para desactivar (no borrar)
- `fetched_at` no se actualiza en updates (solo en insert)

### Candidate Profile
- `personal_concerns` es TEXT libre — nunca normalizar ni parsear
- Solo un perfil activo a la vez (`is_active = 1`)
- Skills, educación, experiencia: JSON serializado

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
idx_evaluations_offer_id ON offer_evaluations(offer_id)
idx_evaluations_match_score ON offer_evaluations(match_score)
idx_companies_name ON companies(name)
```

## Schema

El schema completo está en `src/db/schema.sql`. Consultar siempre antes de modificar modelos o consultas.