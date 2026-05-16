# Design & Style Guide (style.md)

## Visual Concept
- **Theme:** Clean, minimalistic, ReadOmni-inspired dark mode.
- **Vibe:** Modern, focused on reading experience.
- **Responsiveness:** Mobile-first approach for reading on phones.

## Color Palette (ReadOmni Extracted - Shadcn UI Compatible)
```css
:root {
  --background: #151619;
  --foreground: #f2f2f3;
  --card: #1f2023;
  --card-foreground: #f2f2f3;
  --popover: #151619;
  --popover-foreground: #f2f2f3;
  --primary: #e2e6e9;
  --primary-foreground: #1c1e21;
  --secondary: #242529;
  --secondary-foreground: #f2f2f3;
  --muted: #34373c;
  --muted-foreground: #a0a4ac;
  --accent: #2c2d30;
  --accent-foreground: #f2f2f3;
  --destructive: #db5154;
  --destructive-foreground: #f2f2f3;
  --border: #282a2e;
  --input: #242529;
  --ring: #3d3f43;
  --radius: 0.5rem;
}
```

## Typography
- **Primary Font:** Tailwind default sans (`ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"`).
- **Weights:** Normal (`400`), Medium (`500`), Semibold (`600`), Bold (`700`).

## Core UI Components & Layout
1. **Top Navigation:** Brand logo, "Translate", "Context", "Discover", "Library", "Settings", "Log In".
2. **Main Input Area:** Large `<textarea>` or textbox ("Paste a URL or text to translate...").
3. **Model Selection:** Combobox (e.g. "Wu 1.5 Flash").
4. **Recent Content / Library Grid:** Image + Title + Rating layout for saved novels.

## Scraping Web Strategy
- Target structural elements: `<article>`, `div.chapter-content`, `p`.
- Strip out ads, navigation, and script tags to send clean markdown to the AI.
