# ADR-011: Employer ID desde companyLink tras cambio de API InfoJobs

**Date:** 2026-05-28
**Type:** `architecture`
**Status:** `active`
**Component:** `src/pipeline/fetch.py`

---

## Context

`fetch.py` extrae `employer_id` de cada oferta para identificar la compañía
publicante. Este ID se usa como clave de deduplicación en `fetch_company.py`
(columna `companies.infojobs_company_id`) y para enlazar ofertas con empresas
(`offers.employer_id` → `offers.company_id` → `companies.id`).

Originalmente, el código obtenía `employer_id` de `offer.author.id`:

```python
author_data = offer_data.get("author", {})
employer_id = author_data.get("id")
```

Sin embargo, el actor Apify `easyapi/infojobs-job-scraper` dejó de incluir
el objeto `author` en su respuesta JSON. Como resultado, `employer_id` era
siempre `None` para las 92 ofertas del fetch histórico (T-2).

La API sí devuelve `offer.companyLink`, que contiene un identificador de la
compañía en dos formatos:

1. **Formato largo:** `https://www.infojobs.net/{company}/em-i{HASH}`
   Ejemplo: `https://www.infojobs.net/miniso/em-i98565648564750777378730018305265317846`
2. **Formato corto:** `https://{subdomain}.ofertas-trabajo.infojobs.net`
   Ejemplo: `https://engelvolkers.ofertas-trabajo.infojobs.net`

---

## Decision

**Extraer `employer_id` desde `offer.companyLink` con dos estrategias en
orden de preferencia:**

### Estrategia 1 — Hash `em-i`

Si el `companyLink` contiene `/em-i` seguido de un identificador alfanumérico,
se extrae ese identificador como `employer_id`.

```python
m = re.search(r"/em-i([a-zA-Z0-9_]+)", link)
if m:
    return m.group(1)
```

### Estrategia 2 — Subdominio

Si no hay `em-i`, se extrae el subdominio del `companyLink`, excluyendo `www`
(que corresponde al formato largo sin `em-i`, caso no observado pero
prevenido).

```python
m = re.match(r"https?://([^.]+)\.", link)
if m and m.group(1) != "www":
    return m.group(1)
```

### Implementación

- Nueva función `_extract_employer_id(offer_data: dict) -> str | None`
  en `src/pipeline/fetch.py`
- Reemplaza la línea `author_data.get("id")` en `_upsert_offer()`
- Backfill: script inline que lee `raw_data` de cada oferta existente y
  actualiza `employer_id` — 92/92 poblados sin errores

### Ejemplos de IDs resultantes

| Formato | employer_id | company_name |
|---------|------------|--------------|
| em-i | `98565648564750777378730018305265317846` | MINISO |
| em-i | `0d2e7df9544de7b6c388d98563ffa7` | TELUS International AI |
| subdominio | `tragsa` | GRUPO TRAGSA |
| subdominio | `between` | BETWEEN Technology |
| subdominio | `eurofirms-peoplefirst` | Eurofirms People First |

---

## Discarded alternatives

- **Usar `companyLogo` UUID como ID.** La URL del logo contiene un UUID
  (`/upload/81/81dc3dda-3832-4074-a2c4-25c6ed92bb7f`) pero no hay garantía
  de que el segmento previo (`81`) o el UUID sean el company ID de InfoJobs.
- **Usar `companyName` como clave.** Inestable: el mismo `companyName` puede
  variar entre ofertas de la misma empresa (ej: "NTT DATA" vs "NTT DATA
  ofertas de empleo profesionales"), y no es un identificador canónico.
- **Consultar API de InfoJobs para resolver companyLink.** Coste de red y
  latencia innecesarios cuando el identificador ya está en el link.

---

## Consequences

- **92/92 ofertas tienen `employer_id` poblado** tras el backfill. Cobertura
  completa sobre el dataset actual.
- **IDs heterogéneos.** Los hashes `em-i` son strings largos (>20 chars);
  los subdominios son cortos (<20 chars). `fetch_company.py` los trata como
  strings opacos en `infojobs_company_id` — no hay impacto.
- **Sin cambios en `fetch_company.py`.** Usa `employer_id` como string en
  `companies.infojobs_company_id`, compatible con ambos formatos.
- **171 tests passing.** Ningún test dependía de `author.id`.
- **Si InfoJobs cambia el formato de `companyLink`** en el futuro, solo hay
  que actualizar `_extract_employer_id()` — el resto del pipeline no se entera.

---

## References

- ADR-001 — ADR as a decision documentation system
- `src/pipeline/fetch.py` — `_extract_employer_id()` implementación
- `src/pipeline/fetch_company.py` — consumidor de `employer_id`
- `MEMORIES.md` — sección "employer_id desde companyLink (mayo 2026)"
