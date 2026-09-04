import {
  Audio,
  OffthreadVideo,
  Img,
  useCurrentFrame,
  useVideoConfig,
  Sequence,
  AbsoluteFill,
  interpolate,
  staticFile,
} from "remotion";
import React from "react";
import { z } from "zod";

// --- SCHEMAS ---
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

export const shortFlowSchema = z.object({
  audioUrl: z.string(),
  bgMusicUrl: z.string().optional(),
  bgMusicVolume: z.number().default(0.15),
  words: z.array(wordSchema),
  mode: z.enum(["FACTS", "STORY", "THIS_OR_THAT", "RANK_IT", "CAPTION_THIS", "NEWS", "NEWS_SERIOUS", "RIDDLE"]),
  category: z.string().default("general"),
  titleText: z.string().optional(),
  subtitleYPos: z.number().default(1600), // in pixels (out of 1920)
  captionStyle: z.enum(["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL"]).default("HORMOZI"),
  avatarUrl: z.string().optional(),
  backgrounds: z.array(backgroundSchema).default([]),
  thisOrThat: thisOrThatSchema.optional(),
  rankIt: rankItSchema.optional(),
  captionThis: captionThisSchema.optional(),
});

type ShortFlowProps = z.infer<typeof shortFlowSchema>;

// Helper function to check if asset path is video
const isVideoAsset = (src: string) => {
  const s = src.toLowerCase();
  return s.endsWith(".mp4") || s.endsWith(".mov") || s.endsWith(".webm");
};

// --- HELPER FOR INFLUENCER & PRESET SUBTITLES ---
const Subtitles: React.FC<{
  words: z.infer<typeof wordSchema>[];
  currentTime: number;
  yPos: number;
  fps: number;
  captionStyle?: "HORMOZI" | "GLOW_BOX" | "BOUNCE" | "MINIMAL";
}> = ({ words, currentTime, yPos, fps, captionStyle = "HORMOZI" }) => {
  const frame = useCurrentFrame();
  
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

          const rotation = isActive ? (index % 2 === 0 ? -4 : 4) : 0;

          return (
            <span
              key={index}
              style={{
                fontFamily: "Impact, Arial Black, sans-serif",
                fontSize: "96px",
                color: isActive ? getHormoziColor(w.word) : "#FFFFFF",
                opacity: isActive ? 1.0 : 0.60,
                textTransform: "uppercase",
                transform: `scale(${scale}) rotate(${rotation}deg)`,
                display: "inline-block",
                textShadow: "0px 10px 25px rgba(0,0,0,0.9), 5px 5px 0px #000000",
                WebkitTextStroke: "5px #000000",
                transition: "transform 0.06s ease-out, opacity 0.08s ease",
              }}
            >
              {w.word}
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
                fontFamily: "Impact, Arial Black, sans-serif",
                fontSize: "82px",
                color: isActive ? "#FFFFFF" : "#CBD5E1",
                background: isActive
                  ? "linear-gradient(135deg, #FF007F, #7928CA)"
                  : "rgba(15, 23, 42, 0.75)",
                padding: "10px 28px",
                borderRadius: "20px",
                border: isActive ? "3px solid #FF007F" : "2px solid rgba(255,255,255,0.15)",
                boxShadow: isActive ? "0 10px 30px rgba(255, 0, 127, 0.6)" : "0 5px 15px rgba(0,0,0,0.3)",
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
                fontFamily: "Impact, Arial Black, sans-serif",
                fontSize: "92px",
                color: isActive ? "#FFD700" : "#FFFFFF",
                opacity: isActive ? 1.0 : 0.7,
                textTransform: "uppercase",
                transform: `translateY(${translateY}px) scale(${scale})`,
                display: "inline-block",
                textShadow: isActive
                  ? "0 0 20px #FFD700, 0 0 40px #FF4500, 4px 4px 0px #000000"
                  : "3px 3px 0px #000000",
                WebkitTextStroke: "4px #000000",
                transition: "transform 0.08s ease-out, color 0.08s ease",
              }}
            >
              {w.word}
            </span>
          );
        }

        // 4. MINIMAL STYLING (Clean dark box with crisp modern text)
        const scale = isActive ? 1.05 : 1.0;
        return (
          <span
            key={index}
            style={{
              fontFamily: "Arial Black, sans-serif",
              fontSize: "78px",
              color: isActive ? "#38BDF8" : "#F1F5F9",
              background: "rgba(0, 0, 0, 0.85)",
              padding: "8px 22px",
              borderRadius: "12px",
              borderLeft: isActive ? "6px solid #38BDF8" : "none",
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
}> = ({ bg, fps, durationInFrames }) => {
  const frame = useCurrentFrame();
  
  // Smooth continuous camera zoom (Ken Burns)
  const scale = interpolate(
    frame,
    [0, durationInFrames],
    [1.04, 1.14],
    { extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ transform: `scale(${scale})`, transformOrigin: "center" }}>
      {bg.type === "video" ? (
        <OffthreadVideo
          src={staticFile(bg.path)}
          muted
          loop
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : (
        <Img
          src={staticFile(bg.path)}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      )}
    </AbsoluteFill>
  );
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
  avatarUrl,
  backgrounds,
  thisOrThat,
  rankIt,
  captionThis,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();
  const currentTime = frame / fps;
  const durationInSeconds = durationInFrames / fps;

  // Snap progression for progress bar
  const progressPercent = Math.min(100, (currentTime / durationInSeconds) * 100);

  return (
    <AbsoluteFill style={{ backgroundColor: "#0b0c10", overflow: "hidden" }}>
      {/* 1. PRIMARY VOICE AUDIO */}
      <Audio src={staticFile(audioUrl)} />

      {/* 2. OPTIONAL BACKGROUND MUSIC */}
      {bgMusicUrl && (
        <Audio src={staticFile(bgMusicUrl)} volume={bgMusicVolume} loop />
      )}

      {/* 3. DYNAMIC BACKGROUND LAYOUTS */}
      {mode === "THIS_OR_THAT" && thisOrThat ? (
        // Split-screen comparison layout
        <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%" }}>
          {/* Top Panel (Option A) */}
          <div style={{ flex: 1, position: "relative", overflow: "hidden", borderBottom: "8px solid #ff007f" }}>
            {isVideoAsset(thisOrThat.imageA) ? (
              <OffthreadVideo
                src={staticFile(thisOrThat.imageA)}
                muted
                loop
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            ) : (
              <Img
                src={staticFile(thisOrThat.imageA)}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            )}
            {/* Glassmorphic Option A Label */}
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
                  fontFamily: "Impact, Arial Black, sans-serif",
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
              <OffthreadVideo
                src={staticFile(thisOrThat.imageB)}
                muted
                loop
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            ) : (
              <Img
                src={staticFile(thisOrThat.imageB)}
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
                  fontFamily: "Impact, Arial Black, sans-serif",
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
                fontFamily: "Impact, Arial Black, sans-serif",
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
                      src={staticFile(item.image)}
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
                        fontFamily: "Impact, Arial Black, sans-serif",
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
                        fontFamily: "Impact, Arial Black, sans-serif",
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
              src={staticFile(captionThis.image)}
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
                fontFamily: "Impact, Arial Black, sans-serif",
                fontSize: "80px",
                color: "#000000",
                textTransform: "uppercase",
              }}
            >
              {captionThis.promptText}
            </span>
          </div>
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
                />
              </Sequence>
            );
          })}
        </div>
      )}

      {/* 4. OVERLAYS (HEADER/TITLE/TICKER) */}
      {titleText && (
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
                fontFamily: "Impact, Arial Black, sans-serif",
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

      {/* 5. STYLISH CAPTIONS */}
      <Subtitles
        words={words}
        currentTime={currentTime}
        yPos={subtitleYPos}
        fps={fps}
        captionStyle={captionStyle}
      />

      {/* 6. PROGRESS BAR (Snappy sliding bottom bar) */}
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
