// Visual templates: a designed "skin" laid over the picture, under the hook title and the captions.
// Each template is a small React component. Text slots are optional: a slot with no text is simply not drawn, so a template never
// shows made-up names or handles. The picture itself (crop, captions, hook) is untouched.
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { z } from "zod";

export const VISUAL_TEMPLATES = ["podcast-card", "neon-frame", "news-banner", "minimal-line"] as const;

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
  const t = frame / fps;
  const total = durationInFrames / fps;
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
  const { frame, fps, t, progress } = useProgress();
  const name = clean(text.speaker, 28);
  const role = clean(text.role, 38);
  const show = clean(text.show, 24);
  const slide = spring({ frame: frame - 8, fps, config: { damping: 16, stiffness: 120 } });
  const out = interpolate(t, [6.0, 6.5], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 360, background: "linear-gradient(rgba(0,0,0,0.55), rgba(0,0,0,0))" }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 420, background: "linear-gradient(rgba(0,0,0,0), rgba(0,0,0,0.5))" }} />
      {name && (
        <div style={{ position: "absolute", top: 120, left: 56, display: "flex", alignItems: "stretch", opacity: out, transform: `translateX(${(1 - slide) * -520}px)` }}>
          <div style={{ width: 12, background: accent, borderRadius: 6 }} />
          <div style={{ background: "rgba(10,10,14,0.82)", padding: "16px 30px 16px 24px", borderRadius: "0 16px 16px 0" }}>
            <div style={{ fontFamily: FONT, fontSize: 56, color: "#fff", textTransform: "uppercase", letterSpacing: 1, lineHeight: 1.05 }}>{name}</div>
            {role && <div style={{ fontFamily: BODY, fontSize: 30, color: accent, fontWeight: 700, marginTop: 4 }}>{role}</div>}
          </div>
        </div>
      )}
      {show && (
        <div style={{ position: "absolute", top: 126, right: 56, background: accent, color: "#0b0c10", fontFamily: BODY, fontWeight: 800, fontSize: 30, padding: "10px 22px", borderRadius: 999, textTransform: "uppercase", letterSpacing: 1 }}>
          {show}
        </div>
      )}
      <div style={{ position: "absolute", left: 0, bottom: 0, height: 10, width: `${progress * 100}%`, background: accent }} />
      <EndCta text={text.cta} accent={accent} bottom={330} />
    </AbsoluteFill>
  );
};

// 2. NEON FRAME: glowing border, handle chip, progress along the top of the frame.
const NeonFrame: React.FC<LayerProps> = ({ text, accent = "#00F0FF" }) => {
  const { t, progress } = useProgress();
  const pulse = 0.75 + 0.25 * Math.sin(t * 3.2);
  const handle = clean(text.handle || text.show, 26);
  const second = "#FF2BD6";
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", inset: 26, borderRadius: 44, border: `6px solid ${accent}`, boxShadow: `0 0 ${24 * pulse}px ${accent}, inset 0 0 ${28 * pulse}px ${accent}66, 0 0 ${60 * pulse}px ${second}88` }} />
      <div style={{ position: "absolute", top: 58, left: 80, right: 80, height: 8, borderRadius: 4, background: "rgba(255,255,255,0.18)" }}>
        <div style={{ width: `${progress * 100}%`, height: "100%", borderRadius: 4, background: `linear-gradient(90deg, ${accent}, ${second})`, boxShadow: `0 0 14px ${accent}` }} />
      </div>
      {handle && (
        <div style={{ position: "absolute", top: 92, left: 0, right: 0, display: "flex", justifyContent: "center" }}>
          <div style={{ fontFamily: BODY, fontWeight: 800, fontSize: 34, color: "#fff", background: "rgba(8,8,20,0.7)", padding: "8px 26px", borderRadius: 999, border: `3px solid ${second}`, textShadow: `0 0 12px ${second}` }}>
            {handle}
          </div>
        </div>
      )}
      <EndCta text={text.cta} accent={accent} bottom={300} />
    </AbsoluteFill>
  );
};

// 3. NEWS BANNER: label + headline bar at the top, scrolling ticker at the bottom, progress bar.
const NewsBanner: React.FC<LayerProps> = ({ text, accent = "#E63946" }) => {
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
        <div style={{ position: "absolute", top: 120, left: 0, right: 0, display: "flex", transform: `translateX(${(1 - slide) * -1100}px)` }}>
          <div style={{ background: accent, color: "#fff", fontFamily: FONT, fontSize: 46, padding: "18px 28px", letterSpacing: 2 }}>{label}</div>
          <div style={{ background: "rgba(255,255,255,0.96)", color: "#111", fontFamily: BODY, fontWeight: 800, fontSize: 44, padding: "18px 30px", flex: 1, whiteSpace: "nowrap", overflow: "hidden" }}>{headline}</div>
        </div>
      )}
      {ticker && (
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 150, height: 78, background: "rgba(10,10,16,0.88)", borderTop: `5px solid ${accent}`, overflow: "hidden", display: "flex", alignItems: "center" }}>
          <div style={{ whiteSpace: "nowrap", fontFamily: BODY, fontWeight: 700, fontSize: 36, color: "#fff", transform: `translateX(${-shift}px)` }}>{tickerText.repeat(6)}</div>
        </div>
      )}
      <div style={{ position: "absolute", left: 0, bottom: 0, height: 10, width: `${progress * 100}%`, background: accent }} />
    </AbsoluteFill>
  );
};

// 4. MINIMAL LINE: a hairline progress bar, a small handle, and a closing line.
const MinimalLine: React.FC<LayerProps> = ({ text, accent = "#FFFFFF" }) => {
  const { progress } = useProgress();
  const handle = clean(text.handle || text.show, 26);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", zIndex: 30 }}>
      <div style={{ position: "absolute", left: 56, right: 56, bottom: 120, height: 4, background: "rgba(255,255,255,0.28)", borderRadius: 2 }}>
        <div style={{ width: `${progress * 100}%`, height: "100%", background: accent, borderRadius: 2 }} />
      </div>
      {handle && (
        <div style={{ position: "absolute", left: 56, bottom: 142, fontFamily: BODY, fontWeight: 700, fontSize: 32, color: "#fff", textShadow: "0 2px 10px rgba(0,0,0,0.7)" }}>{handle}</div>
      )}
      <EndCta text={text.cta} accent={accent} bottom={200} />
    </AbsoluteFill>
  );
};

export const TemplateLayer: React.FC<{ template?: string; text?: TemplateText; accent?: string; hookSeconds: number }> = ({ template, text, accent, hookSeconds }) => {
  const props = { text: text || {}, accent, hookSeconds };
  switch (template) {
    case "podcast-card": return <PodcastCard {...props} />;
    case "neon-frame": return <NeonFrame {...props} />;
    case "news-banner": return <NewsBanner {...props} />;
    case "minimal-line": return <MinimalLine {...props} />;
    default: return null;
  }
};
