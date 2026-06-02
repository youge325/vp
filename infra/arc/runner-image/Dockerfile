FROM ghcr.io/actions/actions-runner:latest AS common

ARG DEBIAN_FRONTEND=noninteractive
ARG DIRECT_NO_PROXY="localhost,127.0.0.1,::1,mirrors.tuna.tsinghua.edu.cn,mirrors6.tuna.tsinghua.edu.cn,mirrors.ustc.edu.cn,cmcc.mirrors.ustc.edu.cn,www.paddlepaddle.org.cn,download.pytorch.org,security.ubuntu.com,deb.nodesource.com,sh.rustup.rs,static.rust-lang.org"
ARG NODE_MAJOR=24
ARG PLAYWRIGHT_VERSION=1.60.0

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    CARGO_HTTP_TIMEOUT=600 \
    CARGO_NET_RETRY=10 \
    NO_PROXY=${DIRECT_NO_PROXY} \
    no_proxy=${DIRECT_NO_PROXY} \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    VP_FFMPEG_PATH=/usr/bin/ffmpeg \
    VP_FFPROBE_PATH=/usr/bin/ffprobe \
    VP_PYTHON_EXECUTABLE=/opt/vp/venv/bin/python \
    VP_RIFE_MODEL_DIR=/opt/vp/models \
    PATH=/opt/vp/venv/bin:/home/runner/.cargo/bin:$PATH

USER root

RUN printf '%s\n' \
      '#!/bin/sh' \
      'unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy' \
      'export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1,mirrors.tuna.tsinghua.edu.cn,mirrors6.tuna.tsinghua.edu.cn,mirrors.ustc.edu.cn,cmcc.mirrors.ustc.edu.cn,www.paddlepaddle.org.cn,download.pytorch.org,security.ubuntu.com,deb.nodesource.com,sh.rustup.rs,static.rust-lang.org}"' \
      'export no_proxy="$NO_PROXY"' \
      'exec "$@"' \
      > /usr/local/bin/vp-direct \
    && chmod +x /usr/local/bin/vp-direct

RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/*git-core* \
    && printf '%s\n' \
      '# Prefer native IPv6 addresses when both the host and package source support them.' \
      'label ::1/128 0' \
      'label ::/0 1' \
      'label 2002::/16 2' \
      'label ::/96 3' \
      'label ::ffff:0:0/96 4' \
      'precedence ::1/128 50' \
      'precedence ::/0 40' \
      'precedence 2002::/16 30' \
      'precedence ::/96 20' \
      'precedence ::ffff:0:0/96 10' \
      >> /etc/gai.conf \
    && printf '%s\n' \
      'Acquire::http::Proxy::mirrors.tuna.tsinghua.edu.cn "DIRECT";' \
      'Acquire::https::Proxy::mirrors.tuna.tsinghua.edu.cn "DIRECT";' \
      'Acquire::http::Proxy::mirrors6.tuna.tsinghua.edu.cn "DIRECT";' \
      'Acquire::https::Proxy::mirrors6.tuna.tsinghua.edu.cn "DIRECT";' \
      'Acquire::http::Proxy::security.ubuntu.com "DIRECT";' \
      'Acquire::https::Proxy::security.ubuntu.com "DIRECT";' \
      'Acquire::http::Proxy::deb.nodesource.com "DIRECT";' \
      'Acquire::https::Proxy::deb.nodesource.com "DIRECT";' \
      > /etc/apt/apt.conf.d/99vp-direct-mirrors \
    && printf '%s\n' \
      'Types: deb' \
      'URIs: https://mirrors.tuna.tsinghua.edu.cn/ubuntu' \
      'Suites: noble noble-updates noble-backports' \
      'Components: main restricted universe multiverse' \
      'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' \
      '' \
      'Types: deb' \
      'URIs: http://security.ubuntu.com/ubuntu/' \
      'Suites: noble-security' \
      'Components: main restricted universe multiverse' \
      'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg' \
      > /etc/apt/sources.list.d/ubuntu.sources \
    && vp-direct apt-get update \
    && vp-direct apt-get install -y --no-install-recommends \
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
    && vp-direct curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key -o /tmp/nodesource.gpg.key \
    && gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg /tmp/nodesource.gpg.key \
    && rm -f /tmp/nodesource.gpg.key \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list \
    && vp-direct apt-get update \
    && vp-direct apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/vp /ms-playwright \
    && python3 -m venv /opt/vp/venv \
    && vp-direct /opt/vp/venv/bin/python -m pip config set global.index-url https://mirrors6.tuna.tsinghua.edu.cn/pypi/web/simple \
    && vp-direct /opt/vp/venv/bin/python -m pip install --upgrade pip setuptools wheel

COPY backend/requirements.txt /tmp/backend-requirements.txt

RUN vp-direct /opt/vp/venv/bin/pip install -r /tmp/backend-requirements.txt pytest-cov onnx opencv-python-headless \
    && rm -f /tmp/backend-requirements.txt

COPY backend/models /opt/vp/models
COPY frontend/src-tauri/Cargo.toml frontend/src-tauri/Cargo.lock /tmp/vp-src-tauri/

RUN npx --yes "playwright@${PLAYWRIGHT_VERSION}" install --with-deps chromium \
    && mkdir -p /tmp/vp-src-tauri/src/bin \
    && printf 'fn main() {}\n' > /tmp/vp-src-tauri/src/main.rs \
    && printf 'fn main() {}\n' > /tmp/vp-src-tauri/src/bin/dump_schema.rs \
    && touch /tmp/vp-src-tauri/src/lib.rs \
    && chown -R runner:runner /opt/vp /ms-playwright /home/runner /tmp/vp-src-tauri \
    && chmod -R a+rX /opt/vp/models /ms-playwright

USER runner

ENV CARGO_HTTP_MULTIPLEXING=false

RUN mkdir -p /home/runner/.cargo \
    && printf '%s\n' \
      '[source.crates-io]' \
      "replace-with = 'ustc'" \
      '' \
      '[source.ustc]' \
      'registry = "sparse+https://mirrors.ustc.edu.cn/crates.io-index/"' \
      '' \
      '[http]' \
      'timeout = 600' \
      'multiplexing = false' \
      > /home/runner/.cargo/config.toml \
    && vp-direct curl -fsSL https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y --profile minimal --default-toolchain stable \
    && rm -f /tmp/rustup-init.sh \
    && cd /tmp/vp-src-tauri \
    && vp-direct cargo fetch --locked \
    && cd / \
    && rm -rf /tmp/vp-src-tauri \
    && rustc --version \
    && cargo --version \
    && node --version \
    && python --version \
    && ffmpeg -version | head -n 1

USER root

RUN printf '%s\n' \
      'vp_append_no_proxy() {' \
      '  current="${NO_PROXY:-${no_proxy:-}}"' \
      '  for host in $(printf "%s" "$VP_DIRECT_NO_PROXY" | tr "," " "); do' \
      '    case ",$current," in' \
      '      *",$host,"*) ;;' \
      '      *) current="${current:+$current,}$host" ;;' \
      '    esac' \
      '  done' \
      '  export NO_PROXY="$current"' \
      '  export no_proxy="$current"' \
      '}' \
      'vp_append_no_proxy' \
      > /etc/profile.d/vp-package-network.sh \
    && printf '%s\n' \
      '#!/bin/sh' \
      'unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy' \
      '. /etc/profile.d/vp-package-network.sh' \
      'exec "$@"' \
      > /usr/local/bin/vp-direct \
    && chmod +x /usr/local/bin/vp-direct \
    && vp-direct /opt/vp/venv/bin/python -m pip config --global set global.index-url https://mirrors6.tuna.tsinghua.edu.cn/pypi/web/simple

USER runner

ENV VP_DIRECT_NO_PROXY=${DIRECT_NO_PROXY} \
    BASH_ENV=/etc/profile.d/vp-package-network.sh \
    PIP_INDEX_URL=https://mirrors6.tuna.tsinghua.edu.cn/pypi/web/simple

FROM common AS pytorch

RUN vp-direct pip3 install --retries 10 --timeout 120 torch torchvision --index-url https://download.pytorch.org/whl/cu132 \
    && python - <<'PY'
import torch
import torchvision

print(f"torch={torch.__version__}")
print(f"torchvision={torchvision.__version__}")
PY

FROM common AS paddle

RUN for attempt in 1 2 3; do \
      vp-direct python -m pip install --retries 10 --timeout 120 --pre paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/nightly/cu129/ && break; \
      if [ "$attempt" = "3" ]; then exit 1; fi; \
      sleep 10; \
    done \
    && python - <<'PY'
import importlib.metadata as metadata

print(f"paddlepaddle-gpu={metadata.version('paddlepaddle-gpu')}")
PY
