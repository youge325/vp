# Docker Kubernetes 上的 Actions Runner Controller

本目录保存 Docker Kubernetes 集群使用的 ARC runner scale set 配置。它为当前仓库创建 Linux ARC runners，用来运行新增的 ARC 影子 workflows：

```text
https://github.com/youge325/vp
```

原有 Windows workflows 保持不变，继续负责现有 Windows CI 与 Windows portable release。新增的 `*-arc.yml` workflows 是并行验证链路，不替代原有 workflows；其中 `build-arc.yml` 和 `release-arc.yml` 只验证 Linux ARC release build，不上传 GitHub Release。

## 版本与命名

- ARC chart 版本：`0.14.2`
- Controller namespace：`arc-systems`
- Runner namespace：`arc-runners`
- Controller release：`arc`
- Runner scale set releases：`vp-linux-arc`、`vp-linux-arc-pytorch`、`vp-linux-arc-paddle`
- Runner scale set 名称：`vp-linux-arc`、`vp-linux-arc-pytorch`、`vp-linux-arc-paddle`
- Runner images：
  - `ghcr.io/youge325/vp-arc-runner:latest`
  - `ghcr.io/youge325/vp-arc-runner-pytorch:latest`
  - `ghcr.io/youge325/vp-arc-runner-paddle:latest`
- Labels：`linux`、`arc`、`docker-k8s`
- Warm runner：`minRunners: 1`

## 自定义 Runner 镜像

自定义镜像定义在 `infra/arc/runner-image/Dockerfile`。镜像基于 `ghcr.io/actions/actions-runner:latest`，预装 Node、Rust/Cargo、Python venv、FFmpeg、Playwright Chromium 依赖、Tauri Linux 构建依赖，并把模型复制到 `/opt/vp/models`。镜像按 TUNA Ubuntu 24.04 DEB822 源格式配置 apt，Python venv 默认使用清华 PyPI 镜像源，Cargo 使用 USTC crates.io sparse registry 镜像。

镜像里的包源访问策略：

- `NO_PROXY`/`no_proxy` 覆盖 TUNA、USTC、Paddle nightly、PyTorch CUDA wheel、Ubuntu security、NodeSource、Rustup 等包源域名。
- `/etc/profile.d/vp-package-network.sh` 通过 `BASH_ENV` 在 runner 的 bash 步骤里合并这些直连域名；即使 Docker 或 Kubernetes 注入了自己的 `NO_PROXY`，也会保留包源直连规则。
- pip 同时写入镜像级全局配置并设置 `PIP_INDEX_URL=https://mirrors6.tuna.tsinghua.edu.cn/pypi/web/simple`，runner 用户的 pip 默认走清华 IPv6 PyPI 源。
- Dockerfile 内的 apt、pip、Cargo 构建步骤通过 `vp-direct` 包装器显式清除 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 及小写变体，运行时也可以用 `vp-direct <command>` 强制直连这些包源。
- apt 额外写入 `/etc/apt/apt.conf.d/99vp-direct-mirrors`，对 TUNA Ubuntu、Ubuntu security、NodeSource host 设置 `DIRECT`。
- `/etc/gai.conf` 降低 IPv4-mapped 地址优先级；当源站同时提供 IPv4/IPv6 且宿主网络支持 IPv6 时，优先使用原生 IPv6。`mirrors6.tuna.tsinghua.edu.cn` 是 PyPI 的显式 IPv6 源；Paddle nightly 是否走 IPv6 取决于 `www.paddlepaddle.org.cn` 当前 DNS 是否提供 AAAA 记录。

Dockerfile 提供三个 build targets：

- `common`：通用 runner，安装 backend 基础依赖、`onnxruntime-gpu`、ONNX、OpenCV、Playwright、Rust/Cargo。
- `pytorch`：继承 `common`，使用 `pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu132` 安装 PyTorch。
- `paddle`：继承 `common`，使用 `python -m pip install --pre paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/nightly/cu129/` 安装 Paddle。

从仓库根目录构建并推送：

```powershell
docker buildx build --target common `
  --file infra/arc/runner-image/Dockerfile `
  --tag ghcr.io/youge325/vp-arc-runner:latest `
  --push .

docker buildx build --target pytorch `
  --file infra/arc/runner-image/Dockerfile `
  --tag ghcr.io/youge325/vp-arc-runner-pytorch:latest `
  --push .

docker buildx build --target paddle `
  --file infra/arc/runner-image/Dockerfile `
  --tag ghcr.io/youge325/vp-arc-runner-paddle:latest `
  --push .
```

如果只想先本地验证构建：

```powershell
docker buildx build --target common `
  --file infra/arc/runner-image/Dockerfile `
  --tag ghcr.io/youge325/vp-arc-runner:latest .

docker buildx build --target pytorch `
  --file infra/arc/runner-image/Dockerfile `
  --tag ghcr.io/youge325/vp-arc-runner-pytorch:latest .

docker buildx build --target paddle `
  --file infra/arc/runner-image/Dockerfile `
  --tag ghcr.io/youge325/vp-arc-runner-paddle:latest .
```

如果 GHCR 推送权限暂时不可用，可先把本地镜像加载到 Docker Desktop kind 集群并依赖 `imagePullPolicy: IfNotPresent` 验证：

```powershell
kind load docker-image ghcr.io/youge325/vp-arc-runner:latest --name desktop
kind load docker-image ghcr.io/youge325/vp-arc-runner-pytorch:latest --name desktop
kind load docker-image ghcr.io/youge325/vp-arc-runner-paddle:latest --name desktop
```

镜像默认提供这些路径给 ARC workflows 使用：

```text
VP_PYTHON_EXECUTABLE=/opt/vp/venv/bin/python
VP_FFMPEG_PATH=/usr/bin/ffmpeg
VP_FFPROBE_PATH=/usr/bin/ffprobe
VP_RIFE_MODEL_DIR=/opt/vp/models
```

## GitHub App

创建一个安装到 `youge325/vp` 仓库的 GitHub App。仓库级 runner 需要授予：

- Repository permissions：`Administration` read/write
- Repository permissions：`Actions` read-only
- 本地 smoke 验证不需要订阅 webhooks

不要把私钥提交到 git。创建 Kubernetes secret 前，只在当前 shell 中提供这些值：

```powershell
$env:ARC_GITHUB_APP_ID = "<app-id>"
$env:ARC_GITHUB_APP_INSTALLATION_ID = "<installation-id>"
$env:ARC_GITHUB_APP_PRIVATE_KEY_PATH = "C:\path\to\github-app.private-key.pem"
```

创建 namespaces 和 GitHub App secret：

```powershell
kubectl create namespace arc-systems --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace arc-runners --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic arc-github-app `
  --namespace arc-runners `
  --from-literal=github_app_id="$env:ARC_GITHUB_APP_ID" `
  --from-literal=github_app_installation_id="$env:ARC_GITHUB_APP_INSTALLATION_ID" `
  --from-file=github_app_private_key="$env:ARC_GITHUB_APP_PRIVATE_KEY_PATH" `
  --dry-run=client -o yaml | kubectl apply -f -
```

## 安装或升级

安装 controller：

```powershell
helm upgrade --install arc `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller `
  --namespace arc-systems `
  --create-namespace `
  --version 0.14.2
```

安装或升级 runner scale sets：

```powershell
helm upgrade --install vp-linux-arc `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set `
  --namespace arc-runners `
  --create-namespace `
  --version 0.14.2 `
  --values infra/arc/runner-scale-set-values.yaml

helm upgrade --install vp-linux-arc-pytorch `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set `
  --namespace arc-runners `
  --create-namespace `
  --version 0.14.2 `
  --values infra/arc/runner-scale-set-values-pytorch.yaml

helm upgrade --install vp-linux-arc-paddle `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set `
  --namespace arc-runners `
  --create-namespace `
  --version 0.14.2 `
  --values infra/arc/runner-scale-set-values-paddle.yaml
```

## 验证

本地渲染 manifests：

```powershell
helm template arc `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller `
  --namespace arc-systems `
  --version 0.14.2

helm template vp-linux-arc `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set `
  --namespace arc-runners `
  --version 0.14.2 `
  --values infra/arc/runner-scale-set-values.yaml

helm template vp-linux-arc-pytorch `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set `
  --namespace arc-runners `
  --version 0.14.2 `
  --values infra/arc/runner-scale-set-values-pytorch.yaml

helm template vp-linux-arc-paddle `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set `
  --namespace arc-runners `
  --version 0.14.2 `
  --values infra/arc/runner-scale-set-values-paddle.yaml
```

检查集群状态：

```powershell
helm list -A
kubectl get pods -n arc-systems
kubectl get pods -n arc-runners
kubectl get autoscalingrunnersets.actions.github.com -n arc-runners
```

静态检查新增 ARC workflows：

```powershell
rg -n "runs-on: vp-linux-arc" .github/workflows/*-arc.yml .github/workflows/arc-linux-smoke.yml
rg -n "vp-linux-arc-pytorch|vp-linux-arc-paddle" .github/workflows/test-backend-arc.yml
rg -n "minRunners: 1" infra/arc/runner-scale-set-values*.yaml
```

然后在 GitHub Actions 页面触发 `ARC Linux Smoke`，并观察新增的 `Test Frontend ARC`、`Test Backend ARC`、`End-to-End Tests ARC`、`Build ARC`、`Release ARC` 影子 workflows。

## 排障

查看 controller 和 listener 日志：

```powershell
kubectl logs -n arc-systems deploy/arc-gha-rs-controller -c manager
kubectl get pods -n arc-runners
kubectl describe autoscalingrunnerset -n arc-runners vp-linux-arc
kubectl describe autoscalingrunnerset -n arc-runners vp-linux-arc-pytorch
kubectl describe autoscalingrunnerset -n arc-runners vp-linux-arc-paddle
```

如果 runner pod 无法拉取自定义镜像，先确认 GHCR 镜像存在且集群有权限读取。公开镜像通常不需要额外 secret；私有镜像需要为 `arc-runners` namespace 配置 `imagePullSecrets`。

如果 listener 无法认证，请用正确的 App ID、installation ID 和私钥重新创建 `arc-github-app` secret。不要提交这些值。

## 卸载

```powershell
helm uninstall vp-linux-arc -n arc-runners
helm uninstall vp-linux-arc-pytorch -n arc-runners
helm uninstall vp-linux-arc-paddle -n arc-runners
helm uninstall arc -n arc-systems
```
