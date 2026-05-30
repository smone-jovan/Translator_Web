# ADR-048: Cleanup Logic Hardening

## Status
Accepted

## Date
2026-05-30

## Context
The cleanup system (`CleanerTools`) had several issues that caused false positives and data loss:

1. **Overly aggressive ad detection**: Patterns like `\.com`, `\.net`, `\.org` matched ANY line containing these substrings — even legitimate story content mentioning domains.
2. **Hallucination stripper on original text**: `strip_garbled_hallucination_lines()` was applied to both original Chinese text and translated text. The hallucination detector uses Latin/CJK token ratios that can incorrectly flag legitimate CJK content.
3. **ORM mutation in preview**: The `cleanup-preview` endpoint ran cleaners on live ORM objects, then called `db.rollback()`. The Python objects remained dirty in memory even after rollback.
4. **Duplicate URL detection**: `AD_LINE_PATTERNS` had `https?://` and `www\.`, then `_is_ad_or_web_noise()` checked the same patterns again.

## Decision

### Fix 1: Stricter Ad Detection
- Removed broad TLD patterns (`www\.`, `https?://`) from `AD_LINE_PATTERNS`.
- `_is_ad_or_web_noise()` now only matches full URLs: `https?://\S{4,}` and `www\.\S{4,}`.
- Bare domain mentions (e.g., "telegram", "discord") still match via specific patterns.

### Fix 2: Hallucination Stripper Flag
- Added `is_translated: bool = False` parameter to `clean_text_block()`.
- `strip_garbled_hallucination_lines()` only runs when `is_translated=True`.
- `run_txt_cleaner()` passes `is_translated=True` only for translated content.
- Original Chinese text is never processed by the hallucination stripper.

### Fix 3: Preview Endpoint Rewrite
- `cleanup-preview` now works with string copies instead of ORM objects.
- Builds `chapter_copies` list with title/body strings.
- Runs EPUB cleaner logic (false chapter detection, merge) on copies.
- Runs TXT cleaner logic on remaining copies.
- Compiles preview text from cleaned copies.
- No ORM mutation, no rollback needed.

### Fix 4: Remove Duplicate Detection
- Removed `https?://` and `www\.` from `AD_LINE_PATTERNS`.
- `_is_ad_or_web_noise()` handles URL detection exclusively.

## Alternatives Considered

### Use Alembic for migrations instead of auto-migration
- **Pros**: Proper migration tooling, rollback support.
- **Cons**: Adds dependency; current auto-migration works for this project's scale.
- **Rejected**: Premature optimization for a single-user app.

### Disable hallucination stripper entirely
- **Pros**: Eliminates false positives.
- **Cons**: Loses real hallucination detection for translated text.
- **Rejected**: The stripper is valuable for translated content; just needs to skip original text.

## Consequences
- **Positive:** Ad detection no longer strips legitimate story content mentioning domains.
- **Positive:** Original Chinese text is preserved without hallucination-stripper interference.
- **Positive:** Preview endpoint is safe — no ORM state pollution.
- **Negative/Risk:** Some real ad lines with bare domain mentions may now be missed (trade-off for precision).
