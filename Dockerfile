# Hugging Face Spaces (Docker SDK): Streamlit on port 7860.
# Native `sdk: streamlit` was removed from the Space creation UI (2025-04-30 changelog).
# APT packages mirror packages.txt — update both when changing system deps.

FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gifsicle \
    build-essential \
    python3-dev \
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    proj-bin \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user requirements.txt packages.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

EXPOSE 7860

CMD ["streamlit", "run", "Home.py", \
    "--server.port", "7860", \
    "--server.address", "0.0.0.0", \
    "--server.headless", "true", \
    "--browser.gatherUsageStats", "false"]
