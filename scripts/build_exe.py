import os
import sys
import subprocess

# Force UTF-8 stdout for Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def build_standalone_exe():
    print("============================================================")
    print("      ShortsGenerator Executable Build Script")
    print("============================================================")
    
    # 1. Ensure PyInstaller is installed
    try:
        import PyInstaller
        print("[Log] PyInstaller is already installed.")
    except ImportError:
        print("[Log] Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    output_name = "ShortsGeneratorUI"
    hidden_imports = [
        "yt_dlp",
        "requests",
        "torch",
        "cv2",
        "PIL",
        "numpy",
        "stable_whisper",
        "moviepy",
        "scipy",
        "customtkinter",
        "manim",
        "engine.analysis",
        "engine.script_gen",
        "engine.video_gen",
        "engine.voice_gen"
    ]
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--noconsole",
        "--name", output_name,
        "--collect-all", "customtkinter",
        "--collect-all", "manim",
        "gui_app.py"
    ]
    
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    print(f"[Log] Building Desktop GUI Executable: {output_name}.exe ...")
    print(f"[Log] Running command: {' '.join(cmd)}")
    
    res = subprocess.run(cmd)
    if res.returncode == 0:
        exe_path = os.path.join("dist", f"{output_name}.exe")
        print("\n============================================================")
        print(f"BUILD COMPLETE! GUI Executable generated at:")
        print(f"   --> {os.path.abspath(exe_path)}")
        print("============================================================")
    else:
        print(f"\n[Error] Build failed with return code {res.returncode}")

if __name__ == "__main__":
    build_standalone_exe()
