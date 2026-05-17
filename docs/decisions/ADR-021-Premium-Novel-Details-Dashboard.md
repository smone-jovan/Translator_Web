# ADR-021: Premium Immersive Novel Details Dashboard with Adaptive Glassmorphism & Theme Inheritance

## Status
Accepted & Implemented

## Date
2026-05-17

## Context
Following the successful integration of the Novel Updates scraper, the platform now possesses robust and comprehensive novel metadata (Clean Chinese original title, official English title, genres list, chapter/volume status, COO status, cover image, and full synopses). 

Previously, the details page inside each thread (when a user clicked a card in their library) was functional but visual styling was plain and didn't convey a "premium, publishing-grade ebook application" experience. 

To take full advantage of the rich scraped metadata, the details page needs to be redesigned into an immersive visual dashboard that:
1. **Dazzles the User**: Provides a visually stunning, publication-quality first impression with smooth transitions and deep structural hierarchy.
2. **Inherits Theme Colors Perfectly**: Renders flawlessly across all user-selected themes (Black, OLED, White, Sepia, Omni, Obsidian) by utilizing custom-tailored CSS design tokens rather than hardcoded colors.
3. **Supports Fluid Mobile Experience**: Automatically adapts to varying screens (from iPhone 13 Pro Max to 4K desktop screens) through intelligent flex grids and scale factor modifiers.
4. **Is Integrated Seamlessly**: Exposes clear calls to action (Read Now and Batch Translate) and transitions into the chapter listing or reader panel naturally.

## Decision
We will implement an advanced visual redesign for the thread header page inside `ReaderPage.tsx` using custom Vanilla CSS variables, responsive viewport grids, and glassmorphism.

### 1. Visual Architecture and Elements
The new interface consists of a multi-tiered layout structure:
- **Immersive Backdrop Cover Blur**: If a cover image exists, we render a copy of the cover scaled to `110%`, set to absolute positioning, and styled with a heavy backdrop filter (`blur(40px)`), brightness limitation (`brightness-[0.3]`), and soft opacity (`opacity-30`). This overlays the page background with custom ambient glows matching the dominant colors of the book cover.
- **Premium Cover Art Container**: A highly styled album-art-like thumbnail showcasing the book cover with sharp rounded corners (`rounded-3xl`), detailed deep shadows (`shadow-[0_20px_50px_rgba(0,0,0,0.5)]`), subtle border highlights, and scale-up hover animations.
- **Tonal Color-Mix Badge Grid**: Genres and tags are automatically mapped onto custom pill tags styled with `bg-[color-mix(in_srgb,var(--secondary)_50%,transparent)]` and matched borders. This guarantees that tags remain legible and high-contrast in light mode, sepia, and dark OLED environments alike.
- **Dynamic Title Header Block**: Integrates:
  - The Chinese raw title inside a styled pill badge (`我怎么可能是圣女？`).
  - The English translated title styled with massive, extra-bold tracking (`tracking-tight text-3xl md:text-5xl font-black font-sans`).
  - A small subtitle showing the creator/source type.
- **Call-to-Action Studio Panel**: A high-impact row featuring:
  - **Read Now**: A vibrant, bold solid red-to-crimson gradient button with a glowing hover effect (`from-red-600 to-red-500 hover:from-red-500 hover:to-red-400`) that immediately deep-links the reader to their bookmark location.
  - **Batch Translate**: A beautiful border outline button matching the primary theme colors, opening the translation workflow directly.

### 2. Multi-Theme Adaptation & Design Tokens
Hardcoded colors are fully eliminated in favor of active semantic CSS tokens. All colors now inherit from our central theme variables:
- Backgrounds inherit from `var(--background)`.
- Cards and panel backdrops inherit from `var(--card)` or `var(--secondary)`.
- Borders inherit from `var(--border)`.
- Interactive texts inherit from `var(--primary)` or `var(--accent)`.

This ensures that:
- In **Obsidian / Dark Mode**, elements glow with elegant gold-green highlight shadows.
- In **OLED / OLED Black**, panels collapse into perfect pitch-black outlines, saving battery.
- In **Sepia / Warm**, backgrounds inherit smooth parchment hues with rich dark-chocolate typography.
- In **White / Light**, elements are bordered with crisp, clear hairline dividers and readable dark gray text.

### 3. Mobile-First Layout Responsiveness
To make the design look incredibly premium on mobile devices (e.g. mobile phones, iPads), the header adapts via standard CSS grid utilities:
- **Layout Flow**: On desktop viewports, details are laid out horizontally in a split flex row (`flex-row items-start gap-8`). On mobile viewports, details collapse smoothly into a vertical stack (`flex-col items-center gap-6 text-center`).
- **Typography Scale**: English Title text sizes adjust fluidly from `text-3xl font-black` (mobile) to `text-5xl font-black` (desktop) to ensure zero layout overflows.
- **Grid Badge Limits**: Metadata lists adapt to single-line or multi-line wrap grids based on the horizontal window width, ensuring readability is maintained without truncating crucial series data.

## Consequences
- **Outstanding User Impression**: Redefines the landing page experience, transforming the app into a publication-grade personal library dashboard.
- **Legibility Across Scales**: Excellent typographic contrast and visual hierarchy on all screens.
- **Zero Maintenance Overhead**: By utilizing semantic tokens, any new themes added to the platform in the future will automatically apply to this dashboard with zero extra coding required.
- **Full Operational Continuity**: Retains all bookmarks, scroll behaviors, prefetching, and translation features intact.
