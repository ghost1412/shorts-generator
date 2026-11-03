"""Open the browser app in a real browser and take screenshots (used by the "UI screenshots" workflow).

Builds a canned finished run (two tiny 9:16 clips + a results.json) so the review screen can be shown without running the pipeline.

    python scripts/ui_screenshots.py OUT_DIR
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "ui-screenshots")
os.makedirs(out_dir, exist_ok=True)
PORT = 7871

# 1. a workspace with one finished run
home = tempfile.mkdtemp(prefix="sf_ui_")
session = os.path.join(home, "sessions", "web_20261103_120000")
os.makedirs(session)
try:
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    ffmpeg = "ffmpeg"
clips = []
for i, (title, score, color) in enumerate([("Why the sky is blue (and sunsets are red)", 86, "0x2b5876"),
                                           ("The one trick nobody tells you about light", 63, "0x4e4376")], start=1):
    video = os.path.join(session, f"video_clip_{i}.mp4")
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s=360x640:r=25:d=3",
                    "-f", "lavfi", "-i", "sine=frequency=330:d=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", video], check=True)
    clips.append({"clip_index": i, "video_path": video, "start": 12.0 * i, "end": 12.0 * i + 24, "duration": 24.0,
                  "viral_score": score, "hook": title, "reason": "Strong opening line and a clear payoff" if score > 80 else "Decent moment, slower start",
                  "title": title, "description": "A short, clear explanation viewers can follow in half a minute.",
                  "tags": ["science", "light", "explained"], "thumbnail": None})
with open(os.path.join(session, "results.json"), "w", encoding="utf-8") as f:
    json.dump({"source_video": "demo.mp4", "session_dir": session, "total_clips": 2,
               "settings": {"extract_mode": "shorts", "layout": "single", "smart_crop": True, "tighten": True, "tighten_mode": "cut",
                            "use_remotion": True, "caption_style": "HORMOZI", "subtitle_y_pos": 1150, "brand": None},
               "clips": clips}, f)

# the workspace of a real install gets these copied in from the package; mirror that
import shutil
shutil.copytree(os.path.join(ROOT, "assets", "caption_previews"), os.path.join(home, "assets", "caption_previews"))

# 2. start the app on that workspace
env = dict(os.environ, SHORTSFLOW_HOME=home, PYTHONIOENCODING="utf-8")
app = subprocess.Popen([sys.executable, os.path.join(ROOT, "webui.py"), "--port", str(PORT)], cwd=ROOT, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    for _ in range(90):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}", timeout=2)
            break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit("the app did not start")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"http://127.0.0.1:{PORT}")
        page.wait_for_selector("text=Make shorts from a video in one click", timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(out_dir, "01_start_here.png"), full_page=True)

        page.get_by_text("Open an earlier run").click()
        page.locator('input[aria-label="Earlier runs"]').click()      # the input itself: clicking the label does not open the list in Gradio 5
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(out_dir, "01b_dropdown.png"), full_page=True)
        page.get_by_role("option", name="3 Nov 2026, 12:00 - 2 shorts").click()
        page.get_by_role("button", name="Open", exact=True).click()
        try:
            page.wait_for_selector("text=Your shorts", timeout=30000)
        except Exception:
            page.screenshot(path=os.path.join(out_dir, "02_FAILED.png"), full_page=True)
            print("PAGE TEXT:", page.inner_text("body")[:1500])
            app.terminate()
            try:
                print("APP LOG:", app.communicate(timeout=15)[0][-4000:])
            except Exception as e:
                print("could not read the app log:", e)
            raise
        page.wait_for_timeout(2500)
        page.screenshot(path=os.path.join(out_dir, "02_review.png"), full_page=True)
        page.get_by_text("Edit this short: style, start and end").first.click()
        page.wait_for_selector("text=Re-render this short", timeout=15000)
        assert page.get_by_label("Start (seconds in the original video)").first.input_value() in ("12", "12.0")
        page.screenshot(path=os.path.join(out_dir, "02b_edit_panel.png"), full_page=True)
        page.get_by_text("Edit this short: style, start and end").first.click()

        page.get_by_role("button", name="Remove this short").first.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(out_dir, "03_after_remove.png"), full_page=True)

        page.get_by_role("button", name="Download all as .zip").click()
        page.wait_for_selector("text=.zip", timeout=30000)
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(out_dir, "04_zip.png"), full_page=True)
        # style picker + brand kit: choose a style, fill the brand, upload a logo, save, then reload to prove it persisted
        from PIL import Image
        logo = os.path.join(home, "my_logo.png")
        Image.new("RGBA", (300, 300), (255, 80, 120, 255)).save(logo)
        page.goto(f"http://127.0.0.1:{PORT}")
        page.wait_for_selector("text=Make shorts from a video in one click", timeout=60000)
        page.get_by_text("Pink glow box").click()
        page.wait_for_timeout(800)
        page.get_by_text("Your brand: logo, @handle, end card").click()
        page.get_by_label("@handle").fill("@lightexplained")
        page.get_by_label("End card text (last 2 seconds)").fill("Follow for more")
        page.locator("input[type=file]").nth(1).set_input_files(logo)
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Save my brand").click()
        page.wait_for_selector("text=Saved your brand", timeout=30000)
        page.screenshot(path=os.path.join(out_dir, "05_style_and_brand.png"), full_page=True)
        saved = os.path.join(home, "brand", "brand.json")
        assert os.path.exists(saved), "brand.json was not written"
        assert json.load(open(saved, encoding="utf-8"))["handle"] == "@lightexplained"
        page.reload()
        page.wait_for_selector("text=Make shorts from a video in one click", timeout=60000)
        page.get_by_text("Your brand: logo, @handle, end card").click()
        page.wait_for_selector("text=Your brand is saved", timeout=30000)
        assert page.get_by_label("@handle").input_value() == "@lightexplained", "the saved handle was not reloaded"
        page.screenshot(path=os.path.join(out_dir, "06_brand_reloaded.png"), full_page=True)
        browser.close()
    print("screenshots written to", out_dir)
finally:
    app.terminate()
    try:
        app.wait(timeout=10)
    except Exception:
        app.kill()
