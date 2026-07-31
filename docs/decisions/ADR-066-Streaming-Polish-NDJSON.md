# ADR-066: Streaming Polish via NDJSON

## Status
Accepted

## Date
2026-06-11

## Context
The `/api/threads/{thread_id}/translate-titles` endpoint processes chapter titles in bulk (up to 1000+ titles in chunks of 50). In HARD polish mode, this can take 10-20 minutes of continuous AI processing. The original implementation returned a single JSON response after all chunks completed, causing:
- HTTP timeouts from browser/proxy (typically 2-minute limit)
- Frontend losing connection mid-process with no progress feedback
- Users unable to tell if the process was stuck or still working

## Decision
Refactor the polish endpoint to use **NDJSON (Newline-Delimited JSON) StreamingResponse** instead of a single JSON response.

### Backend (`polish.py`)
- Wrap the chunked processing loop in an `async def stream_generator()` that yields progress updates
- Each chunk yields: `{"status": "processing", "chunk": N, "total": M}`
- On completion: `{"status": "done", "count": X}`
- On error: `{"status": "error", "message": "..."}`
- Return `StreamingResponse(stream_generator(), media_type="application/x-ndjson")`
- In HARD mode, skip the 1-second inter-chunk delay for maximum throughput
- In SOFT mode, retain the 1-second delay to avoid rate limiting on lighter APIs

### Frontend (`ReaderPage.tsx`)
- Consume the stream body using `ReadableStream` reader to keep the HTTP connection alive
- Wait for the stream to fully complete before calling `fetchThread()` to refresh data

## Alternatives Considered

### Server-Sent Events (SSE)
- Pros: Native browser EventSource API, automatic reconnection
- Cons: Requires `text/event-stream` MIME type, more complex protocol for a simple progress update
- Rejected: NDJSON is simpler and sufficient for this use case

### WebSocket
- Pros: Full bidirectional communication, real-time progress
- Cons: Requires WebSocket infrastructure, session management, reconnection logic
- Rejected: Overkill for a unidirectional progress stream

### Increasing HTTP Timeout
- Pros: Zero code changes
- Cons: Doesn't solve the user experience problem (no progress feedback), fragile across different proxy/CDN configurations
- Rejected: Band-aid fix that doesn't address the root cause

## Consequences
- Polish operations no longer timeout regardless of chapter count
- Users see that the process is alive (connection stays open)
- HARD mode runs at maximum speed (no inter-chunk delay)
- Frontend must consume the stream body to keep connection alive
- Future polish features can extend the NDJSON protocol with richer progress data
