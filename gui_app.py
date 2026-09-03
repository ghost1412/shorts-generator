import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class ShortsGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ ShortsFlow AI - YouTube Shorts Generator")
        self.root.geometry("680x640")
        self.root.minsize(600, 580)
        
        # Set modern theme / padding
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.create_widgets()

    def create_widgets(self):
        # Header Banner
        header_frame = ttk.Frame(self.root, padding=15)
        header_frame.pack(fill="x")
        
        title_label = ttk.Label(header_frame, text="⚡ ShortsFlow AI Generator", font=("Segoe UI", 16, "bold"))
        title_label.pack(anchor="w")
        subtitle_label = ttk.Label(header_frame, text="Turn YouTube links or video files into viral 9:16 Shorts on autopilot.", font=("Segoe UI", 9))
        subtitle_label.pack(anchor="w", pady=(2, 0))

        # Main Input Frame
        main_frame = ttk.LabelFrame(self.root, text=" Generation Options ", padding=15)
        main_frame.pack(fill="x", padx=15, pady=5)

        # 1. Source Video URL / File
        ttk.Label(main_frame, text="Source Video (YouTube Link or Local File):", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        
        self.source_var = tk.StringVar()
        self.source_entry = ttk.Entry(main_frame, textvariable=self.source_var, width=50)
        self.source_entry.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(0, 10))
        
        browse_btn = ttk.Button(main_frame, text="Browse...", command=self.browse_file)
        browse_btn.grid(row=1, column=1, sticky="w", pady=(0, 10))

        # 2. Clips Count & Duration
        options_grid = ttk.Frame(main_frame)
        options_grid.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)

        ttk.Label(options_grid, text="Number of Clips:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.clip_count_var = tk.StringVar(value="3")
        clip_spin = ttk.Spinbox(options_grid, from_=1, to=20, textvariable=self.clip_count_var, width=6)
        clip_spin.grid(row=0, column=1, sticky="w", padx=(0, 20))

        ttk.Label(options_grid, text="Target Duration (sec):").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.duration_var = tk.StringVar(value="30")
        dur_spin = ttk.Spinbox(options_grid, from_=10, to=60, textvariable=self.duration_var, width=6)
        dur_spin.grid(row=0, column=3, sticky="w")

        # 3. Editing Style Preset
        style_frame = ttk.Frame(main_frame)
        style_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(style_frame, text="Editing Style Preset:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 10))
        self.style_var = tk.StringVar(value="Standard (Clean)")
        style_cb = ttk.Combobox(
            style_frame, 
            textvariable=self.style_var, 
            values=["Standard (Clean)", "Meme (SFX & Funny Captions)", "Funny", "Action", "Sarcastic"], 
            state="readonly", 
            width=30
        )
        style_cb.pack(side="left")

        # 4. Flags (Smart Crop, Tighten, Mashup)
        flags_frame = ttk.Frame(main_frame)
        flags_frame.grid(row=4, column=0, columnspan=2, sticky="w", pady=5)

        self.smart_crop_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(flags_frame, text="AI Face & Smart Crop (9:16)", variable=self.smart_crop_var).pack(side="left", padx=(0, 15))

        self.tighten_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(flags_frame, text="Remove Silences (Fast Pacing)", variable=self.tighten_var).pack(side="left", padx=(0, 15))

        self.mashup_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(flags_frame, text="Combine into Single Reel", variable=self.mashup_var).pack(side="left")

        # Action Button Frame
        action_frame = ttk.Frame(self.root, padding=10)
        action_frame.pack(fill="x", padx=15)

        self.generate_btn = tk.Button(
            action_frame, 
            text="🚀 Generate Shorts Now", 
            font=("Segoe UI", 11, "bold"), 
            bg="#0078d4", 
            fg="white", 
            activebackground="#005a9e", 
            activeforeground="white",
            relief="flat",
            padx=20,
            pady=8,
            command=self.start_generation
        )
        self.generate_btn.pack(fill="x")

        # Log Output Frame
        log_frame = ttk.LabelFrame(self.root, text=" Live Output Logs ", padding=10)
        log_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        self.log_text = tk.Text(log_frame, wrap="word", font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select Source Video File",
            filetypes=[("Video Files", "*.mp4 *.mov *.mkv *.avi *.webm"), ("All Files", "*.*")]
        )
        if filename:
            self.source_var.set(filename)

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def start_generation(self):
        source = self.source_var.get().strip()
        if not source:
            messagebox.showerror("Input Error", "Please enter a YouTube link or select a video file.")
            return

        self.generate_btn.config(state="disabled", text="⏳ Processing Shorts...")
        self.log_text.delete("1.0", tk.END)
        self.log("============================================================")
        self.log(f"Starting Shorts Generation for: {source}")
        self.log("============================================================\n")

        # Launch process thread to keep GUI responsive
        threading.Thread(target=self.run_process, args=(source,), daemon=True).start()

    def run_process(self, source):
        try:
            # Build Python command
            python_exe = sys.executable
            # Prefer GPU Python 3.12 environment if present on Windows
            gpu_python = r"C:\Users\win10\AppData\Local\Programs\Python\Python312\python.exe"
            if os.path.exists(gpu_python):
                python_exe = gpu_python

            cmd = [
                python_exe, "main.py",
                "--source_video", source,
                "--clip_count", self.clip_count_var.get(),
                "--target_duration", self.duration_var.get(),
                "--output_json", "gui_latest_run.json"
            ]

            if self.smart_crop_var.get():
                cmd.append("--smart_crop")
            if self.tighten_var.get():
                cmd.append("--tighten")
            if self.mashup_var.get():
                cmd.append("--mashup")

            style = self.style_var.get()
            if "Meme" in style:
                cmd.extend(["--style", "meme"])
            elif "Funny" in style:
                cmd.extend(["--style", "funny"])
            elif "Action" in style:
                cmd.extend(["--style", "action"])
            elif "Sarcastic" in style:
                cmd.extend(["--style", "sarcastic"])

            # Execute subprocess with stdout piping
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in proc.stdout:
                self.root.after(0, self.log, line.strip())

            proc.wait()

            if proc.returncode == 0:
                self.root.after(0, self.on_success)
            else:
                self.root.after(0, self.on_failure, f"Process exited with error code {proc.returncode}")

        except Exception as e:
            self.root.after(0, self.on_failure, str(e))

    def on_success(self):
        self.generate_btn.config(state="normal", text="🚀 Generate Shorts Now")
        self.log("\n============================================================")
        self.log("🎉 SUCCESS! Generated clips are saved in the sessions/ folder.")
        self.log("============================================================")
        messagebox.showinfo("Success", "Shorts generation completed successfully!\nCheck the 'sessions/' folder for your output videos.")

    def on_failure(self, err):
        self.generate_btn.config(state="normal", text="🚀 Generate Shorts Now")
        self.log(f"\n[Error] Extraction failed: {err}")
        messagebox.showerror("Generation Failed", f"An error occurred during video generation:\n{err}")

def main():
    root = tk.Tk()
    app = ShortsGeneratorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
