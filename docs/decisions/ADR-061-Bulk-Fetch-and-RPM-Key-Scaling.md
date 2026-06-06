# ADR-061: Bulk Fetch Bypass and Multi-Key RPM Scaling

## Status
Accepted

## Date
2026-06-06

## Context

We encountered two distinct operational bottlenecks during batch processing:
1. **Scraping Rate Limits**: When scraping hundreds of chapters from novel hosting sites, parallel requests often trigger aggressive anti-bot protections (like Cloudflare blocks or IP bans).
2. **API Quota Waste**: Users wanted to securely save offline backups of raw Chinese novel text. The only way to get the text previously was to run a full AI Translation, burning API limits and time just to obtain the raw text.
3. **Static RPM Limits**: The system had strict built-in RPM pacing delays (e.g., Gemini 2.5 Flash waits 12.2s between requests to stay below 5 RPM). However, users with multiple API keys noticed that the speed did not scale. The application still enforced the 12.2s delay globally, regardless of how many keys were configured in the rotation pool.

## Decision

We have implemented two architectural changes to the background task engine:

### 1. Bulk Fetch (LLM Bypass)
We introduced a `fetch_only` boolean to the `BatchTranslateRequest`. When `fetch_only` is true, the `BackgroundTranslator` executes standard sequential batch jobs but **skips all LLM translation and terminology extraction calls**. 
* The system utilizes the existing `ActiveBatch` queue, enforcing a sequential lock to prevent bot protection triggers.
* A random artificial delay (`asyncio.sleep(random.uniform(1.0, 2.5))`) is injected between fetches to simulate human reading speeds.
* The chapter status is marked as `idle` instead of `done`, so it can be picked up by future actual translation batches.

### 2. Multi-Key RPM Scaling (Round-Robin Pacing)
We refactored `_enforce_pacing` inside `background_translator.py` to scale the RPM limit mathematically by the number of active API keys.
* **Key Count Division**: `required_delay = required_delay / num_keys`. For example, a 12.2s delay with 3 keys becomes a 4.06s delay.
* **Aggressive Key Rotation**: If multiple keys exist, `rotate_api_key` is called on *every single request* rather than only as a fallback during HTTP `429 Too Many Requests` errors. This guarantees that requests are evenly distributed across the key pool, strictly respecting each key's individual RPM limit while drastically speeding up the overall batch translation.

## Consequences
* **Positive**: Users can now aggressively download and archive raw chapter data overnight safely without wasting LLM quota.
* **Positive**: Adding extra API keys now directly linearly increases batch translation speed. 
* **Neutral**: Because the `GlobalSetting` is updated in the database on every key rotation, SQLite write frequency will increase during batch processing. However, because translation occurs sequentially with a minimum 1.0s delay (when skipping) or API generation time (when translating), the write volume (max ~1 write per second) is trivial for SQLite.
