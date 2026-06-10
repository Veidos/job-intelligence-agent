# ADR-016: Custom Scraper to Replace Apify for InfoJobs Offers

**Date:** 2026-06-09
**Type:** `architecture` `dependency`
**Status:** `completed` (2026-06-10)
**Component:** `src/pipeline/fetch.py`, `src/pipeline/infojobs_scraper.py`

---

## Context

The current pipeline uses `alvaraaz/infojobs-actor` (`lRxJmbuhggr0LU3uj`) on Apify to fetch job offers from InfoJobs. This actor uses Puppeteer to scrape InfoJobs' public search page and returns a limited set of fields:

```
code, title, description, city, link, contractType, workday, teleworking,
publishedAt, companyName, companyLogo, companyLink, states, upsellings,
executive, newBOId
```

Critical structured data from the InfoJobs offer page is **not captured** by the Apify actor:

| Field | Captured | Source |
|-------|----------|--------|
| Description (free text) | ✅ | `description` field |
| Title | ✅ | `title` field |
| City | ✅ | `city` field |
| Work mode | ✅ | `teleworking` field |
| Contract type | ✅ | `contractType` field |
| Salary | ❌ | Not present in Apify payload |
| **Experience min** | ❌ | LLM infers 0 from description (wrong: real value is 3 years) |
| **Studies required** | ❌ | Not present in Apify payload |
| **Languages required** | ❌ | Not present in Apify payload |
| **Knowledge / Skills** | ❌ | LLM extracts 1-2 generic skills instead of 8+ real ones |
| **Sector** | ❌ | Not present in Apify payload |

The consequence: the scoring pipeline receives only 1-2 skills per offer (extracted by gemma4 from the free-text description), producing inflated scores because:
- `M_core` and `M_sec` are computed over too few skills
- `experience_min` defaults to 0, giving `F_exp = 1.0`
- Structured requirements like languages, studies, and specific knowledge are invisible to the pipeline

Additionally, Apify costs ~$2.70/month ($0.09/run × 30 days) for a service we could replicate with HTTP requests.

## Decision

**Replace the Apify actor with a custom scraper written in Python** using `requests` + `BeautifulSoup` (or `lxml`) that:

1. **Search phase:** Sends HTTP GET to InfoJobs search result pages (same URLs currently used with Apify), parses the HTML list to extract offer codes, titles, and detail links.
2. **Detail phase:** For each new offer, sends HTTP GET to the individual offer page and extracts:
   - All "Requisitos" structured fields (estudios mínimos, experiencia mínima, idiomas requeridos, conocimientos necesarios, sector)
   - Free-text description
   - Salary, contract type, work mode, workday
   - Publication date, company, city, province
3. **Persistence:** Same 3-phase fetch design (persist raw → upsert → enrich) but with our own raw data.

## Discarded alternatives

1. **Keep Apify + add separate detail scraper** — More complex (two sources), still paying $2.70/month, and the search results also have data quality issues (wrong experience_min, missing salary).

2. **InfoJobs official API** — InfoJobs developer portal is open, but requires OAuth with real user accounts and has usage restrictions. Not viable for an automated pipeline.

3. **Replace Apify with a different Apify actor** — Other actors (`easyapi/infojobs-job-scraper`, `shahidirfan/infojobs-scraper`) have similar limitations. None extract the "Requisitos" structured section.

## Consequences

### Positive
- Full control over extracted fields (including estudios, idiomas, conocimientos)
- Experience min, salary, and skills are extracted directly from HTML, not inferred by LLM
- $0 cost per run (no Apify credits)
- No dependency on third-party actor maintenance or uptime
- Same search URLs, same keywords — no change to search_config or keyword system

### Negative
- Need to implement and maintain HTML parsing logic for InfoJobs
- InfoJobs HTML changes could break extraction (mitigation: use resilient selectors + fallbacks)
- Slightly more code to maintain (~200-300 lines for search + detail + parser)

### Migration strategy
- New scraper runs alongside Apify during validation
- Apify remains as fallback until the new scraper is validated on real data
- Flag `--use-apify` in run.py to toggle between scraper and Apify during transition
- **Completed 2026-06-10:** Apify dependency fully removed; scraper propio is the only fetch path.
  See `src/pipeline/infojobs_scraper.py` and `scraper_raw_responses` table.

---

## Implementation outline

```python
# src/pipeline/infojobs_scraper.py

def search_infojobs(keywords: list[str]) -> list[dict]:
    """GET search results page, parse offer list."""

def scrape_offer_detail(offer_id: str, link: str) -> dict:
    """GET individual offer page, parse all structured fields."""

def parse_requisitos(soup: BeautifulSoup) -> dict:
    """Extract estudios, experiencia, idiomas, conocimientos from HTML."""
```

## Impact on existing code

| File | Change |
|------|--------|
| `src/pipeline/fetch.py` | Replaced Apify `actor_client.call()` with `InfoJobsScraper` + `InfoJobsParser` |
| `src/pipeline/infojobs_scraper.py` | New: `SearchStub`, `RawOfferDetail` contracts; `InfoJobsParser` (HTML) + `InfoJobsScraper` (HTTP) |
| `src/pipeline/run.py` | Updated to call `run_fetch_scraper()` instead of `run_fetch()` |
| `src/db/schema.sql` | Added `scraper_raw_responses` table (append-only, same pattern as `apify_raw_responses`) |
| `src/db/migrate.py` | Added migration for `scraper_raw_responses` |
| `tests/unit/test_scraper.py` | 33 tests against real HTML snapshots (Beca + Senior) |
| `requirements.txt` | Removed `apify_client`, `apify_shared`; added `beautifulsoup4`, `lxml`, `curl_cffi` |
| `.env.example` | `APIFY_TOKEN` no longer required |
| `docs/PIPELINE.md` | Step 1 updated to reflect custom scraper |
