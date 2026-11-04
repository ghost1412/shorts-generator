"""clip_extract pipeline, moved verbatim from main.py (runs when: getattr(args, "source_video", None) and args.mode not in ["TRAILER_MISSED", "FUNNY_EXPLAINER", "PHOTO_REEL"])."""
import os
import sys
import json
import subprocess
from engine.media_gen import is_url, download_source_video_from_url
from engine.pipeline import POOL_SIZE, print_clip_score_table


def make_reel_chapters(highlights, transcript_path, reel_path, session_dir):
    """YouTube chapters for the highlights reel (also written to <session>/chapters.txt), or [] when the reel is too short
    or anything goes wrong: chapters are a bonus and must never fail the run."""
    try:
        from engine.analysis import probe_duration
        from engine.chapters import chapters_for_reel, format_chapters
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                segments = json.load(f).get("segments", [])
        except (OSError, ValueError, TypeError):
            segments = []
        total = probe_duration(reel_path) if reel_path and os.path.exists(reel_path) else None
        chapters = chapters_for_reel(highlights, segments, total=total)
        if chapters:
            with open(os.path.join(session_dir, "chapters.txt"), "w", encoding="utf-8") as f:
                f.write(format_chapters(chapters) + "\n")
            print(f"[Log] {len(chapters)} YouTube chapters written to chapters.txt and the description")
        return chapters
    except Exception as e:
        print(f"[Warning] Could not build chapters: {e}")
        return []


def _marker(clip_file, kind):
    return f"{clip_file}.{kind}"


def _fingerprint(value):
    import hashlib
    return hashlib.md5(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def already_done(clip_file, kind, value):
    """True when `kind` ("branded", "clean") was already applied to this clip with the same settings (--use_cache reuses
    finished clips, and stamping the logo or normalising the audio a second time would damage them)."""
    try:
        with open(_marker(clip_file, kind), "r", encoding="utf-8") as f:
            return f.read().strip() == _fingerprint(value)
    except OSError:
        return False


def mark_done(clip_file, kind, value):
    try:
        with open(_marker(clip_file, kind), "w", encoding="utf-8") as f:
            f.write(_fingerprint(value))
    except OSError:
        pass


def align_clips_with_highlights(highlights, files, extract_mode="shorts", mashup=False):
    """(highlights, files) restricted to the clips that were really rendered, in highlight order.

    Short clips are named video_clip_<n>.mp4 where n is the 1-based highlight number, so the file name says which
    highlight it belongs to. Other outputs (the long-form reel, the mashup) are returned unchanged."""
    import re
    if extract_mode == "long" or mashup or not files:
        return highlights, files
    by_index = {}
    for f in files:
        m = re.search(r"video_clip_(\d+)\.mp4$", str(f).replace("\\", "/"))
        if not m:
            return highlights, files               # not the per-highlight naming: leave things as they are
        by_index[int(m.group(1)) - 1] = f
    kept = sorted(i for i in by_index if 0 <= i < len(highlights))
    if len(kept) < len(highlights):
        missing = [i + 1 for i in range(len(highlights)) if i not in by_index]
        print(f"[Warning] {len(highlights) - len(kept)} clip(s) could not be rendered (clip {', '.join(map(str, missing))}); "
              "the others keep their own titles and thumbnails.")
    return [highlights[i] for i in kept], [by_index[i] for i in kept]


def run(args, target_bitrate, target_preset):
    import time
    from engine.video_gen import extract_segments
    from engine.analysis import process_source_video
    from engine.social_gen import generate_viral_metadata
    
    print(f"--- Starting AI Extraction: {args.source_video} ---")
    
    session_dir = args.session_dir if args.session_dir else f"sessions/extraction_{int(time.time())}"
    os.makedirs(session_dir, exist_ok=True)
    
    # Check the brand kit now: a missing logo or a bad position used to surface only after the whole render, before
    # metadata.json and --output_json were written
    brand_kit = None
    if any(getattr(args, k, None) for k in ("brand", "logo", "handle", "end_card")):
        from engine.branding import load_brand
        try:
            brand_kit = load_brand(getattr(args, "brand", None), getattr(args, "logo", None),
                                   getattr(args, "handle", None), getattr(args, "end_card", None))
        except (OSError, ValueError) as e:
            print(f"[Error] Brand kit problem: {e}")
            sys.exit(2)

    # --tighten_mode speed is a MoviePy-only effect: the animated-caption (Remotion) path cuts instead
    if getattr(args, "use_remotion", False) and getattr(args, "tighten", False) and getattr(args, "tighten_mode", "cut") == "speed":
        print("[Warning] --tighten_mode speed is not available with animated captions (--use_remotion): the pauses are cut instead.")

    source_url = args.source_video if is_url(args.source_video) else None   # chapters are cached under the URL, not the file
    # 🟢 Auto-download video if source_video is a URL
    if is_url(args.source_video):
        print(f"[Log] Detected Video URL: '{args.source_video}'. Downloading stream...")
        args.source_video = download_source_video_from_url(args.source_video, session_dir, cookies_from_browser=getattr(args, 'cookies_from_browser', None), cookies_file=getattr(args, 'cookies', None))
        print(f"[Log] Video downloaded locally to: {args.source_video}")

    # Transcript-based trimming: --cut "phrase" / --edit_transcript FILE. Renders an edited source and continues with it.
    if getattr(args, "cut", None) or getattr(args, "edit_transcript", None):
        from engine.transcript_edit import prepare_edited_source
        args.source_video = prepare_edited_source(
            args.source_video, session_dir, phrases=getattr(args, "cut", None),
            edit_path=getattr(args, "edit_transcript", None), keep_fillers=getattr(args, "remove_fillers", False),
            language=getattr(args, "language", "en"))

    print("[Log] Running Transcript-based Highlight Analysis...")
    # 🟢 EXPERT GUARD: Prevention of Mode Confusion
    if args.extract_mode == "shorts" and args.target_duration > 60:
        print(f"[Warning] Target duration {args.target_duration}s exceeds YouTube Shorts limit (60s).")
        print("[Log] Capping short duration at 60s. For longer highlights, use --extract_mode long.")
        args.target_duration = 60
        
    # Get chapters if requested
    chapters_path = None
    if args.use_chapters:
        from engine.media_gen import get_chapters_json_path
        chapters_path = get_chapters_json_path(source_url or args.source_video, session_dir)

    highlights, transcript_path, interest_points, silence_intervals = process_source_video(
        args.source_video, session_dir, mode=args.extract_mode, 
        clip_count=args.clip_count, target_duration=args.target_duration,
        min_duration=args.min_duration,
        use_audio_detect=args.use_audio_detect, style=args.style,
        user_context=args.user_context, style_context=args.style_context,
        smart_crop=args.smart_crop, tighten=args.tighten, use_cache=args.use_cache,
        chapters_path=chapters_path, use_llm_scoring=True,
        find_query=getattr(args, 'find', None),
        keep_fillers=getattr(args, 'remove_fillers', False),
        language=getattr(args, 'language', 'en'),
        snap=not getattr(args, 'no_snap', False),
    )
    
    # The filler pass needs the words as spoken: a translated transcript has no "um" in it
    spoken_transcript_path = transcript_path

    # Captions in another language: translate the word-timed transcript once the moments are chosen
    if getattr(args, "caption_lang", None):
        from engine.caption_translate import resolve_language, translate_transcript
        try:
            transcript_path = translate_transcript(transcript_path, resolve_language(args.caption_lang))
        except (ValueError, RuntimeError) as e:
            print(f"[Error] {e}")
            sys.exit(2)

    # Chinese captions in the script the user asked for (before the clips, captions and titles are made)
    zh_script = getattr(args, "zh_script", "auto") or "auto"
    if zh_script != "auto":
        from engine.zh_script import convert_highlights, convert_transcript
        transcript_path = convert_transcript(transcript_path, zh_script)
        convert_highlights(highlights, zh_script)

    # 🟢 Print the beautiful new score table
    print_clip_score_table(highlights)
    
    # 🟢 Handle Preview Mode
    if args.preview:
        print("\n[Log] 🔍 PREVIEW MODE ENABLED: Rendering fast 3fps proxy instead of full extraction...")
        for i, h in enumerate(highlights):
            out_preview = os.path.join(session_dir, f"preview_clip_{i+1}.mp4")
            cmd = [
                "ffmpeg", "-y", "-ss", str(h['start']), "-i", args.source_video,
                "-t", str(h['end'] - h['start']),
                "-vf", "scale=-2:360", "-r", "3", "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", out_preview
            ]
            subprocess.run(cmd, capture_output=True)
            print(f"  -> Generated {out_preview}")
        print("\n[Log] Preview renders complete. Check session folder.")
        sys.exit(0)
    
    
    # Filter signals based on user flags
    final_interest = interest_points if args.smart_crop else None
    final_silence = silence_intervals if args.tighten else None
    if getattr(args, "remove_fillers", False):
        from engine.fillers import remove_fillers
        with open(spoken_transcript_path, 'r', encoding='utf-8') as f:
            t_segments = json.load(f).get('segments', [])
        total = max([s.get('end', 0) for s in t_segments] or [0]) + 1.0
        rms = None
        try:  # loudness envelope (100 fps) so cuts land on the real "um", not Whisper's rough timestamp
            import librosa
            from engine.analysis import extract_audio_mono
            audio_path = os.path.join(session_dir, "audio_mono.wav")
            if not os.path.exists(audio_path):
                audio_path = extract_audio_mono(args.source_video, session_dir)
            audio, _sr = librosa.load(audio_path, sr=16000)
            rms = librosa.feature.rms(y=audio, frame_length=640, hop_length=160)[0]
        except Exception as e:
            print(f"[Warning] Could not refine filler cuts from audio ({e}); using Whisper timestamps.")
        final_silence, n_fillers = remove_fillers(silence_intervals if args.tighten else [], t_segments, total, rms=rms)
        print(f"[Log] Removing {n_fillers} filler word(s) (um/uh/er...)")
    
    if not highlights:
        print("[Error] No highlights identified.")
        sys.exit(1)
        
    print(f"[Log] Extracting {len(highlights)} segments in parallel via FFmpeg...")
    
    # Check orientation and letterbox
    from engine.analysis import detect_letterbox, detect_orientation
    letterbox_crop = detect_letterbox(args.source_video) if args.smart_crop else None
    orientation = detect_orientation(args.source_video) if args.smart_crop else "landscape"
    
    # Resolve visual filter (Auto vs Manual)
    active_video_filter = getattr(args, 'video_filter', 'none')
    if active_video_filter == "auto":
        from engine.script_gen import auto_detect_video_filter
        active_video_filter = auto_detect_video_filter(user_context=args.user_context, style_context=args.style_context, category=args.category, prompt=args.prompt)
        print(f"[Log] 🎨 Auto-detected video filter: '{active_video_filter}'")

    extracted_files = extract_segments(
        args.source_video, highlights, transcript_path, session_dir, 
        mode=args.extract_mode, bitrate=target_bitrate, preset=target_preset, codec="libx264",
        is_challenge=(args.mode == "CHALLENGE"), use_hq=args.hq, use_superres=getattr(args, 'superres', False),
        editing_style=args.style, gif_dir=args.gif_dir,
        interest_points=final_interest, silence_intervals=final_silence,
        tighten_mode=args.tighten_mode, use_remotion=args.use_remotion, use_cache=args.use_cache,
        mashup=args.mashup, mashup_mode=args.mashup_mode,
        orientation=orientation, letterbox_crop=letterbox_crop,
        caption_style=args.caption_style, subtitle_y_pos=args.subtitle_y_pos,
        video_filter=active_video_filter, user_context=args.user_context,
        max_workers=getattr(args, 'max_workers', None),
        layout=args.layout,
        filler_video=getattr(args, 'filler_video', None),
        remove_fillers=getattr(args, 'remove_fillers', False),
        reel_captions=getattr(args, 'reel_captions', False)
    )
    
    # Pair every output with ITS highlight. Everything below walks `highlights` and `extracted_files` in step, but the
    # renderer only returns the clips that succeeded (and worker threads add them in finishing order), so after one
    # failed clip the titles, thumbnails, SRTs and results.json would all be shifted onto the wrong video.
    highlights, extracted_files = align_clips_with_highlights(highlights, extracted_files, args.extract_mode,
                                                              getattr(args, "mashup", False))

    # Auto B-roll: stock cutaways on spoken nouns, overlaid on the finished vertical clips (engine/broll.py)
    if getattr(args, "broll", False) and extracted_files:
        if args.extract_mode == "long" or getattr(args, "mashup", False):
            print("[Log] B-roll applies to short vertical clips; skipped for the highlights video.")
        else:
            from engine.broll import clip_words, apply_to_clip
            words_source = os.path.join(session_dir, "transcript.json")  # original language: the keyword list is English
            if not os.path.exists(words_source):
                words_source = transcript_path
            try:
                with open(words_source, 'r', encoding='utf-8') as f:
                    broll_transcript = json.load(f)
            except (OSError, ValueError):
                broll_transcript = {}
            hook_on = bool(getattr(args, "hook_overlay", False) and args.use_remotion)
            caption_y = args.subtitle_y_pos if args.use_remotion else 1150
            placed = 0
            for i, clip_file in enumerate(extracted_files):
                if i >= len(highlights):
                    break
                words = clip_words(broll_transcript, highlights[i]['start'], highlights[i]['end'], final_silence,
                                   tighten_mode=args.tighten_mode, remove_fillers=getattr(args, "remove_fillers", False))
                if words is None:
                    print("[Warning] B-roll timing needs --tighten_mode cut when tightening; skipped.")
                    break
                placed += apply_to_clip(clip_file, words, layout=getattr(args, "layout", "single"),
                                        caption_y=caption_y, hook_overlay=hook_on)
            print(f"[Log] B-roll: {placed} cutaway(s) added across {len(extracted_files)} clip(s).")

    # Audio clean-up (noise reduction + loudness normalisation); runs on the finished clips of every render path
    if getattr(args, "clean_audio", False) and extracted_files:
        from engine.audio_clean import clean_clips
        todo = [f for f in extracted_files if not already_done(f, "clean", True)]
        print(f"[Log] Cleaning audio of {len(todo)} clip(s)...")
        for f in todo:
            if clean_clips([f]):
                mark_done(f, "clean", True)

    # Brand kit: logo watermark, @handle and end card (the kit was validated before the render started)
    if brand_kit and extracted_files:
        from engine.branding import apply_brand
        print(f"[Log] Applying brand kit to {len(extracted_files)} clip(s)...")
        for clip_file in extracted_files:
            if already_done(clip_file, "branded", brand_kit):
                continue    # --use_cache reuses finished clips: do not stamp the logo on a second time
            try:
                apply_brand(clip_file, brand_kit)
                mark_done(clip_file, "branded", brand_kit)
            except Exception as e:
                print(f"[Warning] Branding failed for {os.path.basename(clip_file)}: {e}")

    # Export SRT for each extracted file
    if getattr(args, 'srt', False) and extracted_files and os.path.exists(transcript_path):
        print(f"[Log] Exporting SRT files for {len(extracted_files)} clips...")
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                t_data = json.load(f)
            for i, clip_file in enumerate(extracted_files):
                if i < len(highlights):
                    hi = highlights[i]
                    # Copies: one transcript serves every clip, so one clip's offsets must not leak into the next
                    clip_segs = []
                    for seg in t_data.get('segments', []):
                        if seg['end'] <= hi['start'] or seg['start'] >= hi['end']:
                            continue
                        clip_segs.append(dict(seg, start=max(0.0, seg['start'] - hi['start']),
                                              end=min(hi['end'] - hi['start'], seg['end'] - hi['start'])))
                    srt_path = clip_file.rsplit('.', 1)[0] + ".srt"
                    from engine.pipeline import export_srt
                    export_srt({'segments': clip_segs}, srt_path)
        except Exception as e:
            print(f"[Warning] Failed to export SRT files: {e}")

    # 🟢 Policy-Safety: Prepend AI Voiceover Commentary Hook if --add_commentary is set
    if getattr(args, 'add_commentary', False) and extracted_files:
        print("[Log] 🎙️ Policy Protection Active: Generating AI intro commentary hooks for clips...")
        from engine.script_gen import generate_clip_commentary_hook
        from engine.voice_gen import generate_voice
        from engine.video_gen import create_rounded_header_banner
        import imageio_ffmpeg

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        for i, clip_file in enumerate(extracted_files):
            try:
                hi = highlights[i] if i < len(highlights) else {}
                snippet_text = hi.get("text") or hi.get("context") or hi.get("reason") or "Viral video moment"
                hook_sentence = generate_clip_commentary_hook(snippet_text, category=getattr(args, 'category', 'general'))
                print(f"  -> Clip #{i+1} Commentary Hook: '{hook_sentence}'")

                comm_audio_path = os.path.join(session_dir, f"comm_audio_{i}.mp3")
                comm_voice = getattr(args, "voice", None) or "en-US-BrianNeural"
                generate_voice(hook_sentence, output_audio=comm_audio_path, voice_name=comm_voice, rate="+0%", add_cta=False)

                if os.path.exists(comm_audio_path):
                    show_banner = getattr(args, 'show_banner', False)
                    temp_out = clip_file.replace(".mp4", "_comm.mp4")

                    # Calculate exact commentary audio duration
                    comm_dur = 3.5
                    try:
                        res = subprocess.run([ffmpeg_exe, "-i", comm_audio_path], capture_output=True, text=True)
                        for line in res.stderr.split("\n"):
                            if "Duration:" in line:
                                dur_str = line.split("Duration:")[1].split(",")[0].strip()
                                parts = dur_str.split(":")
                                comm_dur = float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
                                break
                    except Exception:
                        pass

                    if show_banner:
                        banner_path = create_rounded_header_banner(text="VIRAL REACTION", width=860, height=110, bg_color="white", text_color="black")
                        filter_complex = (
                            f"[0:v][1:v]overlay=(main_w-overlay_w)/2:30:enable='between(t,0,{comm_dur + 0.5:.2f})'[outv];"
                            f"[0:a]volume=enable='between(t,0,{comm_dur:.2f})':volume=0.20[ducked_bg];"
                            f"[2:a]adelay=0|0,volume=1.2[commaudio];"
                            f"[ducked_bg][commaudio]amix=inputs=2:duration=first:dropout_transition=1[outa]"
                        )

                        cmd = [
                            ffmpeg_exe, "-y",
                            "-i", clip_file,
                            "-i", banner_path,
                            "-i", comm_audio_path,
                            "-filter_complex", filter_complex,
                            "-map", "[outv]",
                            "-map", "[outa]",
                            "-c:v", "libx264", "-preset", "fast",
                            "-c:a", "aac", "-b:a", "192k",
                            temp_out
                        ]
                    else:
                        # Audio-only commentary mix with smart audio ducking (drops original clip audio to 20% while commentary speaks)
                        filter_complex = (
                            f"[0:a]volume=enable='between(t,0,{comm_dur:.2f})':volume=0.20[ducked_bg];"
                            f"[1:a]adelay=0|0,volume=1.2[commaudio];"
                            f"[ducked_bg][commaudio]amix=inputs=2:duration=first:dropout_transition=1[outa]"
                        )

                        cmd = [
                            ffmpeg_exe, "-y",
                            "-i", clip_file,
                            "-i", comm_audio_path,
                            "-filter_complex", filter_complex,
                            "-map", "0:v",
                            "-map", "[outa]",
                            "-c:v", "copy",
                            "-c:a", "aac", "-b:a", "192k",
                            temp_out
                        ]

                    run_res = subprocess.run(cmd, capture_output=True, text=True)
                    if run_res.returncode == 0 and os.path.exists(temp_out):
                        os.replace(temp_out, clip_file)
                        print(f"  -> Applied commentary hook to clip #{i+1} (Ducked background audio to 20%)")
            except Exception as ce:
                print(f"[Warning] Could not apply commentary hook to clip #{i+1}: {ce}")

            

    
    if not extracted_files:
        print("[Error] No videos were generated. Check the logs for FFmpeg failures.")
        sys.exit(1)
    
    # Generate viral metadata for Highlights
    print("[Log] Generating viral metadata for extracted clips...")
    highlights_meta = []
    
    if args.extract_mode == "long" or getattr(args, "mashup", False):
        summary_context = " ".join([h.get('context', h.get('reason', '')) for h in highlights[:5]])
        meta = generate_viral_metadata(summary_context, mode="STORY", category="gaming")
        filename = "mashup_reel.mp4" if getattr(args, "mashup", False) else "highlight_reel.mp4"
        reel_item = {
            "file": filename,
            "title": meta.get('title', 'Viral Mashup' if getattr(args, "mashup", False) else 'Viral Highlight Reel'),
            "description": meta.get('description', ''),
            "tags": meta.get('tags', [])
        }
        if not getattr(args, "mashup", False):
            reel_chapters = make_reel_chapters(highlights, transcript_path, extracted_files[0] if extracted_files else None, session_dir)
            if reel_chapters:
                from engine.chapters import format_chapters
                block = format_chapters(reel_chapters)
                reel_item["chapters"] = reel_chapters
                reel_item["description"] = (reel_item["description"].rstrip() + "\n\nChapters:\n" + block).strip()
        highlights_meta.append(reel_item)
    else:
        from concurrent.futures import ThreadPoolExecutor
        from engine.social_gen import clip_transcript_text
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_segments = json.load(f).get('segments', [])
        except (OSError, ValueError):
            transcript_segments = []

        def fetch_meta(idx_h):
            i, h = idx_h
            if i >= len(extracted_files): return None
            # Sanitize technical jargon from the context/reason
            raw_context = h.get('context', h.get('reason', 'Viral Highlight'))
            if any(j in raw_context for j in ["Recovered", "Regex", "FFmpeg", "stderr"]):
                raw_context = "Viral Clip Highlight"
            
            # Auto-detect topic name and category from user_context, args.category, session_dir, or source_video name
            lower_session = args.session_dir.lower() if args.session_dir else ""
            lower_source = args.source_video.lower() if args.source_video else ""
            lower_ctx = args.user_context.lower() if args.user_context else ""
            lower_combo = f"{lower_session} {lower_source} {lower_ctx}"
            
            active_cat = getattr(args, 'category', None) or "general"
            import re
            
            topic_name = "Viral Highlight"
            if re.search(r'\b(ghost|tsushima)\b', lower_combo):
                topic_name = "Ghost of Tsushima"
                active_cat = "gaming"
            elif re.search(r'\b(nfs|rivals|need for speed)\b', lower_combo):
                topic_name = "Need for Speed Rivals"
                active_cat = "gaming"
            elif re.search(r'\b(gta|grand theft auto)\b', lower_combo):
                topic_name = "GTA 6"
                active_cat = "gaming"
            elif re.search(r'\b(rdr|rdr2|red dead)\b', lower_combo):
                topic_name = "Red Dead Redemption 2"
                active_cat = "gaming"
            elif re.search(r'\b(witcher)\b', lower_combo):
                topic_name = "The Witcher 3"
                active_cat = "gaming"
            elif re.search(r'\b(spider|spiderman)\b', lower_combo):
                topic_name = "Spider-Man"
                active_cat = "gaming"
            elif re.search(r'\b(elden|elden ring)\b', lower_combo):
                topic_name = "Elden Ring"
                active_cat = "gaming"
            elif any(m in lower_combo for m in ["music", "song", "track", "emdi", "ncs", "audio"]):
                topic_name = "Music Performance / Track"
                active_cat = "music"
            elif args.user_context:
                topic_name = " ".join(args.user_context.split()[:4])
                
            content_info = {
                "topic_name": topic_name,
                "game_name": topic_name if active_cat == "gaming" else topic_name,
                "scene_description": raw_context,
                "user_context": args.user_context,
                "styles": args.style if isinstance(args.style, list) else ([args.style] if args.style else [])
            }
            
            if active_cat != "gaming" and topic_name == "Viral Highlight":
                from engine.social_gen import generate_clip_metadata
                meta = generate_clip_metadata(clip_transcript_text(transcript_segments, h['start'], h['end']),
                                              hook=h.get('hook_text'), user_context=args.user_context)
            else:
                meta = generate_viral_metadata(content_info, mode="STORY", category=active_cat, user_context=args.user_context)
            return {
                "file": os.path.basename(extracted_files[i]),
                "title": meta.get('title', 'Viral Moment'),
                "description": meta.get('description', ''),
                "tags": meta.get('tags', []),
                "title_variants": meta.get('title_variants', [])
            }

        with ThreadPoolExecutor(max_workers=min(POOL_SIZE, len(highlights))) as executor:
            results = list(executor.map(fetch_meta, enumerate(highlights)))
            highlights_meta = [r for r in results if r is not None]
        
    # Thumbnail per clip: a frame near the start with the hook as a badge
    from engine.video_gen import generate_thumbnail_with_badge
    reel_mode = args.extract_mode == "long" or getattr(args, "mashup", False)
    for i, clip_file in enumerate([] if reel_mode else extracted_files):
        if i >= len(highlights):
            break
        meta_item = highlights_meta[i] if i < len(highlights_meta) else {}
        badge = highlights[i].get('hook_text') or meta_item.get('title') or "MUST WATCH"
        thumb = clip_file.rsplit('.', 1)[0] + ".jpg"
        try:
            generate_thumbnail_with_badge(clip_file, thumb, badge_text=badge, at_time=1.5)
            if os.path.exists(thumb) and i < len(highlights_meta):
                highlights_meta[i]["thumbnail"] = os.path.basename(thumb)
        except Exception as e:
            print(f"[Warning] Thumbnail failed for clip #{i+1}: {e}")

    with open(os.path.join(session_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(highlights_meta, f, indent=4)
        
    if getattr(args, "clip_report", None):
        from engine.clip_report import build_rows, write_report
        try:
            report_rows = build_rows(highlights, [] if reel_mode else extracted_files, highlights_meta, session_dir)
            for path in write_report(report_rows, session_dir, args.clip_report, source=str(args.source_video)):
                print(f"[Log] Clip report: {path}")
        except (OSError, ValueError) as e:
            print(f"[Warning] Could not write the clip report: {e}")

    if getattr(args, "output_json", None):
        output_json_data = {
            "source_video": args.source_video,
            "session_dir": session_dir,
            "total_clips": len(highlights),
            # what this run used, so a single clip can be re-rendered later with the same settings (engine/rerender.py)
            "settings": {
                "extract_mode": args.extract_mode, "layout": getattr(args, "layout", "single"), "filler_video": getattr(args, "filler_video", None),
                "smart_crop": bool(args.smart_crop), "tighten": bool(args.tighten), "tighten_mode": args.tighten_mode,
                "use_remotion": bool(args.use_remotion), "caption_style": args.caption_style,
                "subtitle_y_pos": args.subtitle_y_pos, "brand": getattr(args, "brand", None),
                "caption_lang": getattr(args, "caption_lang", None), "zh_script": getattr(args, "zh_script", "auto"),
                "clean_audio": bool(getattr(args, "clean_audio", False)), "hook_overlay": bool(getattr(args, "hook_overlay", False)),
                "broll": bool(getattr(args, "broll", False)),
                "auto_zoom": bool(getattr(args, "auto_zoom", False)),
                "caption_color": getattr(args, "caption_color", None),
                "caption_emoji": bool(getattr(args, "caption_emoji", False)),
                "remove_fillers": bool(getattr(args, "remove_fillers", False)),
                "video_filter": getattr(args, "video_filter", None) if getattr(args, "video_filter", "none") not in (None, "none", "auto") else None,
                "logo": getattr(args, "logo", None), "handle": getattr(args, "handle", None),
                "end_card": getattr(args, "end_card", None),
            },
            "clips": []
        }
        if highlights_meta and highlights_meta[0].get("chapters"):
            output_json_data["chapters"] = highlights_meta[0]["chapters"]
        for i, h in enumerate(highlights):
            clip_path = extracted_files[i] if i < len(extracted_files) else ""
            meta_item = highlights_meta[i] if i < len(highlights_meta) else {}
            output_json_data["clips"].append({
                "clip_index": i + 1,
                "video_path": clip_path,
                "start": h.get("start"),
                "end": h.get("end"),
                "duration": round(h.get("end", 0) - h.get("start", 0), 2),
                "viral_score": h.get("viral_score", 85),
                "hook": h.get("hook_text", meta_item.get("title", "")),
                "reason": h.get("reason", "High-engagement segment"),
                "title": meta_item.get("title", f"Clip #{i+1}"),
                "description": meta_item.get("description", ""),
                "tags": meta_item.get("tags", []),
                "title_variants": meta_item.get("title_variants", []),
                "thumbnail": os.path.join(os.path.dirname(clip_path), meta_item["thumbnail"]) if meta_item.get("thumbnail") and clip_path else None
            })
        with open(args.output_json, "w", encoding="utf-8") as f_out:
            json.dump(output_json_data, f_out, indent=4)
        print(f"[Log] Exported structured JSON results to: {args.output_json}")

    print(f"[Log] SUCCESS! Extracted videos to {session_dir}")
    sys.exit(0)
