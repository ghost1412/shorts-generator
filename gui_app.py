import os
import sys
import threading
import subprocess
import json

try:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "customtkinter", "pillow"], check=True)
    import customtkinter as ctk
    from tkinter import filedialog, messagebox

# Configure theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ModernShortsGeneratorUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⚡ ShortsFlow AI Studio - Complete AI & Master Engine")
        self.geometry("1040x840")
        self.minsize(940, 740)

        # Header Frame
        self.create_header()

        # Tabview navigation
        self.tabview = ctk.CTkTabview(self, width=1000, height=640)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(10, 10))

        self.tab_clipping = self.tabview.add("✂️ Video Extraction")
        self.tab_context = self.tabview.add("🧠 AI Context & Styles")
        self.tab_llms = self.tabview.add("🤖 Integrated LLMs & Models")
        self.tab_modes = self.tabview.add("🎬 Standalone Modes & Manim")
        self.tab_quality = self.tabview.add("📐 Resolution & Quality")
        self.tab_character = self.tabview.add("🧙 Story Creator")
        self.tab_advanced = self.tabview.add("⚙️ Advanced & Batch")
        self.tab_logs = self.tabview.add("📋 Execution Logs")

        self.build_clipping_tab()
        self.build_context_tab()
        self.build_llms_tab()
        self.build_modes_tab()
        self.build_quality_tab()
        self.build_character_tab()
        self.build_advanced_tab()
        self.build_logs_tab()

        # Footer Action Bar
        self.create_footer()

    def create_header(self):
        header = ctk.CTkFrame(self, fg_color="#0F172A", height=70, corner_radius=10)
        header.pack(fill="x", padx=20, pady=(15, 5))

        title_label = ctk.CTkLabel(
            header, 
            text="⚡ ShortsFlow AI Studio", 
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#38BDF8"
        )
        title_label.pack(side="left", padx=20, pady=10)

        subtitle_label = ctk.CTkLabel(
            header, 
            text="Autonomous Short/Long Video Pipeline & Multi-LLM Engine", 
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#94A3B8"
        )
        subtitle_label.pack(side="left", pady=10)

        gpu_badge = ctk.CTkLabel(
            header,
            text="🟢 RTX 4060 GPU CUDA Active",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#064E3B",
            text_color="#34D399",
            corner_radius=6,
            padx=10,
            pady=4
        )
        gpu_badge.pack(side="right", padx=20, pady=15)

    def build_llms_tab(self):
        # 1. API Keys & Provider Settings Card
        keys_card = ctk.CTkFrame(self.tab_llms, fg_color="#1E293B", corner_radius=10)
        keys_card.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(keys_card, text="🔑 API Keys & Provider Integration", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 2))
        ctk.CTkLabel(keys_card, text="Paste your custom Gemini, HuggingFace, or Stock API keys below to integrate your own accounts.", font=ctk.CTkFont(size=11), text_color="#94A3B8").pack(anchor="w", padx=15, pady=(0, 10))

        grid_keys = ctk.CTkFrame(keys_card, fg_color="transparent")
        grid_keys.pack(fill="x", padx=15, pady=(0, 10))

        # Gemini API Key
        ctk.CTkLabel(grid_keys, text="⚡ Gemini API Key:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38BDF8").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        self.gemini_key_entry = ctk.CTkEntry(grid_keys, placeholder_text="Paste your Gemini API Key (e.g. AIzaSy...)", width=450, show="*")
        self.gemini_key_entry.insert(0, os.getenv("GEMINI_API_KEY", ""))
        self.gemini_key_entry.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=6)

        # HuggingFace API Key
        ctk.CTkLabel(grid_keys, text="🤗 HuggingFace Key:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#FBBF24").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        self.hf_key_entry = ctk.CTkEntry(grid_keys, placeholder_text="Paste your HuggingFace Token (hf_...)", width=450, show="*")
        self.hf_key_entry.insert(0, os.getenv("HF_API_KEY", ""))
        self.hf_key_entry.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=6)

        # Pexels API Key
        ctk.CTkLabel(grid_keys, text="📹 Pexels Stock Key:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#34D399").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        self.pexels_key_entry = ctk.CTkEntry(grid_keys, placeholder_text="Paste your Pexels Stock API Key", width=450, show="*")
        self.pexels_key_entry.insert(0, os.getenv("PEXELS_API_KEY", ""))
        self.pexels_key_entry.grid(row=2, column=1, sticky="w", padx=(0, 10), pady=6)

        # Force Ollama Switch
        self.ollama_switch = ctk.CTkSwitch(grid_keys, text="🦙 Force Local Ollama LLM (Bypass Cloud API for Offline/Privacy)")
        self.ollama_switch.grid(row=3, column=0, columnspan=2, sticky="w", pady=6)

        save_btn = ctk.CTkButton(grid_keys, text="💾 Save API Keys", width=140, fg_color="#0284C7", hover_color="#0369A1", command=self.save_api_keys)
        save_btn.grid(row=0, column=2, rowspan=4, padx=15, pady=6, sticky="ns")

        # 2. Model Status & Cascading Hierarchy Card
        card = ctk.CTkFrame(self.tab_llms, fg_color="#1E293B", corner_radius=10)
        card.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(card, text="🤖 Integrated AI LLMs & Cascading Fallback Hierarchy", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 5))
        ctk.CTkLabel(card, text="ShortsFlow AI automatically cascades across these models for maximum intelligence and zero downtime.", text_color="#94A3B8").pack(anchor="w", padx=15, pady=(0, 15))

        # Model Grid Cards
        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=5)

        # 1. Google Gemini API
        m1 = ctk.CTkFrame(grid, fg_color="#0F172A", corner_radius=8, border_width=1, border_color="#38BDF8")
        m1.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(m1, text="⚡ Google Gemini API", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38BDF8").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(m1, text="Models: gemini-3.7-flash, gemini-3.6-flash\nStatus: Integrated Primary API\nRole: Viral script generation & narrative extractions", font=ctk.CTkFont(size=11), text_color="#CBD5E1", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        # 2. Local Ollama LLM
        m2 = ctk.CTkFrame(grid, fg_color="#0F172A", corner_radius=8, border_width=1, border_color="#10B981")
        m2.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(m2, text="🦙 Local Ollama LLM", font=ctk.CTkFont(size=13, weight="bold"), text_color="#34D399").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(m2, text="Models: qwen3:8b (or local Qwen/Llama)\nStatus: Integrated Local Privacy Fallback\nRole: Unlimited offline processing & reasoning", font=ctk.CTkFont(size=11), text_color="#CBD5E1", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        # 3. HuggingFace Router API
        m3 = ctk.CTkFrame(grid, fg_color="#0F172A", corner_radius=8, border_width=1, border_color="#F59E0B")
        m3.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(m3, text="🤗 HuggingFace Router", font=ctk.CTkFont(size=13, weight="bold"), text_color="#FBBF24").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(m3, text="Models: meta-llama/Llama-3.1-8B-Instruct\nStatus: Integrated Secondary Cloud API\nRole: Facts, WYR & Trivia generator fallback", font=ctk.CTkFont(size=11), text_color="#CBD5E1", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        # 4. Whisper GPU Transcription
        m4 = ctk.CTkFrame(grid, fg_color="#0F172A", corner_radius=8, border_width=1, border_color="#8B5CF6")
        m4.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(m4, text="🎙️ Faster-Whisper GPU Engine", font=ctk.CTkFont(size=13, weight="bold"), text_color="#C084FC").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(m4, text="Models: Whisper Medium/Large-v3 (FP16 CUDA)\nStatus: NVIDIA RTX GPU Accelerated (~10x speed)\nRole: Word-level timestamped transcription", font=ctk.CTkFont(size=11), text_color="#CBD5E1", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

    def save_api_keys(self):
        gemini_key = self.gemini_key_entry.get().strip()
        hf_key = self.hf_key_entry.get().strip()
        pexels_key = self.pexels_key_entry.get().strip()

        if gemini_key: os.environ["GEMINI_API_KEY"] = gemini_key
        if hf_key: os.environ["HF_API_KEY"] = hf_key
        if pexels_key: os.environ["PEXELS_API_KEY"] = pexels_key

        env_file = ".env"
        env_vars = {}
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if "=" in line and not line.strip().startswith("#"):
                            parts = line.strip().split("=", 1)
                            env_vars[parts[0].strip()] = parts[1].strip()
            except Exception:
                pass

        if gemini_key: env_vars["GEMINI_API_KEY"] = gemini_key
        if hf_key: env_vars["HF_API_KEY"] = hf_key
        if pexels_key: env_vars["PEXELS_API_KEY"] = pexels_key

        try:
            with open(env_file, "w", encoding="utf-8") as f:
                for k, v in env_vars.items():
                    f.write(f"{k}={v}\n")
        except Exception as e:
            print(f"[Warning] Failed to write .env file: {e}")

        messagebox.showinfo("ShortsFlow AI", "✅ API Keys saved successfully!\nYour custom Gemini API Key will be used for all video generations.")

    def build_clipping_tab(self):
        card1 = ctk.CTkFrame(self.tab_clipping, fg_color="#1E293B", corner_radius=10)
        card1.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(card1, text="📹 Video Source (YouTube URL or Local File)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 5))

        src_frame = ctk.CTkFrame(card1, fg_color="transparent")
        src_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.source_entry = ctk.CTkEntry(
            src_frame, 
            placeholder_text="Paste YouTube Link (https://www.youtube.com/watch?v=...) or select video file path", 
            width=680
        )
        self.source_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(src_frame, text="📁 Browse", width=90, command=self.browse_source_file)
        browse_btn.pack(side="right")

        card2 = ctk.CTkFrame(self.tab_clipping, fg_color="#1E293B", corner_radius=10)
        card2.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(card2, text="🎛️ Extraction & Duration Controls", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 10))

        grid = ctk.CTkFrame(card2, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=(0, 15))

        # Extract Mode (Shorts vs Long)
        ctk.CTkLabel(grid, text="Extraction Format:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 5), pady=8)
        self.extract_mode_dropdown = ctk.CTkOptionMenu(
            grid,
            values=[
                "shorts (Short-form 9:16 vertical clips up to 60s)",
                "long (Long-form extended highlights / compilations)"
            ],
            width=360
        )
        self.extract_mode_dropdown.grid(row=0, column=1, columnspan=2, sticky="w", pady=8)

        # Clip Count Slider
        ctk.CTkLabel(grid, text="Clip Count:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=8)
        self.clip_count_lbl = ctk.CTkLabel(grid, text="3 clips", font=ctk.CTkFont(weight="bold"))
        self.clip_count_lbl.grid(row=1, column=1, sticky="w", padx=(0, 15), pady=8)

        self.clip_slider = ctk.CTkSlider(grid, from_=1, to=30, number_of_steps=29, command=self.update_clip_lbl, width=220)
        self.clip_slider.set(3)
        self.clip_slider.grid(row=1, column=2, sticky="w", padx=(0, 30), pady=8)

        # UNLIMITED Target Duration Input
        ctk.CTkLabel(grid, text="Target Duration (Seconds):", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, sticky="w", padx=(0, 5), pady=8)
        
        dur_frame = ctk.CTkFrame(grid, fg_color="transparent")
        dur_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=8)

        self.dur_entry = ctk.CTkEntry(dur_frame, width=100)
        self.dur_entry.insert(0, "30")
        self.dur_entry.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(dur_frame, text="(Enter any duration: e.g. 30s, 60s, 180s, 300s, 600s, 1800s)").pack(side="left")

        # Toggles
        card3 = ctk.CTkFrame(self.tab_clipping, fg_color="#1E293B", corner_radius=10)
        card3.pack(fill="x", padx=15, pady=10)

        toggles_frame = ctk.CTkFrame(card3, fg_color="transparent")
        toggles_frame.pack(fill="x", padx=15, pady=15)

        self.smart_crop_switch = ctk.CTkSwitch(toggles_frame, text="AI Smart Crop (9:16 Face Tracking)")
        self.smart_crop_switch.select()
        self.smart_crop_switch.grid(row=0, column=0, padx=(0, 20), pady=5, sticky="w")

        self.tighten_switch = ctk.CTkSwitch(toggles_frame, text="Tighten Pacing (Silence Removal)")
        self.tighten_switch.select()
        self.tighten_switch.grid(row=0, column=1, padx=(0, 20), pady=5, sticky="w")

        self.mashup_switch = ctk.CTkSwitch(toggles_frame, text="Combine into Single Reel (Mashup)")
        self.mashup_switch.grid(row=0, column=2, pady=5, sticky="w")

        self.audio_detect_switch = ctk.CTkSwitch(toggles_frame, text="Use Audio Signal Detection (Spikes)")
        self.audio_detect_switch.grid(row=1, column=0, padx=(0, 20), pady=5, sticky="w")

        self.cache_switch = ctk.CTkSwitch(toggles_frame, text="Reuse Cached Transcripts & Videos")
        self.cache_switch.select()
        self.cache_switch.grid(row=1, column=1, pady=5, sticky="w")

    def update_clip_lbl(self, val):
        self.clip_count_lbl.configure(text=f"{int(val)} clips")

    def build_context_tab(self):
        card = ctk.CTkFrame(self.tab_context, fg_color="#1E293B", corner_radius=10)
        card.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(card, text="🧠 AI Extraction Instructions & Style Presets", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 10))

        # 1. Multiple Editing Style Presets Checkboxes
        style_frame = ctk.CTkFrame(card, fg_color="transparent")
        style_frame.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(style_frame, text="Editing Style Presets (Select one or multiple):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 5))

        styles_grid = ctk.CTkFrame(style_frame, fg_color="transparent")
        styles_grid.pack(fill="x", pady=5)

        self.style_meme_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(styles_grid, text="Meme (Sound Effects, Zooms & Captions)", variable=self.style_meme_var).grid(row=0, column=0, padx=(0, 20), pady=5, sticky="w")

        self.style_funny_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(styles_grid, text="Funny (Comedy Effects & Fast Pacing)", variable=self.style_funny_var).grid(row=0, column=1, padx=(0, 20), pady=5, sticky="w")

        self.style_action_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(styles_grid, text="Action (High Energy Transitions & Cuts)", variable=self.style_action_var).grid(row=0, column=2, pady=5, sticky="w")

        self.style_sarcastic_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(styles_grid, text="Sarcastic (Deadpan Commentary & SFX)", variable=self.style_sarcastic_var).grid(row=1, column=0, padx=(0, 20), pady=5, sticky="w")

        self.style_stylish_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(styles_grid, text="Stylish (Cinematic Grading & Smooth Cuts)", variable=self.style_stylish_var).grid(row=1, column=1, padx=(0, 20), pady=5, sticky="w")

        # 2. Dedicated User Context Box
        ctx_frame = ctk.CTkFrame(card, fg_color="transparent")
        ctx_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(ctx_frame, text="User Narrative Context (--user_context):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(ctx_frame, text="Guide the AI on what specific scenes or content to extract (e.g. 'Extract high-speed police chases and funny GTA fails').", text_color="#94A3B8").pack(anchor="w", pady=(0, 5))
        self.user_context_box = ctk.CTkTextbox(ctx_frame, height=75)
        self.user_context_box.pack(fill="x")

        # 3. Dedicated Style Context Box
        sctx_frame = ctk.CTkFrame(card, fg_color="transparent")
        sctx_frame.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(sctx_frame, text="Editing Style Context (--style_context):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(sctx_frame, text="Custom instructions for pacing and visual editing (e.g. 'Ultra fast cuts, dramatic bass drops, zoom in on funny faces').", text_color="#94A3B8").pack(anchor="w", pady=(0, 5))
        self.style_context_box = ctk.CTkTextbox(sctx_frame, height=75)
        self.style_context_box.pack(fill="x")

    def build_quality_tab(self):
        card = ctk.CTkFrame(self.tab_quality, fg_color="#1E293B", corner_radius=10)
        card.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(card, text="📐 Resolution, Format & Bitrate Controls", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 10))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=5)

        # Aspect Ratio / Resolution
        ctk.CTkLabel(grid, text="Resolution & Format:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=8)
        self.res_dropdown = ctk.CTkOptionMenu(
            grid,
            values=[
                "9:16 Vertical (Shorts/Reels/TikTok - 1080x1920)",
                "16:9 Landscape (YouTube Standard - 1920x1080)",
                "1:1 Square (Instagram Post - 1080x1080)",
                "4:5 Portrait (Social Feed - 1080x1350)"
            ],
            width=380
        )
        self.res_dropdown.grid(row=0, column=1, columnspan=2, sticky="w", pady=8)

        # Quality Preset
        ctk.CTkLabel(grid, text="Render Quality Preset:", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=8)
        self.quality_dropdown = ctk.CTkOptionMenu(
            grid,
            values=["Medium (12M Bitrate - Standard)", "High (25M Bitrate - HQ Master)", "Ultra (50M Bitrate - 4K Crisp)", "Low (4M Bitrate - Fast Draft)"],
            width=380
        )
        self.quality_dropdown.grid(row=1, column=1, columnspan=2, sticky="w", pady=8)

        # Manual Bitrate & FFmpeg Preset
        ctk.CTkLabel(grid, text="Manual Bitrate (e.g. 15000k):").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=8)
        self.bitrate_entry = ctk.CTkEntry(grid, placeholder_text="Auto (leave blank for preset)", width=220)
        self.bitrate_entry.grid(row=2, column=1, sticky="w", pady=8)

        ctk.CTkLabel(grid, text="FFmpeg Preset:").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=8)
        self.preset_dropdown = ctk.CTkOptionMenu(
            grid,
            values=["medium (Balanced)", "ultrafast (Fastest)", "slow (High Quality)", "slower (Maximum Compression)"],
            width=220
        )
        self.preset_dropdown.grid(row=3, column=1, sticky="w", pady=8)

    def build_modes_tab(self):
        card = ctk.CTkFrame(self.tab_modes, fg_color="#1E293B", corner_radius=10)
        card.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(card, text="🎬 Standalone Content Generation Modes", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 10))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=5)

        # Mode Dropdown
        ctk.CTkLabel(grid, text="Select Content Mode:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        self.mode_dropdown = ctk.CTkOptionMenu(
            grid,
            values=[
                "FACTS (2 Truths 1 Lie)",
                "STORY (AI First-Person Story)",
                "EXPLAINER (Manim Math/Code Animations)",
                "MUSIC (AI Audio & Visuals)",
                "RIDDLE (Lateral Thinking Challenge)",
                "NEWS (RSS Headlines)",
                "NEWS_SERIOUS",
                "REDDIT (AITA Drama)",
                "TRIVIA (3 Options Reveal)",
                "QUOTE (Cinematic Deep Quotes)",
                "JWST (Space & Universe)",
                "WYR (Would You Rather)",
                "FIND_IT (Spot the Hidden Object)",
                "ODD_ONE_OUT",
                "GUESS_SOUND"
            ],
            width=360
        )
        self.mode_dropdown.grid(row=0, column=1, sticky="w", pady=5)

        # Topic / Prompt
        ctk.CTkLabel(grid, text="Prompt / Topic / Title:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        self.prompt_entry = ctk.CTkEntry(grid, placeholder_text="e.g. 'Mind-bending quantum physics facts' or 'Pythagorean Theorem'", width=480)
        self.prompt_entry.grid(row=1, column=1, columnspan=2, sticky="w", pady=5)

        # Custom Script Box
        ctk.CTkLabel(grid, text="Custom Script (Optional):").grid(row=2, column=0, sticky="nw", padx=(0, 10), pady=5)
        self.script_box = ctk.CTkTextbox(grid, width=480, height=75)
        self.script_box.grid(row=2, column=1, columnspan=2, sticky="w", pady=5)

        # Custom Background Media (Image or Video)
        ctk.CTkLabel(grid, text="Custom BG Media:").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=5)
        bg_frame = ctk.CTkFrame(grid, fg_color="transparent")
        bg_frame.grid(row=3, column=1, columnspan=2, sticky="w", pady=5)

        self.bg_media_entry = ctk.CTkEntry(bg_frame, placeholder_text="Path to custom background video (.mp4/.mov) or image (.png/.jpg)...", width=380)
        self.bg_media_entry.pack(side="left", padx=(0, 10))

        browse_bg_btn = ctk.CTkButton(bg_frame, text="📁 Browse Media", width=100, command=self.browse_bg_media)
        browse_bg_btn.pack(side="left")

        # Category, Persona, Vibe
        opt_grid = ctk.CTkFrame(card, fg_color="transparent")
        opt_grid.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(opt_grid, text="Category:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.cat_dropdown = ctk.CTkOptionMenu(
            opt_grid,
            values=["science", "space", "history", "tech", "gaming", "animals", "cooking_hacks", "world", "politics"],
            width=150
        )
        self.cat_dropdown.grid(row=0, column=1, padx=(0, 15))

        ctk.CTkLabel(opt_grid, text="Music Vibe:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.vibe_dropdown = ctk.CTkOptionMenu(
            opt_grid,
            values=["suspense", "spooky", "cinematic", "upbeat"],
            width=140
        )
        self.vibe_dropdown.grid(row=0, column=3, padx=(0, 15))

        ctk.CTkLabel(opt_grid, text="Cartoon Persona:").grid(row=0, column=4, sticky="w", padx=(0, 5))
        self.persona_dropdown = ctk.CTkOptionMenu(
            opt_grid,
            values=["Default", "mafia_cat", "orange_cat", "rabbit", "robot", "superhero"],
            width=140
        )
        self.persona_dropdown.grid(row=0, column=5)

    def build_character_tab(self):
        card = ctk.CTkFrame(self.tab_character, fg_color="#1E293B", corner_radius=10)
        card.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(card, text="🧙 Interactive Story & Kids Character Creator", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 10))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(grid, text="Hero Type:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        self.hero_entry = ctk.CTkEntry(grid, placeholder_text="e.g. friendly dragon, brave knight, teddy bear", width=420)
        self.hero_entry.grid(row=0, column=1, sticky="w", pady=6)

        ctk.CTkLabel(grid, text="Hero Name:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        self.hero_name_entry = ctk.CTkEntry(grid, placeholder_text="e.g. Barnaby, Luna, Sparky", width=420)
        self.hero_name_entry.grid(row=1, column=1, sticky="w", pady=6)

        ctk.CTkLabel(grid, text="Companion:").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        self.companion_entry = ctk.CTkEntry(grid, placeholder_text="e.g. Twinkle the Pixie, Barnaby the Owl", width=420)
        self.companion_entry.grid(row=2, column=1, sticky="w", pady=6)

        ctk.CTkLabel(grid, text="Adventure Quest:").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=6)
        self.quest_entry = ctk.CTkEntry(grid, placeholder_text="e.g. Finding the Lost Crystal of Wisdom", width=420)
        self.quest_entry.grid(row=3, column=1, sticky="w", pady=6)

        ctk.CTkLabel(grid, text="Adventure Setting:").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=6)
        self.setting_entry = ctk.CTkEntry(grid, placeholder_text="e.g. Starry Night Forest, Enchanted Castle", width=420)
        self.setting_entry.grid(row=4, column=1, sticky="w", pady=6)

    def build_advanced_tab(self):
        card = ctk.CTkFrame(self.tab_advanced, fg_color="#1E293B", corner_radius=10)
        card.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(card, text="⚙️ Batch Processing, ComfyUI & Export Settings", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 10))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=5)

        # Batch File
        ctk.CTkLabel(grid, text="Batch File (urls.txt):").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        self.batch_entry = ctk.CTkEntry(grid, placeholder_text="Path to text file containing video URLs (one per line)", width=460)
        self.batch_entry.grid(row=0, column=1, sticky="w", pady=5)
        ctk.CTkButton(grid, text="Browse", width=80, command=self.browse_batch_file).grid(row=0, column=2, padx=(10, 0))

        # Output JSON Export
        ctk.CTkLabel(grid, text="JSON Export Path:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        self.json_entry = ctk.CTkEntry(grid, placeholder_text="e.g. output_results.json", width=460)
        self.json_entry.grid(row=1, column=1, sticky="w", pady=5)

        # Switches
        sw_frame = ctk.CTkFrame(card, fg_color="transparent")
        sw_frame.pack(fill="x", padx=15, pady=15)

        self.remotion_switch = ctk.CTkSwitch(sw_frame, text="Use Remotion Engine")
        self.remotion_switch.pack(side="left", padx=(0, 15))

        self.comfy_switch = ctk.CTkSwitch(sw_frame, text="Use ComfyUI AI Backgrounds")
        self.comfy_switch.pack(side="left", padx=(0, 15))

        self.skip_upload_switch = ctk.CTkSwitch(sw_frame, text="Skip Social Uploads")
        self.skip_upload_switch.select()
        self.skip_upload_switch.pack(side="left")

    def build_logs_tab(self):
        card = ctk.CTkFrame(self.tab_logs, fg_color="#1E293B", corner_radius=10)
        card.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(card, text="📋 Real-Time Execution Log Console", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 5))

        self.log_text = ctk.CTkTextbox(card, font=ctk.CTkFont(family="Consolas", size=12), text_color="#E2E8F0", fg_color="#0F172A")
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    def create_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(5, 15))

        self.generate_btn = ctk.CTkButton(
            footer,
            text="🚀 GENERATE VIDEO PIPELINE NOW",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            height=48,
            command=self.start_generation
        )
        self.generate_btn.pack(fill="x")

    def browse_source_file(self):
        fn = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.mov *.mkv *.webm"), ("All Files", "*.*")])
        if fn:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, fn)

    def browse_batch_file(self):
        fn = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if fn:
            self.batch_entry.delete(0, "end")
            self.batch_entry.insert(0, fn)

    def browse_bg_media(self):
        fn = filedialog.askopenfilename(filetypes=[("Media Files", "*.mp4 *.mov *.png *.jpg *.jpeg *.webp"), ("All Files", "*.*")])
        if fn:
            self.bg_media_entry.delete(0, "end")
            self.bg_media_entry.insert(0, fn)

    def log(self, msg):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def start_generation(self):
        self.tabview.set("📋 Execution Logs")
        self.log_text.delete("1.0", "end")
        self.generate_btn.configure(state="disabled", text="⏳ PIPELINE RUNNING...")

        threading.Thread(target=self.run_generation_thread, daemon=True).start()

    def run_generation_thread(self):
        try:
            python_exe = sys.executable
            gpu_python = r"C:\Users\win10\AppData\Local\Programs\Python\Python312\python.exe"
            if os.path.exists(gpu_python):
                python_exe = gpu_python

            cmd = [python_exe, "main.py"]

            source = self.source_entry.get().strip()
            batch = self.batch_entry.get().strip()
            mode_choice = self.mode_dropdown.get()

            # Resolution & Quality Mapping
            q_choice = self.quality_dropdown.get()
            if "High" in q_choice: cmd.extend(["--quality", "high"])
            elif "Ultra" in q_choice: cmd.extend(["--quality", "ultra"])
            elif "Low" in q_choice: cmd.extend(["--quality", "low"])
            else: cmd.extend(["--quality", "medium"])

            bitrate = self.bitrate_entry.get().strip()
            if bitrate: cmd.extend(["--bitrate", bitrate])

            preset_choice = self.preset_dropdown.get().split()[0]
            if preset_choice: cmd.extend(["--preset", preset_choice])

            # Character Creator
            hero = self.hero_entry.get().strip()
            if hero: cmd.extend(["--hero", hero])

            hero_name = self.hero_name_entry.get().strip()
            if hero_name: cmd.extend(["--hero_name", hero_name])

            companion = self.companion_entry.get().strip()
            if companion: cmd.extend(["--companion", companion])

            quest = self.quest_entry.get().strip()
            if quest: cmd.extend(["--quest", quest])

            setting = self.setting_entry.get().strip()
            if setting: cmd.extend(["--setting", setting])

            # Mode vs Extraction determination
            if source:
                cmd.extend(["--source_video", source])
                
                # Extract Format (shorts vs long)
                ext_fmt = self.extract_mode_dropdown.get().split()[0]
                cmd.extend(["--extract_mode", ext_fmt])

                cmd.extend(["--clip_count", str(int(self.clip_slider.get()))])

                # Unlimited Target Duration
                target_dur = self.dur_entry.get().strip()
                if target_dur:
                    cmd.extend(["--target_duration", target_dur])

                if self.smart_crop_switch.get(): cmd.append("--smart_crop")
                if self.tighten_switch.get(): cmd.append("--tighten")
                if self.mashup_switch.get(): cmd.append("--mashup")
                if self.audio_detect_switch.get(): cmd.append("--use_audio_detect")
                if self.cache_switch.get(): cmd.append("--use_cache")
                
                # Multiple Style Presets Flags
                if self.style_meme_var.get(): cmd.extend(["--style", "meme"])
                if self.style_funny_var.get(): cmd.extend(["--style", "funny"])
                if self.style_action_var.get(): cmd.extend(["--style", "action"])
                if self.style_sarcastic_var.get(): cmd.extend(["--style", "sarcastic"])
                if self.style_stylish_var.get(): cmd.extend(["--style", "stylish"])

            elif batch:
                cmd.extend(["--batch_file", batch])
            else:
                mode_key = mode_choice.split()[0]
                cmd.extend(["--mode", mode_key])

                prompt = self.prompt_entry.get().strip()
                if prompt: cmd.extend(["--prompt", prompt])

                script = self.script_box.get("1.0", "end").strip()
                if script: cmd.extend(["--script", script])

                cmd.extend(["--category", self.cat_dropdown.get()])
                cmd.extend(["--vibe", self.vibe_dropdown.get()])

                persona = self.persona_dropdown.get()
                if persona != "Default": cmd.extend(["--persona", persona])

            # User Context & Style Context
            user_ctx = self.user_context_box.get("1.0", "end").strip()
            if user_ctx: cmd.extend(["--user_context", user_ctx])

            style_ctx = self.style_context_box.get("1.0", "end").strip()
            if style_ctx: cmd.extend(["--style_context", style_ctx])

            json_out = self.json_entry.get().strip()
            if json_out: cmd.extend(["--output_json", json_out])

            if self.remotion_switch.get(): cmd.append("--use_remotion")
            if self.comfy_switch.get(): cmd.append("--use_comfy")
            if self.skip_upload_switch.get(): cmd.append("--skip-upload")
            if hasattr(self, "ollama_switch") and self.ollama_switch.get(): cmd.append("--use_ollama")

            bg_media = self.bg_media_entry.get().strip() if hasattr(self, "bg_media_entry") else ""
            if bg_media: cmd.extend(["--bg_media", bg_media])

            self.log("============================================================")
            self.log(f"[ShortsFlow Studio] Executing Command:")
            self.log(f"   {' '.join(cmd)}")
            self.log("============================================================\n")

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            if hasattr(self, "gemini_key_entry") and self.gemini_key_entry.get().strip():
                env["GEMINI_API_KEY"] = self.gemini_key_entry.get().strip()
            if hasattr(self, "hf_key_entry") and self.hf_key_entry.get().strip():
                env["HF_API_KEY"] = self.hf_key_entry.get().strip()
            if hasattr(self, "pexels_key_entry") and self.pexels_key_entry.get().strip():
                env["PEXELS_API_KEY"] = self.pexels_key_entry.get().strip()

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env
            )

            for line in proc.stdout:
                self.after(0, self.log, line.strip())

            proc.wait()

            if proc.returncode == 0:
                self.after(0, self.on_success)
            else:
                self.after(0, self.on_failure, f"Process failed with exit code {proc.returncode}")

        except Exception as e:
            self.after(0, self.on_failure, str(e))

    def on_success(self):
        self.generate_btn.configure(state="normal", text="🚀 GENERATE VIDEO PIPELINE NOW")
        self.log("\n============================================================")
        self.log("🎉 SUCCESS! Video generation completed. Output saved in sessions/")
        self.log("============================================================")
        messagebox.showinfo("ShortsFlow AI", "Generation Completed Successfully!\nOutput saved in 'sessions/' folder.")

    def on_failure(self, err):
        self.generate_btn.configure(state="normal", text="🚀 GENERATE VIDEO PIPELINE NOW")
        self.log(f"\n[Error] Pipeline error: {err}")
        messagebox.showerror("ShortsFlow AI Error", f"Generation error occurred:\n{err}")

if __name__ == "__main__":
    app = ModernShortsGeneratorUI()
    app.mainloop()
