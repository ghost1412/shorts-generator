FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    WEBUI_HOST=0.0.0.0 \
    WEBUI_PORT=7860

# FFmpeg, Manim/Pango build deps, Chromium libs for Remotion, Node.js 20,
# and MS core fonts - the caption presets are designed around Impact / Arial Black.
RUN sed -i 's/^Components: main$/Components: main contrib/' /etc/apt/sources.list.d/debian.sources \
    && echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections \
    && apt-get update && apt-get install -y --no-install-recommends ttf-mscorefonts-installer fontconfig \
    && fc-cache -f \
    && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates gnupg build-essential pkg-config \
        libcairo2-dev libpango1.0-dev libglib2.0-dev \
        libnss3 libatk-bridge2.0-0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
        libasound2 libpangocairo-1.0-0 libgtk-3-0 fonts-dejavu fonts-liberation \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch keeps the image ~3 GB smaller; GPU users can rebuild with the CUDA wheel.
COPY requirements.txt requirements-full.txt ./
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements-full.txt

COPY remotion-video/package*.json remotion-video/
RUN cd remotion-video && npm install

COPY . .

EXPOSE 7860 8080
CMD ["python", "webui.py"]
