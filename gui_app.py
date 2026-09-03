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

        self.title("⚡ ShortsFlow AI Studio - Full Options Video Generator")
        self.geometry("980x780")
        self.minsize(900, 700)

        # Header Frame
        self.create_header()

        # Tabview navigation
        self.tabview = ctk.CTkTabview(self, width=940, height=580)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(10, 10))

        self.tab_clipping = self.tabview.add("✂️ Video Extraction")
        self.tab_modes = self.tabview.add("🎬 AI Modes & Manim")
        self.tab_quality = self.tabview.add("📐 Resolution & Render Quality")
        self.tab_character = self.tabview.add("🧙 Hero & Story Creator")
        self.tab_advanced = self.tabview.add("⚙️ Advanced & ComfyUI")
        self.tab_logs = self.tabview.add("📋 Execution Logs")

        self.build_clipping_tab()
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
            text="Complete Autonomous Video Pipeline & AI Clipping Engine", 
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

    def build_clipping_tab(self):
        card1 = ctk.CTkFrame(self.tab_clipping, fg_color="#1E293B", corner_radius=10)
        card1.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(card1, text="📹 Video Source (YouTube URL or Local File)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 5))

        src_frame = ctk.CTkFrame(card1, fg_color="transparent")
        src_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.source_entry = ctk.CTkEntry(
            src_frame, 
            placeholder_text="Paste YouTube Link (https://www.youtube.com/watch?v=...) or select video path", 
            width=640
        )
        self.source_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(src_frame, text="📁 Browse", width=90, command=self.browse_source_file)
        browse_btn.pack(side="right")

        card2 = ctk.CTkFrame(self.tab_clipping, fg_color="#1E293B", corner_radius=10)
        card2.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(card2, text="🎛️ Extraction & Editing Settings", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 10))

        grid = ctk.CTkFrame(card2, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=(0, 15))

        # Clips Slider
        ctk.CTkLabel(grid, text="Clip Count:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.clip_count_lbl = ctk.CTkLabel(grid, text="3 clips", font=ctk.CTkFont(weight="bold"))
        self.clip_count_lbl.grid(row=0, column=1, sticky="w", padx=(0, 15))

        self.clip_slider = ctk.CTkSlider(grid, from_=1, to=15, number_of_steps=14, command=self.update_clip_lbl, width=180)
        self.clip_slider.set(3)
        self.clip_slider.grid(row=0, column=2, sticky="w", padx=(0, 30))

        # Duration Slider
        ctk.CTkLabel(grid, text="Target Duration:").grid(row=0, column=3, sticky="w", padx=(0, 5))
        self.dur_lbl = ctk.CTkLabel(grid, text="30s", font=ctk.CTkFont(weight="bold"))
        self.dur_lbl.grid(row=0, column=4, sticky="w", padx=(0, 15))

        self.dur_slider = ctk.CTkSlider(grid, from_=10, to=60, number_of_steps=10, command=self.update_dur_lbl, width=180)
        self.dur_slider.set(30)
        self.dur_slider.grid(row=0, column=5, sticky="w")

        # Editing Style Dropdown
        style_frame = ctk.CTkFrame(card2, fg_color="transparent")
        style_frame.pack(fill="x", padx=15, pady=(5, 15))

        ctk.CTkLabel(style_frame, text="Editing Style Preset:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        self.style_dropdown = ctk.CTkOptionMenu(
            style_frame,
            values=["Standard (Clean)", "Meme (SFX & Viral Captions)", "Funny", "Action", "Sarcastic", "Stylish"],
            width=280
        )
        self.style_dropdown.pack(side="left")

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

        self.cache_switch = ctk.CTkSwitch(toggles_frame, text="Reuse Cached Transcripts & Videos")
        self.cache_switch.select()
        self.cache_switch.grid(row=1, column=0, padx=(0, 20), pady=5, sticky="w")

    def update_clip_lbl(self, val):
        self.clip_count_lbl.configure(text=f"{int(val)} clips")

    def update_dur_lbl(self, val):
        self.dur_lbl.configure(text=f"{int(val)}s")

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
            width=360
        )
        self.res_dropdown.grid(row=0, column=1, columnspan=2, sticky="w", pady=8)

        # Quality Preset
        ctk.CTkLabel(grid, text="Render Quality Preset:", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=8)
        self.quality_dropdown = ctk.CTkOptionMenu(
            grid,
            values=["Medium (12M Bitrate - Standard)", "High (25M Bitrate - HQ Master)", "Ultra (50M Bitrate - 4K Crisp)", "Low (4M Bitrate - Fast Draft)"],
            width=360
        )
        self.quality_dropdown.grid(row=1, column=1, columnspan=2, sticky="w", pady=8)

        # Manual Bitrate & FFmpeg Preset
        ctk.CTkLabel(grid, text="Manual Bitrate (e.g. 15000k):").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=8)
        self.bitrate_entry = ctk.CTkEntry(grid, placeholder_text="Auto (leave blank for preset)", width=200)
        self.bitrate_entry.grid(row=2, column=1, sticky="w", pady=8)

        ctk.CTkLabel(grid, text="FFmpeg Preset:").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=8)
        self.preset_dropdown = ctk.CTkOptionMenu(
            grid,
            values=["medium (Balanced)", "ultrafast (Fastest)", "slow (High Quality)", "slower (Maximum Compression)"],
            width=200
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
            width=340
        )
        self.mode_dropdown.grid(row=0, column=1, sticky="w", pady=5)

        # Topic / Prompt
        ctk.CTkLabel(grid, text="Prompt / Topic / Title:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        self.prompt_entry = ctk.CTkEntry(grid, placeholder_text="e.g. 'Mind-bending quantum physics facts' or 'Pythagorean Theorem'", width=450)
        self.prompt_entry.grid(row=1, column=1, columnspan=2, sticky="w", pady=5)

        # Custom Script Box
        ctk.CTkLabel(grid, text="Custom Script (Optional):").grid(row=2, column=0, sticky="nw", padx=(0, 10), pady=5)
        self.script_box = ctk.CTkTextbox(grid, width=450, height=80)
        self.script_box.grid(row=2, column=1, columnspan=2, sticky="w", pady=5)

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
        self.hero_entry = ctk.CTkEntry(grid, placeholder_text="e.g. friendly dragon, brave knight, teddy bear", width=380)
        self.hero_entry.grid(row=0, column=1, sticky="w", pady=6)

        ctk.CTkLabel(grid, text="Hero Name:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        self.hero_name_entry = ctk.CTkEntry(grid, placeholder_text="e.g. Barnaby, Luna, Sparky", width=380)
        self.hero_name_entry.grid(row=1, column=1, sticky="w", pady=6)

        ctk.CTkLabel(grid, text="Companion:").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        self.companion_entry = ctk.CTkEntry(grid, placeholder_text="e.g. Twinkle the Pixie, Barnaby the Owl", width=380)
        self.companion_entry.grid(row=2, column=1, sticky="w", pady=6)

        ctk.CTkLabel(grid, text="Adventure Quest:").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=6)
        self.quest_entry = ctk.CTkEntry(grid, placeholder_text="e.g. Finding the Lost Crystal of Wisdom", width=380)
        self.quest_entry.grid(row=3, column=1, sticky="w", pady=6)

        ctk.CTkLabel(grid, text="Adventure Setting:").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=6)
        self.setting_entry = ctk.CTkEntry(grid, placeholder_text="e.g. Starry Night Forest, Enchanted Castle", width=380)
        self.setting_entry.grid(row=4, column=1, sticky="w", pady=6)

    def build_advanced_tab(self):
        card = ctk.CTkFrame(self.tab_advanced, fg_color="#1E293B", corner_radius=10)
        card.pack(fill="both", expand=True, padx=15, pady=10)

        ctk.CTkLabel(card, text="⚙️ Batch Processing, ComfyUI & Export Settings", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC").pack(anchor="w", padx=15, pady=(12, 10))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=5)

        # Batch File
        ctk.CTkLabel(grid, text="Batch File (urls.txt):").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        self.batch_entry = ctk.CTkEntry(grid, placeholder_text="Path to text file containing video URLs (one per line)", width=420)
        self.batch_entry.grid(row=0, column=1, sticky="w", pady=5)
        ctk.CTkButton(grid, text="Browse", width=80, command=self.browse_batch_file).grid(row=0, column=2, padx=(10, 0))

        # Output JSON Export
        ctk.CTkLabel(grid, text="JSON Export Path:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        self.json_entry = ctk.CTkEntry(grid, placeholder_text="e.g. output_results.json", width=420)
        self.json_entry.grid(row=1, column=1, sticky="w", pady=5)

        # User Context / Instructions
        ctk.CTkLabel(grid, text="Narrative Instructions:").grid(row=2, column=0, sticky="nw", padx=(0, 10), pady=10)
        self.context_box = ctk.CTkTextbox(grid, width=420, height=70)
        self.context_box.grid(row=2, column=1, columnspan=2, sticky="w", pady=10)

        # Switches
        sw_frame = ctk.CTkFrame(card, fg_color="transparent")
        sw_frame.pack(fill="x", padx=15, pady=10)

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
            text="🚀 GENERATE SHORTS NOW",
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
                cmd.extend(["--clip_count", str(int(self.clip_slider.get()))])
                cmd.extend(["--target_duration", str(int(self.dur_slider.get()))])
                if self.smart_crop_switch.get(): cmd.append("--smart_crop")
                if self.tighten_switch.get(): cmd.append("--tighten")
                if self.mashup_switch.get(): cmd.append("--mashup")
                if self.cache_switch.get(): cmd.append("--use_cache")
                
                style = self.style_dropdown.get()
                if "Meme" in style: cmd.extend(["--style", "meme"])
                elif "Funny" in style: cmd.extend(["--style", "funny"])
                elif "Action" in style: cmd.extend(["--style", "action"])
                elif "Sarcastic" in style: cmd.extend(["--style", "sarcastic"])
                elif "Stylish" in style: cmd.extend(["--style", "stylish"])

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

            json_out = self.json_entry.get().strip()
            if json_out: cmd.extend(["--output_json", json_out])

            context = self.context_box.get("1.0", "end").strip()
            if context: cmd.extend(["--user_context", context])

            if self.remotion_switch.get(): cmd.append("--use_remotion")
            if self.comfy_switch.get(): cmd.append("--use_comfy")
            if self.skip_upload_switch.get(): cmd.append("--skip-upload")

            self.log("============================================================")
            self.log(f"[ShortsFlow Studio] Executing Command:")
            self.log(f"   {' '.join(cmd)}")
            self.log("============================================================\n")

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

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
        self.generate_btn.configure(state="normal", text="🚀 GENERATE SHORTS NOW")
        self.log("\n============================================================")
        self.log("🎉 SUCCESS! Video generation completed. Output saved in sessions/")
        self.log("============================================================")
        messagebox.showinfo("ShortsFlow AI", "Generation Completed Successfully!\nOutput saved in 'sessions/' folder.")

    def on_failure(self, err):
        self.generate_btn.configure(state="normal", text="🚀 GENERATE SHORTS NOW")
        self.log(f"\n[Error] Pipeline error: {err}")
        messagebox.showerror("ShortsFlow AI Error", f"Generation error occurred:\n{err}")

if __name__ == "__main__":
    app = ModernShortsGeneratorUI()
    app.mainloop()
