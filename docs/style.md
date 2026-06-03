# Design & Style Guide (style.md)

## Visual Concept
- **Theme:** Multi-theme support with Obsidian Night as default. Six presets available.
- **Vibe:** Modern, focused on reading experience (Glassmorphism, dark-first).
- **Responsiveness:** Mobile-first approach for reading on phones.

## Theme Presets (CSS `data-theme` Attribute)
Aplikasi mendukung 6 preset visual yang disimpan di server (`GlobalSetting`) dan diaplikasikan via `data-theme` attribute pada `<html>`.

| Theme | Attribute | Background | Foreground | Primary | Card |
|:---|:---|:---|:---|:---|:---|
| **Obsidian Night (Default)** | `:root` | #0a0a0c | #f2f2f7 | #00f2fe | #121214 |
| **Black** | `data-theme="black"` | #111418 | #f2f2f3 | #e2e6e9 | #181c22 |
| **OLED** | `data-theme="oled"` | #000000 | #f2f2f3 | #e2e6e9 | #0a0a0a |
| **White** | `data-theme="white"` | #f8fafc | #0f172a | #0f172a | #ffffff |
| **Sepia** | `data-theme="sepia"` | #f5f1e8 | #4a3f35 | #4a3f35 | #fdfcf9 |
| **Omni** | `data-theme="omni"` | #0f2b60 | #e0e7ff | #818cf8 | #153573 |

### CSS Variable System
Semua komponen menggunakan CSS variables melalui `var(--background)`, `var(--foreground)`, dsb. Variabel-variabel ini didefinisikan di `src/index.css`. Berdasarkan ADR-028, variabel tema telah dikeluarkan dari `@layer base` agar mendapatkan tingkat prioritas spesifisitas CSS tertinggi dan tidak ter-override oleh ekstensi dark-mode otomatis browser.

Token utama:
- `--background`, `--foreground` — warna dasar halaman
- `--card`, `--card-foreground` — warna kartu/container
- `--primary`, `--primary-foreground` — warna aksi utama
- `--secondary`, `--secondary-foreground` — warna sekunder
- `--muted`, `--muted-foreground` — warna teks subdued
- `--accent`, `--accent-foreground` — warna sorotan
- `--destructive`, `--destructive-foreground` — warna peringatan/hapus
- `--border`, `--input`, `--ring` — warna border, input, dan focus ring

## Component Patterns

### 1. Settings Overlay (Floating Modal)
- **Position:** Absolute (top-right).
- **Style:** Backdrop-blur, thin border, semi-transparent card.
- **Controls:** Consolidated typography (Size +/-) and translation actions.

### 2. Glassmorphism Card
```css
.glass {
  background-color: color-mix(in srgb, var(--card) 85%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
  box-shadow: 0 4px 20px rgba(74, 63, 53, 0.08);
}

.glass-subtle {
  background-color: color-mix(in srgb, var(--secondary) 50%, transparent);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid color-mix(in srgb, var(--border) 50%, transparent);
}
```

### 3. Reader Interface
- **Layout:** Side-by-side (Original/Translated) on desktop, Stacked on mobile.
- **Font:** Google Font "Atkinson Hyperlegible" atau sans-serif bersih.
- **Line Height:** 1.8 (Leading-relaxed) untuk kenyamanan membaca lama.

## Typography
- **Primary Font:** Atkinson Hyperlegible (imported via Google Fonts).
- **Fallback Chain:** `ui-sans-serif, system-ui, sans-serif`.
- **Weights:** Normal (`400`), Bold (`700`), Italic (`400i`, `700i`).
- **Scale:** Base 18px (adjustable via reader settings).
- **Font Smoothing:** antialiased (WebKit + Moz).

## Animation Guidelines
- **Transitions:** `duration-300` untuk opening overlays.
- **Micro-interactions:** Subtle pulse pada status "Translating...".
- **Scrolling:** Smooth scroll behavior.
- **Fade-in:** `fadeIn 0.2s ease-in-out` with `translateY(4px)` for page entrance.

## Scrollbar Styling
- **Width:** 6px (thin, non-intrusive).
- **Track:** `var(--background)`.
- **Thumb:** `var(--muted)` → `var(--muted-foreground)` on hover.
- **Border Radius:** 3px.
