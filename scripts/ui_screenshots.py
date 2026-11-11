"""Open the browser app in a real browser and take screenshots (used by the "UI screenshots" workflow).

Builds a canned finished run (two tiny 9:16 clips + a results.json) so the review screen can be shown without running the pipeline.

    python scripts/ui_screenshots.py OUT_DIR [README_IMAGES_DIR]

With a second directory it also writes tight, resized crops of the review, edit and style/brand screens for the README.
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
readme_dir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else None
os.makedirs(out_dir, exist_ok=True)
if readme_dir:
    os.makedirs(readme_dir, exist_ok=True)
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
GIFS = [os.path.join(ROOT, "demos", "demo_spot_the_lie.gif"), os.path.join(ROOT, "demos", "demo_facts.gif")]
for i, (title, score, color) in enumerate([("Which of these three facts is the lie?", 86, "0x2b5876"),
                                           ("The sea god a Roman emperor declared war on", 63, "0x4e4376")], start=1):
    video = os.path.join(session, f"video_clip_{i}.mp4")
    if os.path.exists(GIFS[i - 1]):      # sample clips from the repo's own demo GIFs, so the screenshots look like the real thing
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", GIFS[i - 1], "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=25",
                        "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", video], check=True)
    else:
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s=360x640:r=25:d=3",
                        "-f", "lavfi", "-i", "sine=frequency=330:d=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", video], check=True)
    clips.append({"clip_index": i, "video_path": video, "start": 12.0 * i, "end": 12.0 * i + 24, "duration": 24.0,
                  "viral_score": score, "hook": title, "reason": "Strong opening line and a clear payoff" if score > 80 else "Decent moment, slower start",
                  "title": title, "description": "A quick quiz short: spot the lie before the answer comes up.",
                  "tags": ["facts", "quiz", "spotthelie"], "thumbnail": None})
# a word-timed transcript covering both clips (12 s .. 48 s), so the click-to-cut word boxes show up in the edit panel
_TEXT = ("which of these three facts is the lie the first one says that octopuses have three hearts the second says honey never "
         "spoils and the third says goldfish forget everything after three seconds only one of them is false so take a moment "
         "and think before the answer comes up on the screen you know what the sea god a roman emperor declared war on was "
         "neptune and the emperor even ordered his soldiers to collect seashells as the spoils of that war").split()
_words = [{"word": " " + w, "start": round(12.0 + 0.5 * i, 2), "end": round(12.0 + 0.5 * i + 0.4, 2)} for i, w in enumerate(_TEXT)]
with open(os.path.join(session, "transcript.json"), "w", encoding="utf-8") as f:
    json.dump({"language": "en", "segments": [{"start": _words[0]["start"], "end": _words[-1]["end"], "text": " ".join(_TEXT), "words": _words}]}, f)
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

    def crop(page, name, top, bottom, pad=14, width=1280, max_w=1000):
        """Save page[top.y - pad : bottom.bottom + pad] as a resized JPEG for the README (only when a README dir was given)."""
        if not readme_dir:
            return
        from PIL import Image
        page.evaluate("window.scrollTo(0, 0)")
        a, z = top.bounding_box(), bottom.bounding_box()
        y0 = max(0, a["y"] - pad)
        h = (z["y"] + z["height"]) - y0 + pad
        tmp = os.path.join(out_dir, f"_crop_{name}.png")
        page.screenshot(path=tmp, full_page=True, clip={"x": 0, "y": y0, "width": width, "height": h})
        im = Image.open(tmp).convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        im.save(os.path.join(readme_dir, name), quality=84, optimize=True)
        os.remove(tmp)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"http://127.0.0.1:{PORT}")
        page.wait_for_selector("text=Make shorts from a video in one click", timeout=60000)
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(out_dir, "01_start_here.png"), full_page=True)
        # the sample button fills the link box and shows the credit
        page.get_by_role("button", name="No video handy? Try a 2-minute sample").click()
        page.get_by_text("public domain").first.wait_for(timeout=15000)
        assert "samples-v1/shortsflow_sample_nasa.mp4" in page.get_by_label("Video link (YouTube or other)").first.input_value()
        page.screenshot(path=os.path.join(out_dir, "01a_sample.png"), full_page=False)
        page.get_by_label("Video link (YouTube or other)").first.fill("")

        # the new options: Extras on Start here, the Dub tab, and Extras on Clip (advanced)
        page.get_by_text("Extras (optional)").first.click()
        page.get_by_text("Clean up the sound").first.wait_for(timeout=15000)
        page.screenshot(path=os.path.join(out_dir, "01c_extras.png"), full_page=True)
        page.get_by_text("Extras (optional)").first.click()
        page.get_by_role("tab", name="Dub a video").click()
        page.get_by_text("Re-voice a video in another language").wait_for(timeout=15000)
        assert page.get_by_label("Voice engine").count() >= 1 and page.get_by_label("Voice", exact=True).count() >= 1
        page.screenshot(path=os.path.join(out_dir, "01d_dub_tab.png"), full_page=True)
        page.get_by_role("tab", name="Clip (advanced)").click()
        page.locator("text=Extras >> visible=true").first.click()
        page.wait_for_timeout(600)
        page.screenshot(path=os.path.join(out_dir, "01e_clip_extras.png"), full_page=True)
        page.get_by_role("tab", name="Start here").click()
        page.wait_for_timeout(300)

        page.get_by_text("Earlier runs: open, continue or reuse").click()
        page.locator('input[aria-label="Earlier runs"]').click()     # the input itself: clicking the label does not open the list in Gradio 5
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
        crop(page, "webui_review.jpg", page.get_by_text("Your shorts", exact=True), page.get_by_role("button", name="Download all as .zip"))
        page.get_by_text("Edit this short: style, start and end").first.click()
        page.wait_for_selector("text=Re-render this short", timeout=15000)
        assert page.get_by_label("Start (seconds in the original video)").first.input_value() in ("12", "12.0")
        page.screenshot(path=os.path.join(out_dir, "02b_edit_panel.png"), full_page=True)
        crop(page, "webui_edit.jpg", page.get_by_text("Your shorts", exact=True), page.get_by_role("button", name="Undo last change").first)
        # click-to-cut words: the boxes are there, a typed phrase ticks its words
        page.get_by_text("Words in this short").first.wait_for(timeout=15000)
        assert page.get_by_role("checkbox").count() > 40, "the word tick boxes did not show"
        page.get_by_label("Or type a phrase to tick").first.fill("honey never spoils")
        page.get_by_role("button", name="Tick phrase").first.click()
        page.wait_for_timeout(1200)
        ticked = page.locator(".sf-words input[type=checkbox]:checked").count()
        assert ticked == 3, f"the phrase should tick 3 words, ticked {ticked}"
        page.screenshot(path=os.path.join(out_dir, "02c_word_cuts.png"), full_page=True)
        # timeline strip: this short, the other short, and the start/end nudge buttons move the boxes
        assert page.locator(".sf-tl-clip >> visible=true").count() >= 1, "the timeline strip did not show"
        assert page.locator(".sf-tl-other >> visible=true").count() >= 1, "the other short is missing from the strip"
        start_box = page.get_by_label("Start (seconds in the original video)").first
        end_box_t = page.get_by_label("End (seconds)").first
        page.get_by_role("button", name="Start +1 s").first.click()
        page.wait_for_timeout(1000)
        assert float(start_box.input_value()) == 13.0, f"Start +1 s gave {start_box.input_value()}"
        page.get_by_role("button", name="End -1 s").first.click()
        page.wait_for_timeout(1000)
        assert float(end_box_t.input_value()) == 35.0, f"End -1 s gave {end_box_t.input_value()}"
        assert page.get_by_text("0:13 to 0:35").first.is_visible(), "the strip did not follow the buttons"
        page.locator(".sf-tl").first.scroll_into_view_if_needed()
        page.screenshot(path=os.path.join(out_dir, "02d_timeline.png"), full_page=False)
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
        from PIL import ImageDraw, ImageFont
        mark = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        draw = ImageDraw.Draw(mark)
        draw.ellipse([10, 10, 290, 290], fill=(255, 80, 120, 255))
        try:
            font = ImageFont.truetype("arialbd.ttf", 120)
        except OSError:
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", 120)
            except OSError:
                font = ImageFont.load_default()
        draw.text((150, 150), "SF", fill=(255, 255, 255, 255), font=font, anchor="mm")
        mark.save(logo)
        page.goto(f"http://127.0.0.1:{PORT}")
        page.wait_for_selector("text=Make shorts from a video in one click", timeout=60000)
        page.get_by_text("Pink glow box").click()
        page.wait_for_timeout(800)
        page.get_by_text("Your brand: logo, @handle, end card").click()
        page.locator("input[type=file]").nth(1).set_input_files(logo)
        page.wait_for_timeout(1000)
        saved = os.path.join(home, "brand", "brand.json")
        for attempt in range(3):          # Gradio can miss a typed value if Save is clicked right away: type, leave the box, check, then save
            handle_box = page.get_by_label("@handle", exact=True)
            handle_box.fill("@lightexplained")
            handle_box.press("Tab")
            end_box = page.get_by_label("End card text (last 2 seconds)")
            end_box.fill("Follow for more")
            end_box.press("Tab")
            page.wait_for_timeout(600)
            if handle_box.input_value() != "@lightexplained":
                continue
            page.get_by_role("button", name="Save my brand").click()
            page.wait_for_selector("text=Saved your brand", timeout=30000)
            for _ in range(20):
                if os.path.exists(saved) and json.load(open(saved, encoding="utf-8")).get("handle") == "@lightexplained":
                    break
                page.wait_for_timeout(250)
            else:
                continue
            break
        page.screenshot(path=os.path.join(out_dir, "05_style_and_brand.png"), full_page=True)
        crop(page, "webui_style_brand.jpg", page.get_by_text("Caption style", exact=True).first, page.get_by_role("button", name="Remove brand"),
             width=700, max_w=700)
        saved = os.path.join(home, "brand", "brand.json")
        assert os.path.exists(saved), "brand.json was not written"
        got = json.load(open(saved, encoding="utf-8"))
        assert got.get("handle") == "@lightexplained", f"saved brand was {got}"
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
