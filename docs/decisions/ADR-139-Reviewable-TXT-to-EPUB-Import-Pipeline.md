# ADR-139: Reviewable TXT-to-EPUB Import Pipeline

## Status
Accepted

## Date
2026-11-01

## Context

ReadOmni already has the durable concepts needed for a book import: a `Thread`
is a book/project and a `Chapter` is an ordered unit within that book.  EPUB
upload currently creates those records immediately, while the standalone TXT
Cleaner accepts a `.txt` file and returns a cleaned download without creating a
library book.

That leaves a distinct user need unmet: a reader with a long TXT novel needs to
turn it into a navigable EPUB and, optionally, a library thread.  A direct TXT
import would be unsafe and difficult to correct because TXT files often have
inconsistent chapter headings, front matter, advertisements, duplicated
headings, and chapters that are too long to review comfortably.

The required product flow is therefore:

```text
Select TXT -> derive review drafts -> review and edit titles/content
           -> choose a new or existing thread -> confirm import
           -> export the imported chapters as EPUB
```

The wording "draft" is intentional: no `Thread` or `Chapter` may be created
until the user has reviewed the proposed sections and explicitly confirms the
target.  This is analogous to the review-before-import property of ADR-069,
but the TXT file is local content rather than a list of remote chapter URLs.

This decision must also preserve the following established constraints:

- The current TXT Cleaner remains a one-off cleanup/download tool; it is not
  repurposed into an importer (ADR-037).
- The existing Book Builder remains the authoritative EPUB generator
  (ADR-014).  The TXT importer must not add a second EPUB implementation.
- `main` and `ghost` are independent workspaces.  Database selection is
  request-scoped through `get_db`; no process-global or browser-global draft
  state may bridge workspaces (ADR-115 and ADR-118).
- The project must not add a dependency, schema migration, or persistent
  staging data solely for this feature without separate approval.

## Decision

Implement TXT-to-EPUB as a deterministic, two-phase import pipeline with a
reviewable, non-persistent draft representation.

### 1. Dedicated Import Surface

Add an explicit **Import TXT to EPUB** entry point on the Translate page.  It
must be visually and behaviorally separate from the existing **TXT Cleaner**.
The Cleaner continues to return a cleaned `.txt` download and never creates a
thread.

The review UI is a two-step responsive modal/wizard:

1. **Review and edit**
   - Shows the editable book title and an ordered list of chapter drafts.
   - Each draft exposes an editable title and body, word count, and any split
     marker such as `Part 2/3`.
   - A user may exclude a draft.  Reordering and drag-and-drop are explicitly
     out of scope for the first version; retained drafts preserve parser order.
2. **Confirm**
   - The target is selected explicitly here, not inferred from a previously
     selected Translate-page thread.
   - The user chooses **New thread** or **Existing thread** and sees a final
     count of the drafts that will be imported.
   - For an existing thread, the UI states that selected drafts are appended;
     it never replaces existing chapters.

The modal must be usable at a 375 px viewport: scrollable draft content,
reachable actions, explicit form labels, disabled controls while a request is
in flight, and no icon-only primary action.  A failed preview or confirmation
does not discard the current edits.  Closing or refreshing before confirmation
does discard drafts; this limitation is deliberate because drafts are not
persisted.

### 2. Deterministic Draft Parsing

Create a pure backend TXT-import service whose parser is independent of
FastAPI, SQLAlchemy, and filesystem writes.  Its input is decoded text and its
output is ordered draft values containing at least title, body, source chapter
ordinal, split ordinal, split total, and a server-computed word count.

The parser follows these rules:

1. **Decode strictly.** Try `utf-8-sig`, `utf-8`, `gb18030`, `big5`, and
   `shift_jis` in that order.  If all fail, reject the upload with HTTP 422;
   do not use a permissive `latin-1` / `errors="ignore"` fallback that could
   silently corrupt a novel.
2. **Reject invalid source content.** Reject an empty or whitespace-only file,
   NUL bytes, and content that cannot satisfy the preview limits below.
3. **Recognize headings only at a line boundary.** The initial supported
   patterns cover English (`Chapter 12`, `Ch. 12`), Indonesian (`Bab 12`), and
   common CJK forms (`第十二章`, `第12节`, `第3回`, `第2卷`).  Matching is
   intentionally conservative: a sentence merely mentioning "chapter" is not
   a new chapter.
4. **Preserve preface text.** Non-empty text before the first recognized
   heading becomes a `Prologue` draft.  When no heading is recognized, the
   entire file becomes a single editable `Chapter 1` source draft.
5. **Never lose or duplicate text.** Concatenating a source draft's split
   bodies, separated by the parser's normal paragraph separator, must preserve
   the source body.  Heading text is represented by the title, not duplicated
   in the body.
6. **Split only when necessary.** A source chapter over 6,000 words is divided
   at paragraph boundaries into sections as close to the limit as possible.
   Derived titles use ` — Part N/M`.  The 6,000-word threshold is a fixed
   first-version policy, not an exposed tuning setting.
7. **Prefer fidelity over the limit.** A single paragraph over the threshold
   is returned intact and flagged as oversized; the parser never cuts through
   a paragraph, sentence, Markdown image token, or dialogue solely to satisfy
   the limit.

Heading recognition is an assistive heuristic, not a claim of perfect book
structure.  The review screen is the mandatory correction surface for false
positives, missing headings, fallback titles, and oversized sections.

### 3. Preview and Confirm API Boundary

Introduce a dedicated router rather than extending the cleanup or EPUB upload
endpoints.  The proposed API contracts are:

| Endpoint | Request | Response / invariant |
| --- | --- | --- |
| `POST /api/txt-import/preview` | multipart `.txt` upload | Default book title plus parsed draft values. Performs no database write. |
| `POST /api/txt-import/confirm` | JSON: edited book metadata, included drafts, and target `{ mode: "new" }` or `{ mode: "existing", thread_id }` | `{ thread_id, chapter_ids }` after one successful database commit. |

The preview endpoint must use `read_upload_limited`, but it has a smaller
TXT-review cap of **10 MiB** even though the shared upload ceiling is 50 MiB.
A 50 MiB plain-text file would expand into a large JSON response and editable
React state, producing poor or unsafe client behavior.  The implementation
must additionally set bounded limits for the number of returned drafts and the
total reviewable character count; exceeding either returns a clear 413/422
response rather than truncating source text silently.

The confirm endpoint is authoritative.  It must validate all fields supplied
by the browser again: included-draft count, non-empty normalized title,
non-empty body, title/body length limits, total payload size, target mode, and
the existence of an existing target thread.  Server-generated ordering and
word counts replace browser-provided derived values.  Preview data is helpful
but is never trusted as a capability or authorization token.

This ADR defines a new public REST contract.  Its Pydantic models, status
codes, and error messages must be documented in code and tested before the
status becomes Accepted.

### 4. Atomic Import Semantics

Confirmation has exactly two modes:

- **New thread:** create one `Thread` with `source_type="txt"`, the confirmed
  title as both title fields, and optional author metadata.  The default title
  derives from the safe filename stem; if unavailable, use `Imported TXT`.
- **Existing thread:** query the `Thread` through the request's `get_db`
  session.  Never update existing thread metadata or chapters as a side effect
  of TXT import.

For both modes, calculate the first chapter order in the server.  A new thread
starts at `0`; an existing thread starts at `MAX(Chapter.order) + 1` (or `0`
when it has no chapters).  The client must not choose database order values.

All validation occurs before records are flushed.  The implementation then
creates the new thread, if applicable, adds all chapters, flushes to obtain
IDs, and performs one commit.  Any exception rolls back the session and
returns an error; a failed confirmation must leave neither a partial new thread
nor a partial chapter tail.  Confirmation is not server-idempotent in the
first version because drafts are deliberately non-persistent; the UI prevents
double submission by disabling its Confirm action while it is in flight.

### 5. EPUB Generation After Import

After a successful confirm response, the client calls the existing
`POST /api/threads/{thread_id}/export` EPUB endpoint with exactly the returned
`chapter_ids`.  The exporter already falls back to original titles and content
when translations do not exist, so no secondary EPUB writer is required.

Import success and EPUB download success are separate states:

- A successful import followed by a failed download still leaves a valid book
  in the chosen thread.  The UI must say so and offer retry from Book Builder.
- Exporting to an existing thread includes only the newly imported chapter IDs,
  not every prior chapter in that thread.
- EPUB metadata uses the confirmed title and author.  Existing-thread metadata
  remains unchanged unless the user edits it through the existing book-info
  flow.

### 6. Workspace, Security, and Data Boundaries

- Every route uses `Depends(get_db)` and the resulting request-scoped session.
  It must not call unscoped `SessionLocal`, mutate `ACTIVE_WORKSPACE`, create a
  global draft cache, or queue a background task holding ambiguous workspace
  identity.
- The frontend's same-origin API wrapper continues to attach `X-Workspace`.
  A thread ID from another workspace therefore resolves as not found in the
  active workspace and is never an import target.
- No filesystem path is derived from the TXT filename or content.  Filename
  extension checks are user feedback only; server-side byte/content validation
  is authoritative.
- TXT bodies are stored as text in existing database fields.  The importer does
  not execute content, fetch links, interpret HTML, or apply an LLM-based
  cleanup step.
- Markdown-style image references are preserved as text.  Their existing
  export handling remains governed by the Book Builder and image safety rules;
  this importer adds no image-fetching behavior.

### 7. Verification Required Before Acceptance

The feature is Accepted only when the following evidence exists:

1. Parser unit tests cover UTF-8 BOM, CRLF, each supported heading family,
   preface, no-heading fallback, false-looking inline text, paragraph-safe
   splitting, an unbreakable oversized paragraph, and no lost/duplicated body
   text.
2. Preview API tests cover a valid TXT file, wrong extension, empty content,
   NUL bytes, undecodable bytes, preview-size limit, and draft-count/character
   limits.
3. Confirm API tests prove creation of a TXT thread, append-after-maximum-order
   behavior, edited titles/bodies, excluded drafts, missing target 404, and a
   forced failure that leaves no partial records.
4. Workspace tests prove imports remain in the authenticated active workspace
   and cannot append to a same-numeric-ID thread in the other workspace.
5. Export integration tests prove an EPUB generated after import contains only
   the newly returned IDs and uses original content when no translation exists.
6. Manual UI QA covers the two wizard stages, keyboard/focus behavior, 375 px
   layout, confirm-double-click prevention, retained edits after API errors,
   and the distinct outcome where import succeeds but EPUB download fails.
7. Required quality gates pass: targeted pytest tests, full backend pytest
   suite, `npm run typecheck`, `npm run lint`, and `npm run build`.

## Alternatives Considered

### Directly create a thread during TXT upload

- Pros: Fewer requests and a simpler implementation.
- Cons: Creates incorrect or unwanted library data before the user can correct
  the parser; cleanup then becomes destructive.
- Rejected: Violates the requested Review and edit then Confirm workflow.

### Persist server-side drafts in a staging table

- Pros: Allows refresh/resume and server-side idempotency tokens.
- Cons: Requires schema migration, retention/cleanup policy, per-workspace
  ownership, and a security model for abandoned uploaded content.
- Rejected for v1: The user requested a review flow, not durable drafts.  The
  added persistence is disproportionate and requires separate approval.

### Convert TXT to EPUB entirely in the browser

- Pros: No new backend API or database changes.
- Cons: Cannot safely import into a selected existing thread, duplicates the
  established EPUB builder, and produces inconsistent styling/metadata.
- Rejected: Conflicts with ADR-014 and does not meet the library-import need.

### Use an LLM to detect chapters or rewrite titles

- Pros: May recognize non-standard headings.
- Cons: Adds cost, latency, nondeterminism, privacy exposure, and possible
  unwanted edits to source text.
- Rejected: Draft creation must be local, deterministic, and fully reviewable.

### Split long chapters by raw characters or tokens

- Pros: Very simple and predictable size limit.
- Cons: Breaks paragraphs, dialogue, markup, and reading continuity.
- Rejected: The reader-facing structure is more important than an exact cap.

### Treat standalone TXT Cleaner as the importer

- Pros: Reuses an existing upload control.
- Cons: Its contract is a cleaned-file download, not draft review or library
  import; changing it would break the user's mental model and ADR-037 scope.
- Rejected: Keep the actions separate.

## Consequences

### Positive

- Users can correct chapter boundaries, titles, and content before library data
  exists.
- Existing threads gain a safe append workflow without overwriting their
  metadata, chapters, reading state, or translations.
- EPUB output uses one established rendering path and is limited to the newly
  selected draft chapters.
- The implementation needs no schema migration, dependency, global mutable
  state, or background job.
- Strict decoding prevents the silent mojibake and data loss caused by
  permissive fallbacks.

### Costs and trade-offs

- Drafts are intentionally lost after a page refresh or modal close before
  confirmation.  Durable resumable imports are deferred to a future ADR.
- Heuristic heading recognition can be wrong; review is required rather than
  optional.
- The 10 MiB preview cap rejects some large archives even though the generic
  upload service supports 50 MiB.  Users can split a source file before import;
  a scalable persisted-staging design may be considered later.
- A network/download error after a committed import cannot be rolled back
  automatically, because the library record is already valid and retryable.
- Repeated confirm requests made outside the UI can create duplicate chapters;
  full server idempotency is explicitly deferred with persistent staging.

## Related Decisions

- ADR-014 — Premium Book Export System
- ADR-037 — Thread-Level TXT Cleaning and Book Builder Cleanup Preview
- ADR-069 — TOC Scraper and Bulk Import Pipeline
- ADR-115 — Request-scoped dual-workspace isolation
- ADR-118 — Frontend workspace-cache isolation

## Adoption & Hardening Notes

This ADR has been **Accepted** and fully implemented with all verification gates and test suites passing.

### Post-Implementation Hardening (Doubt-Driven Development):
1. **N+1 Query Cache in EPUB Exporter**: `ContextEngine.get_glossary_lock_rules` is queried and compiled once outside the chapter loop in `backend/routers/export.py`, reducing 2,000 queries to 1 query during 1,000-chapter book exports.
2. **Hierarchical Volume Merging & TOC Filtering**: Multi-level volume headings (`Book -> Volume -> Part -> Chapter`) merge cleanly into chapter titles while filtering empty-body Table of Contents blocks, eliminating HTTP 422 deadlocks on raw webnovel archives.
3. **Atomic Pre-Commit Attribute Capture**: `thread_id` and `chapter_ids` are captured after `db.flush()` and before `db.commit()`, eliminating the post-commit `db.refresh()` query storm.
4. **XHTML Title Escaping**: `ch_title` is escaped via `html.escape()` before being injected into EPUB XHTML templates, preventing XML corruption from `<` or `&`.
5. **Unified Smart Upload Control**: The primary upload button on `TranslatePage.tsx` accepts `.epub,.txt`, automatically routing `.txt` uploads to the reviewable import wizard.
