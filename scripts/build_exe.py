import os
import sys
import subprocess

def build_standalone_exe():
    print("============================================================")
    print("      🚀 ShortsGenerator Executable Build Script 🚀")
    print("============================================================")
    
    # 1. Ensure PyInstaller is installed
    try:
        import PyInstaller
        print("[Log] PyInstaller is already installed.")
    except ImportError:
        print("[Log] Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    output_name = "ShortsGenerator"
    hidden_imports = [
        "yt_dlp",
        "requests",
        "torch",
        "cv2",
        "PIL",
        "numpy",
        "stable_whisper",
        "moviepy",
        "scipy"
    ]
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", output_name,
        "--console"
    ]
    
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    cmd.append("main.py")

    print(f"[Log] Building executable: {output_name}.exe ...")
    print(f"[Log] Running command: {' '.join(cmd)}")
    
    res = subprocess.run(cmd)
    if res.returncode == 0:
        exe_path = os.path.join("dist", f"{output_name}.exe")
        print("\n============================================================")
        print(f"🎉 BUILD COMPLETE! Executable generated at:")
        print(f"   --> {os.path.abspath(exe_path)}")
        print("============================================================")
    else:
        print(f"\n[Error] Build failed with return code {res.returncode}")

if __name__ == "__main__":
    build_standalone_exe()
