# ADR 033: Premium Reader UX & Mobile Interface Refinements

## Context
Following the implementation of persistent cross-device reading progress, the actual reading user experience required polishing to meet a "premium" standard akin to Apple Books or Kindle. We identified several specific UX friction points:
1. The floating "Scroll-To-Top" button was overly aggressive, rendering at the very top of a chapter when it had no use, and its visual design was a static, rudimentary square.
2. The mobile reader lacked an accessible way to toggle settings or jump back to the chapter list without scrolling all the way back to the top or hunting for hidden headers.
3. The absolute bottom of the reading columns contained massive, empty `div` spacers to prevent bottom-toolbar overlap, leading to a jarring "blank white void" at the end of every chapter.
4. The Library Grid cards featured a redundant direct "Delete" icon that cluttered the mobile view and posed an accidental deletion risk, despite the delete action already existing safely within the card's `MoreVertical` (three-dot) menu.

## Decision

We instituted a set of targeted UI/UX refinements using advanced Tailwind styling and conditional React rendering:

1. **Morphing SVG Radial Progress Button:**
   - The scroll-to-top button now remains completely hidden until `scrollProgress > 5`, preventing visual spam at the start of a chapter.
   - The button's physical shape utilizes dynamic border-radius calculation (`Math.min(50, 16 + (scrollProgress / 100) * 34)%`), smoothly morphing from a rounded-square (`rounded-2xl`) into a perfect circle as the user nears the chapter's end.
   - We overlaid a premium, absolute-positioned `<svg>` with a dynamically animated `strokeDashoffset` to draw a crisp radial progress circle around the border as the user scrolls.

2. **Dedicated Mobile Floating Toolbar:**
   - We introduced a new fixed bottom toolbar specifically for the `ReaderPage.tsx` mobile layout (`md:hidden`).
   - This toolbar only renders when reading a chapter (`!showChapterList`) and respects the user's viewport interaction (`controlsVisible` state fades it in/out upon tapping or scrolling).
   - We stripped away heavy actions (like Batch Translate, Download, or Save) from this mobile bar, strictly limiting it to the two most essential navigational elements: **List** (Chapter List) and **Settings**.

3. **"End of Chapter" Premium Divider:**
   - We replaced the giant blank `h-28` spacers at the bottom of the content containers with a sophisticated divider.
   - The divider utilizes semi-transparent gradient horizontal lines bounding a subtle "End of Chapter" uppercase badge, anchored by a glowing primary-colored dot (`shadow-[0_0_8px_rgba(var(--primary-rgb),0.5)]`).
   - This explicitly signals the end of content gracefully while still providing enough padded height (`h-20`) to scroll comfortably past the text on all form factors.

4. **Library Card De-Cluttering:**
   - We removed the direct `Trash2` icon action from the hover state of the `LibraryBookCard`. The deletion workflow is now exclusively routed through the card's Material-UI `Menu`, ensuring a cleaner interface and preventing accidental taps on touch screens.

## Consequences
- **Positive:** The reading experience feels significantly more refined, engaging, and alive. The morphing progress button provides direct, beautiful tactile feedback.
- **Positive:** Mobile users have immediate, non-intrusive access to settings and chapter lists without screen clutter.
- **Positive:** The end of a chapter feels like a deliberate design resolution rather than missing content.
- **Positive:** Less accidental book deletions due to the removal of the direct card delete icon.

## Status
Accepted
