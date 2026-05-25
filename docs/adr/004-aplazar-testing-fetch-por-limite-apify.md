# 004 — Postpone T-2 and T-3 testing due to Apify API limit

**Date:** 2026-05-22
**Type:** `operational`
**Status:** `active`

## Context

Test T-2 (fetch.py with `sinceDate=_24_HOURS` in real production) requires
running the Apify actor `lRxJmbuhggr0LU3uj`. When attempting it, the error:

> `Monthly usage hard limit exceeded`

was obtained.

The Apify FREE plan has 5 USD/month credit. It was exhausted during
previous development (last real fetch: 2026-05-19). 0.30€ remain but the
monthly hard limit prevents any execution, even with `maxItems=3`.

**Additional dependency detected (2026-05-22):** T-3 (fetch_company.py)
is also blocked. The `employer_id` field is captured from the Apify
response in `fetch.py` (`author.id` from InfoJobs). The 147 offers in DB
have `employer_id = NULL`, so `fetch_company.py` finds no data
to process. T-3 shares the same root cause as T-2.

## Decision

Postpone T-2 and T-3 until the next Apify billing cycle (June 2026).
Continue with T-4 to T-9 using the 147 existing offers in DB and local Ollama.

## Discarded alternatives

- **Pay for a higher tier:** not justified for MVP testing, the FREE
  plan covers normal pipeline usage (~2-3 USD/month).
- **Switch to another data source (Indeed, LinkedIn, Jobicy):** requires
  new adapter development. Not viable for testing what is already built.
- **Force test with another Apify actor:** the limit is per account, not per actor.

## Consequences

- T-2 and T-3 remain in ⏳ pending status, not ❌ failed.
- The real pipeline has not been validated end-to-end with a real fetch against InfoJobs.
- Deduplication by `source_id` was already tested with 147 offers in DB.
- `build_search_urls` and the `sinceDate` parameter are validated at unit test level
  with cassettes (test_fetch_cassettes.py).
- `fetch_company.py` cannot be tested without `employer_id` in the offers.
- In June 2026, T-2 and T-3 will be resumed with priority before any other work.
