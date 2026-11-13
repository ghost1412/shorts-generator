// Bundled OFL caption fonts so captions look the same on every machine:
//  - Anton (similar to Impact) for Latin text
//  - Noto Sans (bold, Latin + Greek + Cyrillic subset) so Russian/Ukrainian/Bulgarian/Greek captions are not boxes (Anton has no Cyrillic)
//  - Noto Sans Arabic (bold subset) for Arabic-script captions
//  - Chinese/Japanese/Korean are NOT bundled (10-18 MB per language): the Python side cuts a per-render subset (engine/script_fonts.py)
//    and passes it as the `extraFont` prop, loaded in ShortFlow.tsx as family "NotoCJK".
//  - Noto Sans Devanagari, so Hindi/Marathi/Sanskrit captions do not render as empty boxes on machines (CI, Docker)
//    that have no Devanagari system font. The browser falls back to it per character, right after Anton.
import { continueRender, delayRender, staticFile } from "remotion";

const SOFT_TIMEOUT_MS = 8000;

// Never lets a font hold a render: a font that fails or is slower than SOFT_TIMEOUT_MS is given up on and the browser falls back to
// Impact / Arial Black / system fonts (a GitHub runner once waited 178 s for one font and failed the render).
export const loadFont = (family: string, file: string, weight?: string) => {
  const handle = delayRender(`Loading ${family} caption font`, { timeoutInMilliseconds: 60000 });
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    clearTimeout(timer);
    continueRender(handle);
  };
  const timer = setTimeout(finish, SOFT_TIMEOUT_MS);
  new FontFace(family, `url(${staticFile(file)})`, weight ? { weight } : undefined)
    .load()
    .then((font) => {
      document.fonts.add(font);
      finish();
    })
    .catch(finish);
};
const load = loadFont;

load("Anton", "fonts/Anton-Regular.ttf");
load("NotoDevanagari", "fonts/NotoSansDevanagari.ttf", "100 900");
load("NotoCyrillic", "fonts/NotoSansCyrillic.ttf");
// Caveat (HANDWRITTEN style) and JetBrains Mono (TYPEWRITER style) are loaded only when that style is used, see useStyleFont in ShortFlow.tsx.
load("NotoArabic", "fonts/NotoSansArabic.ttf"); // bold, Arabic script only (Arabic/Persian/Urdu); needs RTL handling in ShortFlow.tsx
