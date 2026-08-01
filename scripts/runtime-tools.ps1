Set-StrictMode -Version Latest

$script:VpRepositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$script:VpApplicationDefaults = $null

function Get-VpFirstCommandPath {
    param([string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $command -and -not [string]::IsNullOrWhiteSpace($command.Source)) {
            return (Resolve-Path -LiteralPath $command.Source).Path
        }
    }
    return ""
}

function Get-VpApplicationDefaults {
    if ($null -eq $script:VpApplicationDefaults) {
        $contractPath = Join-Path $script:VpRepositoryRoot "contracts\application-defaults.json"
        if (-not (Test-Path -LiteralPath $contractPath -PathType Leaf)) {
            throw "Application defaults contract is missing: $contractPath"
        }
        $script:VpApplicationDefaults = Get-Content -LiteralPath $contractPath -Raw -Encoding utf8 | ConvertFrom-Json
    }
    return $script:VpApplicationDefaults
}

function Get-VpDefaultRifeModelPaths {
    param([string]$ModelDir)

    if ([string]::IsNullOrWhiteSpace($ModelDir)) {
        throw "RIFE model directory was not provided."
    }
    $version = [string](Get-VpApplicationDefaults).interpolation.model
    if ([string]::IsNullOrWhiteSpace($version)) {
        throw "Application defaults contain an empty RIFE model version."
    }
    $pytorchFilename = "flownet_v${version}.pkl"
    $onnxFilename = "rife_v${version}.onnx"
    return [pscustomobject]@{
        Version = $version
        PytorchFilename = $pytorchFilename
        OnnxFilename = $onnxFilename
        PytorchPath = Join-Path $ModelDir $pytorchFilename
        OnnxPath = Join-Path (Join-Path (Join-Path $ModelDir "interpolation") "rife") $onnxFilename
    }
}

function Test-VpNonEmptyFile {
    param([string]$Path)

    return (Test-Path -LiteralPath $Path -PathType Leaf) -and ((Get-Item -LiteralPath $Path).Length -gt 0)
}

function Test-VpDefaultRifeModels {
    param([string]$ModelDir)

    if ([string]::IsNullOrWhiteSpace($ModelDir) -or -not (Test-Path -LiteralPath $ModelDir -PathType Container)) {
        return $false
    }
    $paths = Get-VpDefaultRifeModelPaths -ModelDir $ModelDir
    return (Test-VpNonEmptyFile -Path $paths.PytorchPath) -and (Test-VpNonEmptyFile -Path $paths.OnnxPath)
}

function Assert-VpDefaultRifeModels {
    param([string]$ModelDir)

    $paths = Get-VpDefaultRifeModelPaths -ModelDir $ModelDir
    if (-not (Test-VpNonEmptyFile -Path $paths.PytorchPath)) {
        throw "Default PyTorch RIFE model is missing or empty: $($paths.PytorchPath)"
    }
    if (-not (Test-VpNonEmptyFile -Path $paths.OnnxPath)) {
        throw "Default ONNX RIFE model is missing or empty: $($paths.OnnxPath)"
    }
    return $paths
}
