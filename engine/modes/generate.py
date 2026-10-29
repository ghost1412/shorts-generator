"""
Idea-to-video pipeline (script -> voice -> backgrounds -> render -> metadata -> upload),
moved verbatim from main.py. Runs for every mode that is not a standalone pipeline.
"""
import os
import sys
import io
import time
import random
import argparse
import json
import re
import subprocess
from dotenv import load_dotenv
from supabase import create_client, Client
from engine.utils import decrypt_secret, find_fact_start_times
from engine.pipeline import POOL_SIZE, VIBE_VOICE_MAP, CARTOON_VOICE_MAP, CARTOON_AUDIO_CONFIG, report_status, export_srt, print_clip_score_table
from engine.script_gen import generate_mixed_facts, generate_story, generate_wyr, generate_reddit_story, generate_trivia, generate_quote, generate_funny_news, generate_sound_challenge, generate_odd_one_out_script, generate_riddle, generate_jwst_script
from engine.voice_gen import generate_voice
from engine.media_gen import download_background_video, download_image, download_sfx, fetch_jwst_images, is_url, download_source_video_from_url
from engine.video_gen import create_shorts_video
from engine.storage import upload_to_storage


def run(args, target_bitrate, target_preset):
    print("--- Starting Shorts Generator ---", flush=True)

    # 0. Manual Script Override
    youtube_video_id = None
    if args.script:
        print("[Log] Manual script detected. Skipping generation...")
        full_script = args.script
        mode = "STORY" # Default to story-style branding for manual scripts
        category = "tech"
        story_data = {"title": "coding setup", "story": full_script}
        facts_data = [] # Not used in story mode but kept for metadata function compatibility
    else:
        # 1. Choose Mode (Manual override or random)
        if args.mode and args.mode != "AUTO":
            mode = args.mode
        else:
            # 🟢 BALANCED MULTI-MODE SELECTION: Includes all newly added viral modes
            mode = random.choices(
                ["FACTS", "FIND_IT", "WYR", "ODD_ONE_OUT", "EMOJI_GUESS", "STORY", "TRIVIA", "REDDIT", "QUOTE", "NEWS", "NEWS_SERIOUS", "GUESS_SOUND", "RIDDLE", "EXPLAINER", "TOP_5", "CHAT_STORY", "HORROR", "TRUE_CRIME", "BIBLE", "ARTICLE", "UGC"],
                weights=[15, 5, 10, 10, 20, 5, 5, 5, 5, 10, 10, 5, 10, 15, 10, 10, 10, 10, 10, 10, 10]
            )[0]
        if args.recap_title and not args.mode: mode = "MOVIE_RECAP"

        # 🟢 AUTO-CARTOON: Enforce character personas for all News modes
        if mode in ("NEWS", "NEWS_SERIOUS"):
            if not args.cartoon:
                print(f"[Log] {mode} detected. Auto-enabling Cartoon Mode...")
                args.cartoon = True

            # 🟢 MULTI-CAT RANDOMIZATION: Pick between cats if no persona is set
            if not args.persona:
                args.persona = random.choice(["mafia_cat", "orange_cat"])
                print(f"[Log] Randomly selected persona: {args.persona}")

        # 2. Choose Category
        categories = ["science", "math", "aptitude", "space", "physics", "puzzle", "animals", "history", "anime_lore", "intimacy_facts", "cooking_hacks", "world", "politics", "celebrities", "tech", "sports", "kids", "children", "bedtime"]
        if not args.category or args.category.lower() == "random":
            if mode in ("EMOJI_GUESS", "FUNNY_EXPLAINER"):
                category = random.choice(["movies", "pop_culture", "superheroes", "disney", "anime", "video_games"])
            elif mode in ("NEWS", "NEWS_SERIOUS"):
                category = random.choice(["world", "tech", "celebrities", "sports", "science", "politics"])
            elif mode == "FACTS":
                # FACTS deliberately states one false claim - keep it away from real people, politics and kids
                category = random.choice(["science", "space", "animals", "history", "physics", "world",
                                          "tech", "human_body", "ocean", "ancient_civilizations", "food", "geography"])
            else:
                category = random.choice(categories)
        else:
            category = args.category
        topic = args.prompt if args.prompt else category

        if args.hero or args.interactive:
            category = "kids"
        print(f"[Log] Generating content for category/topic: '{topic}' (Category: {category})...", flush=True)

        try:
            if mode == "EXPLAINER":
                from engine.script_gen import generate_manim_script
                manim_data = generate_manim_script(topic, extract_mode=args.extract_mode, target_duration=args.target_duration)
                full_script = manim_data["voiceover_text"]
                facts_data = []
                print(f"[Log] EXPLAINER Script generated for topic '{topic}': Title='{manim_data['title']}'")
            elif mode == "FACTS":
                facts_res = generate_mixed_facts(category)
                hook = facts_res["hook"]
                facts_data = facts_res["facts"]

                # Construct the script: Hook -> Challenge Intro -> Facts -> Loop Outro
                full_script = f"{hook} ... Two of these are true. One is a LIE. ... "
                fact_segments = []
                for i, f in enumerate(facts_data[:3]): # Max 3 segments for UI consistency
                    fact_segments.append(f"Number {i+1}. {f['fact']}")

                full_script += " ... ".join(fact_segments)

                # 🟢 Viral loop: ask for the answer instead of a fake-out reveal (answer goes in the description)
                full_script += f" ... So, which number is the lie? {facts_res.get('loop_lead', 'Go back and check again.')}"
            elif mode == "MOVIE_RECAP":
                from engine.script_gen import generate_movie_recap
                recap_data = generate_movie_recap(args.recap_title)
                full_script = recap_data.get("story") or recap_data.get("script", "")
                facts_data = []
                story_data = {"title": args.recap_title, "story": full_script}
            elif mode == "TRAILER_MISSED":
                from engine.script_gen import generate_trailer_missed_script
                trailer_title = args.recap_title or args.category
                if not trailer_title and args.source_video:
                    base = os.path.splitext(os.path.basename(args.source_video))[0]
                    trailer_title = base.replace("_", " ").replace("-", " ")
                if not trailer_title:
                    trailer_title = "the trailer"

                recap_data = generate_trailer_missed_script(trailer_title)
                full_script = f"{recap_data['story']} ... {recap_data.get('loop_lead', 'Go back and check for yourself.')}"
                facts_data = []
                story_data = {"title": trailer_title, "story": full_script}
            elif mode == "STORY":
                hero = args.hero
                hero_name = args.hero_name
                companion = args.companion
                quest = args.quest
                setting = args.setting

                if args.interactive:
                    print("\n🌟 --- Welcome to the Interactive Children's Story Creator! --- 🌟\n")
                    print("Let's build a character together!")

                    # 1. Hero selection
                    heroes = [
                        "Sleepy Bear 🧸",
                        "Friendly Dragon 🐉",
                        "Brave Squirrel 🐿️",
                        "Magic Unicorn 🦄",
                        "Curious Fish 🐟"
                    ]
                    print("\n1. Choose a Hero type:")
                    for idx, h in enumerate(heroes):
                        print(f"  [{idx + 1}] {h}")
                    try:
                        choice = int(input("Enter number (1-5): "))
                        hero = heroes[choice - 1]
                    except Exception:
                        hero = "Sleepy Bear 🧸"

                    # 2. Hero name
                    hero_name = input("\n2. Enter your Hero's name: ").strip()
                    if not hero_name:
                        hero_name = "Luna"

                    # 3. Companion selection
                    companions = [
                        "Twinkle the Pixie 🧚",
                        "Oliver the Wise Owl 🦉",
                        "Barnaby the Busy Beaver 🦫",
                        "Flutter the Rainbow Butterfly 🦋"
                    ]
                    print("\n3. Choose a friendly companion:")
                    for idx, c in enumerate(companions):
                        print(f"  [{idx + 1}] {c}")
                    try:
                        choice = int(input("Enter number (1-4): "))
                        companion = companions[choice - 1]
                    except Exception:
                        companion = "Twinkle the Pixie 🧚"

                    # 4. Quest selection
                    quests = [
                        "find the lost star 🌟",
                        "learn to fly high in the sky 🎈",
                        "find a secret hidden treasure 💎",
                        "help a sad friend feel better 🤝"
                    ]
                    print("\n4. Choose a magical quest:")
                    for idx, q in enumerate(quests):
                        print(f"  [{idx + 1}] {q}")
                    try:
                        choice = int(input("Enter number (1-4): "))
                        quest = quests[choice - 1]
                    except Exception:
                        quest = "find the lost star 🌟"

                    # 5. Setting selection
                    settings = [
                        "Starry Night Forest 🌌",
                        "Candy Land Hills 🍭",
                        "Underwater Castle 🏰",
                        "Sky Island Palace ☁️"
                    ]
                    print("\n5. Choose the setting:")
                    for idx, s in enumerate(settings):
                        print(f"  [{idx + 1}] {s}")
                    try:
                        choice = int(input("Enter number (1-4): "))
                        setting = settings[choice - 1]
                    except Exception:
                        setting = "Starry Night Forest 🌌"

                    # Force category to kids
                    category = "kids"

                if hero:
                    story_data = generate_story(
                        category=category,
                        hero=hero,
                        hero_name=hero_name,
                        companion=companion,
                        quest=quest,
                        setting=setting
                    )
                else:
                    story_data = generate_story(topic if topic else category)

                if not story_data: sys.exit(1)

                # Construct script with strategic viral pauses
                full_script = f"{story_data['story']} ... {story_data.get('loop_lead', 'Hit the plus if you want more.')}"
                facts_data = [] # Not used in story mode but kept for metadata function compatibility
                print(f"[Log] Story: {story_data['story']}")
            elif mode == "FIND_IT" or mode == "FIND_CAT": # Supporting old flag for safety
                target_q = args.category or args.hero or args.prompt or "Cat"
                num_t = args.clip_count if getattr(args, "clip_count", 7) and args.clip_count != 5 else 7
                intros = [
                    f"99% of people WILL FAIL to find all {num_t} {target_q}s! 🧠",
                    f"Only GIGACHADS can spot all {num_t} {target_q}s! 🗿",
                    f"Can you spot all {num_t} hidden {target_q}s before time runs out? 🤫",
                    f"If you find all {num_t} {target_q}s, you owe me a sub! 🤝"
                ]
                full_script = f"{random.choice(intros)} ... 🔍 10 seconds on the clock! ... ... ... ... ... Did you spot them all? Comment below!"
                facts_data = []
                print(f"[Log] Meme Puzzle Game Mode: {mode} (Target: {target_q}, Count: {num_t})", flush=True)
            elif mode == "EMOJI_GUESS":
                from engine.script_gen import generate_emoji_guess
                emoji_data = generate_emoji_guess(category)
                full_script = emoji_data.get("script", f"Can you guess this from emojis? {emoji_data.get('emojis')} ... 5 seconds on the clock! ... Answer is {emoji_data.get('answer')}!")
                facts_data = []
                print(f"[Log] EMOJI_GUESS Data: {emoji_data}")
            elif mode == "WYR":
                wyr_data = generate_wyr(category)
                full_script = f"Would you rather? 🔴 {wyr_data['option_a']} ... OR ... 🔵 {wyr_data['option_b']} ... ... What did you choose? Let me know in the comments!"
                facts_data = [] # Not used
                print(f"[Log] WYR Data: {wyr_data}")
            elif mode == "REDDIT":
                reddit_data = generate_reddit_story(category)
                full_script = f"{reddit_data['title']} ... {reddit_data['story']} ... Whose side are you on? Let me know!"
                facts_data = []
                print(f"[Log] Reddit Data: {reddit_data}")
            elif mode == "TRIVIA":
                trivia_data = generate_trivia(category)
                full_script = f"Are you a genius? Let's find out! ... {trivia_data['question']} ... A: {trivia_data['opt_a']} ... B: {trivia_data['opt_b']} ... C: {trivia_data['opt_c']} ... ... Answer is ... {trivia_data['answer']}. Did you get it right?"
                facts_data = [] # Not used
                print(f"[Log] TRIVIA Data: {trivia_data}")
            elif mode == "QUOTE":
                quote_data = generate_quote(category)
                full_script = f"Listen closely... ... {quote_data['quote']} ... ... ... ... Do you agree?"
                facts_data = []
                print(f"[Log] QUOTE Data: {quote_data}")
            elif mode == "ODD_ONE_OUT":
                # 🟢 REVERT: Static high-tension script for better viral engagement
                intros = [
                    "99% of people FAIL this test! 🧠",
                    "Only a GENIUS can spot the odd one! 🗿",
                    "Is your brain awake? Find the difference! 🧐",
                    "Bro, this one is actually impossible! 🤫",
                    "If you find it in 3 seconds, you're a LEGEND! 🏆"
                ]
                hook = random.choice(intros)
                theme = f"One of these is NOT a {category}..."
                full_script = f"{hook} ... {theme} ... Find it before the time runs out! ... ... ... ... ... Did you spot the odd one? Let me know!"
                odd_res = {"hook": hook, "theme": theme} # For metadata consistency
                facts_data = []
                print(f"[Log] ODD_ONE_OUT (Revert): {full_script}")
            elif mode == "RIDDLE":
                riddle_data = generate_riddle(category)
                full_script = f"{riddle_data['hook']} ... {riddle_data['question']} ... ... ... ... Comment the answer below!"
                facts_data = []
                print(f"[Log] RIDDLE Data: {riddle_data}")
            elif mode == "NEWS":
                selected_persona = args.persona if args.persona else ("rabbit" if args.cartoon else None)
                news_data = generate_funny_news(category, tone="funny", persona=selected_persona)
                news_source = news_data.get('source', 'Unknown')
                full_script = f"{news_data['hook']} ... {news_data['story']}"
                facts_data = []
                print(f"[Log] NEWS (funny) Data: {news_data}")
            elif mode == "NEWS_SERIOUS":
                selected_persona = args.persona if args.persona else ("rabbit" if args.cartoon else None)
                news_data = generate_funny_news(category, tone="serious", persona=selected_persona)
                news_source = news_data.get('source', 'Unknown')
                full_script = f"{news_data['hook']} ... {news_data['story']}"
                facts_data = []
                print(f"[Log] NEWS_SERIOUS Data: {news_data}")
            elif mode == "GUESS_SOUND":
                sound_data = generate_sound_challenge(category)
                full_script = f"{sound_data['hook']} ... ... ... ... ... {sound_data['reveal_text']}"
                facts_data = [] # Not used
                print(f"[Log] GUESS_SOUND Data: {sound_data}")
            elif mode == "CHALLENGE":
                from engine.script_gen import generate_breath_challenge
                challenge_data = generate_breath_challenge()
                full_script = challenge_data["script"]
                facts_data = []
                print(f"[Log] CHALLENGE Data: {challenge_data}")
            elif mode == "TREND":
                from engine.script_gen import generate_trend_script
                trend_data = generate_trend_script(category)
                if not trend_data: sys.exit(1)
                full_script = trend_data.get("script") or trend_data.get("story", "")
                facts_data = []
                print(f"[Log] TREND Data: {trend_data}")
            elif mode == "JWST":
                jwst_data = generate_jwst_script()
                full_script = f"{jwst_data['hook']} ... {jwst_data['story']} ... {jwst_data.get('loop_lead', '')}"
                facts_data = []
                print(f"[Log] JWST Data: {jwst_data}")
            elif mode == "FUNNY_EXPLAINER":
                from engine.script_gen import generate_funny_explainer_script
                scene_prompt = None
                raw_source_input = getattr(args, 'source_video', None)

                # Handle YouTube URL or local source video input
                if raw_source_input:
                    if is_url(raw_source_input):
                        temp_dl_dir = f"assets/temp_{random.randint(100000, 999999)}"
                        os.makedirs(temp_dl_dir, exist_ok=True)
                        print(f"[Log] 🎵 Detected YouTube URL for scene video: '{raw_source_input}'. Downloading...")
                        args.source_video = download_source_video_from_url(raw_source_input, temp_dl_dir)

                    # Extract YouTube Title & Description from yt-dlp info.json
                    video_meta_info = ""
                    try:
                        from engine.media_gen import get_chapters_json_path
                        info_p = get_chapters_json_path(raw_source_input)
                        if info_p and os.path.exists(info_p):
                            with open(info_p, 'r', encoding='utf-8') as f_info:
                                i_data = json.load(f_info)
                                v_title = i_data.get("title", "")
                                v_desc = i_data.get("description", "")
                                if v_title:
                                    video_meta_info = f"VIDEO TITLE / SHOW: {v_title}"
                                    if v_desc:
                                        video_meta_info += f"\nVIDEO DESCRIPTION: {v_desc[:400]}"
                                    print(f"[Log] 🎬 Extracted video metadata: '{v_title}'")
                    except Exception as e:
                        print(f"[Warning] Could not extract video metadata: {e}")

                    transcript_context = ""
                    if args.source_video and os.path.exists(args.source_video):
                        try:
                            from engine.analysis import transcribe_video
                            temp_t_dir = args.session_dir if args.session_dir else f"assets/temp_{random.randint(100000, 999999)}"
                            print(f"[Log] 🎙️ Transcribing source video to extract scene context for FUNNY_EXPLAINER...")
                            t_path = transcribe_video(args.source_video, temp_t_dir)
                            if os.path.exists(t_path):
                                with open(t_path, 'r', encoding='utf-8') as tf:
                                    t_data = json.load(tf)
                                    transcript_text = t_data.get("text", "")
                                    if not transcript_text and "segments" in t_data:
                                        transcript_text = " ".join([seg.get("text", "") for seg in t_data["segments"]])
                                    if transcript_text and len(transcript_text.strip()) > 10:
                                        if len(transcript_text) > 2500:
                                            part1 = transcript_text[:1000]
                                            mid_idx = len(transcript_text) // 2
                                            part2 = transcript_text[mid_idx - 600 : mid_idx + 600]
                                            part3 = transcript_text[-1000:]
                                            transcript_context = f"FULL VIDEO DIALOGUE:\n[BEGINNING]: {part1}\n\n[MIDDLE]: {part2}\n\n[ENDING]: {part3}"
                                        else:
                                            transcript_context = f"FULL VIDEO DIALOGUE:\n{transcript_text}"
                                        print(f"[Log] 📄 Extracted full video transcript ({len(transcript_text)} chars).")
                        except Exception as e:
                            print(f"[Warning] Failed to transcribe source video: {e}")

                    user_ctx = getattr(args, 'scene', None) or args.prompt or getattr(args, 'user_context', None) or ""
                    context_parts = []
                    if video_meta_info: context_parts.append(video_meta_info)
                    if user_ctx: context_parts.append(f"USER CONTEXT / SHOW SCENE: {user_ctx}")
                    if transcript_context: context_parts.append(transcript_context)

                    if context_parts:
                        scene_prompt = "\n\n".join(context_parts)

                if not scene_prompt:
                    scene_prompt = getattr(args, 'scene', None) or args.prompt or category or "Why cats knock glasses off tables at 3 AM"

                vibe = getattr(args, 'vibe', 'sarcastic') or 'sarcastic'
                funny_data = generate_funny_explainer_script(scene_prompt, vibe=vibe, target_duration=args.target_duration)
                step_texts = " ".join([s.get('text', '') for s in funny_data.get('scene_steps', []) if isinstance(s, dict)])
                full_script = f"{funny_data.get('hook', '')} {step_texts} {funny_data.get('outro', '')}".strip()
                facts_data = []
                print(f"[Log] 😼 FUNNY_EXPLAINER Data: {funny_data}")
            elif mode == "TEACH":
                from engine.script_gen import generate_teach_script
                vibe_val = getattr(args, 'vibe', 'upbeat')
                if not vibe_val or vibe_val == 'suspense':
                    vibe_val = 'upbeat'
                    args.vibe = 'upbeat'
                teach_data = generate_teach_script(category=category, topic_prompt=topic, vibe=vibe_val)
                full_script = teach_data.get("narrator_script", "")
                facts_data = []
                print(f"[Log] 🎓 TEACH Data: {teach_data}")
            elif mode == "TOP_5":
                from engine.script_gen import generate_top5_script
                top5_data = generate_top5_script(category)
                full_script = top5_data.get("narrator_script", "")
                facts_data = []
                print(f"[Log] 🔝 TOP_5 Data: {top5_data}")
            elif mode == "CHAT_STORY":
                from engine.script_gen import generate_chat_story_script
                chat_data = generate_chat_story_script(topic)
                full_script = chat_data.get("narrator_script", "")
                facts_data = []
                print(f"[Log] 💬 CHAT_STORY Data: {chat_data}")
            elif mode == "HORROR":
                from engine.script_gen import generate_horror_story_script
                horror_data = generate_horror_story_script(topic)
                full_script = horror_data.get("narrator_script", "")
                facts_data = []
                print(f"[Log] 👁️ HORROR Data: {horror_data}")
            elif mode == "TRUE_CRIME":
                from engine.script_gen import generate_true_crime_script
                crime_data = generate_true_crime_script(topic)
                full_script = crime_data.get("narrator_script", "")
                facts_data = []
                print(f"[Log] 🕵️ TRUE_CRIME Data: {crime_data}")
            elif mode == "BIBLE":
                from engine.script_gen import generate_bible_story_script
                bible_data = generate_bible_story_script(topic)
                full_script = bible_data.get("narrator_script", "")
                facts_data = []
                print(f"[Log] 📜 BIBLE Data: {bible_data}")
            elif mode == "ARTICLE":
                from engine.script_gen import generate_article_summary_script
                article_data = generate_article_summary_script(topic)
                full_script = article_data.get("narrator_script", "")
                facts_data = []
                print(f"[Log] 📰 ARTICLE Data: {article_data}")
            elif mode == "UGC":
                from engine.script_gen import generate_ugc_product_script
                ugc_data = generate_ugc_product_script(topic)
                full_script = ugc_data.get("narrator_script", "")
                facts_data = []
                print(f"[Log] 🚀 UGC Data: {ugc_data}")
        except RuntimeError as e:
            print(f"[Error] Generation failed: {e}")
            print("[Log] Skipping this video - exiting non-zero so the scheduled run is flagged.")
            sys.exit(1)

    print(f"[Log] Full Script: \"{full_script}\"", flush=True)

    # 2. Generate Voice & Timings
    print("[Log] Generating voiceover and timing data...", flush=True)
    # Use a unique session ID and directory for complete isolation
    session_id = random.randint(100000, 999999)
    session_dir = f"assets/temp_{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    voice_file = os.path.join(session_dir, "voice.mp3")
    subs_file = os.path.join(session_dir, "subs.json")

    # Map vibe to an emotional voice
    is_kids_story = category.lower() in ["kids", "children", "bedtime"] or bool(args.hero or args.interactive)
    if is_kids_story:
        selected_voice = "en-US-AvaNeural"
        selected_pitch = "+0Hz"
        selected_rate = "+5%"
        print(f"[Log] Kids Story Mode Active: Voice={selected_voice}, Pitch={selected_pitch}, Rate={selected_rate}")
    else:
        selected_voice = getattr(args, "voice", None) or VIBE_VOICE_MAP.get(args.vibe, "en-US-GuyNeural")
        selected_pitch = "+0Hz"
        selected_rate = "+20%" if mode == "FUNNY_EXPLAINER" else "+15%"

    # Overwrite voice if Cartoon persona is active
    selected_persona = args.persona if args.persona else ("mafia_cat" if args.cartoon else None)
    if selected_persona and mode in ["NEWS", "NEWS_SERIOUS"]:
        p_key = selected_persona.lower()
        selected_voice = CARTOON_VOICE_MAP.get(p_key, CARTOON_VOICE_MAP["default"])
        audio_cfg = CARTOON_AUDIO_CONFIG.get(p_key, CARTOON_AUDIO_CONFIG["default"])
        selected_pitch = audio_cfg["pitch"]
        selected_rate = audio_cfg["rate"]
        print(f"[Log] Cartoon Persona '{selected_persona}' Active: Voice={selected_voice}, Pitch={selected_pitch}, Rate={selected_rate}")
    else:
        print(f"[Log] Selected voice for '{args.vibe}' vibe: {selected_voice}")

    # Voice CTA only for interactive/game modes
    add_cta = mode in ["FACTS", "WYR", "FIND_IT", "ODD_ONE_OUT", "TRIVIA", "GUESS_SOUND", "EMOJI_GUESS"]
    audio_path, subs_path = generate_voice(
        full_script, 
        output_audio=voice_file, 
        output_subs=subs_file, 
        voice_name=selected_voice, 
        rate=selected_rate, 
        pitch=selected_pitch, 
        add_cta=add_cta
    )

    if args.video_id and args.user_id:
        report_status(args.video_id, args.user_id, "In-Progress Video", "Processing", None, mode)

    if not audio_path or not subs_path:
        print("[Error] Voice generation failed.")
        sys.exit(1)

    # 3. Source Media (Dynamic Backgrounds)
    print("[Log] Searching for relevant background videos...")
    bg_video_paths = []

    # 🧪 A/B EXPERIMENT: Disabled (defaults to Pexels / media_gen search)
    LOCAL_BG_DIR = "assets/backgrounds/local"
    is_local_experiment = False
    local_bg_pool = []
    if is_local_experiment:
        local_bg_pool = [os.path.join(LOCAL_BG_DIR, f) for f in os.listdir(LOCAL_BG_DIR) if f.endswith(".mp4")]
        if local_bg_pool:
            print(f"[Log] 🧪 SEARCH_EXPERIMENT: Local Collection Selected (60% Bucket)")
        else:
            print(f"[Log] [Warning] Local experiment selected but pool is empty, falling back to Pexels.")
            is_local_experiment = False

    def get_video_duration(path):
        """Gets duration of a video using ffprobe."""
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"[Warning] Failed to get duration for {path}: {e}")
            return 10.0 # Fallback

    def get_bg_path(query, out_path, target_duration=15.0, force_literal=False):
        if getattr(args, "bg_media", None) and os.path.exists(args.bg_media):
            from engine.media_gen import download_background_video
            path = download_background_video(query, output_path=out_path, custom_bg=args.bg_media)
            return [path] if path else []

        if is_local_experiment and local_bg_pool:
            # Pick one or more random videos from the local pool until target_duration is covered
            selected_paths = []
            current_len = 0
            while current_len < target_duration and local_bg_pool:
                choice = random.choice(local_bg_pool)
                d = get_video_duration(choice)
                selected_paths.append(os.path.abspath(choice))
                current_len += d
                if len(local_bg_pool) > 1: local_bg_pool.remove(choice)
                if not local_bg_pool: break # Pool exhausted
            return selected_paths

        if args.use_comfy:
            from engine.media_gen import generate_ai_background
            path = generate_ai_background(query, output_path=out_path.replace(".mp4", ".png"))
            if path: return [path]
            print("[Warning] ComfyUI failed, falling back to Pexels...")
        from engine.media_gen import download_background_video
        path = download_background_video("", fallback_query=query, output_path=out_path, force_literal=force_literal)
        return [path] if path else []

    # Calculate segments for staggered backgrounds
    audio_duration = get_video_duration(audio_path)
    total_bg_duration = audio_duration + 1.5

    fact_beat_timestamps = None
    if mode == "FACTS":
        # 3 facts, 3 segments - each background starts when its fact is spoken (hook rides on the first)
        fact_starts = find_fact_start_times(subs_path, len(facts_data))
        seg_bounds = ([0.0] + fact_starts[1:] + [total_bg_duration]) if fact_starts else None
        for i, fact in enumerate(facts_data):
            bg_filename = os.path.join(session_dir, f"bg_fact_{i+1}.mp4")
            seg_len = (seg_bounds[i + 1] - seg_bounds[i]) if seg_bounds else total_bg_duration / len(facts_data)
            paths = get_bg_path(fact.get('visual') or fact['fact'], bg_filename, target_duration=seg_len, force_literal=True)
            bg_video_paths.extend(paths)
        if seg_bounds and len(bg_video_paths) == len(facts_data):
            fact_beat_timestamps = seg_bounds[:-1]
    elif mode == "STORY":
        # 2 segments
        seg_len = total_bg_duration / 2
        is_custom_kids = bool(args.hero or args.interactive)

        for i in range(2):
            bg_filename = os.path.join(session_dir, f"bg_story_{i}.mp4")
            if is_custom_kids:
                if args.use_comfy:
                    search_query = f"Whimsical Pixar style 3D render, claymation, cute colorful cartoon illustration for children, scene {i+1}: {story_data['story']}"
                else:
                    search_query = f"{args.setting or category or 'magical forest'}"
            else:
                search_query = f"{category} {story_data['title']}"

            paths = get_bg_path(search_query, bg_filename, target_duration=seg_len)
            bg_video_paths.extend(paths)
    elif mode == "FIND_IT" or mode == "FIND_CAT": # Supporting old flag for safety
        from engine.media_gen import get_puzzle_meme_assets
        target_q = getattr(args, "bg_media", None) or args.category or args.hero or args.prompt or "Cat"
        num_t = args.clip_count if getattr(args, "clip_count", 7) and args.clip_count != 5 else 7
        game_assets = get_puzzle_meme_assets(target_query=target_q, num_objects=num_t, output_dir=session_dir)
        target_path = game_assets["target_path"]
        target_name = game_assets["target_name"]
        num_targets = game_assets["num_targets"]
        if not target_path or not os.path.exists(target_path):
            print(f"[Error] Failed to load {target_name} sticker image.", flush=True)
            sys.exit(1)
        static_bg_path = os.path.join(session_dir, "bg_puzzle_scenic_static.png")
        scenic_queries = [
            "scenic landscape rice terraces nature mountains",
            "beautiful nature landscape vertical 4k",
            "scenic countryside nature vertical",
            "cozy aesthetic room interior"
        ]
        bg_img = download_image(random.choice(scenic_queries), output_path=static_bg_path)
        if bg_img and os.path.exists(bg_img):
            bg_video_paths = [bg_img]
        else:
            bg_filename = os.path.join(session_dir, "bg_puzzle_scenic.mp4")
            paths = get_bg_path("scenic landscape nature mountains", bg_filename, target_duration=total_bg_duration)
            bg_video_paths.extend(paths)
    elif mode == "WYR":
        # 2 backgrounds for split screen
        seg_len = total_bg_duration / 2
        search_query = f"{category} satisfying"
        for i in range(2):
            bg_filename = os.path.join(session_dir, f"bg_wyr_{i}.mp4")
            paths = get_bg_path(search_query if i == 0 else "minecraft parkour", bg_filename, target_duration=seg_len)
            bg_video_paths.extend(paths)
    elif mode == "REDDIT":
        bg_filename = os.path.join(session_dir, "bg_reddit.mp4")
        paths = get_bg_path("satisfying sand", bg_filename, target_duration=total_bg_duration)
        bg_video_paths.extend(paths)
    elif mode == "TRIVIA":
        bg_filename = os.path.join(session_dir, "bg_trivia.mp4")
        paths = get_bg_path("minecraft parkour", bg_filename, target_duration=total_bg_duration)
        bg_video_paths.extend(paths)
    elif mode == "QUOTE":
        bg_filename = os.path.join(session_dir, "bg_quote.mp4")
        paths = get_bg_path("dark cinematic moody slow motion", bg_filename, target_duration=total_bg_duration)
        bg_video_paths.extend(paths)
    elif mode == "ODD_ONE_OUT":
        from engine.media_gen import get_game_assets
        game_assets = get_game_assets(1, output_dir=session_dir)
        target_path = game_assets["target_path"]
        target_name = game_assets["target_name"]
        if not target_path:
            print(f"[Error] Failed to download {target_name} image for ODD_ONE_OUT.", flush=True)
            sys.exit(1)
    elif mode in ("NEWS", "NEWS_SERIOUS"):
        search_query = news_data.get('search_term', 'breaking news broadcast') if 'news_data' in locals() else 'breaking news broadcast'
        bg_filename = os.path.join(session_dir, "bg_news.mp4")
        paths = get_bg_path(search_query, bg_filename, target_duration=total_bg_duration)
        if not paths:
            paths = get_bg_path("news studio broadcast", os.path.join(session_dir, "bg_news_fallback.mp4"), target_duration=total_bg_duration)
        bg_video_paths.extend(paths)
    elif mode == "GUESS_SOUND":
        bg_filename = os.path.join(session_dir, "bg_sound.mp4")
        paths = get_bg_path("satisfying sand", bg_filename, target_duration=total_bg_duration)
        bg_video_paths.extend(paths)

        # Download object image for reveal
        obj_filename = os.path.join(session_dir, "reveal_obj.png")
        download_image(sound_data["object"], output_path=obj_filename)

        # Download sound effect
        sfx_filename = os.path.join(session_dir, "challenge_sfx.mp3")
        download_sfx(sound_data["sound_query"], output_path=sfx_filename)
        bg_filename = os.path.join(session_dir, "bg_gen.mp4")
        path = get_bg_path(category + " satisfying", bg_filename)
        if path: bg_video_paths.append(path)
    elif mode == "RIDDLE":
        bg_filename = os.path.join(session_dir, "bg_riddle.mp4")
        paths = get_bg_path(category + " background", bg_filename, target_duration=total_bg_duration)
        bg_video_paths.extend(paths)
        clue_path = None
    elif mode == "EMOJI_GUESS":
        bg_filename = os.path.join(session_dir, "bg_emoji_guess.mp4")
        query = category if category and category != "random" else "satisfying"
        paths = get_bg_path(query, bg_filename, target_duration=total_bg_duration)
        if not paths:
            paths = get_bg_path("minecraft parkour", os.path.join(session_dir, "bg_emoji_fallback.mp4"), target_duration=total_bg_duration)
        bg_video_paths.extend(paths)
    elif mode == "JWST":
        print("[Log] Fetching James Webb Telescope images...")
        bg_video_paths = fetch_jwst_images(num_images=random.randint(1, 4))
        if not bg_video_paths:
            print("[Warning] No JWST images found, falling back to Pexels space video.")
            bg_filename = os.path.join(session_dir, "bg_jwst_fallback.mp4")
            bg_video_paths = get_bg_path("outer space james webb telescope", bg_filename)
    elif mode == "FUNNY_EXPLAINER":
        bg_video_paths = []
        if getattr(args, 'source_video', None) and os.path.exists(args.source_video):
            print(f"[Log] 🎬 Extracting scene clips across the ENTIRE source video timeline to cover full video...")
            steps = funny_data.get("scene_steps", []) if 'funny_data' in locals() else []
            num_steps = max(3, len(steps))
            clip_dur = total_bg_duration / num_steps

            # Probe total video duration
            src_dur = 60.0
            try:
                probe_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", args.source_video]
                res = subprocess.run(probe_cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    format_info = json.loads(res.stdout).get("format", {})
                    src_dur = float(format_info.get("duration", 60.0))
            except Exception:
                pass

            print(f"[Log] Total source video duration: {src_dur:.1f}s. Extracting {num_steps} scene clips across timeline...")
            step_interval = max(0.0, (src_dur - clip_dur) / max(1, num_steps - 1))

            extracted_scene_paths = []
            for idx in range(num_steps):
                start_t = idx * step_interval
                clip_out = os.path.join(session_dir, f"scene_clip_{idx+1}.mp4")
                cut_cmd = [
                    "ffmpeg", "-y", "-ss", str(round(start_t, 2)), "-i", args.source_video,
                    "-t", str(round(clip_dur, 2)), "-c:v", "libx264", "-c:a", "aac",
                    "-preset", "ultrafast", "-crf", "23", clip_out
                ]
                try:
                    subprocess.run(cut_cmd, capture_output=True, check=True)
                    if os.path.exists(clip_out) and os.path.getsize(clip_out) > 0:
                        extracted_scene_paths.append(clip_out)
                except Exception as e:
                    print(f"[Warning] Failed to cut scene clip at {start_t:.1f}s: {e}")

            if extracted_scene_paths:
                bg_video_paths = extracted_scene_paths
            else:
                bg_video_paths = [args.source_video]
        else:
            steps = funny_data.get("scene_steps", []) if 'funny_data' in locals() else []
            step_dur = total_bg_duration / max(1, len(steps))
            for idx, s in enumerate(steps):
                vp = s.get("visual_prompt") or f"{category or 'funny'} scene"
                s_file = os.path.join(session_dir, f"bg_funny_step_{idx}.mp4")
                s_paths = get_bg_path(vp, s_file, target_duration=step_dur)
                if s_paths:
                    bg_video_paths.extend(s_paths)
        if not bg_video_paths:
            bg_filename = os.path.join(session_dir, "bg_funny_fallback.mp4")
            bg_video_paths = get_bg_path(f"{category or 'funny'} comedy meme", bg_filename, target_duration=total_bg_duration)
    elif mode == "TEACH":
        t_type = teach_data.get("type") if 'teach_data' in locals() else "general"
        dish_or_topic = (teach_data.get("dish_name") if 'teach_data' in locals() else None) or topic or category or "cooking"

        if t_type == "recipe":
            visual_queries = teach_data.get("action_visuals", []) if 'teach_data' in locals() else []
            steps_list = teach_data.get("steps", []) if 'teach_data' in locals() else []
            num_segments = max(len(steps_list), len(visual_queries) if visual_queries else 0, 3)

            if not visual_queries:
                visual_queries = [
                    "boiling pasta pot water",
                    "sizzling garlic butter frying pan",
                    "tossing pasta parmesan cheese",
                    "delicious pasta plating food"
                ]

            seg_dur = total_bg_duration / num_segments
            bg_video_paths = []

            for s_idx in range(num_segments):
                q_term = visual_queries[s_idx % len(visual_queries)]
                s_out = os.path.join(session_dir, f"bg_recipe_action_{s_idx+1}.mp4")
                paths = get_bg_path(q_term, s_out, target_duration=seg_dur, force_literal=True)
                if paths:
                    bg_video_paths.extend(paths)

            if not bg_video_paths:
                bg_filename = os.path.join(session_dir, "bg_recipe_fallback.mp4")
                bg_video_paths = get_bg_path(f"{dish_or_topic} cooking food dish", bg_filename, target_duration=total_bg_duration, force_literal=True)
        elif t_type == "code":
            raw_search = (teach_data.get("search_term") if 'teach_data' in locals() else None) or dish_or_topic
            search_query = f"{raw_search} programming code computer developer matrix"
            bg_filename = os.path.join(session_dir, "bg_teach_code.mp4")
            bg_video_paths = get_bg_path(search_query, bg_filename, target_duration=total_bg_duration, force_literal=True)
        else:
            raw_search = (teach_data.get("search_term") if 'teach_data' in locals() else None) or dish_or_topic
            bg_filename = os.path.join(session_dir, "bg_teach.mp4")
            bg_video_paths = get_bg_path(raw_search, bg_filename, target_duration=total_bg_duration, force_literal=True)
    elif mode == "EXPLAINER":
        print("[Log] Rendering Manim animation code...")
        from engine.video_gen import render_manim_scene
        manim_mp4 = render_manim_scene(manim_data["code"], output_dir=session_dir, extract_mode=args.extract_mode)
        bg_video_paths = [manim_mp4]
    elif mode == "TRAILER_MISSED":
        if not getattr(args, "source_video", None):
            print("[Error] --source_video is required for TRAILER_MISSED mode.")
            sys.exit(1)

        print("[Log] Extracting high-energy clips from trailer video to use as backgrounds...")
        temp_trailer_dir = os.path.join(session_dir, "trailer_clips")
        os.makedirs(temp_trailer_dir, exist_ok=True)

        from engine.analysis import process_source_video
        from engine.video_gen import extract_segments

        # We want 5 highlights of about 8 seconds each
        highlights, transcript_path, interest_points, silence_intervals = process_source_video(
            args.source_video, temp_trailer_dir, mode="shorts", 
            clip_count=5, target_duration=8,
            use_audio_detect=True
        )

        extracted_files = extract_segments(
            args.source_video, highlights, transcript_path, temp_trailer_dir, 
            mode="shorts", bitrate=target_bitrate, preset=target_preset, codec="libx264",
            is_challenge=False, use_hq=args.hq, use_superres=getattr(args, 'superres', False),
            editing_style=args.style, gif_dir=args.gif_dir,
            interest_points=interest_points, silence_intervals=None,
            use_remotion=args.use_remotion,
            caption_style=args.caption_style, subtitle_y_pos=args.subtitle_y_pos,
            max_workers=getattr(args, 'max_workers', None)
        )

        bg_video_paths = extracted_files
    else:
        bg_filename = os.path.join(session_dir, f"bg_{mode.lower()}.mp4")
        search_q = f"{category} {topic}".strip()
        paths = get_bg_path(search_q, bg_filename, target_duration=total_bg_duration)
        if paths:
            bg_video_paths.extend(paths)

    if mode not in ["FIND_IT", "FIND_CAT", "ODD_ONE_OUT"] and not any(bg_video_paths):
        print("[Error] Failed to download any background videos.")
        sys.exit(1)

    if args.video_id and args.user_id:
        report_status(args.video_id, args.user_id, "In-Progress Video", "Processing", None, mode)

    # 4. Compose Video
    print(f"[Log] Composing final interactive video with {args.vibe} mood (Job ID: {session_id})...", flush=True)
    if args.session_dir:
        output_filename = os.path.join(args.session_dir, f"interactive_short_{session_id}.mp4")
    else:
        output_filename = f"interactive_short_{session_id}.mp4"

    # Dynamic Music Selection based on Vibe
    vibe_music_map = {
        "suspense": "music/bg_music.mp3",
        "spooky": "music/spooky.mp3",
        "cinematic": "music/cinematic.mp3",
        "upbeat": "music/upbeat.mp3",
        "sarcastic": "music/upbeat.mp3",
        "funny": "music/upbeat.mp3"
    }
    music_file = vibe_music_map.get(args.vibe, "music/bg_music.mp3")
    bg_music = music_file if os.path.exists(music_file) else "music/bg_music.mp3"

    # 🟢 PRO CONFIG: Unique AI Music generation
    if args.use_ai_audio:
        from engine.comfy_bridge import generate_ai_audio
        print(f"[Log] Generating UNIQUE AI soundtrack for vibe: {args.vibe}")
        # Prompt based on vibe + category
        music_prompt = f"{args.vibe} cinematic {category} background music, high quality, studio grade"
        ai_music = generate_ai_audio(music_prompt, duration=30)
        if ai_music:
            bg_music = ai_music
            print(f"[Log] Using AI-generated soundtrack: {bg_music}")
        else:
            print("[Warning] AI Music generation failed, falling back to stock music.")

    # Resolve cartoon avatar path if active
    avatar_path = None
    selected_persona = args.persona if args.persona else ("mafia_cat" if (args.cartoon or mode in ("NEWS", "NEWS_SERIOUS")) else None)
    if selected_persona:
        for ext in [".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp"]:
            p_path = f"assets/avatars/{selected_persona.lower()}{ext}"
            if os.path.exists(p_path):
                avatar_path = p_path
                break

    remotion_supported_modes = ["FACTS", "STORY", "NEWS", "NEWS_SERIOUS", "RIDDLE", "WYR", "EMOJI_GUESS", "FUNNY_EXPLAINER", "TEACH", "TOP_5", "CHAT_STORY", "HORROR", "TRUE_CRIME", "BIBLE", "ARTICLE", "UGC"]
    if args.use_remotion and mode in remotion_supported_modes:
        from engine.remotion_renderer import render_with_remotion

        remotion_mode = mode
        this_or_that_data = None
        emoji_guess_data = None
        funny_explainer_data = None
        teach_card_data = None

        if mode == "WYR":
            remotion_mode = "THIS_OR_THAT"
            path_a = bg_video_paths[0] if len(bg_video_paths) > 0 else None
            path_b = bg_video_paths[1] if len(bg_video_paths) > 1 else (path_a if path_a else None)
            this_or_that_data = {
                "option_a": wyr_data.get("option_a", "Option A"),
                "option_b": wyr_data.get("option_b", "Option B"),
                "path_a": path_a,
                "path_b": path_b
            }
        elif mode == "EMOJI_GUESS":
            emoji_guess_data = {
                "emojis": emoji_data.get("emojis", "🦁 👑"),
                "answer": emoji_data.get("answer", "The Lion King"),
                "hint": emoji_data.get("hint", "")
            }
        elif mode == "FUNNY_EXPLAINER":
            funny_explainer_data = funny_data if 'funny_data' in locals() else None
        elif mode == "TEACH":
            teach_card_data = teach_data if 'teach_data' in locals() else None

        # Determine dynamic title text for video header
        if mode == "EMOJI_GUESS" and 'emoji_data' in locals() and isinstance(emoji_data, dict):
            render_title = emoji_data.get("title") or f"GUESS THE {emoji_data.get('hint', 'MOVIE').upper()} 🧩"
        elif mode == "TEACH" and 'teach_data' in locals() and isinstance(teach_data, dict):
            render_title = teach_data.get("title", "Learn Something New")
        elif mode == "FUNNY_EXPLAINER" and 'funny_data' in locals() and isinstance(funny_data, dict):
            render_title = funny_data.get("title", "Explainer")
        elif mode == "TOP_5" and 'top5_data' in locals() and isinstance(top5_data, dict):
            render_title = top5_data.get("title", "Top 5 Countdown")
        elif mode == "CHAT_STORY" and 'chat_data' in locals() and isinstance(chat_data, dict):
            render_title = chat_data.get("title", "Chat Story")
        elif mode == "FACTS":
            render_title = "SPOT THE LIE"
        elif args.recap_title:
            render_title = args.recap_title
        elif args.category and args.category.lower() not in ["general", "movies", "ghost of tsushima"]:
            render_title = args.category.title()
        elif category and category.lower() != "general":
            render_title = category.replace("_", " ").title()
        else:
            render_title = None

        final_video = render_with_remotion(
            audio_path=audio_path,
            subs_path=subs_path,
            output_path=output_filename,
            mode=remotion_mode,
            bg_music_path=bg_music,
            title_text=render_title,
            background_paths=bg_video_paths,
            this_or_that=this_or_that_data,
            emoji_guess=emoji_guess_data,
            funny_explainer=funny_explainer_data,
            teach_card=teach_card_data,
            avatar_path=avatar_path,
            caption_style=getattr(args, "caption_style", "HORMOZI"),
            beat_timestamps=fact_beat_timestamps if mode == "FACTS" else None,
            captions=[f"FACT {i+1} / {len(bg_video_paths)}" for i in range(len(bg_video_paths))] if fact_beat_timestamps else None
        )
    else:
        if mode == "FIND_IT" or mode == "FIND_CAT":
            from engine.video_gen import create_meme_puzzle_video
            final_video = create_meme_puzzle_video(
                audio_path,
                bg_video_paths,
                target_path,
                output_filename,
                target_name=target_name,
                num_targets=num_targets,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset,
                show_reveal=getattr(args, "show_reveal", False)
            )
        elif mode == "WYR":
            from engine.video_gen import create_wyr_video
            final_video = create_wyr_video(
                audio_path,
                wyr_data,
                bg_video_paths,
                output_filename,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset
            )
        elif mode == "EMOJI_GUESS":
            from engine.video_gen import create_emoji_guess_video
            final_video = create_emoji_guess_video(
                audio_path,
                subs_path,
                emoji_data,
                bg_video_paths,
                output_filename,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset
            )
        elif mode == "REDDIT":
            from engine.video_gen import create_reddit_video
            final_video = create_reddit_video(
                audio_path,
                subs_path,
                reddit_data,
                bg_video_paths,
                output_filename,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset
            )
        elif mode == "TRIVIA":
            from engine.video_gen import create_trivia_video
            final_video = create_trivia_video(
                audio_path,
                trivia_data,
                bg_video_paths,
                output_filename,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset
            )
        elif mode == "QUOTE":
            from engine.video_gen import create_quote_video
            final_video = create_quote_video(
                audio_path,
                quote_data,
                bg_video_paths,
                output_filename,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset
            )
        elif mode == "ODD_ONE_OUT":
            from engine.video_gen import create_odd_one_out_video
            final_video = create_odd_one_out_video(
                audio_path,
                target_path,
                output_filename,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset
            )
        elif mode == "RIDDLE":
            from engine.video_gen import create_riddle_video
            final_video = create_riddle_video(
                audio_path,
                riddle_data,
                bg_video_paths,
                output_filename,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset,
                clue_path=clue_path
            )
        elif mode == "GUESS_SOUND":
            from engine.video_gen import create_sound_challenge_video
            sfx_path = os.path.join(session_dir, "challenge_sfx.mp3")
            obj_path = os.path.join(session_dir, "reveal_obj.png")
            final_video = create_sound_challenge_video(
                audio_path,
                subs_path,
                sfx_path,
                obj_path,
                bg_video_paths,
                output_filename,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset
            )
        elif mode == "EXPLAINER":
            from engine.video_gen import create_explainer_video
            final_video = create_explainer_video(
                audio_path,
                manim_mp4,
                output_filename,
                music_path=bg_music,
                bitrate=target_bitrate,
                preset=target_preset
            )
        else:
            final_video = create_shorts_video(
                audio_path, 
                subs_path, 
                bg_video_paths, 
                output_filename,
                music_path=bg_music,
                mode=mode,
                use_ai_audio=args.use_ai_audio,
                bitrate=target_bitrate,
                preset=target_preset,
                avatar_path=avatar_path,
                category=category
            )

    print(f"[Log] SUCCESS! Interactive video created: {final_video}")

    # 5. Social Media Automation
    # 5. Viral Metadata Generation (Required for both Upload and Local Report)
    print("[Log] Generating viral metadata...")
    from engine.social_gen import generate_viral_metadata, generate_pinterest_metadata, YouTubeUploader, InstagramUploader, PinterestUploader

    def ensure_dict(data):
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        if not isinstance(data, dict):
            return {"title": "Viral Short", "description": "", "tags": []}

        # Ensure description is a string
        desc = data.get("description", "")
        if isinstance(desc, list):
            data["description"] = "\n".join([str(i) for i in desc])
        elif not isinstance(desc, str):
            data["description"] = str(desc)

        # Ensure title is a string
        title = data.get("title", "")
        if not isinstance(title, str):
            data["title"] = str(title) if title else "Viral Short"

        return data

    if mode == "FACTS":
        metadata = ensure_dict(generate_viral_metadata(facts_data, category=category))
        # Put the answer below the fold so commenters can check themselves
        lie_idx = next((i for i, f in enumerate(facts_data) if f.get("truth") is False), None)
        if lie_idx is not None:
            facts_source = locals().get("facts_res")
            explanation = facts_source.get("lie_explanation", "") if isinstance(facts_source, dict) else ""
            metadata["description"] = (metadata.get("description", "") +
                f"\n\n\n\n⚠️ SPOILER - the lie was #{lie_idx + 1}. {explanation}").strip()
    elif mode == "FIND_IT" or mode == "FIND_CAT":
        metadata = ensure_dict(generate_viral_metadata({"target_name": target_name}, mode="FIND_IT"))
    elif mode == "WYR":
        metadata = ensure_dict(generate_viral_metadata(f"Would You Rather: {wyr_data['option_a']} OR {wyr_data['option_b']}", mode="STORY", category=category))
    elif mode == "REDDIT":
        metadata = ensure_dict(generate_viral_metadata(reddit_data['story'], mode="STORY", category=category))
        # Use reddit title but enforce YouTube's length limit (100 chars max, use 95 for safety)
        metadata['title'] = reddit_data['title'][:95]
    elif mode == "TRIVIA":
        metadata = ensure_dict(generate_viral_metadata(f"Trivia: {trivia_data['question']} Did you guess right?", mode="STORY", category=category))
    elif mode == "QUOTE":
        metadata = ensure_dict(generate_viral_metadata(f"Deep Quote: {quote_data['quote']}", mode="STORY", category=category))
    elif mode == "ODD_ONE_OUT":
        metadata = ensure_dict(generate_viral_metadata({"target_name": f"Odd {target_name}"}, mode="FIND_IT"))
    elif mode in ("NEWS", "NEWS_SERIOUS"):
        metadata = ensure_dict(generate_viral_metadata(news_data.get('story', 'Breaking News'), mode="NEWS", category=category))
        # Append source credit to description
        source_credit = news_data.get('source', '')
        if source_credit:
            metadata['description'] = metadata.get('description', '') + f"\n\n📰 Source: {source_credit}"
    elif mode == "GUESS_SOUND":
        metadata = ensure_dict(generate_viral_metadata(f"Can you guess this sound? It's a {sound_data['object']}", mode="STORY", category=category))
    elif mode == "FUNNY_EXPLAINER":
        funny_title = funny_data.get("title") if 'funny_data' in locals() and isinstance(funny_data, dict) else "Scene Breakdown 🎬"
        funny_desc = funny_data.get("hook") if 'funny_data' in locals() and isinstance(funny_data, dict) else "Viral sarcastic scene breakdown."
        metadata = ensure_dict({
            "title": funny_title,
            "description": funny_desc,
            "tags": ["shorts", "funny", "scenebreakdown", category]
        })
    else:
        # For STORY or other modes
        story_content = story_data['story'] if 'story_data' in locals() and story_data else "Viral Story"
        metadata = ensure_dict(generate_viral_metadata(story_content, mode=mode, category=category))

    # Ensure metadata fields are always populated defensively
    if not metadata.get("title"):
        metadata["title"] = f"Shocking {category} reveal! 😱"
    metadata["title"] = (metadata["title"] or "Viral Short")[:95]

    if not metadata.get("description"):
        metadata["description"] = f"Watch this amazing {category} short!"

    if not isinstance(metadata.get("tags"), list):
        metadata["tags"] = [category, "shorts", "viral", mode.lower()]

    print(f"[Log] Viral Title: {metadata['title']}")

    if args.video_id and args.user_id:
        report_status(args.video_id, args.user_id, metadata['title'], "Processing", None, mode)

    # 6. Social Media Automation
    actually_skip_upload = args.skip_upload

    if not actually_skip_upload:
        print("[Log] Checking for user-specific upload credentials...")
        from engine.social_gen import YouTubeUploader, InstagramUploader

        youtube_creds = None
        if args.user_id:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") # Use Service Role for backend

            if supabase_url and supabase_key:
                supabase: Client = create_client(supabase_url, supabase_key)
                user_res = supabase.from_("user_configs").select("*").eq("user_id", args.user_id).execute()

                if user_res.data:
                    config = user_res.data[0]
                    # Logic: If user has a refresh token, we need a client_id/secret to use it.
                    # We check for User-Specific (BYOK) first, then fallback to Global (Platform) env vars.
                    refresh_token = decrypt_secret(config.get("youtube_refresh_token"))

                    if refresh_token:
                        client_id = decrypt_secret(config.get("youtube_client_id")) or os.getenv("GOOGLE_CLIENT_ID")
                        client_secret = decrypt_secret(config.get("youtube_client_secret")) or os.getenv("GOOGLE_CLIENT_SECRET")

                        if client_id and client_secret:
                            youtube_creds = {
                                "client_id": client_id,
                                "client_secret": client_secret,
                                "refresh_token": refresh_token
                            }
                            print(f"[Log] YouTube credentials initialized for user: {args.user_id}")
                        else:
                            print(f"[Warning] Refresh token present but GOOGLE_CLIENT_ID/SECRET missing for user {args.user_id}. Skipping upload to protect admin channel.")
                            actually_skip_upload = True
                    else:
                        print(f"[Log] No YouTube refresh token found for user {args.user_id}. Skipping upload (Manual triggers do not fallback to admin).")
                        actually_skip_upload = True
                else:
                    print(f"[Log] No configuration found for user {args.user_id} in Supabase. Skipping upload.")
                    actually_skip_upload = True
            else:
                print("[Warning] SUPABASE_URL or SERVICE_ROLE_KEY missing. Skipping user-specific upload check.")
                actually_skip_upload = True

        if not actually_skip_upload:
            print("[Log] Initializing YouTube Uploader...")
            uploader = YouTubeUploader(
                secrets_file=getattr(args, 'youtube_secrets_file', None),
                token_file=getattr(args, 'youtube_token_file', None),
                account=getattr(args, 'youtube_account', None)
            )
            youtube_video_id = None
            if uploader.authenticate(creds_dict=youtube_creds):
                youtube_video_id = uploader.upload_video(
                    final_video, 
                    metadata['title'],
                    metadata['description'],
                    metadata['tags']
                )
            else:
                print("🚀 YouTube Auth failed or skipped.")

        # 6c. Optional Pinterest Upload
        if args.pinterest and not actually_skip_upload:
            print("[Log] Pinterest upload flag detected. Generating Pinterest-specific SEO metadata...")
            # Note: We pass the core data to ensure Pinterest gets its own optimized keywords
            pinterest_info = facts_data if mode == "FACTS" else (story_data if 'story_data' in locals() else {"title": metadata['title']})
            p_metadata = generate_pinterest_metadata(pinterest_info, mode=mode, category=category)

            print(f"[Log] Pinterest Title: {p_metadata['title']}")
            p_uploader = PinterestUploader()
            p_uploader.upload_video(
                final_video,
                p_metadata['title'],
                p_metadata['description'],
                link=args.pinterest_link
            )

        # 6d. Optional Instagram Upload
        if args.instagram and not actually_skip_upload:
            print("[Log] Instagram uploader ready.")
            ig_uploader = InstagramUploader()
            ig_uploader.upload_reel(final_video, f"{metadata['title']}\n\n{metadata['description']}")

    if actually_skip_upload:
        print("[Log] Skip Upload flag detected (or forced). Social media steps ignored.")

    # 7. Permanent Storage Persistence (New Step)
    if args.video_id and args.user_id:
        os.environ["USER_ID"] = args.user_id
        print(f"[Log] Persisting video and thumbnail to cloud storage for user {args.user_id}...")

        # 7a. Extract thumbnail first
        thumbnail_file = f"thumb_{session_id}.jpg"
        thumbnail_path = None
        try:
            print(f"[Log] Extracting thumbnail from {final_video}...")
            subprocess.run([
                'ffmpeg', '-y', '-i', final_video, 
                '-ss', '00:00:01', '-vframes', '1', 
                thumbnail_file
            ], check=True, capture_output=True)
            thumbnail_path = upload_to_storage(thumbnail_file, args.video_id, is_video=False)
            try: os.remove(thumbnail_file)
            except: pass
        except Exception as te:
            print(f"[Warning] Thumbnail extraction/upload failed: {te}")

        # 7b. Upload video
        storage_path = upload_to_storage(final_video, args.video_id, is_video=True)

        # 8. Report Success to Dashboard
        print(f"[Log] Reporting success to dashboard for Job {args.video_id}...")
        report_status(
            args.video_id, 
            args.user_id, 
            metadata['title'], 
            "Published", 
            None, 
            args.mode or mode,
            youtube_video_id,
            storage_path,
            thumbnail_path
        )

    with open(f"{output_filename}.txt", "w", encoding="utf-8") as f:
        f.write(f"Title: {metadata.get('title', 'Viral Short')}\n")
        f.write(f"Description: {metadata.get('description', '')}\n")
        tags_list = metadata.get('tags', [])
        tags_str = ", ".join(tags_list) if isinstance(tags_list, list) else str(tags_list)
        f.write(f"Tags: {tags_str}\n")

    # Multi-Platform Social Metadata Package Export (.meta.json)
    meta_package = {
        "video_path": output_filename,
        "title": metadata.get('title', 'Viral Short'),
        "mode": mode,
        "youtube": {
            "title": metadata.get('title', ''),
            "description": metadata.get('description', ''),
            "tags": metadata.get('tags', [])
        },
        "tiktok": {
            "caption": f"{metadata.get('title', '')} 😱 #fyp #viral #trending #{category.replace(' ', '')}",
            "hashtags": ["#fyp", "#viral", "#trending", f"#{category.replace(' ', '')}"]
        },
        "instagram": {
            "caption": f"{metadata.get('title', '')}\n\nTag someone who needs to see this! 👇\n\n{metadata.get('description', '')}",
            "hashtags": ["#reels", "#explore", "#viral", f"#{category.replace(' ', '')}"]
        }
    }
    try:
        meta_json_path = f"{output_filename}.meta.json"
        with open(meta_json_path, "w", encoding="utf-8") as mf:
            json.dump(meta_package, mf, indent=2, ensure_ascii=False)
        print(f"[Log] 📦 Social Media Metadata Package exported to: {meta_json_path}")
    except Exception as me:
        print(f"[Warning] Failed to export .meta.json: {me}")
