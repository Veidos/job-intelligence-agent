# ADR-025 — Run 42: verificación humana ingerida como oferta

**Date:** 2026-10-08
**Type:** `operational` `architecture`
**Status:** `active`

## Contexto

El run 42 (`20261005T165305Z`) guardó **26 ofertas nuevas**. La inspección posterior
encontró que 12 respuestas de InfoJobs eran páginas de verificación humana, no ofertas:

- HTTP 405, `<h1>¿Eres humano o un robot?</h1>` y texto “Hemos detectado una actividad
  poco habitual… Hacer clic para comprobar”.
- `description_clean` y empresa vacías.
- Las 12 se insertaron como ofertas activas, se clasificaron y evaluaron con score 12.
- Una contaminó el catálogo con `screening_test_administrator`.
- Las 14 restantes eran ofertas reales.

El run terminó con `status=ok`, aunque el contenido ingerido incluía páginas de
verificación y la evaluación registró errores. El parser detectaba algunas variantes
de Distil (“No podemos identificar tu navegador”), pero no esta pantalla “¿Eres humano
o un robot?”; la ruta de detalle tampoco rechazaba el HTTP 405 ni exigía contenido
mínimo antes de devolver un objeto `RawOfferDetail`. `fetch.py` persistía cualquier
resultado no nulo y lo entregaba a clasificación.

### Fallo del asistente

El asistente revisó muestras tempranas del run, vio fichas válidas y concluyó que el
pipeline estaba funcionando. No examinó las 26 filas nuevas ni contrastó el HTML
archivado de toda la ejecución antes de informar el resultado. Por eso no detectó las
12 páginas falsas y transmitió una conclusión incorrecta. La responsabilidad de esa
revisión incompleta fue del asistente.

## Decisión

Una página de verificación humana nunca se considera oferta: se conserva solo como
evidencia raw, no se inserta en `offers`, no se clasifica ni se evalúa, y detiene el
fetch del run sin intentar resolver ni reintentar el reto.

## Limpieza realizada

Por instrucción del usuario se eliminaron las **26 filas `offers`** asociadas a los 26
`source_id` del run 42 y sus **26 filas `offer_evaluations`**. Se eliminaron tanto las
12 respuestas de verificación como las 14 ofertas reales del run: la petición fue
retirar todas las ofertas de esa ejecución. No existían filas relacionadas en
`applications` ni `user_feedback`.

También se retiró `screening_test_administrator` del `role_catalog`, al estar asociado
únicamente a una de las páginas falsas.

Se conservaron deliberadamente:

- Las 26 filas raw de `scraper_raw_responses` y las 52 filas bronze de
  `scraper_raw_html`, para preservar la evidencia original.
- La fila histórica `search_runs.id=42` con los contadores originales; no se reescribió
  el registro del run.
- Las empresas y los datos ajenos al conjunto identificado por el `run_id`.

Antes de la limpieza se creó `data/jobs.db.pre-run42-cleanup-20261008.sqlite` mediante
SQLite Backup API. `PRAGMA integrity_check` devolvió `ok`; después de la transacción,
la verificación confirmó cero ofertas/evaluaciones del conjunto, cero referencias
rotas y `integrity_check=ok`.

## Consecuencias

- El código actual es el baseline `2dce06a` (rollback `e26fbbf`); este ADR documenta
  un incidente de datos ocurrido antes del rollback, no una modificación del scraper.
- El backup permanece local bajo `data/` (ignorado por Git); no se restauró
  `data/jobs.db.v1`, que es de junio y habría perdido datos posteriores.
- El registro de `search_runs` sigue describiendo el resultado original. Para saber
  que sus ofertas fueron retiradas hay que consultar este ADR y el HANDOFF.
- Pendiente para un cambio futuro: validar estado HTTP, firmas de verificación y
  completitud del detalle antes de persistir; cubrir el 405 y el título de verificación
  con fixture offline; impedir que la clasificación cree roles a partir de datos
  incompletos; propagar errores al estado final del run.

## Evidencia

- `run_id`: `20261005T165305Z`; `search_runs.id=42`.
- IDs de oferta eliminados: 311–336.
- Backup previo: `data/jobs.db.pre-run42-cleanup-20261008.sqlite`.
- Código restaurado: `2dce06a`, publicado por el commit de rollback `e26fbbf`.
