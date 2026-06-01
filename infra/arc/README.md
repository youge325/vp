# Docker Kubernetes 上的 Actions Runner Controller

本目录保存 Docker Kubernetes 集群使用的 ARC runner scale set 配置。它为当前仓库创建 `vp-linux-arc` Linux runner，用来运行新增的 ARC 影子 workflows：

```text
https://github.com/youge325/vp
```

原有 Windows workflows 保持不变，继续负责现有 Windows CI 与 Windows portable release。新增的 `*-arc.yml` workflows 是并行验证链路，不替代原有 workflows；其中 `build-arc.yml` 和 `release-arc.yml` 只验证 Linux ARC release build，不上传 GitHub Release。

## 版本与命名

- ARC chart 版本：`0.14.2`
- Controller namespace：`arc-systems`
- Runner namespace：`arc-runners`
- Controller release：`arc`
- Runner scale set release：`vp-linux-arc`
- Runner scale set 名称：`vp-linux-arc`
- Runner image：`ghcr.io/youge325/vp-arc-runner:latest`
- Labels：`linux`、`arc`、`docker-k8s`
- Warm runner：`minRunners: 1`

## 自定义 Runner 镜像

自定义镜像定义在 `infra/arc/runner-image/Dockerfile`。镜像基于 `ghcr.io/actions/actions-runner:latest`，预装 Node、Rust/Cargo、Python venv、FFmpeg、Playwright Chromium 依赖、Tauri Linux 构建依赖，并把模型复制到 `/opt/vp/models`。

从仓库根目录构建并推送：

```powershell
docker buildx build `
  --file infra/arc/runner-image/Dockerfile `
  --tag ghcr.io/youge325/vp-arc-runner:latest `
  --push `
  .
```

如果只想先本地验证构建：

```powershell
docker buildx build `
  --file infra/arc/runner-image/Dockerfile `
  --tag ghcr.io/youge325/vp-arc-runner:latest `
  .
```

如果 GHCR 推送权限暂时不可用，可先把本地镜像加载到 Docker Desktop kind 集群并依赖 `imagePullPolicy: IfNotPresent` 验证：

```powershell
kind load docker-image ghcr.io/youge325/vp-arc-runner:latest --name desktop
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

安装或升级 runner scale set：

```powershell
helm upgrade --install vp-linux-arc `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set `
  --namespace arc-runners `
  --create-namespace `
  --version 0.14.2 `
  --values infra/arc/runner-scale-set-values.yaml
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
rg -n "minRunners: 1" infra/arc/runner-scale-set-values.yaml
```

然后在 GitHub Actions 页面触发 `ARC Linux Smoke`，并观察新增的 `Test Frontend ARC`、`Test Backend ARC`、`End-to-End Tests ARC`、`Build ARC`、`Release ARC` 影子 workflows。

## 排障

查看 controller 和 listener 日志：

```powershell
kubectl logs -n arc-systems deploy/arc-gha-rs-controller -c manager
kubectl get pods -n arc-runners
kubectl describe autoscalingrunnerset -n arc-runners vp-linux-arc
```

如果 runner pod 无法拉取自定义镜像，先确认 GHCR 镜像存在且集群有权限读取。公开镜像通常不需要额外 secret；私有镜像需要为 `arc-runners` namespace 配置 `imagePullSecrets`。

如果 listener 无法认证，请用正确的 App ID、installation ID 和私钥重新创建 `arc-github-app` secret。不要提交这些值。

## 卸载

```powershell
helm uninstall vp-linux-arc -n arc-runners
helm uninstall arc -n arc-systems
```
