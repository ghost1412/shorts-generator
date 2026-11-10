"""Hugging Face Space entry point: the ShortsFlow browser app on CPU hardware."""
import os

os.environ.setdefault("WEBUI_HOST", "0.0.0.0")
os.environ.setdefault("SHORTSFLOW_WHISPER_MODEL", "base")      # the free CPU hardware is slow: a smaller speech model

from shortsflow import webui  # installed from requirements.txt

demo = webui.build_ui().queue(default_concurrency_limit=1, max_size=8)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")))
