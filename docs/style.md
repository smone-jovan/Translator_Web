# Design & Style Guide (style.md)

## Visual Concept
- **Theme:** Clean, minimalistic, ReadOmni-inspired dark mode + Multi-theme support (Sepia, OLED, etc.).
- **Vibe:** Modern, focused on reading experience (Glassmorphism).
- **Responsiveness:** Mobile-first approach for reading on phones.

## Theme Presets (Shadcn UI Compatible)
Aplikasi mendukung beberapa preset visual yang dapat diatur via `ReaderPage` settings overlay.

| Theme | Background | Foreground | Accent |
|:---|:---|:---|:---|
| **OLED** | #000000 | #FFFFFF | #3B82F6 |
| **Sepia** | #F4ECD8 | #5B4636 | #D2B48C |
| **Omni (Default)** | #151619 | #F2F2F3 | #E2E6E9 |

## Component Patterns

### 1. Settings Overlay (Floating Modal)
- **Position:** Absolute (top-right).
- **Style:** Backdrop-blur, thin border, semi-transparent card.
- **Controls:** Consolidated typography (Size +/-) and translation actions.

### 2. Glassmorphism Card
```css
.glass-card {
  background: rgba(21, 22, 25, 0.7);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.05);
}
```

### 3. Reader Interface
- **Layout:** Side-by-side (Original/Translated) on desktop, Stacked on mobile.
- **Font:** Google Font "Atkinson Hyperlegible" atau sans-serif bersih.
- **Line Height:** 1.8 (Leading-relaxed) untuk kenyamanan membaca lama.

## Typography
- **Primary Font:** Inter / Atkinson Hyperlegible.
- **Weights:** Normal (`400`), Bold (`700`).
- **Scale:** Base 18px (adjustable via reader settings).

## Animation Guidelines
- **Transitions:** `duration-300` untuk opening overlays.
- **Micro-interactions:** Subtle pulse pada status "Translating...".
- **Scrolling:** Smooth scroll behavior.
