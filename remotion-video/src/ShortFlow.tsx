import { emojiForWord, emojiFileName } from "./captionEmoji";
import { zoomScaleAt } from "./autoZoom";
import {
  Audio,
  OffthreadVideo,
  Html5Video, // supports `loop` (OffthreadVideo does not)
  Img,
  useCurrentFrame,
  useVideoConfig,
  Sequence,
  AbsoluteFill,
  Loop,
  interpolate,
  spring,
  staticFile,
  delayRender,
  continueRender,
} from "remotion";
import React, { useEffect, useState } from "react";
import { z } from "zod";

// Bundled fonts first (fonts.ts), then the per-render CJK subset ("NotoCJK", see useExtraFont), then system fonts.
const CAPTION_FONT = "Anton, NotoDevanagari, NotoCyrillic, NotoArabic, NotoCJK, Impact, Arial Black, sans-serif";

// Hebrew/Arabic-script text. Such words need direction:rtl on the caption row (first spoken word on the right) and no
// letter-spacing (any spacing breaks the cursive joins between Arabic letters).
// ranges: Hebrew..Arabic Extended (0590-08FF), Hebrew/Arabic presentation forms A (FB1D-FDFF) and B (FE70-FEFF)
const RTL_RANGES: [number, number][] = [[0x0590, 0x08ff], [0xfb1d, 0xfdff], [0xfe70, 0xfeff]];
const isRtl = (s: string) =>
  Array.from(s).some((ch) => {
    const c = ch.codePointAt(0) ?? 0;
    return RTL_RANGES.some(([lo, hi]) => c >= lo && c <= hi);
  });

// Scripts whose glyphs must not get letter-spacing: Arabic/Hebrew (breaks the joins), CJK (already full-width) and
// Devanagari (spacing disables the conjunct ligatures).
const NO_SPACING_RE = /[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uf900-\ufaff\u0900-\u097f]/;
const noLetterSpacing = (s: string) => isRtl(s) || NO_SPACING_RE.test(s);

// "#RRGGBB" + alpha (0..1) -> rgba(); used to derive glows from the --caption_color accent
const withAlpha = (hex: string, a: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

// --- HELPER FOR SAFE ASSET URLS ---
const getAssetUrl = (url: string | undefined | null) => {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) {
    return url;
  }
  return staticFile(url);
};

export const wordSchema = z.object({
  word: z.string(),
  start: z.number(), // in seconds
  end: z.number(),   // in seconds
});

export const backgroundSchema = z.object({
  path: z.string(),
  start: z.number(),
  end: z.number(),
  type: z.enum(["video", "image"]),
  caption: z.string().optional(),
  orientation: z.enum(["portrait", "landscape"]).optional(),
  clipDuration: z.number().optional(), // seconds; used to loop clips shorter than their slot
});

export const thisOrThatSchema = z.object({
  optionA: z.string(),
  optionB: z.string(),
  imageA: z.string(),
  imageB: z.string(),
});

export const rankItemSchema = z.object({
  name: z.string(),
  image: z.string(),
  tier: z.string(),
  start: z.number(),
  end: z.number(),
});

export const rankItSchema = z.object({
  items: z.array(rankItemSchema),
});

export const captionThisSchema = z.object({
  image: z.string(),
  promptText: z.string(),
});

export const emojiGuessSchema = z.object({
  emojis: z.string(),
  answer: z.string(),
  hint: z.string().optional(),
});

export const funnyExplainerStepSchema = z.object({
  step_title: z.string().optional(),
  text: z.string().optional(),
  visual_prompt: z.string().optional(),
  sound_effect: z.string().optional(),
  sarcastic_note: z.string().optional(),
});

export const funnyExplainerSchema = z.object({
  title: z.string().optional(),
  hook: z.string().optional(),
  scene_steps: z.array(funnyExplainerStepSchema).optional(),
  outro: z.string().optional(),
});

export const teachCardSchema = z.object({
  type: z.string().default("general"),
  title: z.string().optional(),
  word_or_phrase: z.string().optional(),
  original_script: z.string().optional(),
  phonetic: z.string().optional(),
  translation: z.string().optional(),
  breakdown: z.array(z.string()).optional(),
  example_sentence: z.string().optional(),
  dish_name: z.string().optional(),
  prep_time: z.string().optional(),
  ingredients: z.array(z.string()).optional(),
  steps: z.array(z.string()).optional(),
  concept: z.string().optional(),
  code_snippet: z.string().optional(),
  key_takeaway: z.string().optional(),
});

export const shortFlowSchema = z.object({
  audioUrl: z.string(),
  bgMusicUrl: z.string().optional(),
  bgMusicVolume: z.number().default(0.15),
  words: z.array(wordSchema),
  mode: z.enum(["FACTS", "STORY", "THIS_OR_THAT", "RANK_IT", "CAPTION_THIS", "NEWS", "NEWS_SERIOUS", "RIDDLE", "EMOJI_GUESS", "PHOTO_REEL", "FUNNY_EXPLAINER", "TEACH"]),
  category: z.string().default("general"),
  titleText: z.string().optional(),
  subtitleYPos: z.number().default(1150), // in pixels (out of 1920)
  captionStyle: z.enum(["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "KARAOKE", "NEON", "BAR"]).default("HORMOZI"),
  captionColor: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(), // --caption_color: accent colour of the active word (any style)
  captionEmoji: z.boolean().default(false), // keyword emoji, drawn from bundled Twemoji PNGs (public/emoji): no system font needed
  hookText: z.string().optional(), // --hook_overlay: big title shown at the start of the clip
  hookSeconds: z.number().default(2.8),
  zoomMoments: z.array(z.object({ start: z.number(), end: z.number(), scale: z.number(), rise: z.number() })).optional(), // --auto_zoom: picture-layer punch-ins (captions never zoom)
  extraFont: z.object({ family: z.string(), url: z.string() }).optional(), // per-render CJK subset font (static file path)
  avatarUrl: z.string().optional(),
  avatarAspect: z.number().optional(), // width / height of the avatar asset; square art is not cropped to 16:9
  avatarKeyed: z.boolean().optional(), // transparent cut-out (green screen removed): drawn without the framed window
  backgrounds: z.array(backgroundSchema).default([]),
  thisOrThat: thisOrThatSchema.optional(),
  rankIt: rankItSchema.optional(),
  captionThis: captionThisSchema.optional(),
  emojiGuess: emojiGuessSchema.optional(),
  funnyExplainer: funnyExplainerSchema.optional(),
  teachCard: teachCardSchema.optional(),
});

type ShortFlowProps = z.infer<typeof shortFlowSchema>;

// Helper function to check if asset path is video
const isVideoAsset = (src: string) => {
  const s = src.toLowerCase();
  return s.endsWith(".mp4") || s.endsWith(".mov") || s.endsWith(".webm");
};

// Keyword emoji drawn from a bundled Twemoji PNG (no system emoji font needed). Renders nothing when there is no emoji.
const CaptionEmoji: React.FC<{ word: string; size: number }> = ({ word, size }) => {
  const e = emojiForWord(word);
  if (!e) return null;
  return (
    <Img
      src={staticFile(`emoji/${emojiFileName(e)}.png`)}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        marginLeft: "12px",
        verticalAlign: "middle",
        display: "inline-block",
        filter: "drop-shadow(4px 4px 0 rgba(0,0,0,0.9))",
      }}
    />
  );
};

// Big title for the first seconds of a clip (--hook_overlay): springs in, holds, fades out.
const HookOverlay: React.FC<{ text: string; seconds: number; fps: number; frame: number }> = ({ text, seconds, fps, frame }) => {
  const t = frame / fps;
  if (t > seconds) return null;
  const pop = spring({ frame, fps, config: { damping: 12, stiffness: 160, mass: 0.8 } });
  const opacity = interpolate(t, [seconds - 0.35, seconds], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const fontSize = text.length > 36 ? 84 : text.length > 22 ? 100 : 118;
  return (
    <div
      style={{
        position: "absolute",
        top: "330px",
        width: "100%",
        display: "flex",
        justifyContent: "center",
        padding: "0 60px",
        boxSizing: "border-box",
        zIndex: 60,
        opacity,
      }}
    >
      <div
        style={{
          transform: `scale(${0.6 + 0.4 * pop}) rotate(${(1 - pop) * -4}deg)`,
          background: "rgba(0, 0, 0, 0.78)",
          border: "6px solid #FFEA00",
          borderRadius: "28px",
          padding: "26px 44px",
          boxShadow: "0 14px 40px rgba(0,0,0,0.6)",
        }}
      >
        <div
          style={{
            fontFamily: "Anton, NotoDevanagari, NotoCyrillic, Impact, Arial Black, sans-serif",
            fontSize: `${fontSize}px`,
            lineHeight: 1.08,
            color: "#FFEA00",
            textTransform: "uppercase",
            textAlign: "center",
            letterSpacing: "1px",
            textShadow: "4px 4px 0 #000000",
          }}
        >
          {text}
        </div>
      </div>
    </div>
  );
};

// --- LINE-BASED CAPTION STYLES: KARAOKE (colour sweep), NEON (glow), BAR (subtitle bar) ---
// The line (a chunk of a few words) stays put while the highlight moves along it, unlike the one-word styles.
type LineStyle = "KARAOKE" | "NEON" | "BAR";
const LINE_CFG: Record<LineStyle, { maxWords: number; maxChars: number; accent: string }> = {
  KARAOKE: { maxWords: 4, maxChars: 24, accent: "#FFE600" },
  NEON: { maxWords: 3, maxChars: 20, accent: "#00F0FF" },
  BAR: { maxWords: 6, maxChars: 34, accent: "#FFD60A" },
};

// Split the transcript into lines: at most maxWords / maxChars per line, and a new line after a pause.
const chunkRanges = (words: z.infer<typeof wordSchema>[], maxWords: number, maxChars: number) => {
  const ranges: [number, number][] = [];
  let start = 0;
  let chars = 0;
  for (let i = 0; i < words.length; i++) {
    const len = Array.from(words[i].word).length + 1;
    const pause = i > 0 ? words[i].start - words[i - 1].end : 0;
    if (i > start && (i - start >= maxWords || chars + len > maxChars || pause > 0.8)) {
      ranges.push([start, i - 1]);
      start = i;
      chars = 0;
    }
    chars += len;
  }
  if (words.length) ranges.push([start, words.length - 1]);
  return ranges;
};

const LineCaptions: React.FC<{
  words: z.infer<typeof wordSchema>[];
  displayWordIdx: number;
  currentWordIdx: number;
  currentTime: number;
  yPos: number;
  captionStyle: LineStyle;
  accent?: string;
  captionEmoji: boolean;
}> = ({ words, displayWordIdx, currentWordIdx, currentTime, yPos, captionStyle, accent, captionEmoji }) => {
  const cfg = LINE_CFG[captionStyle];
  const color = accent ?? cfg.accent;
  const range = chunkRanges(words, cfg.maxWords, cfg.maxChars).find(([a, b]) => displayWordIdx >= a && displayWordIdx <= b);
  if (!range) return null;
  const line = words.slice(range[0], range[1] + 1);
  const rtl = line.some((b) => isRtl(b.word));
  const cjk = line.some((b) => NO_SPACING_RE.test(b.word));

  const renderWord = (w: z.infer<typeof wordSchema>, i: number) => {
    const idx = range[0] + i;
    const isActive = idx === currentWordIdx;
    const spacing = noLetterSpacing(w.word) ? "0px" : captionStyle === "NEON" ? "3px" : "-1px";
    const emoji = isActive && captionEmoji ? <CaptionEmoji word={w.word} size={72} /> : null;
    const span = Math.max(0.05, w.end - w.start);
    const progress = Math.min(1, Math.max(0, (currentTime - w.start) / span)); // 0 = not yet spoken, 1 = spoken

    if (captionStyle === "KARAOKE") {
      const base: React.CSSProperties = {
        fontFamily: CAPTION_FONT,
        fontSize: "86px",
        textTransform: "uppercase",
        letterSpacing: spacing,
        whiteSpace: "pre",
        WebkitTextStroke: "10px #000000",
        paintOrder: "stroke fill",
      };
      const pct = Math.round(progress * 1000) / 10;
      return (
        <React.Fragment key={idx}>
          <span
            style={{
              position: "relative",
              display: "inline-block",
              transform: `scale(${isActive ? 1.08 : 1})`,
              textShadow: "0px 10px 26px rgba(0,0,0,0.85), 5px 5px 0px #000000",
            }}
          >
            <span style={{ ...base, color: "#FFFFFF" }}>{w.word}</span>
            <span
              aria-hidden
              style={{
                ...base,
                color,
                position: "absolute",
                left: 0,
                top: 0,
                // the sweep runs with the reading direction: left->right, or right->left for Arabic/Hebrew words
                clipPath: isRtl(w.word) ? `inset(0 0 0 ${100 - pct}%)` : `inset(0 ${100 - pct}% 0 0)`,
              }}
            >
              {w.word}
            </span>
          </span>
          {emoji}
        </React.Fragment>
      );
    }

    if (captionStyle === "NEON") {
      const t = Math.max(0, currentTime - w.start);
      const flicker = isActive ? interpolate(t, [0, 0.04, 0.08, 0.12], [0.45, 1, 0.75, 1], { extrapolateRight: "clamp" }) : 1;
      return (
        <React.Fragment key={idx}>
          <span
            style={{
              fontFamily: CAPTION_FONT,
              fontSize: "80px",
              textTransform: "uppercase",
              letterSpacing: spacing,
              whiteSpace: "pre",
              display: "inline-block",
              opacity: flicker,
              color: isActive ? "#FFFFFF" : "transparent",
              WebkitTextStroke: isActive ? "0px transparent" : `3px ${withAlpha(color, 0.75)}`,
              textShadow: isActive
                ? `0 0 8px ${color}, 0 0 20px ${color}, 0 0 42px ${color}, 0 0 84px ${withAlpha(color, 0.7)}`
                : `0 0 14px ${withAlpha(color, 0.5)}`,
            }}
          >
            {w.word}
          </span>
          {emoji}
        </React.Fragment>
      );
    }

    // BAR
    return (
      <React.Fragment key={idx}>
        <span
          style={{
            display: "inline-block",
            color: isActive ? color : progress >= 1 ? "#FFFFFF" : "rgba(255,255,255,0.68)",
            transform: `scale(${isActive ? 1.06 : 1})`,
            whiteSpace: "pre",
          }}
        >
          {w.word}
        </span>
        {emoji}
      </React.Fragment>
    );
  };

  const words$ = line.map(renderWord);
  return (
    <div
      style={{
        position: "absolute",
        top: `${yPos}px`,
        width: "100%",
        display: "flex",
        justifyContent: "center",
        padding: "0 40px",
        boxSizing: "border-box",
        zIndex: 50,
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "center",
          direction: rtl ? "rtl" : "ltr",
          gap: cjk ? "6px" : captionStyle === "BAR" ? "0.3em" : "16px",
          ...(captionStyle === "BAR"
            ? {
                maxWidth: "940px",
                background: "rgba(8, 10, 16, 0.78)",
                borderRadius: "18px",
                padding: "20px 36px",
                boxShadow: "0 10px 30px rgba(0,0,0,0.45)",
                fontFamily: "Arial, NotoDevanagari, NotoCyrillic, NotoArabic, NotoCJK, sans-serif",
                fontWeight: 800,
                fontSize: "60px",
                lineHeight: 1.2,
                textAlign: "center",
              }
            : {}),
        }}
      >
        {words$}
      </div>
    </div>
  );
};

// --- HELPER FOR INFLUENCER & PRESET SUBTITLES ---
const Subtitles: React.FC<{
  words: z.infer<typeof wordSchema>[];
  currentTime: number;
  yPos: number;
  fps: number;
  captionStyle?: "HORMOZI" | "GLOW_BOX" | "BOUNCE" | "MINIMAL" | LineStyle;
  captionEmoji?: boolean;
  accent?: string;
}> = ({ words, currentTime, yPos, fps, captionStyle = "HORMOZI", captionEmoji = false, accent }) => {
  // Find current word index
  let currentWordIdx = words.findIndex(
    (w) => currentTime >= w.start && currentTime <= w.end
  );

  let displayWordIdx = currentWordIdx;
  if (displayWordIdx === -1) {
    // Find the word that ended closest to currentTime but before it
    let lastSpokenIdx = -1;
    for (let i = 0; i < words.length; i++) {
      if (words[i].end <= currentTime) {
        lastSpokenIdx = i;
      } else {
        break;
      }
    }
    // Keep visible for a brief moment after speaking stops
    if (lastSpokenIdx !== -1 && currentTime - words[lastSpokenIdx].end < 1.2) {
      displayWordIdx = lastSpokenIdx;
    }
  }

  if (displayWordIdx === -1) return null;

  if (captionStyle === "KARAOKE" || captionStyle === "NEON" || captionStyle === "BAR") {
    return (
      <LineCaptions
        words={words}
        displayWordIdx={displayWordIdx}
        currentWordIdx={currentWordIdx}
        currentTime={currentTime}
        yPos={yPos}
        captionStyle={captionStyle}
        accent={accent}
        captionEmoji={captionEmoji}
      />
    );
  }

  // Grouping strategy based on style:
  // HORMOZI & BOUNCE: show only the active word centred (punch-word style)
  // GLOW_BOX & MINIMAL: show ±1 word window for context
  const isSingleWordMode = captionStyle === "HORMOZI" || captionStyle === "BOUNCE";
  const startIdx = isSingleWordMode ? displayWordIdx : Math.max(0, displayWordIdx - 1);
  const endIdx   = isSingleWordMode ? displayWordIdx : Math.min(words.length - 1, displayWordIdx + 1);
  const burstWords = words.slice(startIdx, endIdx + 1);

  return (
    <div
      style={{
        position: "absolute",
        top: `${yPos}px`,
        width: "100%",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        flexWrap: "wrap",
        direction: burstWords.some((b) => isRtl(b.word)) ? "rtl" : "ltr",
        gap: captionStyle === "GLOW_BOX" ? "20px" : "16px",
        padding: "0 40px",
        zIndex: 50,
      }}
    >
      {burstWords.map((w, index) => {
        const isActive = currentWordIdx !== -1 && w.start === words[currentWordIdx].start;
        const timeSinceStart = Math.max(0, currentTime - w.start);

        // 1. HORMOZI STYLING
        if (captionStyle === "HORMOZI") {
          const scale = isActive
            ? interpolate(
                timeSinceStart,
                [0, 0.07, 0.15, 0.28],
                [0.8, 1.3, 0.95, 1.05],
                { extrapolateRight: "clamp" }
              )
            : 1.0;

          const getHormoziColor = (word: string) => {
            const clean = word.toLowerCase().replace(/[^a-z0-9]/g, "");
            if (/\d/.test(clean) || ["super", "crazy", "insane", "billion", "secret", "never", "always", "top"].includes(clean)) {
              return "#39FF14"; // Neon Green for numbers & power words
            }
            if (clean.length > 6) return "#00E5FF"; // Vivid Cyan for longer words
            return "#FFEA00"; // Neon Yellow default active
          };

          // Alternate tilt per spoken word (index is always 0 in single-word mode)
          const rotation = isActive ? ((displayWordIdx + index) % 2 === 0 ? -4 : 4) : 0;

          return (
            <span
              key={index}
              style={{
                fontFamily: CAPTION_FONT,
                fontSize: "100px",
                color: isActive ? (accent ?? getHormoziColor(w.word)) : "#FFFFFF",
                opacity: isActive ? 1.0 : 0.60,
                textTransform: "uppercase",
                transform: `scale(${scale}) rotate(${rotation}deg)`,
                display: "inline-block",
                letterSpacing: isRtl(w.word) ? "0px" : "-4px",
                textShadow: isActive 
                  ? "0px 20px 45px rgba(0,0,0,1.0), 8px 8px 0px #000000" 
                  : "0px 10px 25px rgba(0,0,0,0.9), 5px 5px 0px #000000",
                WebkitTextStroke: "12px #000000",
                paintOrder: "stroke fill", // outline drawn behind the fill so it doesn't eat into the glyphs
                transition: "transform 0.04s cubic-bezier(0.17, 0.67, 0.83, 0.67), opacity 0.05s ease",
              }}
            >
              {w.word}
              {isActive && captionEmoji ? <CaptionEmoji word={w.word} size={90} /> : null}
            </span>
          );
        }

        // 2. GLOW_BOX STYLING (Glassmorphic pill box)
        if (captionStyle === "GLOW_BOX") {
          const scale = isActive
            ? interpolate(
                timeSinceStart,
                [0, 0.1, 0.2],
                [0.9, 1.1, 1.0],
                { extrapolateRight: "clamp" }
              )
            : 0.95;

          return (
            <span
              key={index}
              style={{
                fontFamily: CAPTION_FONT,
                fontSize: "82px",
                color: isActive ? "#FFFFFF" : "#CBD5E1",
                background: isActive
                  ? (accent ? `linear-gradient(135deg, ${accent}, ${withAlpha(accent, 0.6)})` : "linear-gradient(135deg, #FF007F, #7928CA)")
                  : "rgba(15, 23, 42, 0.75)",
                padding: "10px 28px",
                borderRadius: "20px",
                border: isActive ? `3px solid ${accent ?? "#FF007F"}` : "2px solid rgba(255,255,255,0.15)",
                boxShadow: isActive ? `0 10px 30px ${accent ? withAlpha(accent, 0.6) : "rgba(255, 0, 127, 0.6)"}` : "0 5px 15px rgba(0,0,0,0.3)",
                textTransform: "uppercase",
                transform: `scale(${scale})`,
                display: "inline-block",
                textShadow: isActive ? "2px 2px 0px #000000" : "none",
                transition: "transform 0.08s ease, background 0.1s ease",
              }}
            >
              {w.word}
            </span>
          );
        }

        // 3. BOUNCE STYLING (Upward spring jump with intense drop shadow glow)
        if (captionStyle === "BOUNCE") {
          const translateY = isActive
            ? interpolate(
                timeSinceStart,
                [0, 0.08, 0.18, 0.3],
                [0, -25, 5, 0],
                { extrapolateRight: "clamp" }
              )
            : 0;

          const scale = isActive ? 1.15 : 0.95;

          return (
            <span
              key={index}
              style={{
                fontFamily: CAPTION_FONT,
                fontSize: "92px",
                color: isActive ? (accent ?? "#FFD700") : "#FFFFFF",
                opacity: isActive ? 1.0 : 0.7,
                textTransform: "uppercase",
                transform: `translateY(${translateY}px) scale(${scale})`,
                display: "inline-block",
                textShadow: isActive
                  ? `0 0 20px ${accent ?? "#FFD700"}, 0 0 40px ${accent ?? "#FF4500"}, 4px 4px 0px #000000`
                  : "3px 3px 0px #000000",
                WebkitTextStroke: "8px #000000",
                paintOrder: "stroke fill",
                transition: "transform 0.08s ease-out, color 0.08s ease",
              }}
            >
              {w.word}
              {isActive && captionEmoji ? <CaptionEmoji word={w.word} size={84} /> : null}
            </span>
          );
        }

        // 4. MINIMAL STYLING (Clean dark box with crisp modern text)
        const scale = isActive ? 1.05 : 1.0;
        return (
          <span
            key={index}
            style={{
              fontFamily: "Arial Black, NotoDevanagari, NotoCyrillic, NotoArabic, NotoCJK, sans-serif",
              fontSize: "78px",
              color: isActive ? (accent ?? "#38BDF8") : "#F1F5F9",
              background: "rgba(0, 0, 0, 0.85)",
              padding: "8px 22px",
              borderRadius: "12px",
              borderLeft: isActive ? `6px solid ${accent ?? "#38BDF8"}` : "none",
              textTransform: "uppercase",
              transform: `scale(${scale})`,
              display: "inline-block",
              boxShadow: "0 8px 20px rgba(0,0,0,0.5)",
              transition: "transform 0.08s ease",
            }}
          >
            {w.word}
          </span>
        );
      })}
    </div>
  );
};

// --- HELPER COMPONENT FOR KEN BURNS ZOOM EFFECT ON BACKGROUNDS ---
const BackgroundSegment: React.FC<{
  bg: z.infer<typeof backgroundSchema>;
  fps: number;
  durationInFrames: number;
  isFirst: boolean;
  zoomMoments?: { start: number; end: number; scale: number; rise: number }[];
}> = ({ bg, fps, durationInFrames, isFirst, zoomMoments }) => {
  const frame = useCurrentFrame();
  
  // Smooth continuous camera zoom (Ken Burns)
  const scale = interpolate(
    frame,
    [0, durationInFrames],
    [1.04, 1.12],
    { extrapolateRight: "clamp" }
  );

  // Crossfade opacity (0.4s fade out at end, fade in at start)
  const fadeFrames = 12; // 0.4s at 30fps
  const safeEndFade = Math.max(fadeFrames + 1, durationInFrames - fadeFrames);
  
  // Opacity calculation for Crossfade
  const opacity = isFirst
    ? interpolate(
        frame,
        [safeEndFade, durationInFrames],
        [1, 0],
        { extrapolateRight: "clamp" }
      )
    : interpolate(
        frame,
        [0, fadeFrames, safeEndFade, durationInFrames],
        [0, 1, 1, 0],
        { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
      );

  // --auto_zoom: the zoom is on this picture layer only, so captions, the hook title and the brand never move
  const punch = zoomMoments && zoomMoments.length ? zoomScaleAt(bg.start + frame / fps, zoomMoments) : 1.0;
  const activeScale = bg.type === "video" ? punch : scale;

  const badgeScale = spring({ frame, fps, config: { damping: 10, mass: 0.5, stiffness: 140 } });

  // OffthreadVideo has no `loop` prop - repeat short stock clips explicitly so they never run out
  const clipFrames = bg.clipDuration ? Math.floor(bg.clipDuration * fps) : 0;
  const videoEl = (
    <OffthreadVideo
      src={getAssetUrl(bg.path)}
      muted
      style={{ width: "100%", height: "100%", objectFit: "cover" }}
    />
  );

  return (
    <AbsoluteFill style={{ transform: `scale(${activeScale})`, transformOrigin: "center", opacity, backgroundColor: "#000" }}>
      {bg.type === "video" ? (
        clipFrames > 0 && clipFrames < durationInFrames ? (
          <Loop durationInFrames={clipFrames}>{videoEl}</Loop>
        ) : (
          videoEl
        )
      ) : (
        <div style={{ width: "100%", height: "100%", position: "relative", overflow: "hidden" }}>
          {/* Blurred Background Layer for Non-Vertical Photos */}
          <Img
            src={getAssetUrl(bg.path)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: "blur(25px) brightness(0.6)",
              transform: "scale(1.2)",
              position: "absolute",
              top: 0,
              left: 0,
            }}
          />
          {/* Foreground Crisp Image (objectFit: contain ensures no horizontal cropping) */}
          <Img
            src={getAssetUrl(bg.path)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "contain",
              position: "relative",
              zIndex: 1,
              filter: "drop-shadow(0 10px 30px rgba(0,0,0,0.5))",
            }}
          />
        </div>
      )}

      {/* Segment badge (e.g. "FACT 2 / 3") - sits under the title header */}
      {bg.caption && (
        <div
          style={{
            position: "absolute",
            top: "250px",
            width: "100%",
            display: "flex",
            justifyContent: "center",
            transform: `scale(${badgeScale})`,
            zIndex: 41,
          }}
        >
          <span
            style={{
              fontFamily: CAPTION_FONT,
              fontSize: "54px",
              color: "#000000",
              background: "#FFEA00",
              padding: "6px 30px",
              borderRadius: "14px",
              letterSpacing: "2px",
              boxShadow: "0 8px 24px rgba(0,0,0,0.55)",
            }}
          >
            {bg.caption}
          </span>
        </div>
      )}
    </AbsoluteFill>
  );
};

const PhotoReelSegment: React.FC<{
  bg: z.infer<typeof backgroundSchema>;
  fps: number;
  durationInFrames: number;
  segmentIndex: number;
  isFirst: boolean;
}> = ({ bg, fps, durationInFrames, segmentIndex, isFirst }) => {
  const frame = useCurrentFrame();

  // 1. Spring physics entrance bounce
  const spr = spring({
    frame,
    fps,
    config: {
      damping: 12,
      mass: 0.5,
      stiffness: 100,
    },
  });

  const entryScale = interpolate(spr, [0, 1], [0.92, 1.0]);

  // 2. Multi-axis dynamic Ken Burns motion based on segmentIndex
  const modeIndex = segmentIndex % 4;
  let transformStr = "";

  if (modeIndex === 0) {
    // Zoom In
    const zoom = interpolate(frame, [0, durationInFrames], [1.0, 1.15], { extrapolateRight: "clamp" });
    transformStr = `scale(${zoom * entryScale})`;
  } else if (modeIndex === 1) {
    // Zoom Out
    const zoom = interpolate(frame, [0, durationInFrames], [1.18, 1.02], { extrapolateRight: "clamp" });
    transformStr = `scale(${zoom * entryScale})`;
  } else if (modeIndex === 2) {
    // Pan Right + Scale
    const panX = interpolate(frame, [0, durationInFrames], [-4, 4], { extrapolateRight: "clamp" });
    transformStr = `scale(${1.08 * entryScale}) translateX(${panX}%)`;
  } else {
    // Pan Left + Scale
    const panX = interpolate(frame, [0, durationInFrames], [4, -4], { extrapolateRight: "clamp" });
    transformStr = `scale(${1.08 * entryScale}) translateX(${panX}%)`;
  }

  // 3. Flash / Light-Leak Cut Effect (3-frame white burst at start of segment)
  const flashOpacity = interpolate(
    frame,
    [0, 2, 6],
    [0.9, 0.4, 0],
    { extrapolateRight: "clamp" }
  );

  // 4. Crossfade Opacity at transition boundaries
  const fadeFrames = 8;
  const safeEndFade = Math.max(fadeFrames + 1, durationInFrames - fadeFrames);
  const opacity = isFirst
    ? interpolate(frame, [safeEndFade, durationInFrames], [1, 0], { extrapolateRight: "clamp" })
    : interpolate(frame, [0, fadeFrames, safeEndFade, durationInFrames], [0, 1, 1, 0], { extrapolateRight: "clamp", extrapolateLeft: "clamp" });

  // 5. Animated Caption Sticker Pop-In
  const stickerSpr = spring({
    frame: Math.max(0, frame - 4),
    fps,
    config: { damping: 14, mass: 0.6, stiffness: 120 },
  });
  const stickerScale = interpolate(stickerSpr, [0, 1], [0.5, 1.0]);
  const stickerOpacity = interpolate(stickerSpr, [0, 1], [0, 1]);

  const isPortrait = bg.orientation === "portrait";

  return (
    <AbsoluteFill style={{ opacity, backgroundColor: "#060608" }}>
      {/* Background Ambient Blur Layer (for landscape photos) */}
      {!isPortrait && (
        <div style={{ width: "100%", height: "100%", position: "absolute", top: 0, left: 0, overflow: "hidden" }}>
          <Img
            src={getAssetUrl(bg.path)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: "blur(40px) brightness(0.55) contrast(1.1)",
              transform: "scale(1.3)",
              position: "absolute",
              top: 0,
              left: 0,
            }}
          />
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              background: "radial-gradient(circle at center, transparent 30%, rgba(0, 0, 0, 0.8) 100%)",
              zIndex: 1,
            }}
          />
        </div>
      )}

      {/* Main Photo Layer */}
      {isPortrait ? (
        // Edge-to-Edge Fullscreen Vertical Photo (9:16 Canvas)
        <div
          style={{
            width: "100%",
            height: "100%",
            transform: transformStr,
            transformOrigin: "center",
            position: "relative",
            zIndex: 2,
          }}
        >
          <Img
            src={getAssetUrl(bg.path)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        </div>
      ) : (
        // Floating Glassmorphism Photo Card for Horizontal Photos
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            position: "relative",
            zIndex: 2,
            padding: "60px 40px",
          }}
        >
          <div
            style={{
              width: "100%",
              height: "100%",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              transform: transformStr,
              transformOrigin: "center",
            }}
          >
            <Img
              src={getAssetUrl(bg.path)}
              style={{
                maxWidth: "100%",
                maxHeight: "100%",
                objectFit: "contain",
                borderRadius: "28px",
                boxShadow: "0 30px 80px rgba(0, 0, 0, 0.85), 0 0 40px rgba(255, 0, 127, 0.2)",
                border: "3px solid rgba(255, 255, 255, 0.3)",
              }}
            />
          </div>
        </div>
      )}

      {/* Flash / Light Leak Transition Overlay */}
      {frame < 8 && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            background: "linear-gradient(135deg, #ffffff, #00ffff)",
            opacity: flashOpacity,
            mixBlendMode: "overlay",
            pointerEvents: "none",
            zIndex: 10,
          }}
        />
      )}

      {/* Aesthetic Kinetic Sticker Caption */}
      {bg.caption && (
        <div
          style={{
            position: "absolute",
            bottom: "430px", // above the Shorts/Reels title & description overlay
            width: "100%",
            display: "flex",
            justifyContent: "center",
            zIndex: 20,
            transform: `scale(${stickerScale})`,
            opacity: stickerOpacity,
          }}
        >
          <div
            style={{
              background: "rgba(15, 23, 42, 0.85)",
              backdropFilter: "blur(16px)",
              border: "2px solid rgba(255, 255, 255, 0.3)",
              borderRadius: "50px",
              padding: "16px 36px",
              boxShadow: "0 15px 35px rgba(0,0,0,0.6), 0 0 25px rgba(0,255,255,0.3)",
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <span
              style={{
                fontFamily: CAPTION_FONT,
                fontSize: "36px",
                color: "#ffffff",
                letterSpacing: "1.5px",
                textTransform: "uppercase",
              }}
            >
              {bg.caption}
            </span>
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};

const EmojiGuessOverlay: React.FC<{
  emojis: string;
  answer: string;
  hint?: string;
  fps: number;
}> = ({ emojis, answer, hint, fps }) => {
  const frame = useCurrentFrame();
  const timeInSeconds = frame / fps;

  const revealTime = 5.0;
  const isRevealed = timeInSeconds >= revealTime;
  const countdownSec = Math.max(0, Math.ceil(revealTime - timeInSeconds));

  const pulseScale = interpolate(
    frame % 30,
    [0, 15, 30],
    [1.0, 1.06, 1.0],
    { extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        top: "0px",
        left: "0px",
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "40px",
        zIndex: 35,
      }}
    >
      {hint && (
        <div
          style={{
            position: "absolute",
            top: "250px",
            background: "linear-gradient(135deg, #ff007f, #7928ca)",
            border: "4px solid #ffffff",
            borderRadius: "50px",
            padding: "16px 45px",
            boxShadow: "0 10px 30px rgba(0,0,0,0.6)",
          }}
        >
          <span
            style={{
              fontFamily: CAPTION_FONT,
              fontSize: "48px",
              color: "#ffffff",
              letterSpacing: "2px",
              textTransform: "uppercase",
            }}
          >
            💡 {hint}
          </span>
        </div>
      )}

      <div
        style={{
          transform: `scale(${pulseScale})`,
          background: "rgba(15, 23, 42, 0.88)",
          backdropFilter: "blur(16px)",
          border: "6px solid #00f2fe",
          borderRadius: "40px",
          padding: "40px 60px",
          boxShadow: "0 25px 60px rgba(0, 242, 254, 0.4)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          marginBottom: "60px",
        }}
      >
        <span
          style={{
            fontSize: "110px",
            letterSpacing: "15px",
            filter: "drop-shadow(0 10px 20px rgba(0,0,0,0.8))",
          }}
        >
          {emojis}
        </span>
      </div>

      {!isRevealed ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            background: "rgba(0, 0, 0, 0.8)",
            border: "5px solid #ff0055",
            borderRadius: "30px",
            padding: "20px 50px",
            boxShadow: "0 10px 30px rgba(255, 0, 85, 0.5)",
          }}
        >
          <span
            style={{
              fontFamily: CAPTION_FONT,
              fontSize: "36px",
              color: "#ff0055",
              textTransform: "uppercase",
              letterSpacing: "2px",
            }}
          >
            GUESS THE ANSWER IN...
          </span>
          <span
            style={{
              fontFamily: CAPTION_FONT,
              fontSize: "100px",
              color: "#ffffff",
              textShadow: "0 0 20px #ff0055",
              marginTop: "5px",
            }}
          >
            ⏱️ {countdownSec}s
          </span>
        </div>
      ) : (
        <div
          style={{
            background: "linear-gradient(135deg, #FF007F, #7928CA)",
            border: "6px solid #ffffff",
            borderRadius: "30px",
            padding: "30px 60px",
            boxShadow: "0 20px 50px rgba(255,0,127,0.7)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
          }}
        >
          <span
            style={{
              fontFamily: CAPTION_FONT,
              fontSize: "44px",
              color: "#ffff00",
              textTransform: "uppercase",
              letterSpacing: "2px",
            }}
          >
            💬 WRITE YOUR GUESS
          </span>
          <span
            style={{
              fontFamily: CAPTION_FONT,
              fontSize: "55px",
              color: "#ffffff",
              textShadow: "2px 4px 10px rgba(0,0,0,0.5)",
              marginTop: "10px",
            }}
          >
            IN THE COMMENTS BELOW! 👇
          </span>
        </div>
      )}
    </div>
  );
};

// Loads the CJK subset font that the Python side wrote for this render (too big to bundle for all of zh/ja/ko).
const useExtraFont = (extra?: { family: string; url: string }) => {
  const [handle] = useState(() => (extra ? delayRender("Loading CJK caption font") : null));
  useEffect(() => {
    if (!extra || handle === null) return;
    new FontFace("NotoCJK", `url(${staticFile(extra.url)})`)
      .load()
      .then((font) => {
        document.fonts.add(font);
        continueRender(handle);
      })
      .catch(() => continueRender(handle));
  }, []);
};

export const ShortFlow: React.FC<ShortFlowProps> = ({
  audioUrl,
  bgMusicUrl,
  bgMusicVolume,
  words,
  mode,
  category,
  titleText,
  subtitleYPos,
  captionStyle = "HORMOZI",
  captionColor,
  captionEmoji = false,
  hookText,
  hookSeconds = 2.8,
  zoomMoments,
  extraFont,
  avatarUrl,
  avatarAspect,
  avatarKeyed,
  backgrounds,
  thisOrThat,
  rankIt,
  captionThis,
  emojiGuess,
  funnyExplainer,
  teachCard,
}) => {
  useExtraFont(extraFont);
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const currentTime = frame / fps;
  const durationInSeconds = durationInFrames / fps;

  // Dynamic Audio Ducking & Avatar Bounce Logic
  const isSpeaking = words && words.length > 0
    ? words.some(w => currentTime >= w.start - 0.1 && currentTime <= w.end + 0.3)
    : false;
  const currentVolume = isSpeaking ? 0.08 : bgMusicVolume;

  // Snap progression for progress bar
  const progressPercent = Math.min(100, (currentTime / durationInSeconds) * 100);

  return (
    <AbsoluteFill style={{ backgroundColor: "#0b0c10", overflow: "hidden" }}>
      {/* 1. PRIMARY VOICE AUDIO */}
      <Audio src={getAssetUrl(audioUrl)} />

      {/* 2. OPTIONAL BACKGROUND MUSIC */}
      {bgMusicUrl && (
        <Audio src={getAssetUrl(bgMusicUrl)} volume={currentVolume} loop />
      )}

      {/* 3. DYNAMIC BACKGROUND LAYOUTS */}
      {mode === "THIS_OR_THAT" && thisOrThat ? (
        // Split-screen comparison layout
        <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%" }}>
          {/* Top Panel (Option A) */}
          <div style={{ flex: 1, position: "relative", overflow: "hidden", borderBottom: "8px solid #ff007f" }}>
            {isVideoAsset(thisOrThat.imageA) ? (
              <Html5Video
                src={getAssetUrl(thisOrThat.imageA)}
                muted
                loop
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            ) : (
              <Img
                src={getAssetUrl(thisOrThat.imageA)}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            )}
            {/* Glassmorphic Option A Label */}
            <div
              style={{
                position: "absolute",
                bottom: "150px", // clear of the centre VS badge
                left: "50%",
                transform: "translateX(-50%)",
                background: "rgba(0, 0, 0, 0.7)",
                backdropFilter: "blur(10px)",
                padding: "15px 35px",
                borderRadius: "15px",
                border: "2px solid rgba(255, 255, 255, 0.1)",
              }}
            >
              <h2
                style={{
                  fontFamily: CAPTION_FONT,
                  fontSize: "65px",
                  color: "#ffffff",
                  margin: 0,
                  textTransform: "uppercase",
                  textShadow: "3px 3px 0px #000000",
                }}
              >
                {thisOrThat.optionA}
              </h2>
            </div>
          </div>

          {/* Bottom Panel (Option B) */}
          <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
            {isVideoAsset(thisOrThat.imageB) ? (
              <Html5Video
                src={getAssetUrl(thisOrThat.imageB)}
                muted
                loop
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            ) : (
              <Img
                src={getAssetUrl(thisOrThat.imageB)}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            )}
            {/* Glassmorphic Option B Label */}
            <div
              style={{
                position: "absolute",
                bottom: "40px",
                left: "50%",
                transform: "translateX(-50%)",
                background: "rgba(0, 0, 0, 0.7)",
                backdropFilter: "blur(10px)",
                padding: "15px 35px",
                borderRadius: "15px",
                border: "2px solid rgba(255, 255, 255, 0.1)",
              }}
            >
              <h2
                style={{
                  fontFamily: CAPTION_FONT,
                  fontSize: "65px",
                  color: "#ffffff",
                  margin: 0,
                  textTransform: "uppercase",
                  textShadow: "3px 3px 0px #000000",
                }}
              >
                {thisOrThat.optionB}
              </h2>
            </div>
          </div>

          {/* Central VS Badge */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              background: "#ffff00",
              border: "8px solid #000000",
              borderRadius: "20px",
              padding: "15px 40px",
              zIndex: 30,
              boxShadow: "0 10px 30px rgba(0,0,0,0.5)",
            }}
          >
            <span
              style={{
                fontFamily: CAPTION_FONT,
                fontSize: "100px",
                color: "#000000",
                fontWeight: "bold",
              }}
            >
              VS
            </span>
          </div>
        </div>
      ) : mode === "RANK_IT" && rankIt ? (
        // Sequential Tier List layout
        <div style={{ width: "100%", height: "100%", position: "relative" }}>
          {rankIt.items.map((item, idx) => {
            const startFrame = Math.round(item.start * fps);
            const endFrame = Math.round(item.end * fps);
            const durationInFrames = Math.max(1, endFrame - startFrame);

            return (
              <Sequence
                key={idx}
                from={startFrame}
                durationInFrames={durationInFrames}
              >
                <AbsoluteFill style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
                  {/* Large Central Image */}
                  <div style={{ width: "900px", height: "900px", borderRadius: "30px", overflow: "hidden", boxShadow: "0 25px 50px rgba(0,0,0,0.6)", border: "6px solid #ffd700" }}>
                    <Img
                      src={getAssetUrl(item.image)}
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                  </div>

                  {/* Tier Label Box (S, A, B, C, D) */}
                  <div
                    style={{
                      marginTop: "50px",
                      background: "linear-gradient(135deg, #ffd700, #ff8c00)",
                      borderRadius: "25px",
                      padding: "20px 60px",
                      boxShadow: "0 10px 25px rgba(0,0,0,0.4)",
                      border: "4px solid #000000",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: CAPTION_FONT,
                        fontSize: "120px",
                        color: "#000000",
                        textShadow: "2px 2px 0px rgba(255,255,255,0.4)",
                      }}
                    >
                      TIER {item.tier}
                    </span>
                  </div>

                  {/* Item name label */}
                  <div
                    style={{
                      marginTop: "30px",
                      background: "rgba(0,0,0,0.85)",
                      padding: "15px 40px",
                      borderRadius: "15px",
                      border: "2px solid rgba(255,255,255,0.1)",
                    }}
                  >
                    <h2
                      style={{
                        fontFamily: CAPTION_FONT,
                        fontSize: "65px",
                        color: "#ffffff",
                        margin: 0,
                        textTransform: "uppercase",
                      }}
                    >
                      {item.name}
                    </h2>
                  </div>
                </AbsoluteFill>
              </Sequence>
            );
          })}
        </div>
      ) : mode === "CAPTION_THIS" && captionThis ? (
        // Caption This image layout
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", width: "100%", height: "100%", padding: "50px" }}>
          {/* Main Weird Image */}
          <div style={{ width: "950px", height: "950px", borderRadius: "40px", overflow: "hidden", border: "8px solid #ff007f", boxShadow: "0 30px 60px rgba(0,0,0,0.7)" }}>
            <Img
              src={getAssetUrl(captionThis.image)}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </div>

          {/* Heading Box Prompt */}
          <div
            style={{
              position: "absolute",
              top: "220px",
              background: "#00ffff",
              border: "6px solid #000000",
              borderRadius: "20px",
              padding: "15px 50px",
              boxShadow: "0 12px 24px rgba(0,0,0,0.4)",
            }}
          >
            <span
              style={{
                fontFamily: CAPTION_FONT,
                fontSize: "80px",
                color: "#000000",
                textTransform: "uppercase",
              }}
            >
              {captionThis.promptText}
            </span>
          </div>
        </div>
      ) : mode === "EMOJI_GUESS" && emojiGuess ? (
        // EMOJI_GUESS interactive puzzle layout
        <div style={{ width: "100%", height: "100%", position: "relative" }}>
          {backgrounds.map((bg, idx) => {
            const startFrame = Math.round(bg.start * fps);
            const endFrame = Math.round(bg.end * fps);
            const isLast = idx === backgrounds.length - 1;
            const durationInFrames = Math.max(1, (endFrame - startFrame) + (isLast ? 0 : 15));

            return (
              <Sequence
                key={idx}
                from={startFrame}
                durationInFrames={durationInFrames}
              >
                <BackgroundSegment
                  bg={bg}
                  fps={fps}
                  durationInFrames={durationInFrames}
                  isFirst={idx === 0}
                />
              </Sequence>
            );
          })}
          <EmojiGuessOverlay
            emojis={emojiGuess.emojis}
            answer={emojiGuess.answer}
            hint={emojiGuess.hint}
            fps={fps}
          />
        </div>
      ) : mode === "PHOTO_REEL" ? (
        // Pro Photo Reel Mode with Spring Physics & Flash Cut Transitions
        <div style={{ width: "100%", height: "100%", position: "relative" }}>
          {backgrounds.map((bg, idx) => {
            const startFrame = Math.round(bg.start * fps);
            const endFrame = Math.round(bg.end * fps);
            const isLast = idx === backgrounds.length - 1;
            const durationInFrames = Math.max(1, (endFrame - startFrame) + (isLast ? 0 : 10));

            return (
              <Sequence
                key={idx}
                from={startFrame}
                durationInFrames={durationInFrames}
              >
                <PhotoReelSegment
                  bg={bg}
                  fps={fps}
                  durationInFrames={durationInFrames}
                  segmentIndex={idx}
                  isFirst={idx === 0}
                />
              </Sequence>
            );
          })}
        </div>
      ) : (
        // Standard modes (FACTS, STORY, NEWS, RIDDLE) with background loops
        <div style={{ width: "100%", height: "100%", position: "relative" }}>
          {backgrounds.map((bg, idx) => {
            const startFrame = Math.round(bg.start * fps);
            const endFrame = Math.round(bg.end * fps);
            const isLast = idx === backgrounds.length - 1;
            const durationInFrames = Math.max(1, (endFrame - startFrame) + (isLast ? 0 : 15));

            return (
              <Sequence
                key={idx}
                from={startFrame}
                durationInFrames={durationInFrames}
              >
                <BackgroundSegment
                  bg={bg}
                  fps={fps}
                  durationInFrames={durationInFrames}
                  isFirst={idx === 0}
                  zoomMoments={zoomMoments}
                />
              </Sequence>
            );
          })}
        </div>
      )}

      {/* 4. OVERLAYS (HEADER/TITLE/TICKER) */}
      {titleText && mode !== "TEACH" && !teachCard && (
        <div
          style={{
            position: "absolute",
            top: "100px",
            width: "100%",
            display: "flex",
            justifyContent: "center",
            zIndex: 40,
          }}
        >
          <div
            style={{
              background: "rgba(0, 0, 0, 0.85)",
              padding: "15px 45px",
              borderRadius: "20px",
              border: "3px solid #ffff00",
              boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
            }}
          >
            <h1
              style={{
                fontFamily: CAPTION_FONT,
                fontSize: "75px",
                color: "#ffff00",
                margin: 0,
                textTransform: "uppercase",
                letterSpacing: "2px",
                textAlign: "center",
              }}
            >
              {titleText}
            </h1>
          </div>
        </div>
      )}

      {hookText && <HookOverlay text={hookText} seconds={hookSeconds} fps={fps} frame={frame} />}

      {/* 5. STYLISH CAPTIONS */}
      <Subtitles
        words={words}
        currentTime={currentTime}
        yPos={subtitleYPos}
        fps={fps}
        captionStyle={captionStyle}
        captionEmoji={captionEmoji}
        accent={captionColor}
      />

      {/* 6. CARTOON AVATAR OVERLAY (Big & Centered News Anchor / TV Window) */}
      {avatarUrl && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            zIndex: 45,
            width: "900px",
            height: `${Math.round(900 / Math.min(Math.max(avatarAspect ?? 16 / 9, 0.75), 16 / 9))}px`,
            ...(avatarKeyed
              ? { filter: "drop-shadow(0 20px 28px rgba(0,0,0,0.75))" }
              : {
                  borderRadius: "32px",
                  overflow: "hidden",
                  border: "6px solid #ffffff",
                  boxShadow: "0 25px 60px rgba(0,0,0,0.85), 0 0 35px rgba(251,191,36,0.3)",
                }),
            transform: `translate(-50%, -50%) scale(${isSpeaking ? 1.03 + Math.sin(frame * 0.4) * 0.02 : 1.0})`,
            transition: "transform 0.05s ease-out",
          }}
        >
          {isVideoAsset(avatarUrl) ? (
            <Html5Video
              src={getAssetUrl(avatarUrl)}
              muted
              loop
              // generated clips carry a small watermark in the bottom-right corner; scale from the top-left to push it out of frame
              style={{ width: "100%", height: "100%", objectFit: "cover", transform: "scale(1.07)", transformOrigin: "0 0" }}
            />
          ) : (
            <Img
              src={getAssetUrl(avatarUrl)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: avatarKeyed ? "contain" : "cover",
              }}
            />
          )}
        </div>
      )}

      {/* TEACH CARD OVERLAY */}
      {teachCard && (
        <TeachCardComponent card={teachCard} frame={frame} fps={fps} />
      )}

      {/* 7. PROGRESS BAR (Snappy sliding bottom bar) */}
      <div
        style={{
          position: "absolute",
          bottom: "0px",
          left: "0px",
          width: "100%",
          height: "24px",
          backgroundColor: "#1e1f29",
          zIndex: 60,
        }}
      >
        <div
          style={{
            width: `${progressPercent}%`,
            height: "100%",
            backgroundColor: "#00ffcc",
            boxShadow: "0 0 15px #00ffcc",
            transition: "width 0.05s linear",
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

// --- TEACH CARD COMPONENT FOR MICRO-LEARNING SHORTS ---
const TeachCardComponent: React.FC<{
  card: z.infer<typeof teachCardSchema>;
  frame: number;
  fps: number;
}> = ({ card, frame, fps }) => {
  const { durationInFrames } = useVideoConfig();
  const progress = Math.min(0.99, Math.max(0, frame / Math.max(1, durationInFrames)));

  const popIn = spring({
    frame,
    fps,
    config: { damping: 14, mass: 0.8 },
  });

  const scale = interpolate(popIn, [0, 1], [0.85, 1.0]);
  const opacity = interpolate(popIn, [0, 1], [0, 1]);

  if (card.type === "language") {
    return (
      <div
        style={{
          position: "absolute",
          top: "350px",
          left: "50%",
          transform: `translateX(-50%) scale(${scale})`,
          opacity,
          width: "900px",
          background: "rgba(15, 23, 42, 0.94)",
          backdropFilter: "blur(20px)",
          border: "4px solid #38bdf8",
          borderRadius: "32px",
          padding: "40px",
          boxShadow: "0 25px 60px rgba(0,0,0,0.7), 0 0 40px rgba(56, 189, 248, 0.3)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "24px",
          zIndex: 45,
          color: "#ffffff",
          fontFamily: "system-ui, -apple-system, sans-serif",
        }}
      >
        {card.original_script && (
          <div style={{ fontSize: "56px", color: "#94a3b8", fontWeight: 600 }}>
            {card.original_script}
          </div>
        )}
        <div
          style={{
            fontSize: "76px",
            fontWeight: 900,
            color: "#38bdf8",
            textAlign: "center",
            textShadow: "0 4px 20px rgba(56, 189, 248, 0.5)",
          }}
        >
          {card.word_or_phrase}
        </div>
        {card.phonetic && (
          <div
            style={{
              fontSize: "36px",
              background: "rgba(56, 189, 248, 0.15)",
              color: "#7dd3fc",
              padding: "10px 28px",
              borderRadius: "50px",
              border: "2px solid rgba(56, 189, 248, 0.4)",
              fontStyle: "italic",
            }}
          >
            🔊 {card.phonetic}
          </div>
        )}
        {card.translation && (
          <div
            style={{
              fontSize: "44px",
              fontWeight: 700,
              color: "#f8fafc",
              textAlign: "center",
              borderTop: "2px solid rgba(255, 255, 255, 0.1)",
              paddingTop: "20px",
              width: "100%",
            }}
          >
            "{card.translation}"
          </div>
        )}
        {card.example_sentence && (
          <div
            style={{
              fontSize: "32px",
              color: "#cbd5e1",
              background: "rgba(30, 41, 59, 0.8)",
              padding: "16px 24px",
              borderRadius: "16px",
              textAlign: "center",
              width: "100%",
            }}
          >
            💡 Example: {card.example_sentence}
          </div>
        )}
      </div>
    );
  }

  if (card.type === "code") {
    return (
      <div
        style={{
          position: "absolute",
          top: "380px",
          left: "50%",
          transform: `translateX(-50%) scale(${scale})`,
          opacity,
          width: "920px",
          background: "#0f172a",
          border: "4px solid #38bdf8",
          borderRadius: "24px",
          padding: "36px",
          boxShadow: "0 25px 60px rgba(0,0,0,0.8), 0 0 35px rgba(56, 189, 248, 0.25)",
          display: "flex",
          flexDirection: "column",
          gap: "24px",
          zIndex: 45,
          color: "#f8fafc",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: "36px", fontWeight: 800, color: "#38bdf8" }}>
            ⚡ {card.concept || "Code Trick"}
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <span style={{ width: "16px", height: "16px", borderRadius: "50%", background: "#ef4444" }} />
            <span style={{ width: "16px", height: "16px", borderRadius: "50%", background: "#f59e0b" }} />
            <span style={{ width: "16px", height: "16px", borderRadius: "50%", background: "#10b981" }} />
          </div>
        </div>
        {card.code_snippet && (
          <pre
            style={{
              fontFamily: "'Fira Code', 'Courier New', monospace",
              fontSize: "36px",
              background: "#1e293b",
              color: "#38bdf8",
              padding: "28px",
              borderRadius: "16px",
              border: "2px solid #334155",
              margin: 0,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {card.code_snippet}
          </pre>
        )}
        {card.key_takeaway && (
          <div style={{ fontSize: "32px", color: "#4ade80", fontWeight: 600 }}>
            🚀 {card.key_takeaway}
          </div>
        )}
      </div>
    );
  }

  if (card.type === "recipe") {
    const steps = card.steps || [];
    const stepCount = steps.length;
    // Calculate active step idx directly based on progress across steps
    const activeStepIdx = Math.min(stepCount - 1, Math.max(0, Math.floor(progress * Math.max(1, stepCount))));

    return (
      <>
        {/* TOP FLOATING RECIPE HEADER BADGE & INGREDIENTS BANNER */}
        <div
          style={{
            position: "absolute",
            top: "90px",
            left: "50%",
            transform: `translateX(-50%) scale(${scale})`,
            opacity,
            width: "940px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            zIndex: 45,
            fontFamily: "system-ui, -apple-system, sans-serif",
          }}
        >
          {/* Main Dish Header */}
          <div
            style={{
              background: "rgba(15, 23, 42, 0.94)",
              backdropFilter: "blur(20px)",
              border: "3px solid #fbbf24",
              borderRadius: "24px",
              padding: "16px 28px",
              boxShadow: "0 15px 40px rgba(0,0,0,0.6), 0 0 25px rgba(251, 191, 36, 0.25)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              color: "#ffffff",
            }}
          >
            <div style={{ fontSize: "38px", fontWeight: 900, color: "#fbbf24", letterSpacing: "1px", display: "flex", alignItems: "center", gap: "12px" }}>
              🍳 {card.dish_name || card.title}
            </div>
            {card.prep_time && (
              <div
                style={{
                  fontSize: "24px",
                  background: "#d97706",
                  color: "#ffffff",
                  padding: "6px 18px",
                  borderRadius: "20px",
                  fontWeight: 800,
                  boxShadow: "0 4px 12px rgba(217, 119, 6, 0.4)",
                }}
              >
                ⏱️ {card.prep_time}
              </div>
            )}
          </div>

          {/* Persistent Ingredients Ribbon Bar */}
          {card.ingredients && card.ingredients.length > 0 && (
            <div
              style={{
                background: "rgba(15, 23, 42, 0.90)",
                backdropFilter: "blur(16px)",
                border: "2px solid rgba(251, 191, 36, 0.5)",
                borderRadius: "20px",
                padding: "12px 20px",
                display: "flex",
                alignItems: "center",
                gap: "12px",
                boxShadow: "0 10px 30px rgba(0,0,0,0.5)",
                overflowX: "hidden",
              }}
            >
              <div style={{ fontSize: "22px", fontWeight: 800, color: "#fef08a", whiteSpace: "nowrap" }}>
                🛒 Ingredients:
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
                {card.ingredients.map((ing, i) => (
                  <span
                    key={i}
                    style={{
                      background: "rgba(251, 191, 36, 0.20)",
                      border: "1px solid rgba(251, 191, 36, 0.6)",
                      color: "#ffffff",
                      fontSize: "20px",
                      fontWeight: 700,
                      padding: "4px 12px",
                      borderRadius: "14px",
                      whiteSpace: "nowrap",
                    }}
                  >
                    ✓ {ing}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* BOTTOM FLOATING INSTRUCTION STEP CARD */}
        <div
          style={{
            position: "absolute",
            top: "1350px",
            left: "50%",
            transform: `translateX(-50%) scale(${scale})`,
            opacity,
            width: "940px",
            background: "rgba(15, 23, 42, 0.95)",
            backdropFilter: "blur(20px)",
            border: "3px solid #fbbf24",
            borderRadius: "28px",
            padding: "26px 32px",
            boxShadow: "0 20px 50px rgba(0,0,0,0.85), 0 0 30px rgba(251, 191, 36, 0.25)",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
            zIndex: 45,
            color: "#ffffff",
            fontFamily: "system-ui, -apple-system, sans-serif",
          }}
        >
          {steps.length > 0 && activeStepIdx >= 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {/* Step Stepper Progress Bar */}
              <div style={{ display: "flex", gap: "8px" }}>
                {steps.map((_, i) => (
                  <div
                    key={i}
                    style={{
                      flex: 1,
                      height: "8px",
                      borderRadius: "8px",
                      background: i <= activeStepIdx ? "#fbbf24" : "rgba(255, 255, 255, 0.15)",
                      boxShadow: i === activeStepIdx ? "0 0 12px #fbbf24" : "none",
                      transition: "all 0.2s ease",
                    }}
                  />
                ))}
              </div>

              {/* Active Step Instructions */}
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <div style={{ fontSize: "24px", fontWeight: 800, color: "#fbbf24", textTransform: "uppercase", letterSpacing: "1.2px", display: "flex", alignItems: "center", gap: "8px" }}>
                  📍 Step {activeStepIdx + 1} of {steps.length}
                </div>
                <div style={{ fontSize: "36px", fontWeight: 800, color: "#ffffff", lineHeight: "1.3", textShadow: "0 2px 10px rgba(0,0,0,0.8)" }}>
                  {steps[activeStepIdx]}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </>
    );
  }

  // General concept card
  return (
    <div
      style={{
        position: "absolute",
        top: "400px",
        left: "50%",
        transform: `translateX(-50%) scale(${scale})`,
        opacity,
        width: "900px",
        background: "rgba(15, 23, 42, 0.94)",
        backdropFilter: "blur(20px)",
        border: "4px solid #a855f7",
        borderRadius: "32px",
        padding: "40px",
        boxShadow: "0 25px 60px rgba(0,0,0,0.8), 0 0 35px rgba(168, 85, 247, 0.3)",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
        zIndex: 45,
        color: "#ffffff",
      }}
    >
      <div style={{ fontSize: "52px", fontWeight: 900, color: "#c084fc", textAlign: "center" }}>
        🧠 {card.concept || card.title}
      </div>
      {card.key_takeaway && (
        <div style={{ fontSize: "36px", color: "#f43f5e", fontWeight: 700, textAlign: "center" }}>
          💡 {card.key_takeaway}
        </div>
      )}
    </div>
  );
};

