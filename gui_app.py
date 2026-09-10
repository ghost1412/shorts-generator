import os
import sys
import threading
import subprocess
import json
import time

# PyInstaller Subprocess Hook: If running as compiled executable and given our flag, run backend.
if getattr(sys, 'frozen', False) and len(sys.argv) > 1 and sys.argv[1] == "--run-main-pipeline":
    sys.argv.pop(1)  # Remove flag
    import main
    sys.exit(0)

try:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "customtkinter", "pillow"], check=True)
    import customtkinter as ctk
    from tkinter import filedialog, messagebox

# Configure dark theme aesthetics
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ModernShortsGeneratorUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("⚡ ShortsFlow AI Studio - Complete AI Video Engine")
        self.geometry("1380x940")
        self.minsize(1200, 800)
        self.configure(fg_color="#0A0E17")  # Deep space dark background

        # State Variables
        self.selected_caption_style = "HORMOZI"
        self.is_running = False
        self.latest_output_file = None

        # Build UI Sections
        self.create_header()
        self.create_studio_layout()
        self.create_log_drawer()

    def create_header(self):
        """Top Header Bar with Glassmorphic Accent and Status Badges"""
        header = ctk.CTkFrame(self, fg_color="#0F172A", height=65, corner_radius=12, border_width=1, border_color="#1E293B")
        header.pack(fill="x", padx=16, pady=(12, 6))

        # Brand Logo & Title
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.pack(side="left", padx=16, pady=10)

        ctk.CTkLabel(
            brand_frame,
            text="⚡ ShortsFlow AI Studio",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#38BDF8"
        ).pack(side="left")

        ctk.CTkLabel(
            brand_frame,
            text="  |  Autonomous 9:16 Shorts & Video Studio",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#94A3B8"
        ).pack(side="left", padx=(5, 0))

        # Status Badges Frame
        badges_frame = ctk.CTkFrame(header, fg_color="transparent")
        badges_frame.pack(side="right", padx=16, pady=12)

        # GPU Badge
        gpu_label = ctk.CTkLabel(
            badges_frame,
            text="🟢 RTX GPU CUDA Active",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#064E3B",
            text_color="#34D399",
            corner_radius=6,
            padx=10,
            pady=4
        )
        gpu_label.pack(side="left", padx=4)

        # Remotion Engine Badge
        remotion_label = ctk.CTkLabel(
            badges_frame,
            text="⚡ Remotion React Engine",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1E1B4B",
            text_color="#A78BFA",
            corner_radius=6,
            padx=10,
            pady=4
        )
        remotion_label.pack(side="left", padx=4)

        # Folder Shortcut
        open_folder_btn = ctk.CTkButton(
            badges_frame,
            text="📁 sessions/",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#334155",
            hover_color="#475569",
            width=85,
            height=26,
            command=self.open_output_dir
        )
        open_folder_btn.pack(side="left", padx=4)

    def create_studio_layout(self):
        """Main 3-Column Studio Grid Layout"""
        self.studio_grid = ctk.CTkFrame(self, fg_color="transparent")
        self.studio_grid.pack(fill="both", expand=True, padx=16, pady=4)

        self.studio_grid.grid_columnconfigure(0, weight=3)  # Left Column: Inputs & Modes
        self.studio_grid.grid_columnconfigure(1, weight=4)  # Center Column: Video Canvas & Master CTA
        self.studio_grid.grid_columnconfigure(2, weight=3)  # Right Column: Subtitles & Aesthetics
        self.studio_grid.grid_rowconfigure(0, weight=1)

        self.build_left_pane()
        self.build_center_pane()
        self.build_right_pane()

    def build_left_pane(self):
        """Left Column: Source Video, Extraction Format, All Modes, LLM & Persona Voice"""
        scroll_left = ctk.CTkScrollableFrame(self.studio_grid, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#1E293B")
        scroll_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)

        # Title
        ctk.CTkLabel(scroll_left, text="📥 Source & Extraction Format", font=ctk.CTkFont(size=15, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=14, pady=(14, 2))
        ctk.CTkLabel(scroll_left, text="Specify video source link, extraction format & mode.", font=ctk.CTkFont(size=11), text_color="#94A3B8").pack(anchor="w", padx=14, pady=(0, 8))

        # 1. Source Video Card
        source_card = ctk.CTkFrame(scroll_left, fg_color="#1E293B", corner_radius=10)
        source_card.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(source_card, text="🎬 Source Video (YouTube URL or Local File):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#CBD5E1").pack(anchor="w", padx=12, pady=(10, 4))

        input_row = ctk.CTkFrame(source_card, fg_color="transparent")
        input_row.pack(fill="x", padx=12, pady=(0, 6))

        self.source_entry = ctk.CTkEntry(input_row, placeholder_text="Paste https://youtube.com/watch?v=...", height=34)
        self.source_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        browse_btn = ctk.CTkButton(input_row, text="📁 Browse", width=70, height=34, fg_color="#334155", hover_color="#475569", command=self.browse_file)
        browse_btn.pack(side="left")

        # Extraction Format Dropdown
        ctk.CTkLabel(source_card, text="🎞️ Video Extraction Format:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(anchor="w", padx=12, pady=(2, 2))
        self.extract_mode_menu = ctk.CTkOptionMenu(
            source_card,
            values=[
                "shorts (9:16 Vertical Viral Shorts)",
                "highlights (Single Peak Viral Moment)",
                "mashup (Combine All Clips into 1 Remix Video)",
                "long (Process Long-Form Timeline)"
            ],
            height=30,
            fg_color="#0F172A",
            button_color="#334155"
        )
        self.extract_mode_menu.pack(fill="x", padx=12, pady=(0, 10))

        # 2. Complete Generation Modes Selector
        mode_card = ctk.CTkFrame(scroll_left, fg_color="#1E293B", corner_radius=10)
        mode_card.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(mode_card, text="🎯 All Standalone Content Modes:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#CBD5E1").pack(anchor="w", padx=12, pady=(10, 4))

        self.mode_dropdown = ctk.CTkOptionMenu(
            mode_card,
            values=[
                "✂️ Auto Clipping (Long -> Shorts)",
                "💡 AI Facts Mode",
                "📖 AI Story & Voiceover",
                "🎭 Funny Explainer (Scene Breakdown)",
                "🧮 Manim Math & CS Explainer",
                "🤔 This or That (WYR Challenge)",
                "🏆 Rank-It Tier List Reveal",
                "❓ Interactive Trivia Quiz",
                "🧩 Riddle & Lateral Thinking",
                "📰 News Breakdown (Persona/Cartoon)",
                "🚀 JWST Space Deep-Dive",
                "🔊 Guess Sound Challenge",
                "🖼️ Photo Reel & Slideshow",
                "🎨 Color Grade Video Only"
            ],
            height=34,
            fg_color="#0F172A",
            button_color="#334155",
            command=self.on_mode_dropdown_change
        )
        self.mode_dropdown.pack(fill="x", padx=12, pady=(0, 8))

        # Context & Script Input (--user_context)
        ctk.CTkLabel(mode_card, text="User Context / Scene Target:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(anchor="w", padx=12, pady=(2, 2))
        self.user_context_entry = ctk.CTkEntry(mode_card, placeholder_text="e.g. 'Dexter Morgan scene' or 'Pythagorean theorem'", height=30)
        self.user_context_entry.pack(fill="x", padx=12, pady=(0, 6))

        # Style & Pacing Context (--style_context)
        ctk.CTkLabel(mode_card, text="Editing Style & Pacing Context:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(anchor="w", padx=12, pady=(2, 2))
        self.style_context_entry = ctk.CTkEntry(mode_card, placeholder_text="e.g. 'fast cuts', 'cinematic build-up', 'meme pacing'", height=30)
        self.style_context_entry.pack(fill="x", padx=12, pady=(0, 6))

        # Mood / Vibe Selector
        ctk.CTkLabel(mode_card, text="Narrative Vibe / Mood:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(anchor="w", padx=12, pady=(2, 2))
        self.vibe_menu = ctk.CTkOptionMenu(mode_card, values=["suspense", "sarcastic", "energetic", "calm", "mysterious", "spooky", "cinematic", "funny"], height=28, fg_color="#0F172A", button_color="#334155")
        self.vibe_menu.pack(fill="x", padx=12, pady=(0, 10))

        # 3. AI Model, Cartoon Persona & Voice Synthesizer Card
        ai_card = ctk.CTkFrame(scroll_left, fg_color="#1E293B", corner_radius=10)
        ai_card.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(ai_card, text="🤖 LLM Model Provider:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#CBD5E1").pack(anchor="w", padx=12, pady=(10, 4))
        self.llm_provider = ctk.CTkOptionMenu(
            ai_card,
            values=["⚡ Gemini API (Primary)", "🦙 Local Ollama (Qwen/Llama)", "🤗 HuggingFace Router", "🚀 Groq Llama 3.3 70B", "🐉 DeepSeek Chat"],
            height=30,
            fg_color="#0F172A",
            button_color="#334155"
        )
        self.llm_provider.pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkLabel(ai_card, text="🎙️ Text-to-Speech Voice:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(anchor="w", padx=12, pady=(2, 2))
        self.voice_menu = ctk.CTkOptionMenu(
            ai_card,
            values=["en-US-GuyNeural (Male Dramatic)", "en-US-JennyNeural (Female Crisp)", "en-GB-SoniaNeural (British Deep)", "en-AU-WilliamNeural (Aussie Energetic)", "en-US-ChristopherNeural (Heroic)"],
            height=28,
            fg_color="#0F172A",
            button_color="#334155"
        )
        self.voice_menu.pack(fill="x", padx=12, pady=(0, 8))

        # Cartoon Persona Selector
        ctk.CTkLabel(ai_card, text="🧙 Cartoon Persona / Avatar:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(anchor="w", padx=12, pady=(2, 2))
        self.persona_menu = ctk.CTkOptionMenu(
            ai_card,
            values=["none (Standard Host)", "mafia_cat (Mafia Boss Cat)", "superhero (Hero Narrator)", "robot (Robotic Commentary)", "rabbit (Squeaky Cartoon)", "old_man (Grumpy Old Man)", "orange_cat (Energetic Cat)"],
            height=28,
            fg_color="#0F172A",
            button_color="#334155"
        )
        self.persona_menu.pack(fill="x", padx=12, pady=(0, 10))

        # API Keys Accordion Drawer
        keys_btn = ctk.CTkButton(scroll_left, text="🔑 Edit API Keys (.env)", fg_color="transparent", text_color="#38BDF8", hover_color="#1E293B", anchor="w", command=self.toggle_keys_window)
        keys_btn.pack(fill="x", padx=10, pady=(4, 10))

    def build_center_pane(self):
        """Center Column: Live 9:16 Video Canvas Preview & Master CTA"""
        center_frame = ctk.CTkFrame(self.studio_grid, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#1E293B")
        center_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        # Title
        ctk.CTkLabel(center_frame, text="🎬 Live Canvas & Render Controls", font=ctk.CTkFont(size=15, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=16, pady=(14, 2))

        # 9:16 Vertical Video Canvas Mock Container
        self.canvas_frame = ctk.CTkFrame(center_frame, fg_color="#020617", corner_radius=14, border_width=2, border_color="#38BDF8")
        self.canvas_frame.pack(fill="both", expand=True, padx=20, pady=8)

        # Mock Video Content Inside Canvas
        preview_inner = ctk.CTkFrame(self.canvas_frame, fg_color="#0F172A", corner_radius=10)
        preview_inner.pack(fill="both", expand=True, padx=10, pady=10)

        # Top Badge Tag Bar inside Canvas
        badge_row = ctk.CTkFrame(preview_inner, fg_color="transparent")
        badge_row.pack(fill="x", padx=10, pady=8)

        badge_box = ctk.CTkFrame(badge_row, fg_color="#1E1B4B", corner_radius=6)
        badge_box.pack(side="right")
        ctk.CTkLabel(badge_box, text="9:16 Vertical Short", font=ctk.CTkFont(size=10, weight="bold"), text_color="#A78BFA").pack(padx=8, pady=3)

        # Mock Caption Text Display (Shows real-time subtitle preset feedback)
        self.caption_preview_label = ctk.CTkLabel(
            preview_inner,
            text="TRANSFORM YOUR VIDEOS\nINTO VIRAL SHORTS",
            font=ctk.CTkFont(family="Impact", size=22, weight="bold"),
            text_color="#FFEA00",
            justify="center"
        )
        self.caption_preview_label.pack(expand=True)

        # Editable Parameters Below Canvas
        param_row = ctk.CTkFrame(center_frame, fg_color="transparent")
        param_row.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(param_row, text="Target Duration (s):", font=ctk.CTkFont(size=11), text_color="#94A3B8").pack(side="left", padx=(0, 4))
        self.duration_menu = ctk.CTkComboBox(param_row, values=["15", "30", "45", "60", "90", "120", "180"], width=95, height=28)
        self.duration_menu.set("45")
        self.duration_menu.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(param_row, text="Clip Count:", font=ctk.CTkFont(size=11), text_color="#94A3B8").pack(side="left", padx=(0, 4))
        self.clip_count_menu = ctk.CTkComboBox(param_row, values=["1", "3", "5", "10", "15"], width=85, height=28)
        self.clip_count_menu.set("3")
        self.clip_count_menu.pack(side="left")

        # Destination Output Directory Card
        output_dir_frame = ctk.CTkFrame(center_frame, fg_color="#1E293B", corner_radius=8)
        output_dir_frame.pack(fill="x", padx=16, pady=(6, 4))

        ctk.CTkLabel(output_dir_frame, text="📁 Destination Output Directory:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#CBD5E1").pack(anchor="w", padx=10, pady=(6, 2))

        dir_row = ctk.CTkFrame(output_dir_frame, fg_color="transparent")
        dir_row.pack(fill="x", padx=10, pady=(0, 6))

        self.output_dir_entry = ctk.CTkEntry(dir_row, placeholder_text="Default: sessions/", height=28)
        self.output_dir_entry.insert(0, os.path.abspath("sessions"))
        self.output_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        browse_out_btn = ctk.CTkButton(dir_row, text="📁 Browse", width=70, height=28, fg_color="#334155", hover_color="#475569", command=self.browse_output_dir)
        browse_out_btn.pack(side="left")

        # Master CTA Generate Button
        self.launch_btn = ctk.CTkButton(
            center_frame,
            text="🚀 GENERATE VIRAL SHORT NOW",
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#10B981",
            hover_color="#059669",
            height=50,
            corner_radius=10,
            command=self.start_generation
        )
        self.launch_btn.pack(fill="x", padx=16, pady=(8, 4))

        # Progress Bar & Status Readout
        self.progress_bar = ctk.CTkProgressBar(center_frame, height=8, fg_color="#1E293B", progress_color="#10B981")
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=16, pady=(2, 4))

        self.status_label = ctk.CTkLabel(center_frame, text="Ready to create. Click button to render.", font=ctk.CTkFont(size=11), text_color="#94A3B8")
        self.status_label.pack(pady=(0, 6))

        # Quick Action Buttons Frame
        action_row = ctk.CTkFrame(center_frame, fg_color="transparent")
        action_row.pack(fill="x", padx=16, pady=(0, 10))

        open_folder_btn = ctk.CTkButton(
            action_row,
            text="📁 Open Rendered Videos (sessions/)",
            fg_color="#1E293B",
            hover_color="#334155",
            height=32,
            command=self.open_output_dir
        )
        open_folder_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.play_last_btn = ctk.CTkButton(
            action_row,
            text="▶ Play Output",
            fg_color="#0284C7",
            hover_color="#0369A1",
            height=32,
            state="disabled",
            command=self.play_latest_video
        )
        self.play_last_btn.pack(side="left", padx=(4, 0))

    def build_right_pane(self):
        """Right Column: Subtitle Presets, Aesthetic Filters, Quality Enhancements & Quality Settings"""
        scroll_right = ctk.CTkScrollableFrame(self.studio_grid, fg_color="#0F172A", corner_radius=12, border_width=1, border_color="#1E293B")
        scroll_right.grid(row=0, column=2, sticky="nsew", padx=(6, 0), pady=4)

        # Title
        ctk.CTkLabel(scroll_right, text="🎨 Subtitle & Pipeline Studio", font=ctk.CTkFont(size=15, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=14, pady=(14, 2))
        ctk.CTkLabel(scroll_right, text="Select caption presets & visual quality options.", font=ctk.CTkFont(size=11), text_color="#94A3B8").pack(anchor="w", padx=14, pady=(0, 8))

        # Subtitle Style Selection Cards
        ctk.CTkLabel(scroll_right, text="💬 Remotion Subtitle Style Preset:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#CBD5E1").pack(anchor="w", padx=14, pady=(4, 4))

        self.preset_cards = {}
        styles = [
            ("HORMOZI", "⚡ Hormozi Pop", "Dynamic word spring + neon highlights"),
            ("GLOW_BOX", "✨ Glow Box", "Glassmorphic gradient phrase pill box"),
            ("BOUNCE", "💥 Bounce Jump", "Upward jump animation + drop shadow"),
            ("MINIMAL", "💬 Minimal Bar", "Clean modern dark bar subtitle")
        ]

        for key, title, desc in styles:
            card = ctk.CTkFrame(scroll_right, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#334155", cursor="hand2")
            card.pack(fill="x", padx=10, pady=3)

            card.bind("<Button-1>", lambda e, k=key: self.select_caption_style(k))

            lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color="#38BDF8")
            lbl_title.pack(anchor="w", padx=12, pady=(6, 0))
            lbl_title.bind("<Button-1>", lambda e, k=key: self.select_caption_style(k))

            lbl_desc = ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=10), text_color="#94A3B8")
            lbl_desc.pack(anchor="w", padx=12, pady=(0, 6))
            lbl_desc.bind("<Button-1>", lambda e, k=key: self.select_caption_style(k))

            self.preset_cards[key] = card

        self.select_caption_style("HORMOZI")  # Default active selection

        # Visual Filter Selection Card
        filter_card = ctk.CTkFrame(scroll_right, fg_color="#1E293B", corner_radius=10)
        filter_card.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(filter_card, text="🎨 Visual Color Grade Preset:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#CBD5E1").pack(anchor="w", padx=12, pady=(8, 4))

        self.video_filter_menu = ctk.CTkOptionMenu(
            filter_card,
            values=["dynamic (AI Scene Switch)", "auto (AI Best Grade)", "none (Natural Colors)", "cyberpunk", "kurosawa (B&W Samurai)", "teal_orange (Movie)", "cinematic_warm", "vibrant_action", "vintage_vhs", "anime_vivid", "matrix_green", "sepia_western", "cold_thriller", "hdr_pop"],
            height=30,
            fg_color="#0F172A",
            button_color="#334155"
        )
        self.video_filter_menu.set("dynamic (AI Scene Switch)")
        self.video_filter_menu.pack(fill="x", padx=12, pady=(0, 8))

        # Pipeline Enhancements & Quality Card
        engine_card = ctk.CTkFrame(scroll_right, fg_color="#1E293B", corner_radius=10)
        engine_card.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(engine_card, text="⚙️ Enhancements & Export Pipeline:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#CBD5E1").pack(anchor="w", padx=12, pady=(8, 4))

        self.smart_crop_switch = ctk.CTkSwitch(engine_card, text="🎯 Smart Crop & EMA Face Tracking", font=ctk.CTkFont(size=11))
        self.smart_crop_switch.select()
        self.smart_crop_switch.pack(anchor="w", padx=12, pady=4)

        self.tighten_switch = ctk.CTkSwitch(engine_card, text="✂️ Auto-Tighten Audio (80ms Silence Cut)", font=ctk.CTkFont(size=11))
        self.tighten_switch.select()
        self.tighten_switch.pack(anchor="w", padx=12, pady=4)

        self.hq_switch = ctk.CTkSwitch(engine_card, text="✨ High Quality Enhancements (Sharpen & Color)", font=ctk.CTkFont(size=11))
        self.hq_switch.pack(anchor="w", padx=12, pady=4)

        self.superres_switch = ctk.CTkSwitch(engine_card, text="📺 Super-Resolution / Legacy Deinterlace", font=ctk.CTkFont(size=11))
        self.superres_switch.pack(anchor="w", padx=12, pady=4)

        self.srt_switch = ctk.CTkSwitch(engine_card, text="📝 Export Standalone SRT Subtitle File", font=ctk.CTkFont(size=11))
        self.srt_switch.pack(anchor="w", padx=12, pady=4)

        self.broll_switch = ctk.CTkSwitch(engine_card, text="🎬 Download & Insert Auto B-Roll Cutaways", font=ctk.CTkFont(size=11))
        self.broll_switch.pack(anchor="w", padx=12, pady=4)

        self.remotion_switch = ctk.CTkSwitch(engine_card, text="⚡ Remotion React Subtitle Engine", font=ctk.CTkFont(size=11))
        self.remotion_switch.select()
        self.remotion_switch.pack(anchor="w", padx=12, pady=(0, 6))

        ctk.CTkLabel(engine_card, text="Parallel Render Thread Workers:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(anchor="w", padx=12, pady=(2, 2))
        self.workers_menu = ctk.CTkOptionMenu(engine_card, values=["2 Workers (Default)", "4 Workers (High-End GPU)", "1 Worker (Low-RAM)"], height=28, fg_color="#0F172A", button_color="#334155")
        self.workers_menu.pack(fill="x", padx=12, pady=(0, 10))

    def create_log_drawer(self):
        """Bottom Expandable Execution Log Drawer"""
        self.log_drawer = ctk.CTkFrame(self, fg_color="#0F172A", height=130, corner_radius=12, border_width=1, border_color="#1E293B")
        self.log_drawer.pack(fill="x", padx=16, pady=(4, 12))

        header_row = ctk.CTkFrame(self.log_drawer, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(6, 2))

        ctk.CTkLabel(header_row, text="📋 Execution Log & Real-time Console", font=ctk.CTkFont(size=11, weight="bold"), text_color="#CBD5E1").pack(side="left")

        self.log_textbox = ctk.CTkTextbox(self.log_drawer, height=85, fg_color="#020617", text_color="#34D399", font=ctk.CTkFont(family="Consolas", size=10))
        self.log_textbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.log_textbox.insert("end", "--- ShortsFlow AI Studio Log Ready ---\n")

    def select_caption_style(self, key):
        """Visually Highlights Selected Caption Style Card"""
        self.selected_caption_style = key

        for card_key, card in self.preset_cards.items():
            if card_key == key:
                card.configure(fg_color="#1E1B4B", border_color="#38BDF8", border_width=2)
            else:
                card.configure(fg_color="#1E293B", border_color="#334155", border_width=1)

        # Update mock canvas text styling
        if key == "HORMOZI":
            self.caption_preview_label.configure(text="TRANSFORM YOUR VIDEOS\nINTO VIRAL SHORTS", text_color="#FFEA00")
        elif key == "GLOW_BOX":
            self.caption_preview_label.configure(text="✨ GLASSMORPHIC GLOW\nPHRASE PILL", text_color="#00E5FF")
        elif key == "BOUNCE":
            self.caption_preview_label.configure(text="💥 UPWARD SPRING JUMP\nANIMATION", text_color="#39FF14")
        else:
            self.caption_preview_label.configure(text="💬 CLEAN MINIMAL\nMODERN BAR", text_color="#F8FAFC")

    def on_mode_dropdown_change(self, val):
        self.log(f"[Info] Selected Generation Mode: {val}")
        if "Auto Clipping" in val or "Color Grade" in val:
            self.voice_menu.configure(state="disabled")
            self.persona_menu.configure(state="disabled")
        else:
            self.voice_menu.configure(state="normal")
            self.persona_menu.configure(state="normal")

    def browse_file(self):
        filename = filedialog.askopenfilename(title="Select Source Video File", filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv")])
        if filename:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, filename)
            self.log(f"[Input] Selected local video: {filename}")

    def browse_output_dir(self):
        folder = filedialog.askdirectory(title="Select Output Directory for Rendered Videos")
        if folder:
            self.output_dir_entry.delete(0, "end")
            self.output_dir_entry.insert(0, folder)
            self.log(f"[Output] Custom output directory set to: {folder}")

    def open_output_dir(self):
        target_dir = self.output_dir_entry.get().strip() or os.path.abspath("sessions")
        os.makedirs(target_dir, exist_ok=True)
        os.startfile(target_dir)

    def play_latest_video(self):
        if self.latest_output_file and os.path.exists(self.latest_output_file):
            os.startfile(self.latest_output_file)
        else:
            self.open_output_dir()

    def toggle_keys_window(self):
        """Popup Dialog to Edit API Keys"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("🔑 Edit API Keys (.env)")
        dialog.geometry("500x340")
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(dialog, text="Edit API Keys", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        f = ctk.CTkFrame(dialog)
        f.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkLabel(f, text="Gemini API Key:").pack(anchor="w", padx=10, pady=(6, 0))
        gemini_e = ctk.CTkEntry(f, width=420, show="*")
        gemini_e.insert(0, os.getenv("GEMINI_API_KEY", ""))
        gemini_e.pack(padx=10, pady=(0, 6))

        ctk.CTkLabel(f, text="HuggingFace API Key:").pack(anchor="w", padx=10, pady=(4, 0))
        hf_e = ctk.CTkEntry(f, width=420, show="*")
        hf_e.insert(0, os.getenv("HF_API_KEY", ""))
        hf_e.pack(padx=10, pady=(0, 6))

        ctk.CTkLabel(f, text="Pexels API Key:").pack(anchor="w", padx=10, pady=(4, 0))
        pex_e = ctk.CTkEntry(f, width=420, show="*")
        pex_e.insert(0, os.getenv("PEXELS_API_KEY", ""))
        pex_e.pack(padx=10, pady=(0, 10))

        def save_keys():
            os.environ["GEMINI_API_KEY"] = gemini_e.get().strip()
            os.environ["HF_API_KEY"] = hf_e.get().strip()
            os.environ["PEXELS_API_KEY"] = pex_e.get().strip()
            self.log("[Success] API keys updated in environment.")
            dialog.destroy()

        ctk.CTkButton(dialog, text="💾 Save API Keys", fg_color="#10B981", command=save_keys).pack(pady=10)

    def log(self, message):
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")

    def open_output_dir(self):
        sessions_dir = os.path.abspath("sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        os.startfile(sessions_dir)

    def play_latest_video(self):
        if self.latest_output_file and os.path.exists(self.latest_output_file):
            os.startfile(self.latest_output_file)
        else:
            self.open_output_dir()

    def start_generation(self):
        if self.is_running:
            messagebox.showwarning("Busy", "A generation job is already running!")
            return

        source = self.source_entry.get().strip()
        mode_str = self.mode_dropdown.get()

        if "Auto Clipping" in mode_str and not source:
            messagebox.showwarning("Input Required", "Please enter a YouTube URL or select a local video file for Auto Clipping.")
            return

        # Prepare Command Line Arguments for main.py
        cmd = [sys.executable, "main.py"]

        # Extraction Format
        ext_mode = self.extract_mode_menu.get().split()[0]

        if "Auto Clipping" in mode_str:
            cmd.extend(["--source_video", source, "--extract_mode", ext_mode])
            if ext_mode == "mashup":
                cmd.append("--mashup")
        elif "AI Facts" in mode_str:
            cmd.extend(["--mode", "FACTS", "--category", self.user_context_entry.get().strip() or "space mysteries"])
        elif "AI Story" in mode_str:
            cmd.extend(["--mode", "STORY", "--category", self.user_context_entry.get().strip() or "sci-fi mystery"])
        elif "Funny Explainer" in mode_str:
            cmd.extend(["--mode", "FUNNY_EXPLAINER"])
            if source: cmd.extend(["--source_video", source])
        elif "Math Explainer" in mode_str:
            cmd.extend(["--mode", "EXPLAINER", "--prompt", self.user_context_entry.get().strip() or "Explain gravity visually"])
        elif "This or That" in mode_str:
            cmd.extend(["--mode", "WYR", "--category", self.user_context_entry.get().strip() or "superpowers"])
        elif "Rank-It" in mode_str:
            cmd.extend(["--mode", "RANK_IT", "--category", self.user_context_entry.get().strip() or "supercars"])
        elif "Trivia Quiz" in mode_str:
            cmd.extend(["--mode", "TRIVIA", "--category", self.user_context_entry.get().strip() or "movies"])
        elif "Riddle" in mode_str:
            cmd.extend(["--mode", "RIDDLE", "--category", self.user_context_entry.get().strip() or "general"])
        elif "News Breakdown" in mode_str:
            cmd.extend(["--mode", "NEWS"])
        elif "JWST Space" in mode_str:
            cmd.extend(["--mode", "JWST"])
        elif "Guess Sound" in mode_str:
            cmd.extend(["--mode", "GUESS_SOUND"])
        elif "Photo Reel" in mode_str:
            cmd.extend(["--mode", "PHOTO_REEL", "--smart_story"])
        elif "Color Grade" in mode_str:
            cmd.extend(["--mode", "FILTER", "--source_video", source])

        # Clip count & duration (Safely extracts typed integers or preset values)
        clip_raw = self.clip_count_menu.get().strip()
        clip_clean = ''.join(c for c in clip_raw if c.isdigit()) or "3"
        cmd.extend(["--clip_count", clip_clean])

        dur_raw = self.duration_menu.get().strip()
        dur_clean = ''.join(c for c in dur_raw if c.isdigit()) or "45"
        cmd.extend(["--target_duration", dur_clean])

        # Voiceover selection (Only needed for AI Script Generation Modes, not Extraction Mode)
        if "Auto Clipping" not in mode_str and "Color Grade" not in mode_str:
            voice_str = self.voice_menu.get().split()[0]
            cmd.extend(["--voice", voice_str])

        # Cartoon Persona
        persona_str = self.persona_menu.get().split()[0]
        if persona_str != "none":
            cmd.extend(["--cartoon", "--persona", persona_str])

        # Vibe / Mood
        cmd.extend(["--vibe", self.vibe_menu.get()])

        # Caption style & Remotion
        if self.remotion_switch.get() == 1:
            cmd.extend(["--use_remotion", "--caption_style", self.selected_caption_style])

        # Filter preset
        filter_val = self.video_filter_menu.get().split()[0]
        if filter_val != "none":
            cmd.extend(["--video_filter", filter_val])

        # Quality & Pipeline Switches
        if self.smart_crop_switch.get() == 1:
            cmd.append("--smart_crop")
        if self.tighten_switch.get() == 1:
            cmd.append("--tighten")
        if self.hq_switch.get() == 1:
            cmd.append("--hq")
        if self.superres_switch.get() == 1:
            cmd.append("--superres")
        if self.srt_switch.get() == 1:
            cmd.append("--srt")
        if self.broll_switch.get() == 1:
            cmd.append("--broll")

        # Worker threads
        workers_val = self.workers_menu.get().split()[0]
        cmd.extend(["--max_workers", workers_val])

        # Custom Session / Output Directory Override
        custom_out_dir = self.output_dir_entry.get().strip()
        if custom_out_dir:
            cmd.extend(["--session_dir", custom_out_dir])

        # User context (--user_context)
        u_ctx = self.user_context_entry.get().strip()
        if u_ctx:
            cmd.extend(["--user_context", u_ctx])

        # Style context (--style_context)
        s_ctx = self.style_context_entry.get().strip()
        if s_ctx:
            cmd.extend(["--style_context", s_ctx])

        # Skip upload for safety
        cmd.append("--skip-upload")

        # Launch Thread
        self.is_running = True
        self.launch_btn.configure(state="disabled", fg_color="#475569", text="⏳ GENERATING SHORT...")
        self.progress_bar.set(0.15)
        self.status_label.configure(text="[Processing] Launching main.py pipeline...", text_color="#FBBF24")

        self.log(f"[Execution] Command: {' '.join(cmd)}")

        threading.Thread(target=self.run_pipeline_thread, args=(cmd,), daemon=True).start()

    def run_pipeline_thread(self, cmd):
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            for line in process.stdout:
                line_str = line.strip()
                if line_str:
                    self.log(line_str)
                    if "Downloading" in line_str:
                        self.progress_bar.set(0.35)
                        self.status_label.configure(text="[Step 1/3] Downloading source video & transcribing...")
                    elif "Remotion" in line_str or "Rendered" in line_str:
                        self.progress_bar.set(0.75)
                        self.status_label.configure(text="[Step 2/3] Rendering Remotion React captions...")
                        if ".mp4" in line_str and ("saved to:" in line_str or "created:" in line_str):
                            parts = line_str.split()
                            for p in parts:
                                if p.endswith(".mp4"):
                                    self.latest_output_file = p
                                    self.play_last_btn.configure(state="normal")
                    elif "SUCCESS" in line_str:
                        self.progress_bar.set(1.0)
                        self.status_label.configure(text="🎉 SUCCESS! Video rendered in sessions/", text_color="#34D399")

            process.wait()

            if process.returncode == 0:
                self.log("[Success] Pipeline completed successfully!")
                self.progress_bar.set(1.0)
                self.status_label.configure(text="🎉 SUCCESS! Video rendered in sessions/", text_color="#34D399")
            else:
                self.log(f"[Error] Pipeline exited with code {process.returncode}")
                self.status_label.configure(text="❌ Execution failed. Check logs below.", text_color="#F87171")

        except Exception as e:
            self.log(f"[Critical Error] {str(e)}")
            self.status_label.configure(text=f"❌ Error: {str(e)}", text_color="#F87171")

        finally:
            self.is_running = False
            self.launch_btn.configure(state="normal", fg_color="#10B981", text="🚀 GENERATE VIRAL SHORT NOW")


if __name__ == "__main__":
    app = ModernShortsGeneratorUI()
    app.mainloop()
