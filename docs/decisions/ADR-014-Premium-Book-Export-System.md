# ADR-014: Premium Book Export System

## Status
Accepted

## Date
2026-05-17

## Context
Users want to read translated content offline on e-readers. They require a way to bundle chapters into a portable format (EPUB) with custom branding (Author name, Cover image) and the ability to select specific chapters.

## Decision
Implement a "Book Builder" export system consisting of a React-based configuration modal and a Python-based EPUB generation service.

### Technical Specifications:
1. **Format Support**: Primary format is **EPUB** (using `EbookLib` or similar). Secondary fallback is **TXT**.
2. **Metadata**: Support custom Author name and Cover image (uploaded via frontend as Base64/Multipart).
3. **Selection Logic**: Users can select chapters using a checklist. Only the **translated content** (titles and body) will be used.
4. **Design Aesthetic**: The export modal will follow the project's "Premium" design system (Glassmorphism, animated transitions).
5. **API Contract**:
   - `POST /api/threads/{id}/export`
   - Payload: `{ format: string, author: string, cover: string(base64), chapter_ids: number[] }` (Default author: "SMONE")

## Alternatives Considered
- **Client-side PDF generation**: Rejected because PDFs are not reflowable and provide a poor e-reader experience compared to EPUB.
- **Always export all chapters**: Rejected because users often translate only portions of a novel or want to export in "volumes".

## Consequences
- **Positive**: High user satisfaction, professional-grade output, offline accessibility.
- **Negative**: Increased server-side processing for large books; image handling adds complexity to the backend.
- **Security**: Need to validate image uploads to prevent malicious file execution.
