# Docker Kubernetes 上的 Actions Runner Controller

本目录保存本机 Docker Kubernetes 集群使用的 ARC runner scale set 配置。它会为当前仓库创建一个名为 `vp-linux-arc` 的 Linux 验证 runner：

```text
https://github.com/youge325/vp
```

现有 Windows workflows 继续使用 `[self-hosted, windows]`，本配置不会迁移或修改它们。

## 版本与命名

- ARC chart 版本：`0.14.2`
- Controller namespace：`arc-systems`
- Runner namespace：`arc-runners`
- Controller release：`arc`
- Runner scale set release：`vp-linux-arc`
- Runner scale set 名称：`vp-linux-arc`
- Labels：`linux`、`arc`、`docker-k8s`

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

安装 runner scale set：

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

然后在 GitHub Actions 页面手动触发 `ARC Linux Smoke` workflow。job 分配后应出现一个 runner pod，job 结束后该 pod 会自动回收。

## 排障

查看 controller 和 listener 日志：

```powershell
kubectl logs -n arc-systems deploy/arc-gha-rs-controller -c manager
kubectl get pods -n arc-runners
kubectl describe autoscalingrunnerset -n arc-runners vp-linux-arc
```

如果 listener 无法认证，请用正确的 App ID、installation ID 和私钥重新创建 `arc-github-app` secret。不要提交这些值。

## 卸载

```powershell
helm uninstall vp-linux-arc -n arc-runners
helm uninstall arc -n arc-systems
```
