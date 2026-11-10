import os
import sys
import io
import argparse
import subprocess
from dotenv import load_dotenv

# 🟢 Force UTF-8 for all standard streams (fixes CP1252/Emoji crashes on Windows)
# Use line_buffering=True to prevent prints from different stages/threads from buffering and overlapping.
if sys.stdout.encoding != 'utf-8' or sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
if sys.stderr.encoding != 'utf-8' or sys.platform == "win32":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)


from engine.paths import project_root
load_dotenv(os.path.join(project_root(), ".env"))
load_dotenv()  # also honour a .env in the current folder

from engine.media_gen import is_url





def parse_args():
    parser = argparse.ArgumentParser(description="Generate either FACTS, STORY, FIND_IT, WYR, REDDIT, TRIVIA, QUOTE, JWST, RIDDLE, ODD_ONE_OUT, or FILTER shorts.")
    parser.add_argument("--mode", choices=["FACTS", "STORY", "FIND_IT", "WYR", "REDDIT", "TRIVIA", "QUOTE", "ODD_ONE_OUT", "NEWS", "NEWS_SERIOUS", "GUESS_SOUND", "RIDDLE", "TREND", "CHALLENGE", "JWST", "TRAILER_MISSED", "MUSIC", "EXPLAINER", "FILTER", "EMOJI_GUESS", "PHOTO_REEL", "FUNNY_EXPLAINER", "TEACH", "DUB", "SPLIT_SCREEN", "PODCAST", "TOP_5", "CHAT_STORY", "HORROR", "TRUE_CRIME", "BIBLE", "ARTICLE", "UGC", "AUTO", "TRIP"], help="Force a specific mode.")
    parser.add_argument("--scene", help="Scene or scenario prompt for FUNNY_EXPLAINER mode.")
    parser.add_argument("--photos_dir", help="Directory containing photos for PHOTO_REEL mode.")
    parser.add_argument("--music", help="Path to audio/music track for PHOTO_REEL or background music.")
    parser.add_argument("--reel_type", choices=["memories", "travel", "product", "then_now", "countdown", "tribute"], help="PHOTO_REEL: give the reel a shape (order, timing, captions, title, look). Blurry and duplicate photos are skipped.")
    parser.add_argument("--reel_text", action="append", help="PHOTO_REEL with --reel_type: your own caption for the next photo (repeat, or separate with |). --prompt is the title / name.")
    parser.add_argument("--smart_story", action="store_true", help="Use Multimodal Vision LLM to re-order photos into a narrative story arc and generate captions.")
    parser.add_argument("--prompt", help="Prompt for AI Music/Image generation.")
    parser.add_argument("--ckpt_name", default="stable_audio_3_medium_base.safetensors", help="Checkpoint name for ComfyUI audio model.")
    parser.add_argument("--category", help="Specify content category.")
    parser.add_argument("--script", help="Provide a manual script to skip generation.")
    parser.add_argument("--vibe", choices=["suspense", "spooky", "cinematic", "upbeat", "sarcastic", "funny"], default="suspense", help="Select background music vibe.")
    parser.add_argument("--voice", help="Specify TTS voice (e.g. en-US-GuyNeural, en-US-ChristopherNeural, en-US-EricNeural, en-US-AnaNeural).")
    parser.add_argument("--user_id", help="The Supabase user ID triggering the generation.")
    parser.add_argument("--video_id", help="The unique ID for this video job.")
    parser.add_argument("--skip-upload", "--skip_upload", action="store_true", dest="skip_upload", help="Generate video but do not upload to social media.")
    parser.add_argument("--recap_title", help="Movie/Story title for MOVIE_RECAP mode.")
    parser.add_argument("--pinterest", action="store_true", help="Enable optional upload to Pinterest.")
    parser.add_argument("--instagram", action="store_true", help="Enable optional upload to Instagram.")
    parser.add_argument("--pinterest_link", help="Optional destination URL for Pinterest Pin (e.g. affiliate link).")
    
    # AI Extraction Flags (Long-form to Short-form)
    parser.add_argument("--source_video", help="Path to long-form source video for AI extraction")
    parser.add_argument("--extract_mode", choices=["shorts", "long"], default="shorts")
    parser.add_argument("--clip_count", type=int, default=5)
    parser.add_argument("--target_duration", type=int, default=30)
    parser.add_argument("--auto_edit", choices=["podcast", "hype", "educational", "vlog"], help="Edit like an editor: one choice turns on the right mix of pause/um cuts, captions, zooms, cutaways, teaser opening, colour and sound effects for this kind of video. Your own flags still win. Writes edit_plan.json.")
    parser.add_argument("--edit_strength", choices=["subtle", "medium", "hyped"], default="medium", help="With --auto_edit: how much of the edit shows (default medium).")
    parser.add_argument("--transitions", choices=["auto", "none", "dissolve", "mix", "punch", "whip", "flash", "glitch", "subject"], default="auto", help="--mode TRIP and the compiled highlight reel (--extract_mode long): a transition on every cut instead of a plain cut (auto = follows --auto_edit: hype mix, vlog punch, others none): punch (fast push-in), whip (slide with motion blur), flash (white), glitch (RGB split), mix (a different one each time) or subject (the person stays in front while the background changes; needs torch + torchvision + opencv, a cut without a clear person gets another type). Length follows --edit_strength.")
    parser.add_argument("--subject_look", choices=["auto", "plain", "glow", "glow_sweep", "spotlight"], default="auto", help="--transitions subject: how the cut-out looks. plain = person stays; glow = a bright outline builds up round the person before the background changes; glow_sweep = outline + a light band + darker background; spotlight = dark background, soft outline; auto (default) = plain for now; the outline looks are experimental.")
    parser.add_argument("--subject_max", type=int, default=2, help="--transitions subject: the most subject cut-outs in one recap (default 2; they only happen where ONE person is in the shot, and are spaced out). The other cuts use the other transitions.")
    parser.add_argument("--subject_color", default="auto", help="--transitions subject: colour of the outline: auto (white), white, gold, cyan, pink or #rrggbb.")
    parser.add_argument("--stat_pops", action="store_true", help="Show striking numbers (\"$200\", \"73%%\", \"10 years\") big on screen the moment they are said. Needs --use_remotion.")
    parser.add_argument("--cold_open", action="store_true", help="Start each short with its strongest line (a 1.5-6 s teaser taken from the clip), then play the clip from its beginning. Shorts only.")
    parser.add_argument("--no_signals", action="store_true", help="Ignore the extra scoring signals (speech-rate change, and laughter/applause with --use_audio_detect).")
    parser.add_argument("--no_rerank", action="store_true", help="Skip the second LLM pass that rates all clip candidates together with context (uses the older per-clip scoring).")
    parser.add_argument("--no_diversity", action="store_true", help="Do not skip near-duplicate clips or prefer different topics when choosing shorts.")
    parser.add_argument("--content", choices=["auto", "game"], default="auto", help="game: pick story moments (cutscenes, dialogue) AND action moments (fights, gameplay, even with no one talking) from game footage. The normal picker only sees stretches where someone speaks.")
    parser.add_argument("--game_framing", choices=["auto", "fit", "crop"], default="auto", help="With --content game: fit = the whole picture over a blurred copy (the minimap, HUD and the game's own subtitles stay), crop = a full-screen portrait crop (face tracked when there is a face), auto (default) = looks at frames inside the chosen moments and picks fit when a HUD or subtitles sit at the sides, crop when the picture is clean. A heuristic: override it when it guesses wrong.")
    parser.add_argument("--game_crop", action="store_true", help="With --content game: same as --game_framing crop.")
    parser.add_argument("--game_mix", type=float, default=0.5, help="With --content game: share of the clips that are story moments (0.5 = half story, half action; 0 = all action; 1 = all story).")
    parser.add_argument("--moments", help="Make shorts from these exact times instead of letting the AI choose (one per line or comma separated): 7:00-7:45, 1:01:40-1:02:30, 420-465. A single time (7:00) starts a short of --target_duration there. Good for cutscenes and any scene you already know.")
    parser.add_argument("--visual_context", action="store_true", help="Let a local vision model (Ollama, e.g. gemma3:12b) look at a few frames of each candidate moment, so the story on screen counts and not only what is said. Slower; skipped with a note when no vision model is installed. Use --user_context to say what the video is about.")
    parser.add_argument("--trip_videos", nargs="+", help="--mode TRIP: your trip videos or folders, in day order (one folder per day, or files named day1, day2 ...). Makes one recap with a title card per day plus an itinerary.")
    parser.add_argument("--trip_album", help="--mode TRIP: a shared Google Photos album link (https://photos.app.goo.gl/...). Its videos (not longer than 5 minutes) are downloaded into <session_dir>/videos, one folder per day. Unofficial: Google can change the page; then download the videos yourself.")
    parser.add_argument("--trip_day", default="", help="--mode TRIP with --trip_album: only this day, e.g. 2026-10-16 or day2.")
    parser.add_argument("--trip_name", default="", help="--mode TRIP: the trip's name, e.g. Northvale. Use --user_context for a note about the trip.")
    parser.add_argument("--recap_length", type=int, default=60, help="--mode TRIP: length of the recap in seconds (default 60).")
    parser.add_argument("--recap_hook", default="", help="--mode TRIP: the opening line over the first glimpses, e.g. \"Woke up at 4 AM just for this view\". Default: written from your note, else a neutral line.")
    parser.add_argument("--recap_lines", default="", help="--mode TRIP: a line of text for each part, in order, separated by | (or one per line), e.g. \"Fry 25g almonds and cashews in ghee | Roast the khoya until golden\". Shown under the part's title and on its shots (a recipe step, a stop's note).")
    parser.add_argument("--recap_open_result", action="store_true", help="--mode TRIP: open with the result first: the opening shots come from the LAST part (the finished dish, the summit, the first dance) before the rest of the story.")
    parser.add_argument("--trip_stops", default="", help="--mode TRIP: name the stops in order, e.g. \"Pinemere Lake, Larkwater Lake, Stonegate Canyon\". The videos (in filming order) are split between them and each stop gets a title card; use this for a one-day tour instead of Day 1, Day 2.")
    parser.add_argument("--recap_aspect", choices=["9:16", "16:9", "2.35:1"], default=None, help="--mode TRIP: frame shape of the recap (default 9:16; the cinematic style defaults to 2.35:1 widescreen).")
    parser.add_argument("--recap_versions", choices=["one", "both"], default="one", help="--mode TRIP: both = two recaps, recap_portrait.mp4 (9:16, only the vertical videos) and recap_landscape.mp4 (16:9, only the landscape videos), so nothing is shown small or cropped.")
    parser.add_argument("--recap_orientation", choices=["any", "landscape", "portrait"], default="any", help="--mode TRIP: use only landscape or only portrait videos (as shown on screen, phone rotation included).")
    parser.add_argument("--recap_no_geocode", action="store_true", help="--mode TRIP: do not look up place names. By default the videos' GPS (rounded to ~100 m) is sent to the free OpenStreetMap service to name the places; with this flag (or SHORTSFLOW_GEOCODE=off) the places stay unnamed unless you give --trip_stops.")
    parser.add_argument("--recap_kind", choices=["trip", "wedding", "event", "family"], default="trip", help="--mode TRIP: what the footage is. trip (default) = travel wording, Day sections, places named from GPS; wedding / event / family = Part sections (name them with --trip_stops, e.g. \"Ceremony, Dinner, Dancing\"), event-style wording and no place lookup.")
    parser.add_argument("--recap_sample", default="auto", metavar="auto|all|N", help="--mode TRIP: how many videos to scan when a part has far more videos than shots. auto (default): wedding/event/family recaps look at about 3 videos per shot, spread over the whole part (fast); trips look at everything. all: scan every video (thorough, slower: every file is read once). A number: that many videos per shot.")
    parser.add_argument("--recap_keep_sound", action="store_true", help="--mode TRIP: keep the clips' own sound (vows, speeches, laughter) under the music instead of a music-only soundtrack.")
    parser.add_argument("--upload_drive", default=None, metavar="FOLDER", help="--mode TRIP: upload the finished recap video(s) to this Google Drive folder (link or id). Needs a one-time sign-in; see engine/drive_upload.py. Also: python -m engine.drive_upload FILE... --folder LINK.")
    parser.add_argument("--recap_avoid", default="", metavar="PATH[,PATH]", help="--mode TRIP: pick NEW moments: skip the moments that earlier recaps used (their itinerary.json files or recap folders, comma separated). Without it the same footage gives the same picks every time.")
    parser.add_argument("--place_names", default="", metavar="LAT,LON=NAME[;...]", help="--mode TRIP: set the name of a place yourself, by its GPS position, e.g. \"42.985,78.465=Larkwater Lake; 42.991,78.326=Pinemere Lakes\". Wrong names are listed with map links in places_review.md next to the recap.")
    parser.add_argument("--recap_rotate", default="", metavar="PART=DEG[,...]", help="--mode TRIP: force the turn of a clip that came out sideways, by a part of its file name and clockwise degrees, e.g. \"183047=270\" (0 cancels a wrong automatic turn).")
    parser.add_argument("--enhance", choices=["off", "auto"], default="off", help="Auto-enhance every video (trip recap) or clip (shorts) like an editor does before styling it: lift dark clips, tame very bright ones, reduce a clear colour cast, add a little colour to dull clips and sharpness. Each video is measured and only corrected where needed, all locally with FFmpeg (it cannot add detail that is not there).")
    parser.add_argument("--enhance_strength", choices=["subtle", "medium"], default="medium", help="With --enhance auto: how strong the corrections are (default medium).")
    parser.add_argument("--recap_style", choices=["auto", "hype", "plain", "cinematic"], default="auto", help="--mode TRIP: auto (default) decides from your footage: widescreen -> cinematic 2.35:1, vertical phone clips -> hype 9:16; cinematic = travel-film look (warm grade, slow fades, quiet black title cards, small spaced place labels); hype (default) opens with the hook over fast glimpses of the most beautiful shots, then the trip title and the whole trip day by day; plain starts at Day 1.")
    parser.add_argument("--no_snap", action="store_true", help="Keep the clip start/end exactly as chosen instead of moving them to sentence boundaries (shorts only).")
    parser.add_argument("--min_duration", type=int, default=15, help="Target minimum clip length in seconds (default 15). Clips can be up to 5 s shorter than this when a moment ends early.")
    parser.add_argument("--session_dir", help="Reuse session for transcription.")
    parser.add_argument("--use_audio_detect", action="store_true", help="Use audio signals (energy/delta) for extraction.")
    parser.add_argument("--style", choices=["sarcastic", "meme", "funny", "action", "stylish"], action="append", help="Optional viral editing styles (can be used multiple times).")
    parser.add_argument("--caption_emoji", action="store_true", help="Pop an emoji next to keywords in HORMOZI/BOUNCE captions (bundled Twemoji images, no system emoji font needed; needs --use_remotion).")
    parser.add_argument("--hook_overlay", action="store_true", help="Show the clip's hook as a big title for the first ~3 seconds (clipping with --use_remotion).")
    parser.add_argument("--auto_zoom", action="store_true", help="Subtle punch-in / slow push-in on the picture at emphasised words and sentence starts (clipping with --use_remotion; not with --layout split_filler).")
    parser.add_argument("--brand", help="brand.json preset (logo, handle, end card) burned into finished clips.")
    parser.add_argument("--logo", help="Logo PNG watermark for finished clips.")
    parser.add_argument("--handle", help="@handle shown next to the logo and on the end card.")
    parser.add_argument("--end_card", help="Text for a closing end card (last 2 seconds), e.g. 'Follow for more'.")
    parser.add_argument("--clean_audio", action="store_true", help="Clean clip audio: noise reduction, gentle compression and loudness normalisation to about -14 LUFS.")
    parser.add_argument("--remove_fillers",action="store_true", help="Cut \"um\" / \"uh\" / \"er\" out of clips (uses Whisper word timestamps; combines with --tighten).")
    parser.add_argument("--language", default="en", help="Spoken language of the source video for transcription (e.g. en, hi, es). Use \"auto\" to let Whisper detect it. Default: en.")
    parser.add_argument("--caption_lang", help="Translate the captions into this language (e.g. es, fr, de, pt, it, hi). Needs an AI provider (Groq, Gemini or Ollama). Clipping mode.")
    parser.add_argument("--zh_script", choices=["auto", "simplified", "traditional"], default="auto", help="Chinese captions in Simplified or Traditional characters (auto = keep what Whisper wrote). Needs: pip install \"shortsflow[zh]\". Clipping mode.")
    parser.add_argument("--clip_report", nargs="?", const="md", choices=["md", "csv", "both"], help="Write a summary of the run (title, time range, score, file, thumbnail) to the session folder as clip_report.md and/or .csv. Clipping mode.")
    parser.add_argument("--reel_captions", action="store_true", help="Burn word captions into long-form highlight reels (--extract_mode long).")
    parser.add_argument("--cut", action="append", metavar="PHRASE", help="Cut every occurrence of this phrase out of the clips, e.g. --cut \"you know\" (repeatable; clipping mode).")
    parser.add_argument("--edit_transcript", metavar="FILE", help="Edited copy of <session_dir>/transcript.txt; the words you deleted are cut from the clips. Re-run with the same --session_dir (do not add --use_cache: it would reuse the clips cut before the edit).")
    parser.add_argument("--find", help="Clip only moments matching this request, e.g. \"where they discuss pricing\" (clipping mode).")
    parser.add_argument("--user_context", help="Extra context to guide AI extraction (specific scenes/styles).")
    parser.add_argument("--style_context", help="Context for editing style and pacing (e.g. 'fast cuts', 'cinematic').")
    parser.add_argument("--gif_dir", help="Path to external GIF library (e.g. animated-gifs repo).")
    parser.add_argument("--hq", action="store_true", help="Enable High-Quality (Premium) enhancements (sharpening, color enhancement).")
    parser.add_argument("--superres", action="store_true", help="Enable Super-Resolution & Deinterlacing filter pipeline for legacy/VCD/VHS videos.")
    parser.add_argument("--video_filter", choices=["auto", "none", "dynamic", "kurosawa", "teal_orange", "cyberpunk", "cinematic_warm", "vibrant_action", "vintage_vhs", "moody_dark", "anime_vivid", "matrix_green", "sepia_western", "cold_thriller", "hdr_pop"], default="none", help="Visual color grade filter preset to apply (or 'auto' / 'dynamic' for AI auto-selection).")
    parser.add_argument("--use_cache", action="store_true", help="Reuse cached highlights and skip existing segments/rendered clips.")
    parser.add_argument("--mashup", action="store_true", help="Create a single mashup/remix video of all highlights instead of separate clips.")
    parser.add_argument("--mashup_mode", choices=["attach", "edit"], default="edit", help="Assembly style for mashup: 'attach' for simple concatenation, 'edit' for premium transition effects and background music.")
    
    parser.add_argument("--output_json", help="Path to write structured JSON results (transcript, clips, scores, hooks).")
    parser.add_argument("--batch_file", help="Path to text file containing list of video URLs or local files to process in batch.")
    parser.add_argument("--cookies_from_browser", default=None, help="Browser to extract cookies from for age-restricted videos (edge, chrome, firefox, brave).")
    parser.add_argument("--cookies", help="Path to cookies.txt file for YouTube authentication.")
    
    parser.add_argument("--use_comfy", action="store_true", help="Use local ComfyUI for premium AI backgrounds.")
    parser.add_argument("--use_ai_audio", action="store_true", help="Use local ComfyUI for premium AI music & SFX.")
    parser.add_argument("--bitrate", type=str, help="Manual bitrate override (e.g. 12000k)")
    parser.add_argument("--preset", type=str, help="Manual preset override (e.g. medium)")
    parser.add_argument("--quality", type=str, default="medium", choices=["low", "medium", "high", "ultra"], help="Output quality preset")
    
    # 🟢 Auto-Editor & AutoClip Flags
    parser.add_argument("--tighten", action="store_true", help="Remove silences from the final video.")
    parser.add_argument("--tighten_mode", choices=["cut", "speed"], default="cut", help="How to handle silences: 'cut' them or 'speed' them up.")
    parser.add_argument("--layout", choices=["single", "split", "active", "auto", "split_filler", "fit"], default="single", help="Vertical framing for clips: fit (the whole picture centred over a blurred copy of itself, nothing cropped off the sides), split_filler (clip on top, looping gameplay/satisfying footage below; see --filler_video), single (face/center crop), split (two speakers stacked), active (cut to whoever is talking, stacked when unsure), auto (picks per clip: active for a two-person shot, otherwise the tracked single crop).")
    parser.add_argument("--filler_video", type=str, default=None, help="Footage for the bottom half of --layout split_filler. Default: a video from assets/backgrounds/local/, else a Pexels stock clip.")
    parser.add_argument("--smart_crop", action="store_true", help="Enabled AI-powered face/interest tracking for vertical cropping.")
    parser.add_argument("--add_commentary", action="store_true", help="Generate an AI voiceover intro commentary hook for third-party clips to ensure 100%% YouTube policy compliance.")
    parser.add_argument("--show_banner", action="store_true", help="Overlay visual rounded header banner ('VIRAL MOMENT') on top of commentary intro clips.")
    
    # 🟢 Gap Closure Flags
    parser.add_argument("--srt", action="store_true", help="Export SRT subtitle file alongside each video.")
    parser.add_argument("--use_chapters", action="store_true", help="Boost scores for segments overlapping YouTube chapters.")
    parser.add_argument("--broll", action="store_true", help="Auto B-roll: short stock cutaways (about 2 s) over the upper part of the frame when a concrete noun is spoken. Needs PEXELS_API_KEY or clips in assets/backgrounds/local; skipped otherwise.")
    parser.add_argument("--preview", action="store_true", help="Render a low-res 3fps proxy video for quick preview.")
    
    # Cartoon/Persona Flags
    parser.add_argument("--cartoon", action="store_true", help="Enable cartoon-style news persona.")
    parser.add_argument("--persona", help="Select a specific cartoon persona (rabbit, robot, squirrel, superhero).")
    parser.add_argument("--use_remotion", action="store_true", help="Use Remotion engine instead of MoviePy for modern professional rendering.")
    parser.add_argument("--caption_style", default="HORMOZI", choices=["HORMOZI", "GLOW_BOX", "BOUNCE", "MINIMAL", "KARAOKE", "NEON", "BAR", "AUTO", "RANDOM"], help="Subtitle animation preset for Remotion renderer (default: HORMOZI). KARAOKE = colour sweep along the line, NEON = glow, BAR = subtitle bar.")
    parser.add_argument("--caption_color", type=str, default=None, help="Accent colour of the active caption word as hex, e.g. '#FF3366' (any caption style; needs --use_remotion).")
    parser.add_argument("--caption_position", choices=["default", "top", "middle", "bottom", "off"], default="default", help="Where the animated captions sit (needs --use_remotion): top, middle or bottom of the screen; off draws none (the game or video already has its own subtitles). default keeps the normal height (and below the picture with --layout fit). An explicit --subtitle_y_pos wins.")
    parser.add_argument("--caption_size", choices=["small", "default", "large", "xlarge"], default="default", help="Size of the animated captions (needs --use_remotion): small 0.8x, large 1.3x, xlarge 1.6x. The top edge stays where it is.")
    parser.add_argument("--subtitle_y_pos", type=int, default=1150, help="Vertical pixel position for animated (Remotion) captions on clips (default: 1150; moved up automatically for --layout split_filler).")
    parser.add_argument("--max_workers", type=int, default=None, help="Force number of parallel rendering worker threads (e.g. 2 or 4 for Remotion/FFmpeg).")
    
    # Provider & Media Overrides
    parser.add_argument("--use_ollama", action="store_true", help="Force local Ollama LLM execution.")
    parser.add_argument("--llm_provider", choices=["auto", "gemini", "ollama", "openai", "anthropic", "deepseek", "groq", "openrouter", "custom"], default="auto", help="Specify LLM provider (gemini, ollama, openai, anthropic, deepseek, groq, openrouter, custom).")
    parser.add_argument("--llm_model", help="Specify exact model name for the LLM provider (e.g., gpt-4o-mini, deepseek-chat, openai/gpt-oss-120b for Groq, qwen2.5:7b for Ollama).")
    parser.add_argument("--bg_media", help="Path to custom local background image (.jpg, .png) or video (.mp4, .mov).")
    
    # Interactive Kids Story Creator Flags
    parser.add_argument("--interactive", action="store_true", help="Launch interactive CLI prompt to create kids characters.")
    parser.add_argument("--hero", help="Type of hero (e.g. teddy bear, friendly dragon).")
    parser.add_argument("--hero_name", help="Name of the hero (e.g. Luna).")
    parser.add_argument("--companion", help="Hero's companion (e.g. Twinkle the Pixie).")
    parser.add_argument("--quest", help="Hero's adventure quest.")
    parser.add_argument("--setting", help="Where the kids story takes place (e.g. magical forest); also used to pick the stock footage.")
    # YouTube Multi-Account Flags
    parser.add_argument("--youtube_account", help="Select YouTube account slot (e.g. 1, 2, channel_b).")
    parser.add_argument("--youtube_token_file", help="Path to custom YouTube token.json file.")
    parser.add_argument("--youtube_secrets_file", help="Path to custom YouTube client_secrets.json file.")

    # Voice, Production & Aspect Ratio Flags
    parser.add_argument("--tts_provider", choices=["auto", "elevenlabs", "voicestudio", "edgetts", "local", "kokoro"], default="auto", help="Specify Text-to-Speech synthesis provider.")
    parser.add_argument("--clone_voice", help="Path to custom audio sample file (.wav, .mp3) for zero-shot voice cloning.")
    parser.add_argument("--aspect_ratio", choices=["9:16", "16:9", "1:1", "4:5"], default="9:16", help="Select output video aspect ratio (default 9:16 vertical).")
    parser.add_argument("--target_lang", help="Target language for --mode DUB (translate and re-voice the video): es, hi, de, fr, ja, pt, zh, it, ru, ko, ar, en, tr, nl, pl, uk, id.")
    parser.add_argument("--dub_captions", action="store_true", help="--mode DUB: burn the translated subtitles into the dubbed video (re-encodes; the .srt is always written). Uses a font with the glyphs for the target script (Hindi, Arabic, Cyrillic, Chinese, Japanese, Korean).")
    parser.add_argument("--dub_original", choices=["music", "quiet", "duck", "mute"], default="music", help="--mode DUB: what happens to the video's own sound: music (default: the original voice is removed and the music and effects stay; needs `pip install demucs`, else it falls back to quiet), quiet (a faint bed under the new voice), duck (lowered only while the new voice speaks), mute (removed).")
    parser.add_argument("--dub_voice", type=str, default=None, help="--mode DUB: voice for the target language: 'female' (default), 'male', or a full edge-tts name such as es-ES-AlvaroNeural.")
    parser.add_argument("--auto_ducking", action="store_true", help="Enable dynamic background music ducking during voice audio.")
    parser.add_argument("--sfx_preset", choices=["auto", "whoosh", "pop", "riser", "boom", "none"], default="auto", help="Select sound effects preset to overlay on visual transitions.")
    parser.add_argument("--enable_zoom", action="store_true", help="Apply smooth camera push-in zoom motion keyframing.")
    parser.add_argument("--enhance_audio", action="store_true", help="Apply studio audio mastering (highpass, noise gate, compressor, EBU R128 loudnorm).")

    args = parser.parse_args()
    # Older option names that the engine never read are now aliases of the features that do the same job
    if args.enhance_audio and not args.clean_audio:
        args.clean_audio = True           # studio audio mastering == noise reduction + loudness normalisation
    if args.enable_zoom and not args.auto_zoom:
        args.auto_zoom = True             # camera push-in == the punch-in zoom (needs --use_remotion)
    for flag, value, default in (("--auto_ducking", args.auto_ducking, False), ("--sfx_preset", args.sfx_preset, "auto")):
        if value != default:
            print(f"[Warning] {flag} is not implemented yet and is ignored.")
    if args.aspect_ratio != "9:16":
        print(f"[Warning] --aspect_ratio {args.aspect_ratio} is not implemented: output is 9:16 vertical (the highlights video is 16:9).")
    if getattr(args, "llm_model", None):
        os.environ["LLM_MODEL"] = args.llm_model      # was never read: only the LLM_MODEL env var worked
    args.auto_edit_plan = None
    if args.auto_edit and getattr(args, "source_video", None):
        from engine.auto_edit import apply_preset
        args.auto_edit_plan = apply_preset(args, args.auto_edit, args.edit_strength, sys.argv[1:])
        on = [k for k, v in args.auto_edit_plan["flags"].items() if v is True and k != "use_remotion"]
        print(f"[Log] 🎬 Auto-edit '{args.auto_edit_plan['label']}' ({args.edit_strength}): {', '.join(on)}; captions {args.caption_style}"
              + (f"; note: {'; '.join(args.auto_edit_plan['notes'])}" if args.auto_edit_plan["notes"] else ""))
    elif args.auto_edit and str(getattr(args, "mode", "") or "").upper() != "TRIP":      # the recap (TRIP) applies the style itself
        print("[Warning] --auto_edit edits video clips (--source_video); it is ignored here.")
    if args.stat_pops:
        os.environ["SHORTSFLOW_STAT_POPS"] = "1"
        if not args.use_remotion:
            print("[Warning] --stat_pops is drawn by the animated renderer; it is ignored without --use_remotion.")
    if args.caption_emoji:
        os.environ["SHORTSFLOW_CAPTION_EMOJI"] = "1"
    from engine import caption_layout
    args.subtitle_y_pos = caption_layout.y_for(getattr(args, "caption_position", "default"), args.subtitle_y_pos)
    if getattr(args, "caption_position", "default") == "off":
        os.environ["SHORTSFLOW_NO_CAPTIONS"] = "1"
    if getattr(args, "caption_size", "default") != "default":
        os.environ["SHORTSFLOW_CAPTION_SIZE"] = str(caption_layout.size_for(args.caption_size))
    if args.hook_overlay:
        os.environ["SHORTSFLOW_HOOK_OVERLAY"] = "1"
    if args.auto_zoom:
        os.environ["SHORTSFLOW_AUTO_ZOOM"] = "1"
        if not args.use_remotion:
            print("[Warning] --auto_zoom needs --use_remotion (animated captions); it is ignored without it.")
        if getattr(args, "layout", None) == "split_filler":
            print("[Warning] --auto_zoom is skipped with --layout split_filler (it would move the seam).")
    if args.caption_color:
        from engine.remotion_renderer import normalize_caption_color
        args.caption_color = normalize_caption_color(args.caption_color)
        if not args.caption_color:
            parser.error("--caption_color must be a hex colour such as '#FF3366'")
        os.environ["SHORTSFLOW_CAPTION_COLOR"] = args.caption_color
    return args



args = parse_args()

NOT_IMPLEMENTED_MODES = ("PODCAST", "SPLIT_SCREEN")
if getattr(args, "mode", None) in NOT_IMPLEMENTED_MODES:
    print(f"[Error] Mode {args.mode} is listed but not implemented yet, so it would not do what its name says. "
          "Use clipping (--source_video ...) or one of the generate modes (FACTS, STORY, NEWS, ...).")
    sys.exit(2)
if getattr(args, "target_lang", None) and getattr(args, "mode", None) != "DUB":
    print("[Warning] --target_lang only works with --mode DUB (translate and re-voice a video); the option is ignored here.")

if getattr(args, "use_ollama", False):
    os.environ["FORCE_OLLAMA"] = "true"
    os.environ["LLM_PROVIDER"] = "ollama"
    print("[Log] 🦙 FORCING Local Ollama LLM execution.")

if getattr(args, "llm_provider", None) and args.llm_provider != "auto":
    os.environ["LLM_PROVIDER"] = args.llm_provider
    print(f"[Log] 🤖 Requested LLM Provider: {args.llm_provider}")

# Quality Mapping (Overridden by manual flags if present)
bitrate_map = {"low": "4M", "medium": "12M", "high": "25M", "ultra": "50M"}
preset_map = {"low": "ultrafast", "medium": "medium", "high": "slow", "ultra": "slower"}

# 🟢 HQ AUTO-BOOST: If --hq is set, default to 'high' quality unless manually specified
if args.hq and (not hasattr(args, 'quality') or args.quality == "medium"):
    args.quality = "high"

target_bitrate = args.bitrate if args.bitrate else bitrate_map.get(args.quality or "medium")
os.environ["SHORTSFLOW_QUALITY"] = args.quality or "medium"   # Remotion output: --quality picks the CRF, --bitrate overrides it
if args.bitrate:
    os.environ["SHORTSFLOW_BITRATE"] = args.bitrate
target_preset = args.preset if args.preset else preset_map.get(args.quality or "medium")

# 🟢 PRO CONFIG: ComfyUI Availability Health Check
if args.use_comfy or args.use_ai_audio:
    from engine.comfy_bridge import is_comfy_available
    if not is_comfy_available():
        print("\n[Warning] ⚠️ PRO FEATURE ALERT: Local ComfyUI is NOT reachable on port 8188.")
        print("[Warning] Falling back to standard generation flow for this run.\n")
        args.use_comfy = False
        args.use_ai_audio = False

# Force UTF-8 encoding for Windows was handled above with line buffering.

# 🟢 Standalone AI Music Generation Mode
if getattr(args, "mode", None) == "MUSIC":
    from engine.modes.music import run as run_music
    run_music(args, target_bitrate, target_preset)

# 🟢 Standalone DUB Mode (translate + re-voice a video)
if getattr(args, "mode", None) == "DUB":
    from engine.modes.dub import run as run_dub
    run_dub(args, target_bitrate, target_preset)

# 🟢 Standalone TRIP recap Mode (several videos -> one recap + itinerary)
if getattr(args, "mode", None) == "TRIP":
    from engine.trip_recap import run as run_trip
    run_trip(args, target_bitrate, target_preset)

# 🟢 Standalone EXPLAINER Mode
if getattr(args, "mode", None) == "EXPLAINER":
    from engine.modes.explainer import run as run_explainer
    run_explainer(args, target_bitrate, target_preset)

# 🟢 PHASE 13: AI Extraction (High-Speed FFmpeg path)
# 🟢 Batch Video File/URL Processing
if getattr(args, "batch_file", None):
    if not os.path.exists(args.batch_file):
        print(f"[Error] Batch file not found: {args.batch_file}")
        sys.exit(1)
        
    print(f"--- Starting Batch Video Processing from: {args.batch_file} ---")
    with open(args.batch_file, "r", encoding="utf-8") as bf:
        urls = [line.strip() for line in bf if line.strip() and not line.strip().startswith("#")]
        
    print(f"[Log] Found {len(urls)} video items to process in batch.")
    import subprocess
    for idx, item in enumerate(urls, start=1):
        print(f"\n==========================================")
        print(f"[Batch {idx}/{len(urls)}] Processing: {item}")
        print(f"==========================================")
        from engine.pipeline import batch_item_command
        is_video_item = is_url(item) or item.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"))
        cmd = batch_item_command(sys.argv[1:], item, idx, python=sys.executable, as_category=not is_video_item)
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"[Warning] Batch item {idx} failed with return code {res.returncode}. Continuing...")
    print("\n[Log] Batch processing completed.")
    sys.exit(0)

# 🟢 Standalone Photo Reel Mode (Photos + Music Beat Sync)
if getattr(args, "mode", None) == "PHOTO_REEL":
    from engine.modes.photo_reel import run as run_photo_reel
    run_photo_reel(args, target_bitrate, target_preset)

# 🟢 Standalone Video Filter Mode
if getattr(args, "mode", None) == "FILTER":
    from engine.modes.video_filter import run as run_video_filter
    run_video_filter(args, target_bitrate, target_preset)

if getattr(args, "source_video", None) and args.mode not in ["TRAILER_MISSED", "FUNNY_EXPLAINER", "PHOTO_REEL"]:
    from engine.modes.clip_extract import run as run_clip_extract
    run_clip_extract(args, target_bitrate, target_preset)

from engine.modes.generate import run as run_generate
run_generate(args, target_bitrate, target_preset)
from engine.pipeline import star_hint
star_hint()
