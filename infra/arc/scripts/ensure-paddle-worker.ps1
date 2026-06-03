[CmdletBinding()]
param(
  [string]$ClusterName = "desktop",
  [string]$ControlPlaneName = "desktop-control-plane",
  [string]$WorkerName = "desktop-worker2",
  [string]$WorkerImage = "kindest/node:v1.35.1",
  [string]$RunnerImage = "ghcr.io/youge325/vp-arc-runner-paddle:latest",
  [string]$NodeLabelValue = "paddle",
  [string]$Namespace = "arc-runners",
  [string]$ReleaseName = "vp-linux-arc-paddle",
  [string]$ValuesFile = "runner-scale-set-values-paddle.yaml",
  [string]$ChartVersion = "0.14.2"
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
  $PSNativeCommandUseErrorActionPreference = $true
}
Set-StrictMode -Version Latest

function Require-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command was not found: $Name"
  }
}

function Test-DockerContainer {
  param([string]$Name)
  $containers = docker ps -a --format "{{.Names}}"
  return $containers -contains $Name
}

function Test-KubeNode {
  param([string]$Name)
  $node = kubectl get node $Name --ignore-not-found -o name
  return -not [string]::IsNullOrWhiteSpace($node)
}

function Test-ImageInNode {
  param(
    [string]$NodeName,
    [string]$Image
  )
  $images = docker exec $NodeName ctr --namespace=k8s.io images ls -q
  return [bool]($images | Where-Object { $_ -eq $Image -or $_ -like "$Image@*" })
}

function Wait-Containerd {
  param([string]$Name)

  for ($attempt = 0; $attempt -lt 90; $attempt += 1) {
    try {
      docker exec $Name sh -lc "test -S /run/containerd/containerd.sock" *> $null
      return
    } catch {
      Start-Sleep -Seconds 2
    }
  }

  throw "containerd socket did not become ready in $Name"
}

Require-Command docker
Require-Command kubectl
Require-Command helm

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$arcDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$valuesPath = Join-Path $arcDir $ValuesFile
$kindNoProxy = "fc00:f853:ccd:e793::/64,172.18.0.0/16,kind-registry-mirror,registry-mirror,10.96.0.0/16,10.244.0.0/16,$ControlPlaneName,desktop-worker,desktop-worker2,desktop-worker3,.svc,.svc.cluster,.svc.cluster.local"

docker image inspect $WorkerImage *> $null
docker image inspect $RunnerImage *> $null

if (-not (Test-DockerContainer $ControlPlaneName)) {
  throw "Control plane container was not found: $ControlPlaneName"
}

$workerContainerExists = Test-DockerContainer $WorkerName
$workerNodeExists = Test-KubeNode $WorkerName

if ($workerContainerExists -and -not $workerNodeExists) {
  Write-Host "Removing unjoined worker container $WorkerName before recreating it..."
  docker rm -f $WorkerName | Out-Host
  $workerContainerExists = $false
}

if (-not $workerContainerExists) {
  Write-Host "Creating kind worker container $WorkerName..."
  docker run -d `
    --tty `
    --name $WorkerName `
    --hostname $WorkerName `
    --label "io.x-k8s.kind.cluster=$ClusterName" `
    --label "io.x-k8s.kind.role=worker" `
    --label "io.kubernetes.pod.namespace=kube-system" `
    --env "KIND_EXPERIMENTAL_CONTAINERD_SNAPSHOTTER" `
    --env "NO_PROXY=$kindNoProxy" `
    --env "no_proxy=$kindNoProxy" `
    --env "HTTP_PROXY=" `
    --env "HTTPS_PROXY=" `
    --env "http_proxy=" `
    --env "https_proxy=" `
    --privileged `
    --security-opt seccomp=unconfined `
    --security-opt apparmor=unconfined `
    --security-opt label=disable `
    --cgroupns private `
    --tmpfs /run `
    --tmpfs /tmp `
    --network kind `
    --restart on-failure:1 `
    --volume /lib/modules:/lib/modules:ro `
    --volume /etc/kind/hosts.toml:/etc/containerd/certs.d/_default/hosts.toml:ro `
    --volume /var `
    --stop-signal SIGRTMIN+3 `
    --stop-timeout 1 `
    $WorkerImage | Out-Host
} else {
  Write-Host "Worker container already exists: $WorkerName"
}

Wait-Containerd -Name $WorkerName

if (-not $workerNodeExists) {
  Write-Host "Joining $WorkerName to kind cluster $ClusterName..."
  $joinCommand = docker exec $ControlPlaneName kubeadm token create --print-join-command
  if ([string]::IsNullOrWhiteSpace($joinCommand)) {
    throw "Failed to create kubeadm join command from $ControlPlaneName"
  }

  $clusterNoProxy = "localhost,127.0.0.1,::1,$kindNoProxy"
  $nodeJoinCommand = "env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy NO_PROXY='$clusterNoProxy' no_proxy='$clusterNoProxy' $joinCommand --node-name $WorkerName --cri-socket unix:///run/containerd/containerd.sock"
  docker exec $WorkerName sh -lc $nodeJoinCommand
} else {
  Write-Host "Kubernetes node already exists: $WorkerName"
}

kubectl wait node/$WorkerName --for=condition=Ready --timeout=180s
kubectl label node $WorkerName "vp.arc/runner-image=$NodeLabelValue" --overwrite

if (-not (Test-ImageInNode -NodeName $WorkerName -Image $RunnerImage)) {
  Write-Host "Importing $RunnerImage into $WorkerName only..."
  docker save $RunnerImage | docker exec --privileged -i $WorkerName ctr --namespace=k8s.io images import --all-platforms --digests --snapshotter=overlayfs -
} else {
  Write-Host "Runner image already exists in ${WorkerName}: $RunnerImage"
}

helm upgrade --install $ReleaseName `
  oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set `
  --namespace $Namespace `
  --create-namespace `
  --version $ChartVersion `
  --values $valuesPath

Write-Host ""
Write-Host "Node labels:"
kubectl get nodes --show-labels

Write-Host ""
Write-Host "$NodeLabelValue runner image on ${WorkerName}:"
docker exec $WorkerName ctr --namespace=k8s.io images ls | Select-String -SimpleMatch $RunnerImage

Write-Host ""
Write-Host "ARC runner pods:"
kubectl get pods -n $Namespace -o wide
