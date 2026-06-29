# ADR-022: Anti-bot hardening del scraper InfoJobs

**Estado:** Active
**Fecha:** 2026-06-29
**Contexto:** ADR-016 (custom scraper replace Apify)

## Problema

Distil Networks (bot protection de InfoJobs) bloquea el scraper tras ~80-150
detail requests por IP. El delay uniforme con jitter (4-6s) era detectable como
patrón de automatización. La sesión 2026-06-15 documentó un bloqueo total de
detail pages para "Ingeniero de Procesos" que requirió delay 2.0→4.0s + jitter
+ fingerprint rotatorio como parche temporal.

## Decisión

5 cambios simultáneos que constituyen la estrategia anti-bot definitiva:

### 1. Sleep log-normal (distribución humana)

```
# Antes (detectable como bot):
time.sleep(delay + random.uniform(0, jitter))  # ~4-6s

# Después (simula lectura humana):
base = random.lognormvariate(mu=2.5, sigma=0.6)  # mediana ~12s
time.sleep(max(8.0, min(base, 45.0)))            # clamp [8, 45]s
```

La log-normal modela tiempos de lectura real: la mayoría de pausas son cortas
(~10-15s) pero ocasionalmente hay pausas largas (~30-45s). Un bot con jitter
uniforme nunca genera esa cola larga.

### 2. Lockfile 20h entre runs

`data/.last_infojobs_run` almacena timestamp Unix del último fetch exitoso.

- Mínimo 20h entre ejecuciones (compatible con cron diario 9:00).
- Protegido contra corrupción: `try/except (ValueError, OSError)` → `elapsed=inf`.
- Solo se persiste si `total_raw > 0` y no es dry-run.
- Se escribe al finalizar `run_fetch_scraper()`, no al iniciar.

### 3. Máximo 8 details por sesión

`MAX_DETAILS_PER_SESSION = 8` en `fetch.py`. Aplicado en el loop de detail
fetches, no en `search()`. Los stubs de búsqueda se recolectan completos
(~1 request por keyword, costo despreciable) pero solo los primeros 8 details
por sesión se fetchean.

Rango seguro: 8 details × ~15s c/u + sleep entre keywords = ~30-60min por
ejecución completa.

### 4. Headers HTTP reales

Cada detail request incluye headers que simulan navegación desde búsqueda:

```
Referer: https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={query}
Sec-Fetch-Site: same-origin
Sec-Fetch-Mode: navigate
```

`_fetch()` acepta `headers: dict | None` como parámetro opcional.

### 5. Fingerprints solo Chromium

```
_FINGERPRINTS = ["chrome131", "chrome124", "chrome120", "chrome119", "edge101"]
```

Safari eliminado. Un fingerprint TLS de Safari desde una IP que históricamente
ha enviado solo Chrome es una señal de inconsistencia para Distil Networks.
Edge 101 se conserva porque Edge Linux existe y es común en entornos
corporativos/dev.

## Alternativa rechazada: Camoufox

Se evaluó re-implementar CamoufoxScraper (rotación de sesión cada 8-10 details).

**Razón del rechazo:** Con IP estática, Distil correlaciona todas las sesiones
independientemente del fingerprint del browser. Camoufox mitiga el fingerprinting
TLS/HTTP2 pero no la correlación por IP. El intento anterior terminó en bloqueo
total; repetirlo desde la misma IP solo aceleraría ese resultado.

**Decisión:** curl_cffi con anti-bot hardening (este ADR) es suficiente mientras
la IP no esté marcada. Si la IP queda bloqueada definitivamente, la solución es
proxy residencial rotatorio, no Camoufox.

## Consecuencias

- **Positivas:** El scraper debería funcionar indefinidamente mientras la IP no
  esté marcada. El perfil de requests es indistinguible de un usuario humano
  (pausas largas, referer real, fingerprint coherente).
- **Negativas:** Fetch completo tarda ~30-60min. El lockfile impide ejecuciones
  múltiples en el mismo día. Compatible con cron diario pero no con re-ejecuciones
  tras fallos parciales.
- **Futuro:** Si la IP queda bloqueada a pesar de este hardening, la única
  solución viable es proxy residencial rotatorio (nuevo ADR). No re-abrir
  Camoufox.
