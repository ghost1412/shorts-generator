// --auto_zoom: punch-in / slow push-in on the picture layer. Mirrors engine/auto_zoom.py::zoom_scale_at.
export type ZoomMoment = { start: number; end: number; scale: number; rise: number };

const RETURN_SECONDS = 0.45;

const easeOut = (p: number) => {
  const c = Math.min(1, Math.max(0, p));
  return 1 - Math.pow(1 - c, 3);
};
const easeInOut = (p: number) => {
  const c = Math.min(1, Math.max(0, p));
  return c * c * (3 - 2 * c);
};

export const zoomScaleAt = (t: number, moments: ZoomMoment[] | undefined): number => {
  let best = 1;
  for (const m of moments ?? []) {
    const rise = Math.max(0.01, m.rise);
    if (t < m.start || t > m.end + RETURN_SECONDS) continue;
    let env: number;
    if (t < m.start + rise) env = easeOut((t - m.start) / rise);
    else if (t <= m.end) env = 1;
    else env = 1 - easeInOut((t - m.end) / RETURN_SECONDS);
    best = Math.max(best, 1 + (m.scale - 1) * env);
  }
  return best;
};
