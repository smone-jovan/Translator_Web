# ADR-019: Custom Book Cover Personalization System

## Status
Accepted

## Date
2026-05-17

## Context
A key differentiator for a premium reading application is the visual aesthetics of the bookshelf. In prior versions:
1. Novel covers were represented by generic text badges or raw placeholder divs, limiting the high-end feel.
2. Generating fallbacks manually led to repetitive layouts across novels without custom covers.
3. To facilitate multi-device synchronization (e.g., from PC to iPhone via local IP LAN) without setting up complex multi-user backend media upload folders and static URL serving directories, we needed a completely portable, high-fidelity storage approach that integrates into our existing SQLite schema.

## Decision
Implement a hybrid **Custom Book Cover Personalization System** that supports portable client-side processed image payloads and direct Web URLs:
1. **Database Schema Extension**: Added `cover_image: Mapped[Optional[str]] = mapped_column(Text)` to the `Thread` model. Schema auto-migration inspects the columns at startup and safely adds this column (`ALTER TABLE threads ADD COLUMN cover_image TEXT`) without deleting database contents.
2. **REST API Endpoint**: Exposed `PUT /api/threads/{thread_id}/cover` accepting either absolute web URLs or Base64 data strings to cleanly persist the covers.
3. **Client-Side Canvas Compression**: Built a canvas-based image downscaler inside the customization modal to crop images to a 3:4 aspect ratio, downscale resolution to `300x400`, and export as a low-overhead compressed JPEG data string under `100KB`. This ensures the SQLite database remains highly compact and portable.
4. **Dynamic Title-Seeded Gradients**: Built an algorithmic HSL string-hashing fallback system based on the book's title to draw custom, modern gradient covers with centralized glassmorphic initials whenever a custom cover is absent.
5. **Bookshelf Grid & Carousel Sync**: Updated components across both the main shelf grid and the Continue Reading history carousel to render covers with premium visual feedback and micro-animations.

## Alternatives Considered

### Server-Side Static Folder Uploads
- **Pros**: Kept database sizes strictly binary-free.
- **Cons**: Broken multi-device synchronization over local IPs unless local port mappings, network mounts, or file sync utilities are configured.
- **Rejected**: Extremely high setup friction; Base64 downscaled strings are completely self-contained and synchronize instantly over any connection.

## Consequences
- Every book on the shelf immediately looks premium, utilizing either dynamic, visual gradients or personal image files.
- Novels are fully portable and synchronizable across laptops, tablets, and iPhones without custom media routing.
- The UI features gorgeous, theme-aware overlays matching Light, Dark, OLED, Omni, and Sepia viewports.
