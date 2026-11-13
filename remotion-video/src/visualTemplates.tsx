// Visual templates: a designed "skin" laid over the picture, under the hook title and the captions.
// Each template is a small React component. Text slots are optional: a slot with no text is simply not drawn, so a template never
// shows made-up names or handles. The picture itself (crop, captions, hook) is untouched.
import React, { createContext, useContext } from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { ClockContext } from "./clock";
import { z } from "zod";

export const VISUAL_TEMPLATES = ["podcast-card", "neon-frame", "news-banner", "minimal-line", "title-bars", "retro-vhs", "film-bars", "polaroid", "episode-badge", "story-progress"] as const;

export const templateTextSchema = z.object({
  show: z.string().optional(), // show / channel title
  speaker: z.string().optional(), // name of the person talking
  role: z.string().optional(), // their role, e.g. "Host" or "Guest, Astrophysicist"
  handle: z.string().optional(), // @handle
  headline: z.string().optional(), // news-banner headline
  label: z.string().optional(), // small label before the headline, default "LATEST"
  cta: z.string().optional(), // end-card line in the last seconds, e.g. "Follow @handle for more"
});
export type TemplateText = z.infer<typeof templateTextSchema>;

// Vertical sizes and offsets below are written for a 1080x1920 frame; V scales them to the real frame height (16:9 and square outputs).
const V = createContext<(n: number) => number>((n) => n);
const useV = () => useContext(V);

type LayerProps = { text: TemplateText; accent?: string; hookSeconds: number };

const FONT = "Anton, NotoDevanagari, NotoCyrillic, NotoArabic, NotoCJK, Impact, Arial Black, sans-serif";
const BODY = "NotoCyrillic, NotoDevanagari, NotoArabic, NotoCJK, 'Segoe UI', Arial, sans-serif";

const clean = (s: string | undefined, max: number) => {
  const t = (s || "").replace(/\s+/g, " ").trim();
  return Array.from(t).length > max ? Array.from(t).slice(0, max - 1).join("") + "…" : t;
};

const useProgress = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const clock = useContext(ClockContext);
  const t = (clock ? clock.offset : 0) + frame / fps;
  const total = clock ? clock.total : durationInFrames / fps;
  return { frame, fps, t, total, progress: Math.min(1, Math.max(0, t / Math.max(0.1, total))) };
};

// The closing line: slides up in the last 2.4 s.
const EndCta: React.FC<{ text?: string; accent: string; bottom: number }> = ({ text, accent, bottom }) => {
  const { t, total } = useProgress();
  const line = clean(text, 48);
  if (!line || total < 6) return null;
  const k = interpolate(t, [total - 2.4, total - 2.0], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  if (k <= 0) return null;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom, display: "flex", justifyContent: "center", opacity: k, transform: `translateY(${(1 - k) * 40}px)` }}>
      <div style={{ background: accent, color: "#0b0c10", fontFamily: BODY, fontWeight: 800, fontSize: 46, padding: "18px 44px", borderRadius: 999, boxShadow: "0 10px 30px rgba(0,0,0,0.45)" }}>
        {line}
      </div>
    </div>
  );
};

// 1. PODCAST CARD: speaker name tag, show chip, soft scrims, thin progress bar.
const PodcastCard: React.FC<LayerProps> = ({ text, accent = "#FFB703" }) => {
  const v = useV();
  const { frame, fps, t, progress } = useProgress();
  const name = clean(text.speaker, 28);
  const role = clean(text.role, 38);
  const show = clean(text.show, 24);
  const slide = spring({ frame: frame - 8, fps, config: { damping: 16, stiffness: 120 } });
  const out = interpolate(t, [6.0, 6.5], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", top: v(0), left: 0, right: 0, height: v(360), background: "linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0))" }} />
      <div style={{ position: "absolute", bottom: v(0), left: 0, right: 0, height: v(420), background: "linear-gradient(rgba(0,0,0,0), rgba(0,0,0,0.5))" }} />
      {name && (
        <div style={{ position: "absolute", top: v(120), left: 56, display: "flex", alignItems: "stretch", opacity: out, transform: `translateX(${(1 - slide) * -520}px)` }}>
          <div style={{ width: 12, background: accent, borderRadius: 6 }} />
          <div style={{ background: "rgba(10,10,14,0.82)", padding: "16px 30px 16px 24px", borderRadius: "0 16px 16px 0" }}>
            <div style={{ fontFamily: FONT, fontSize: 56, color: "#fff", textTransform: "uppercase", letterSpacing: 1, lineHeight: 1.05 }}>{name}</div>
            {role && <div style={{ fontFamily: BODY, fontSize: 30, color: accent, fontWeight: 700, marginTop: 4 }}>{role}</div>}
          </div>
        </div>
      )}
      {show && (
        <div style={{ position: "absolute", top: v(126), right: 56, background: accent, color: "#0b0c10", fontFamily: BODY, fontWeight: 800, fontSize: 30, padding: "10px 22px", borderRadius: 999, textTransform: "uppercase", letterSpacing: 1 }}>
          {show}
        </div>
      )}
      <div style={{ position: "absolute", left: 0, bottom: v(0), height: v(10), width: `${progress * 100}%`, background: accent }} />
      <EndCta text={text.cta} accent={accent} bottom={v(330)} />
    </AbsoluteFill>
  );
};

// 2. NEON FRAME: glowing border, handle chip, progress along the top of the frame.
const NeonFrame: React.FC<LayerProps> = ({ text, accent = "#00F0FF" }) => {
  const v = useV();
  const { t, progress } = useProgress();
  const pulse = 0.75 + 0.25 * Math.sin(t * 3.2);
  const handle = clean(text.handle || text.show, 26);
  const second = "#FF2BD6";
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", inset: 26, borderRadius: 44, border: `6px solid ${accent}`, boxShadow: `0 0 ${24 * pulse}px ${accent}, inset 0 0 ${28 * pulse}px ${accent}66, 0 0 ${60 * pulse}px ${second}88` }} />
      <div style={{ position: "absolute", top: v(58), left: 80, right: 80, height: v(8), borderRadius: 4, background: "rgba(255,255,255,0.18)" }}>
        <div style={{ width: `${progress * 100}%`, height: "100%", borderRadius: 4, background: `linear-gradient(90deg, ${accent}, ${second})`, boxShadow: `0 0 14px ${accent}` }} />
      </div>
      {handle && (
        <div style={{ position: "absolute", top: v(92), left: 0, right: 0, display: "flex", justifyContent: "center" }}>
          <div style={{ fontFamily: BODY, fontWeight: 800, fontSize: 34, color: "#fff", background: "rgba(8,8,20,0.7)", padding: "8px 26px", borderRadius: 999, border: `3px solid ${second}`, textShadow: `0 0 12px ${second}` }}>
            {handle}
          </div>
        </div>
      )}
      <EndCta text={text.cta} accent={accent} bottom={v(300)} />
    </AbsoluteFill>
  );
};

// 3. NEWS BANNER: label + headline bar at the top, scrolling ticker at the bottom, progress bar.
const NewsBanner: React.FC<LayerProps> = ({ text, accent = "#E63946" }) => {
  const v = useV();
  const { frame, fps, t, progress } = useProgress();
  const headline = clean(text.headline || text.show, 60);
  const label = clean(text.label || "LATEST", 14).toUpperCase();
  const ticker = clean([text.show, text.handle, text.cta].filter(Boolean).join("   •   "), 120);
  const slide = spring({ frame: frame - 4, fps, config: { damping: 18, stiffness: 110 } });
  const tickerText = ticker ? `${ticker}   •   ${ticker}   •   ` : "";
  const shift = (t * 140) % Math.max(1, tickerText.length * 12);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      {headline && (
        <div style={{ position: "absolute", top: v(120), left: 0, right: 0, display: "flex", transform: `translateX(${(1 - slide) * -1100}px)` }}>
          <div style={{ background: accent, color: "#fff", fontFamily: FONT, fontSize: 46, padding: "18px 28px", letterSpacing: 2 }}>{label}</div>
          <div style={{ background: "rgba(255,255,255,0.96)", color: "#111", fontFamily: BODY, fontWeight: 800, fontSize: 44, padding: "18px 30px", flex: 1, whiteSpace: "nowrap", overflow: "hidden" }}>{headline}</div>
        </div>
      )}
      {ticker && (
        <div style={{ position: "absolute", left: 0, right: 0, bottom: v(150), height: v(78), background: "rgba(10,10,16,0.88)", borderTop: `5px solid ${accent}`, overflow: "hidden", display: "flex", alignItems: "center" }}>
          <div style={{ whiteSpace: "nowrap", fontFamily: BODY, fontWeight: 700, fontSize: 36, color: "#fff", transform: `translateX(${-shift}px)` }}>{tickerText.repeat(6)}</div>
        </div>
      )}
      <div style={{ position: "absolute", left: 0, bottom: v(0), height: v(10), width: `${progress * 100}%`, background: accent }} />
    </AbsoluteFill>
  );
};

// 4. MINIMAL LINE: a hairline progress bar, a small handle, and a closing line.
const MinimalLine: React.FC<LayerProps> = ({ text, accent = "#FFFFFF" }) => {
  const v = useV();
  const { progress } = useProgress();
  const handle = clean(text.handle || text.show, 26);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", left: 56, right: 56, bottom: v(120), height: v(4), background: "rgba(255,255,255,0.28)", borderRadius: 2 }}>
        <div style={{ width: `${progress * 100}%`, height: "100%", background: accent, borderRadius: 2 }} />
      </div>
      {handle && (
        <div style={{ position: "absolute", left: 56, bottom: v(142), fontFamily: BODY, fontWeight: 700, fontSize: 32, color: "#fff", textShadow: "0 2px 10px rgba(0,0,0,0.7)" }}>{handle}</div>
      )}
      <EndCta text={text.cta} accent={accent} bottom={v(200)} />
    </AbsoluteFill>
  );
};

// 5. TITLE BARS: a solid band with the headline on top and a handle band at the bottom (the classic "title over the video" format).
const TitleBars: React.FC<LayerProps> = ({ text, accent = "#6D28D9" }) => {
  const v = useV();
  const { frame, fps, progress } = useProgress();
  const headline = clean(text.headline || text.show, 70);
  const handle = clean(text.handle, 26);
  const slide = spring({ frame, fps, config: { damping: 18, stiffness: 120 } });
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", top: v(0), left: 0, right: 0, height: v(290), background: accent, display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 56px 0", transform: `translateY(${(1 - slide) * -290}px)`, boxShadow: "0 10px 30px rgba(0,0,0,0.35)" }}>
        {headline && <div style={{ fontFamily: FONT, color: "#fff", fontSize: headline.length > 44 ? 58 : 72, textTransform: "uppercase", textAlign: "center", lineHeight: 1.08, letterSpacing: 1 }}>{headline}</div>}
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: v(0), height: v(210), background: "#0d0d12", borderTop: `6px solid ${accent}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
        {handle && <div style={{ fontFamily: BODY, fontWeight: 800, color: "#fff", fontSize: 44 }}>{handle}</div>}
      </div>
      <div style={{ position: "absolute", left: 0, bottom: v(204), height: v(6), width: `${progress * 100}%`, background: "#fff" }} />
      <EndCta text={text.cta} accent="#fff" bottom={v(250)} />
    </AbsoluteFill>
  );
};

// 6. RETRO VHS: scanlines, a blinking REC light, a running timecode, PLAY label.
const RetroVhs: React.FC<LayerProps> = ({ text, accent = "#FF3B30" }) => {
  const v = useV();
  const { t, fps } = useProgress();
  const pad = (n: number, w = 2) => String(Math.floor(n)).padStart(w, "0");
  const code = `${pad(t / 3600)}:${pad((t / 60) % 60)}:${pad(t % 60)}:${pad((t % 1) * fps)}`;
  const blink = Math.floor(t * 1.6) % 2 === 0;
  const label = clean(text.show || text.handle, 22);
  const mono = "'Courier New', Consolas, monospace";
  const shadow = "2px 2px 0 rgba(0,0,0,0.8), -1px 0 rgba(255,0,80,0.6), 1px 0 rgba(0,200,255,0.6)";
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", inset: 0, background: "repeating-linear-gradient(0deg, rgba(0,0,0,0.22) 0px, rgba(0,0,0,0.22) 2px, rgba(0,0,0,0) 3px, rgba(0,0,0,0) 6px)" }} />
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)" }} />
      <div style={{ position: "absolute", top: v(90), left: 70, display: "flex", alignItems: "center", gap: 18, fontFamily: mono, fontWeight: 700, fontSize: 52, color: "#fff", textShadow: shadow }}>
        <div style={{ width: 34, height: v(34), borderRadius: 17, background: accent, opacity: blink ? 1 : 0.15, boxShadow: blink ? `0 0 18px ${accent}` : "none" }} />
        REC
      </div>
      <div style={{ position: "absolute", top: v(98), right: 70, fontFamily: mono, fontWeight: 700, fontSize: 42, color: "#fff", textShadow: shadow }}>{code}</div>
      <div style={{ position: "absolute", bottom: v(150), left: 70, fontFamily: mono, fontWeight: 700, fontSize: 46, color: "#fff", textShadow: shadow }}>{"▶"} PLAY</div>
      {label && <div style={{ position: "absolute", bottom: v(150), right: 70, fontFamily: mono, fontWeight: 700, fontSize: 40, color: "#fff", textShadow: shadow }}>{label}</div>}
      <EndCta text={text.cta} accent="#fff" bottom={v(260)} />
    </AbsoluteFill>
  );
};

// 7. FILM BARS: letterbox bars with a small title card that fades in and out.
const FilmBars: React.FC<LayerProps> = ({ text, accent = "#E6C068" }) => {
  const v = useV();
  const { t, progress } = useProgress();
  const name = clean(text.speaker || text.show, 30);
  const sub = clean(text.role || text.handle, 40);
  const k = interpolate(t, [0.4, 1.0, 5.2, 5.8], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", top: v(0), left: 0, right: 0, height: v(250), background: "#000" }} />
      <div style={{ position: "absolute", bottom: v(0), left: 0, right: 0, height: v(300), background: "#000" }} />
      <div style={{ position: "absolute", bottom: v(296), left: 0, height: v(4), width: `${progress * 100}%`, background: accent }} />
      {name && (
        <div style={{ position: "absolute", bottom: v(110), left: 70, right: 70, opacity: k, transform: `translateY(${(1 - k) * 18}px)` }}>
          <div style={{ fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 58, color: "#fff", letterSpacing: 4, textTransform: "uppercase" }}>{name}</div>
          {sub && <div style={{ fontFamily: BODY, fontSize: 30, color: accent, letterSpacing: 6, textTransform: "uppercase", marginTop: 8 }}>{sub}</div>}
        </div>
      )}
      <EndCta text={text.cta} accent={accent} bottom={v(320)} />
    </AbsoluteFill>
  );
};

// 8. POLAROID: a coloured mat around a rounded picture, with the handle written on the mat.
const Polaroid: React.FC<LayerProps> = ({ text, accent = "#F5EFE6" }) => {
  const v = useV();
  const { progress } = useProgress();
  const line = clean(text.show || text.headline, 34);
  const handle = clean(text.handle, 26);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", top: v(70), left: 52, right: 52, bottom: v(330), borderRadius: 26, boxShadow: `0 0 0 3000px ${accent}, inset 0 0 0 3px rgba(0,0,0,0.12)` }} />
      <div style={{ position: "absolute", left: 52, right: 52, bottom: v(130), textAlign: "center", color: "#2a2622" }}>
        {line && <div style={{ fontFamily: "'Segoe Script', 'Brush Script MT', cursive, " + BODY, fontSize: v(64), lineHeight: 1.1 }}>{line}</div>}
        {handle && <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: v(34), marginTop: 10, opacity: 0.7 }}>{handle}</div>}
      </div>
      <div style={{ position: "absolute", left: 52, right: 52, bottom: v(60), height: v(6), borderRadius: 3, background: "rgba(0,0,0,0.12)" }}>
        <div style={{ width: `${progress * 100}%`, height: "100%", borderRadius: 3, background: "#2a2622" }} />
      </div>
      <EndCta text={text.cta} accent="#2a2622" bottom={v(345)} />
    </AbsoluteFill>
  );
};

// 9. EPISODE BADGE: a round badge with the episode or tip number, the show name beside it. For series.
const EpisodeBadge: React.FC<LayerProps> = ({ text, accent = "#FF5A1F" }) => {
  const v = useV();
  const { frame, fps, progress } = useProgress();
  const label = clean(text.label, 7).toUpperCase();
  const show = clean(text.show, 26);
  const pop = spring({ frame: frame - 3, fps, config: { damping: 11, stiffness: 150 } });
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      {(label || show) && (
        <div style={{ position: "absolute", top: v(110), left: 60, display: "flex", alignItems: "center", gap: 22, transform: `scale(${pop})`, transformOrigin: "left center" }}>
          {label && (
            <div style={{ width: 170, height: v(170), borderRadius: 85, background: accent, border: "8px solid #fff", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 10px 28px rgba(0,0,0,0.45)" }}>
              <div style={{ fontFamily: FONT, fontSize: label.length > 4 ? 54 : 74, color: "#fff", letterSpacing: 1 }}>{label}</div>
            </div>
          )}
          {show && <div style={{ fontFamily: BODY, fontWeight: 800, fontSize: 40, color: "#fff", background: "rgba(10,10,14,0.78)", padding: "12px 26px", borderRadius: 14, textShadow: "0 2px 6px rgba(0,0,0,0.5)" }}>{show}</div>}
        </div>
      )}
      <div style={{ position: "absolute", left: 0, bottom: v(0), height: v(12), width: `${progress * 100}%`, background: accent }} />
      <EndCta text={text.cta} accent={accent} bottom={v(300)} />
    </AbsoluteFill>
  );
};

// 10. STORY PROGRESS: a thin story-style bar on top with a round initial and the handle.
const StoryProgress: React.FC<LayerProps> = ({ text, accent = "#FFFFFF" }) => {
  const v = useV();
  const { progress } = useProgress();
  const handle = clean(text.handle || text.show, 24);
  const initial = (Array.from(handle.replace(/^@/, ""))[0] || "").toUpperCase();
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", top: v(0), left: 0, right: 0, height: v(220), background: "linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0))" }} />
      <div style={{ position: "absolute", top: v(56), left: 40, right: 40, height: v(8), borderRadius: 4, background: "rgba(255,255,255,0.35)" }}>
        <div style={{ width: `${progress * 100}%`, height: "100%", borderRadius: 4, background: accent }} />
      </div>
      {handle && (
        <div style={{ position: "absolute", top: v(100), left: 40, display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ width: 84, height: v(84), borderRadius: 42, background: "linear-gradient(135deg, #F9CE34, #EE2A7B, #6228D7)", border: "4px solid #fff", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: BODY, fontWeight: 800, fontSize: 40, color: "#fff" }}>{initial}</div>
          <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 38, color: "#fff", textShadow: "0 2px 8px rgba(0,0,0,0.6)" }}>{handle}</div>
        </div>
      )}
      <EndCta text={text.cta} accent="#fff" bottom={v(300)} />
    </AbsoluteFill>
  );
};

export const TemplateLayer: React.FC<{ template?: string; text?: TemplateText; accent?: string; hookSeconds: number }> = ({ template, text, accent, hookSeconds }) => {
  const { height } = useVideoConfig();
  const scale = (n: number) => (height >= 1900 ? n : (n * height) / 1920);
  const props = { text: text || {}, accent, hookSeconds };
  return <V.Provider value={scale}>{pick(template, props)}</V.Provider>;
};

const pick = (template: string | undefined, props: LayerProps) => {
  switch (template) {
    case "podcast-card": return <PodcastCard {...props} />;
    case "neon-frame": return <NeonFrame {...props} />;
    case "news-banner": return <NewsBanner {...props} />;
    case "minimal-line": return <MinimalLine {...props} />;
    case "title-bars": return <TitleBars {...props} />;
    case "retro-vhs": return <RetroVhs {...props} />;
    case "film-bars": return <FilmBars {...props} />;
    case "polaroid": return <Polaroid {...props} />;
    case "episode-badge": return <EpisodeBadge {...props} />;
    case "story-progress": return <StoryProgress {...props} />;
    default: return null;
  }
};
