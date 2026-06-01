FROM ghcr.io/actions/actions-runner:latest

ARG DEBIAN_FRONTEND=noninteractive
ARG NODE_MAJOR=24
ARG PLAYWRIGHT_VERSION=1.60.0

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    VP_FFMPEG_PATH=/usr/bin/ffmpeg \
    VP_FFPROBE_PATH=/usr/bin/ffprobe \
    VP_PYTHON_EXECUTABLE=/opt/vp/venv/bin/python \
    VP_RIFE_MODEL_DIR=/opt/vp/models \
    PATH=/opt/vp/venv/bin:/home/runner/.cargo/bin:$PATH

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      dbus-x11 \
      ffmpeg \
      git \
      gnupg \
      libayatana-appindicator3-dev \
      libgtk-3-dev \
      librsvg2-dev \
      libsoup-3.0-dev \
      libwebkit2gtk-4.1-dev \
      patchelf \
      pkg-config \
      python3 \
      python3-pip \
      python3-venv \
      xz-utils \
      xvfb \
      build-essential \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/vp /ms-playwright \
    && python3 -m venv /opt/vp/venv \
    && /opt/vp/venv/bin/python -m pip install --upgrade pip setuptools wheel

COPY backend/requirements.txt /tmp/backend-requirements.txt

RUN sed -E 's/^onnxruntime-gpu(.*)$/onnxruntime\1/' /tmp/backend-requirements.txt > /tmp/backend-requirements-linux.txt \
    && /opt/vp/venv/bin/pip install -r /tmp/backend-requirements-linux.txt pytest-cov \
    && /opt/vp/venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && (/opt/vp/venv/bin/pip install paddlepaddle || echo "paddlepaddle wheel unavailable for this base image; Paddle-only tests will skip") \
    && rm -f /tmp/backend-requirements.txt /tmp/backend-requirements-linux.txt

COPY backend/models /opt/vp/models

RUN npx --yes "playwright@${PLAYWRIGHT_VERSION}" install --with-deps chromium \
    && chown -R runner:runner /opt/vp /ms-playwright /home/runner \
    && chmod -R a+rX /opt/vp/models /ms-playwright

USER runner

RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable \
    && rustc --version \
    && cargo --version \
    && node --version \
    && python --version \
    && ffmpeg -version | head -n 1
