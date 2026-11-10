"""DUB pipeline: translate a video's speech and re-voice it (runs when: getattr(args, "mode", None) == "DUB")."""
import os
import sys
import time

from engine.media_gen import is_url, download_source_video_from_url


def run(args, target_bitrate=None, target_preset=None):
    from engine.dubbing import dub_video, supported_languages

    if not getattr(args, "source_video", None) or not getattr(args, "target_lang", None):
        print("[Error] DUB mode needs --source_video and --target_lang, e.g. "
              "--mode DUB --source_video talk.mp4 --target_lang es")
        print(f"[Log] Supported languages: {', '.join(supported_languages())}")
        sys.exit(2)

    session_dir = args.session_dir if args.session_dir else f"sessions/dub_{int(time.time())}"
    os.makedirs(session_dir, exist_ok=True)
    if is_url(args.source_video):
        print(f"[Log] Detected Video URL: '{args.source_video}'. Downloading stream...")
        args.source_video = download_source_video_from_url(args.source_video, session_dir)

    try:
        res = dub_video(
            args.source_video, args.target_lang, session_dir,
            language=getattr(args, "language", "en") or "en",
            provider=getattr(args, "tts_provider", "auto") or "auto",
            captions=bool(getattr(args, "dub_captions", False)),
            voice=getattr(args, "dub_voice", None),
            original=getattr(args, "dub_original", "music") or "music",
            about=getattr(args, "user_context", None),
            tone=getattr(args, "dub_tone", "faithful") or "faithful",
            delivery=getattr(args, "dub_delivery", "neutral") or "neutral",
            caption_size=getattr(args, "dub_caption_size", "default") or "default",
            caption_position=getattr(args, "dub_caption_position", "bottom") or "bottom",
        )
    except (ValueError, RuntimeError) as e:
        print(f"[Error] {e}")
        sys.exit(1)

    print(f"[Success] Dubbed video ready at: {res['video']}")
    print(f"[Log] Translated subtitles: {res['srt']}")
    if res["failed_translations"] or res["failed_voices"]:
        print(f"[Warning] {res['failed_translations']} line(s) stayed untranslated and {res['failed_voices']} "
              f"voice line(s) failed (of {res['segments']}); those parts keep the original audio.")
    sys.exit(0)
