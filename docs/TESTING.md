# TESTING.md — Pipeline Integration Testing Checklist

> Checklist de verificación end-to-end del pipeline completo.
> Ejecutar en orden antes de marcar Phase 3 como completa.
>
> **Cómo usar este documento:**
> Al final de cada fase, el agente ejecuta los comandos de verificación
> y genera un reporte visual en `reports/testing/NNN-fase-nombre.html`
> con los resultados automáticos ya rellenos y los ítems manuales
> destacados para revisión humana.
>
> Leyenda:
> - 🤖 Verificable automáticamente (el agente lo comprueba)
> - 👤 Requiere revisión manual (solo el humano puede validarlo)

---

## 0. Prerequisitos

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 0.1 | 🤖 | Ollama corriendo en `localhost:11434` | `curl http://localhost:11434` responde |
| 0.2 | 🤖 | `gemma4:e4b` disponible | aparece en `ollama list` |
| 0.3 | 🤖 | `.env` con las 3 variables requeridas | `APIFY_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` presentes |
| 0.4 | 🤖 | Schema de DB inicializado | `init_db.py` sin errores, tablas presentes |
| 0.5 | 👤 | `PERFIL.md` existente y coherente con el CV real | Lectura manual |

```bash
curl -s http://localhost:11434 && echo "Ollama OK"
ollama list | grep gemma4
python src/db/init_db.py
```

**Reporte:** `reports/testing/00-prerequisitos.html`

---

## 1. Onboarding

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 1.1 | 🤖 | `cv_extractor.py` sin errores | exit 0, sin excepciones |
| 1.2 | 🤖 | `PERFIL.md` generado | fichero existe y no está vacío |
| 1.3 | 👤 | Datos extraídos del CV son correctos | Skills, experiencia y formación coinciden con el CV real |
| 1.4 | 👤 | `interviewer.py` genera preguntas coherentes | Las preguntas son relevantes para el perfil |
| 1.5 | 👤 | `PERFIL.md` final aprobado | El candidato confirma que el perfil le representa |

```bash
PYTHONPATH=. python src/onboarding/run.py --cv assets/cv.pdf
```

**Reporte:** `reports/testing/01-onboarding.html`

---

## 2. fetch.py — Extracción de ofertas

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 2.1 | 🤖 | Apify actor responde sin error | HTTP 200, actor run completado |
| 2.2 | 🤖 | `sinceDate=_24_HOURS` aplicado | `MIN(published_at)` dentro de las últimas 24h |
| 2.3 | 🤖 | `maxItems=50` respetado | `COUNT(*) <= 50` tras el fetch |
| 2.4 | 🤖 | Campos críticos mapeados | `source_id`, `description_raw`, `fetched_at` presentes en todas las filas |
| 2.5 | 🤖 | Deduplicación funciona | Segunda ejecución no incrementa `COUNT(*)` |
| 2.6 | 🤖 | `gemma4:e4b` enriquece sin errores | `description_clean` y `skills_required` rellenos |
| 2.7 | 👤 | Muestra de 5 ofertas — datos coherentes | Títulos, empresas y descripciones tienen sentido |

```bash
PYTHONPATH=. python src/pipeline/fetch.py
sqlite3 data/jobs.db "SELECT COUNT(*), MIN(published_at), MAX(published_at) FROM offers;"
sqlite3 data/jobs.db "SELECT title, employer_name, published_at FROM offers ORDER BY fetched_at DESC LIMIT 5;"
```

**Reporte:** `reports/testing/02-fetch.html`

---

## 3. fetch_company.py — Enriquecimiento de empresas

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 3.1 | 🤖 | Script termina sin excepciones | exit 0 |
| 3.2 | 🤖 | Tabla `companies` tiene registros | `COUNT(*) > 0` |
| 3.3 | 👤 | Datos de empresa son coherentes | Nombres, sectores y tamaños tienen sentido |

```bash
PYTHONPATH=. python src/pipeline/fetch_company.py
sqlite3 data/jobs.db "SELECT COUNT(*) FROM companies;"
sqlite3 data/jobs.db "SELECT name, sector, size FROM companies LIMIT 5;"
```

**Reporte:** `reports/testing/03-fetch-company.html`

---

## 4. role_classifier.py — Clasificación de roles

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 4.1 | 🤖 | Script termina sin excepciones | exit 0 |
| 4.2 | 🤖 | Todas las ofertas tienen `role` asignado | `COUNT(*) WHERE role IS NULL = 0` |
| 4.3 | 🤖 | Todos los `relevance_flag` son válidos | Solo valores: `core`, `adjacent`, `stretch`, `temporal` |
| 4.4 | 👤 | Roles clasificados son coherentes con las ofertas | Una oferta "Data Scientist" con solo SQL no debería ser `ml_engineer` |
| 4.5 | 👤 | Distribución de `relevance_flag` es razonable | No todo `core` ni todo `stretch` |

```bash
PYTHONPATH=. python src/pipeline/role_classifier.py
sqlite3 data/jobs.db "SELECT role, relevance_flag, COUNT(*) FROM offers GROUP BY role, relevance_flag ORDER BY COUNT(*) DESC;"
sqlite3 data/jobs.db "SELECT title, role, relevance_flag FROM offers ORDER BY fetched_at DESC LIMIT 10;"
```

**Reporte:** `reports/testing/04-classifier.html`

---

## 5. evaluate.py — Scoring

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 5.1 | 🤖 | Script termina sin `OperationalError` | exit 0 |
| 5.2 | 🤖 | Todas las ofertas evaluadas | `COUNT(offer_evaluations) = COUNT(offers)` |
| 5.3 | 🤖 | Scores dentro de rango | `total_score` entre 0 y 100 en todas las filas |
| 5.4 | 🤖 | `gemma4:e4b` devuelve JSON válido | Sin errores de parsing en logs |
| 5.5 | 🤖 | Requisitos imposibles → `pre_filter_passed = 0` | Ofertas con certificado discapacidad etc. filtradas |
| 5.6 | 👤 | Distribución de scores razonable | No todos 0 ni todos 100, curva lógica |
| 5.7 | 👤 | Top 5 scores corresponden a ofertas realmente buenas | El candidato confirma que las top son las mejores |
| 5.8 | 👤 | Pre-filtro aplicado a los casos correctos | Las ofertas filtradas tienen requisitos realmente imposibles |

```bash
PYTHONPATH=. python src/pipeline/evaluate.py
sqlite3 data/jobs.db "SELECT MIN(total_score), MAX(total_score), ROUND(AVG(total_score),1), COUNT(*) FROM offer_evaluations;"
sqlite3 data/jobs.db "SELECT o.title, e.total_score, e.pre_filter_passed FROM offers o JOIN offer_evaluations e ON o.id = e.offer_id ORDER BY e.total_score DESC LIMIT 10;"
sqlite3 data/jobs.db "SELECT o.title, e.pre_filter_passed FROM offers o JOIN offer_evaluations e ON o.id = e.offer_id WHERE e.pre_filter_passed = 0 LIMIT 5;"
```

**Reporte:** `reports/testing/05-evaluate.html`

---

## 6. send.py — Envío Telegram

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 6.1 | 🤖 | API Telegram responde sin error | HTTP 200 |
| 6.2 | 🤖 | Se envían máximo 3 ofertas con score ≥ 35 | Lógica de selección correcta |
| 6.3 | 🤖 | Fallback si ninguna ≥ 35 | Envía `"Sin ofertas relevantes hoy."` |
| 6.4 | 👤 | Mensaje legible y bien formateado | Sin caracteres raros, emojis correctos |
| 6.5 | 👤 | Emojis de rating correctos | 🟢 ≥75 / 🟡 55–74 / 🟠 35–54 |
| 6.6 | 👤 | Las 3 ofertas son las mejores del día | El candidato lo confirma visualmente |

```bash
PYTHONPATH=. python src/telegram/send.py --mode daily
```

**Reporte:** `reports/testing/06-send.html`

---

## 7. run.py — Pipeline completo

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 7.1 | 🤖 | `--dry-run` sin errores | exit 0, sin llamadas a Apify ni Telegram |
| 7.2 | 🤖 | Pipeline completo sin errores entre pasos | exit 0, logs limpios |
| 7.3 | 👤 | Resultado end-to-end coherente | Las ofertas del Telegram son las esperadas del día |

```bash
PYTHONPATH=. python src/pipeline/run.py --dry-run
PYTHONPATH=. python src/pipeline/run.py
```

**Reporte:** `reports/testing/07-pipeline-completo.html`

---

## 8. Feedback (Telegram bot)

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 8.1 | 🤖 | Bot responde a `/f1`, `/f2`, `/f3` | Respuesta recibida en Telegram |
| 8.2 | 🤖 | Bot responde a `/dia` | Respuesta recibida en Telegram |
| 8.3 | 🤖 | Feedback guardado en `user_feedback` | Registros con `daily_position` correcto |
| 8.4 | 🤖 | `feedback_processor` comprime sin errores | `user_psychology` actualizado |
| 8.5 | 👤 | Respuesta del bot suena natural | No robótica ni genérica |
| 8.6 | 👤 | `user_psychology` refleja lo dicho | El resumen es coherente con el feedback dado |

```bash
PYTHONPATH=. python src/telegram/bot.py &
sqlite3 data/jobs.db "SELECT * FROM user_feedback ORDER BY created_at DESC LIMIT 5;"
PYTHONPATH=. python src/pipeline/feedback_processor.py
sqlite3 data/jobs.db "SELECT * FROM user_psychology ORDER BY created_at DESC LIMIT 1;"
```

**Reporte:** `reports/testing/08-feedback.html`

---

## 9. Suite de tests automatizados

| # | Tipo | Ítem | Criterio de éxito |
|---|---|---|---|
| 9.1 | 🤖 | Todos los tests passing | 0 failed, 0 errors |
| 9.2 | 👤 | Ningún test es un falso positivo obvio | Revisar tests de evaluación y clasificación |

```bash
pytest tests/ -v
```

**Reporte:** `reports/testing/09-pytest.html`

---

## Criterio de completitud

Phase 3 se considera completa cuando:
1. Todos los ítems 🤖 pasan sin errores
2. Todos los ítems 👤 están revisados y aprobados por el candidato
3. El pipeline ha corrido al menos **un ciclo real completo** sin intervención manual

---

## Instrucciones para el agente

Al finalizar cada fase, genera `reports/testing/NNN-nombre.html` con:
- Resultados de cada query SQL en formato tabla
- Estado 🟢 / 🔴 por cada ítem 🤖 según el output real
- Sección destacada con los ítems 👤 pendientes, con los datos ya extraídos para facilitar la inspección visual
- Timestamp de ejecución
