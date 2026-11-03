// Bundled OFL caption fonts so captions look the same on every machine:
//  - Anton (similar to Impact) for Latin text
//  - Noto Sans (bold, Latin + Greek + Cyrillic subset) so Russian/Ukrainian/Bulgarian/Greek captions are not boxes (Anton has no Cyrillic)
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
