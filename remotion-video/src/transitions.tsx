// Intro and outro transitions: a cover that opens over the first second of a clip and closes over the last one.
// Intro: the cover opens and shows the picture. Outro: the cover closes over it. The same five effects serve both.
//   tiles  - a grid of tiles that break apart and fly away (intro) or fly in and join (outro)
//   panels - two doors slide apart / together
//   iris   - a circle opens / closes
//   blinds - horizontal slats open / close
//   fade   - a plain fade from / to the colour
import React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

export const TRANSITIONS = ["tiles", "panels", "iris", "blinds", "fade"] as const;
export type TransitionName = (typeof TRANSITIONS)[number];

const W = 1080;
const H = 1920;
const ease = Easing.bezier(0.65, 0, 0.35, 1);
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const rand = (i: number, salt: number) => {
  const x = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453;
  return x - Math.floor(x);
};

// cover: 1 = the screen is fully covered, 0 = fully open.
const Tiles: React.FC<{ cover: number; color: string; join: boolean; p: number }> = ({ color, join, p }) => {
  const cols = 6;
  const rows = 10;
  const tw = W / cols;
  const th = H / rows;
  const tiles = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const i = r * cols + c;
      // tiles nearest the centre go first when breaking, last when joining, with some randomness
      const dx0 = (c + 0.5) / cols - 0.5;
      const dy0 = (r + 0.5) / rows - 0.5;
      const dist = Math.sqrt(dx0 * dx0 + dy0 * dy0) / 0.7;
      const delay = 0.45 * (0.55 * dist + 0.45 * rand(i, 1));
      const local = ease(clamp01((p - delay) / 0.55));
      const gone = join ? 1 - local : local; // 0 = in place, 1 = scattered
      const len = Math.sqrt(dx0 * dx0 + dy0 * dy0) || 1;
      const fly = 500 + 700 * rand(i, 2);
      const tx = (dx0 / len) * fly * gone + (rand(i, 3) - 0.5) * 120 * gone;
      const ty = (dy0 / len) * fly * gone + (rand(i, 4) - 0.5) * 120 * gone;
      const rot = (rand(i, 5) - 0.5) * 220 * gone;
      tiles.push(
        <div
          key={i}
          style={{
            position: "absolute",
            left: c * tw,
            top: r * th,
            width: tw + 1,
            height: th + 1,
            background: color,
            transform: `translate(${tx}px, ${ty}px) rotate(${rot}deg) scale(${1 - 0.85 * gone})`,
            opacity: 1 - gone,
            boxShadow: gone > 0.02 ? "0 6px 18px rgba(0,0,0,0.35)" : "none",
          }}
        />,
      );
    }
  }
  return <>{tiles}</>;
};

const Panels: React.FC<{ cover: number; color: string }> = ({ cover, color }) => (
  <>
    <div style={{ position: "absolute", left: 0, top: 0, width: W / 2 + 1, height: H, background: color, transform: `translateX(${-(1 - cover) * 100}%)` }} />
    <div style={{ position: "absolute", right: 0, top: 0, width: W / 2 + 1, height: H, background: color, transform: `translateX(${(1 - cover) * 100}%)` }} />
  </>
);

const Iris: React.FC<{ cover: number; color: string }> = ({ cover, color }) => {
  const r = (1 - cover) * 1250;
  return <div style={{ position: "absolute", inset: 0, background: `radial-gradient(circle at 50% 50%, transparent ${r}px, ${color} ${r + 2}px)` }} />;
};

const Blinds: React.FC<{ cover: number; color: string }> = ({ cover, color }) => {
  const n = 8;
  const h = H / n;
  return (
    <>
      {Array.from({ length: n }).map((_, i) => {
        const s = clamp01((cover * 1.5 - i * 0.07) / 0.7);
        return <div key={i} style={{ position: "absolute", left: 0, top: i * h, width: W, height: h + 1, background: color, transform: `scaleY(${s})` }} />;
      })}
    </>
  );
};

export const TransitionLayer: React.FC<{ intro?: string; outro?: string; color?: string }> = ({ intro, outro, color = "#0b0c10" }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const total = durationInFrames / fps;
  const t = frame / fps;
  const dur = Math.max(0.3, Math.min(0.9, total / 4));
  let name: string | undefined;
  let p = 0;
  let isOutro = false;
  if (intro && t < dur) {
    name = intro;
    p = t / dur;
  } else if (outro && t > total - dur) {
    name = outro;
    p = (t - (total - dur)) / dur;
    isOutro = true;
  }
  if (!name) return null;
  const q = clamp01(p);
  const cover = isOutro ? ease(q) : 1 - ease(q);
  if (name !== "tiles" && cover <= 0.001) return null;
  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 100, pointerEvents: "none", overflow: "hidden" }}>
      {name === "tiles" && <Tiles cover={cover} color={color} join={isOutro} p={q} />}
      {name === "panels" && <Panels cover={cover} color={color} />}
      {name === "iris" && <Iris cover={cover} color={color} />}
      {name === "blinds" && <Blinds cover={cover} color={color} />}
      {name === "fade" && <div style={{ position: "absolute", inset: 0, background: color, opacity: interpolate(cover, [0, 1], [0, 1]) }} />}
    </div>
  );
};
