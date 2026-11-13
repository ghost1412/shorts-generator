// One font loader with a soft timeout, shared by fonts.ts and the per-style fonts in ShortFlow.tsx.
import { continueRender, delayRender, staticFile } from "remotion";

const SOFT_TIMEOUT_MS = 8000;

// A font that fails or is slower than SOFT_TIMEOUT_MS is given up on and the browser falls back to system fonts.
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
