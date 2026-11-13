// Bundled OFL caption fonts so captions look the same on every machine:
//  - Anton (similar to Impact) for Latin text
//  - Noto Sans (bold, Latin + Greek + Cyrillic subset) so Russian/Ukrainian/Bulgarian/Greek captions are not boxes (Anton has no Cyrillic)
//  - Noto Sans Arabic (bold subset) for Arabic-script captions
//  - Chinese/Japanese/Korean are NOT bundled (10-18 MB per language): the Python side cuts a per-render subset (engine/script_fonts.py)
//    and passes it as the `extraFont` prop, loaded in ShortFlow.tsx as family "NotoCJK".
//  - Noto Sans Devanagari, so Hindi/Marathi/Sanskrit captions do not render as empty boxes on machines (CI, Docker)
//    that have no Devanagari system font. The browser falls back to it per character, right after Anton.
import { continueRender, delayRender, staticFile } from "remotion";

const load = (family: string, file: string, weight?: string) => {
  const handle = delayRender(`Loading ${family} caption font`);
  new FontFace(family, `url(${staticFile(file)})`, weight ? { weight } : undefined)
    .load()
    .then((font) => {
      document.fonts.add(font);
      continueRender(handle);
    })
    .catch(() => continueRender(handle)); // fall back to Impact / Arial Black / system fonts
};

load("Anton", "fonts/Anton-Regular.ttf");
load("NotoDevanagari", "fonts/NotoSansDevanagari.ttf", "100 900");
load("NotoCyrillic", "fonts/NotoSansCyrillic.ttf");
load("Caveat", "fonts/Caveat.ttf", "400 700"); // HANDWRITTEN caption style (OFL)
load("JetBrainsMono", "fonts/JetBrainsMono.ttf", "100 800"); // TYPEWRITER caption style (OFL)
load("NotoArabic", "fonts/NotoSansArabic.ttf"); // bold, Arabic script only (Arabic/Persian/Urdu); needs RTL handling in ShortFlow.tsx
