import os
import sys
import argparse
import subprocess
import shutil
import time
import imageio_ffmpeg

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except: pass

def upscale_video(input_video, output_video, model_name="realesrgan-x4plus", scale=4, realesrgan_bin=None):
    """
    Automated AI Video Upscaler using Real-ESRGAN NCNN Vulkan on NVIDIA GPU.
    Extracts frames -> Runs Real-ESRGAN AI Super-Resolution -> Recombines with audio via FFmpeg.
    """
    if not os.path.exists(input_video):
        print(f"[Error] Input video not found: {input_video}")
        return False

    # Dynamic binary search path
    if not realesrgan_bin:
        realesrgan_bin = os.environ.get("REALESRGAN_PATH") or shutil.which("realesrgan-ncnn-vulkan") or shutil.which("realesrgan-ncnn-vulkan.exe")
        if not realesrgan_bin:
            search_paths = [
                "./realesrgan-ncnn-vulkan.exe",
                "tools/realesrgan-ncnn-vulkan.exe",
                "tools/realesrgan/realesrgan-ncnn-vulkan.exe"
            ]
            for p in search_paths:
                if os.path.exists(p):
                    realesrgan_bin = p
                    break

    if not realesrgan_bin or not os.path.exists(realesrgan_bin):
        print(f"[Error] Real-ESRGAN binary not found. Pass --bin or set REALESRGAN_PATH environment variable.")
        return False

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Standard temporary working directories using tempfile module
    import tempfile
    frames_in = tempfile.mkdtemp(prefix="upscale_in_")
    frames_out = tempfile.mkdtemp(prefix="upscale_out_")

    print("\n" + "="*70)
    print(f"[AI UPSCALER] REAL-ESRGAN SUPER-RESOLUTION")
    print(f"Input: {input_video}")
    print(f"Output: {output_video}")
    print(f"Model: {model_name} (Scale: {scale}x)")
    print("="*70)

    # 1. Extract frames from video (High quality JPG for 5x faster disk I/O)
    print("\n[1/3] Extracting frames from video...")
    t0 = time.time()
    extract_cmd = [
        ffmpeg_exe, "-y", "-i", input_video,
        "-qscale:v", "2",
        os.path.join(frames_in, "frame_%08d.jpg")
    ]
    subprocess.run(extract_cmd, check=True)
    frame_count = len(os.listdir(frames_in))
    print(f"[Log] Extracted {frame_count} frames in {time.time()-t0:.1f}s")

    # 2. Run Real-ESRGAN AI Super-Resolution with GPU Multi-threading & Tiling
    print(f"\n[2/3] Running Real-ESRGAN AI Super-Resolution on RTX 4060 GPU...")
    print(f"[Log] Processing {frame_count} frames (Thread pool: 4:4:4, GPU: 0)...")
    t1 = time.time()
    model_dir = os.path.dirname(realesrgan_bin)
    
    # Auto-adjust model name for scale factor
    if scale == 2 and model_name == "realesrgan-x4plus":
        model_name = "realesr-animevideov3"
        print(f"[Log] Using 2x video AI model: realesr-animevideov3")

    upscale_cmd = [
        realesrgan_bin,
        "-i", frames_in,
        "-o", frames_out,
        "-n", model_name,
        "-s", str(scale),
        "-g", "0",        # Use NVIDIA RTX 4060 GPU
        "-j", "4:4:4",    # 4 load, 4 process, 4 save threads for maximum GPU saturation
        "-t", "0",        # Auto tile size optimization
        "-f", "jpg"
    ]
    
    # Run from executable directory so model weights load properly
    subprocess.run(upscale_cmd, cwd=model_dir, check=True)
    print(f"[Log] AI Upscaled {frame_count} frames in {time.time()-t1:.1f}s ({frame_count / max(time.time()-t1, 0.1):.1f} FPS)")

    # 3. Get exact FPS and resolution from upscaled frames for recombine
    print("\n[3/3] Recombining AI upscaled frames with original audio...")
    fps = "30"
    try:
        fps_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate", "-of", "default=noprint_wrappers=1:nokey=1", input_video
        ]
        r_fps = subprocess.run(fps_cmd, capture_output=True, text=True, check=True).stdout.strip()
        if '/' in r_fps:
            num, den = map(float, r_fps.split('/'))
            fps = str(round(num / den, 3))
        else:
            fps = str(round(float(r_fps), 3))
        print(f"[Log] Detected input frame rate: {fps} FPS")
    except Exception as e:
        print(f"[Log] Using fallback frame rate: {fps} FPS")
    
    # Check width of upscaled frames
    sample_frame = os.path.join(frames_out, "frame_00000001.jpg")
    encode_codec = "h264_nvenc"
    if os.path.exists(sample_frame):
        try:
            res_cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", sample_frame]
            w_str, h_str = subprocess.run(res_cmd, capture_output=True, text=True, check=True).stdout.strip().split(',')
            w, h = int(w_str), int(h_str)
            print(f"[Log] AI Upscaled Frame Resolution: {w}x{h}")
            if w > 4096:
                # NVENC H.264 max resolution is 4096. Use NVENC HEVC (H.265) for 8K resolution!
                encode_codec = "hevc_nvenc"
                print(f"[Log] Resolution exceeds 4096 width. Auto-switching to 8K-capable GPU encoder (hevc_nvenc).")
        except Exception as e:
            pass

    # Reassemble video using FFmpeg
    concat_cmd = [
        ffmpeg_exe, "-y",
        "-framerate", fps,
        "-i", os.path.join(frames_out, "frame_%08d.jpg"),
        "-i", input_video,   # For audio stream
        "-map", "0:v:0",
        "-map", "1:a:0?",    # Map audio if present
        "-c:v", encode_codec, "-preset", "p6", "-rc", "vbr", "-cq", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        output_video
    ]
    subprocess.run(concat_cmd, check=True)

    # Clean up temp frames
    shutil.rmtree(frames_in, ignore_errors=True)
    shutil.rmtree(frames_out, ignore_errors=True)

    print("\n" + "="*70)
    print(f"SUCCESS! AI Upscaled 4K Video saved to:")
    print(f"   {os.path.abspath(output_video)}")
    print("="*70 + "\n")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Video Upscaler using Real-ESRGAN")
    parser.add_argument("-i", "--input", required=True, help="Input video file path")
    parser.add_argument("-o", "--output", required=True, help="Output video file path")
    parser.add_argument("-m", "--model", default="realesrgan-x4plus", choices=["realesrgan-x4plus", "realesr-animevideov3", "realesrgan-x4plus-anime"], help="Real-ESRGAN model")
    parser.add_argument("-s", "--scale", type=int, default=4, help="Upscale factor (2, 3, or 4)")
    parser.add_argument("--bin", help="Path to realesrgan-ncnn-vulkan executable")
    args = parser.parse_args()

    upscale_video(args.input, args.output, model_name=args.model, scale=args.scale, realesrgan_bin=args.bin)
