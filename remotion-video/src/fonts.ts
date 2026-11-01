// Bundled OFL caption font (Anton, similar to Impact) so captions look the same on every machine.
import { continueRender, delayRender, staticFile } from "remotion";

const handle = delayRender("Loading Anton caption font");
new FontFace("Anton", `url(${staticFile("fonts/Anton-Regular.ttf")})`)
  .load()
  .then((font) => {
    document.fonts.add(font);
    continueRender(handle);
  })
  .catch(() => continueRender(handle)); // fall back to Impact / Arial Black
