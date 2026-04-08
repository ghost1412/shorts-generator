# 🌊 ShortsFlow: Project Overview

ShortsFlow is a high-performance, AI-driven video automation platform designed to turn long-form content into viral YouTube Shorts, TikToks, and Reels, or generate original content from scratch. 

---

## 🚀 Current Capabilities

### 1. AI-Driven Highlight Extraction (`EXTRACT` Mode)
*   **Transcript Analysis**: Uses OpenAI/HuggingFace LLMs to identify high-potential oral segments from long-form video.
*   **Audio Signal Processing**: Detects emotional spikes via energy/pitch variance and audio deltas (sudden loudness/excitement).
*   **Motion Tracking**: OpenCV-based analysis to identify action-heavy scenes and visually interesting moments.
*   **Smart Cropping**: AI face-tracking and interest-point detection to dynamically center subjects in a vertical 9:16 frame.
*   **Auto-Editing**: "Tightens" clips by automatically removing or speeding up dead air and silences (AutoClip logic).

### 2. Autonomous Content Generation
*   **12+ Specialized Modes**:
    *   **FACTS**: "Spot the Lie" interactive challenges.
    *   **JWST**: Stunning cosmic shorts using the actual James Webb Space Telescope API.
    *   **NEWS**: Professional broadcast style with AI Cartoon Personas (Mafia Cat, Orange Cat, etc.).
    *   **FIND_IT**: Hidden object games with dynamic target placement.
    *   **WYR / TRIVIA**: High-engagement "Would You Rather" and Quiz formats.
    *   **REDDIT / STORY**: Narrative-driven storytelling with immersive backgrounds.
*   **Persona Engine**: Supports multiple character voices (Azure Neural) and animated avatars with automatic green-screen removal.

### 3. "Viral" Aesthetic Engine
*   **Burst Captions**: Word-by-word animated subtitles with keyword-aware coloring (e.g., "money" 💰 is green) and random tilting for an organic feel.
*   **Engagement Hacks**: 
    *   **Progress Bars**: Color-shifting urgency indicators (Yellow ➔ Red) to keep viewers till the last second.
    *   **Pattern Interrupts**: Mid-video flashes and zoom resets to keep the brain engaged.
    *   **Contextual Overlays**: Automated meme GIFs and stickers based on the video's tone.
    *   **Foley Synthesis**: Locally synthesized "Whooshes" and "Ambiance" for a premium soundscape.

### 4. Advanced Media Sourcing
*   **Hybrid Sourcing**: Pulls from Pexels (Stock), JWST API (Science), or a local "High Retention" pool (Minecraft Parkour, GTA Ramps, ASMR).
*   **A/B Background Testing**: Weighted selection favors high-retention gameplay to boost Average View Duration (AVD).
*   **ComfyUI Bridge**: Optional local integration for AI-generated cinematic backgrounds and unique AI soundtracks.

### 5. SaaS Infrastructure
*   **Dashboard**: Premium Next.js interface for managing videos, credits, and payments.
*   **Backend**: Python/FFmpeg engine optimized for parallel rendering.
*   **Automation**: GitHub Actions worker for 24/7 autonomous posting at $0 hosting cost.
*   **Payments**: Dual-gateway support (Stripe + **Lemon Squeezy**). Lemon Squeezy acts as a Merchant of Record, handling global taxes and compliance—making it ideal for users in India and beyond.

---

## 🛠️ Technical Architecture

ShortsFlow uses a **Decoupled Hybrid Architecture**:
*   **Frontend**: Next.js (Hosted on Vercel).
*   **Database/Auth**: Supabase (PostgreSQL + RLS).
*   **Worker Engine**: Python 3.12 + MoviePy + FFmpeg (Hosted on GitHub Actions or Local VPS).
*   **AI Stack**: Stable Whisper (Transcription), GPT-4/Mistral (Scripting), OpenCV (Vision), Librosa (Audio).

---

## 🔮 Future Roadmap (The Vision)

### Phase 1: Platform Expansion
*   **Platform-Specific Presets**: Auto-tune "Safe Zones" and editing styles for Reels vs. TikTok vs. Shorts.
*   **Multi-Language Dubbing**: Automatic translation and voice cloning for global channel empires.
*   **Face-Swap Branding**: Integrate AI face-swapping to put consistent "Host" faces on generated content.

### Phase 2: Intelligence & Optimization
*   **Analytics Feedback Loop**: Automatically adjust editing pacing and background types based on real YouTube Analytics (Views/Retention).
*   **Real-time Stream To Shorts**: Connect to a Twitch/YouTube live stream and extract highlights instantly as they happen.
*   **AI B-Roll Generation**: Use Stable Video Diffusion to generate literal visual representations for facts when stock footage is unavailable.

### Phase 3: Ecosystem Growth
*   **Mobile App**: A native iOS/Android app for "One-Tap" viral generation on the go.
*   **Team Workspaces**: Support for agencies with multi-user approval workflows.
*   **Live Marketplace**: A community hub for sharing custom "Editing Styles" and "Script Templates."
