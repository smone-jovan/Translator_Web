# Temporary API Key Exhaustion Memory

## Problem Statement
How Might We track API keys that have hit their daily quota (RPD) during an active batch translation, so we can temporarily exclude them from rotation, visually notify the user, and automatically stop the batch if all keys are exhausted?

## Recommended Direction
**The In-Memory Blacklist with Midnight Reset & UI Sync**

Instead of building a complex, persistent quota-tracking database, we will use a lightweight, robust in-memory solution:
1. **Backend RAM Blacklist**: We introduce a global Python dictionary `exhausted_keys = { "key1": "2026-06-06" }`. 
2. **Smart 429 Detection**: When the Gemini API returns a `429 Quota Exceeded` error (specifically daily limit, not just rate limit), that API key is added to the blacklist along with the current date.
3. **Smart Rotation**: `rotate_api_key` will skip any key in the blacklist. If *all* keys are blacklisted, it throws a `QuotaExhaustedError`, which explicitly stops the `ActiveBatch` and sets its status to `quota_exhausted`.
4. **Midnight Reset**: Before checking the blacklist, the system compares the stored date with `datetime.date.today()`. If it's a new day, the blacklist for that key is automatically cleared.
5. **UI Integration**: The `/api/threads/active-batch` endpoint will return the number of total keys and exhausted keys. The `BatchProgress` UI will display a small visual indicator (e.g., `🔑 1/3 Exhausted`), and if it hits 100%, it shows a clear "All Keys Exhausted" message.

## Key Assumptions to Validate
- [ ] We can reliably distinguish between a `429 Too Many Requests` (RPM rate limit) and a `429 Quota Exceeded` (RPD daily limit) from the Gemini API response.
- [ ] Users do not restart their backend server frequently enough to wipe out the RAM-based blacklist during a single reading session.
- [ ] The timezone for the "midnight reset" relies on the server's local time, which aligns with the user's expectations.

## MVP Scope
**In:**
- Python RAM-based dictionary for exhausted keys.
- Detection of Gemini Quota Exceeded errors.
- Modifying the round-robin logic to skip exhausted keys.
- Stopping the background worker if 100% of keys are exhausted.
- Updating the frontend progress bar to show a crossed-out key icon and the exhausted count.
- Auto-clearing the RAM blacklist at midnight local time.

**Out:**
- Persistent SQLite tracking of API keys.
- Token counting or preemptive limit prediction.
- A dedicated settings dashboard to manage/unblock keys manually.

## Not Doing (and Why)
- **Token Counting in DB**: Highly prone to desync and over-engineered. Relying on the actual API error is 100% accurate and requires zero DB migrations.
- **Frontend-driven Blacklisting**: Security and architectural anti-pattern. The backend should own secret management and routing.
- **Manual "Reset Key" UI Button**: The user specified they want it to reset automatically at midnight or when the server restarts. Adding a UI button adds unnecessary React state complexity for an edge case.

## Open Questions
- Is a simple icon like `🔑 1/3 Exhausted` in the existing Batch Progress bar sufficient, or do you want a Toast Notification (Pop-up) when the entire batch stops due to exhaustion?
