// NOTE (2026-11-13): package.json lists only *.css under sideEffects, so the bundler drops `import "./fonts"` and NONE of these loads run:
// captions use the machine's own fonts. Listing this file made every font load for the first time, and on GitHub's runner a browser
// tab then stalled in the first font (E2E render failed after 58 s, soft timeout or not). Fix it only together with a CI run.
// Bundled OFL caption fonts so captions look the same on every machine:
//  - Anton (similar to Impact) for Latin text
//  - Noto Sans (bold, Latin + Greek + Cyrillic subset) so Russian/Ukrainian/Bulgarian/Greek captions are not boxes (Anton has no Cyrillic)
//  - Noto Sans Arabic (bold subset) for Arabic-script captions
//  - Chinese/Japanese/Korean are NOT bundled (10-18 MB per language): the Python side cuts a per-render subset (engine/script_fonts.py)
//    and passes it as the `extraFont` prop, loaded in ShortFlow.tsx as family "NotoCJK".
//  - Noto Sans Devanagari, so Hindi/Marathi/Sanskrit captions do not render as empty boxes on machines (CI, Docker)
//    that have no Devanagari system font. The browser falls back to it per character, right after Anton.

import { loadFont } from "./loadFont";

const load = loadFont;

load("Anton", "fonts/Anton-Regular.ttf");
load("NotoDevanagari", "fonts/NotoSansDevanagari.ttf", "100 900");
load("NotoCyrillic", "fonts/NotoSansCyrillic.ttf");
// Caveat (HANDWRITTEN style) and JetBrains Mono (TYPEWRITER style) are loaded only when that style is used, see useStyleFont in ShortFlow.tsx.
load("NotoArabic", "fonts/NotoSansArabic.ttf"); // bold, Arabic script only (Arabic/Persian/Urdu); needs RTL handling in ShortFlow.tsx
