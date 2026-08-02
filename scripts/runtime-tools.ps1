Set-StrictMode -Version Latest

$script:VpRepositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$script:VpApplicationDefaults = $null
$script:VpModelAssets = $null

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

function Get-VpModelAssets {
    if ($null -eq $script:VpModelAssets) {
        $contractPath = Join-Path $script:VpRepositoryRoot "contracts\model-assets.json"
        if (-not (Test-Path -LiteralPath $contractPath -PathType Leaf)) {
            throw "Model assets contract is missing: $contractPath"
        }
        $script:VpModelAssets = Get-Content -LiteralPath $contractPath -Raw -Encoding utf8 | ConvertFrom-Json
    }
    return $script:VpModelAssets
}

function Get-VpRealRawVsrBundlePaths {
    param(
        [string]$ModelDir,
        [string]$RepositoryRoot = $script:VpRepositoryRoot
    )

    if ([string]::IsNullOrWhiteSpace($ModelDir)) {
        throw "Model directory was not provided."
    }
    if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
        throw "Repository root was not provided."
    }

    $bundle = (Get-VpModelAssets).realRawVsrBasicVsr
    $models = foreach ($variant in $bundle.variants) {
        $relativePath = ([string]$variant.relativePath).Replace('/', '\')
        $modelsPrefix = "models\"
        if (-not $relativePath.StartsWith($modelsPrefix, [System.StringComparison]::Ordinal)) {
            throw "Real-RawVSR model path must be rooted under models/: $relativePath"
        }
        [pscustomobject]@{
            ScaleFactor = [int]$variant.scaleFactor
            RelativePath = $relativePath.Substring($modelsPrefix.Length)
            Path = Join-Path $ModelDir $relativePath.Substring($modelsPrefix.Length)
            Bytes = [int64]$variant.inferenceBytes
            Sha256 = [string]$variant.inferenceSha256
        }
    }
    return [pscustomobject]@{
        Models = @($models)
        LicenseRelativePath = ([string]$bundle.license.licenseRelativePath).Replace('/', '\')
        NoticeRelativePath = ([string]$bundle.license.noticeRelativePath).Replace('/', '\')
        LicensePath = Join-Path $RepositoryRoot ([string]$bundle.license.licenseRelativePath)
        NoticePath = Join-Path $RepositoryRoot ([string]$bundle.license.noticeRelativePath)
    }
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

function Assert-VpFileIntegrity {
    param(
        [string]$Path,
        [int64]$ExpectedBytes,
        [string]$ExpectedSha256,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label is missing: $Path"
    }
    $file = Get-Item -LiteralPath $Path
    if ($file.Length -ne $ExpectedBytes) {
        throw "$Label size mismatch: expected $ExpectedBytes, got $($file.Length) ($Path)"
    }
    $actualSha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -cne $ExpectedSha256.ToLowerInvariant()) {
        throw "$Label SHA-256 mismatch: expected $ExpectedSha256, got $actualSha256 ($Path)"
    }
    return $file
}

function Assert-VpRealRawVsrBundle {
    param(
        [string]$ModelDir,
        [string]$RepositoryRoot = $script:VpRepositoryRoot
    )

    $paths = Get-VpRealRawVsrBundlePaths -ModelDir $ModelDir -RepositoryRoot $RepositoryRoot
    foreach ($model in $paths.Models) {
        Assert-VpFileIntegrity -Path $model.Path -ExpectedBytes $model.Bytes -ExpectedSha256 $model.Sha256 -Label "Real-RawVSR BasicVSR x$($model.ScaleFactor) model" | Out-Null
    }
    foreach ($licenseFile in @($paths.LicensePath, $paths.NoticePath)) {
        if (-not (Test-VpNonEmptyFile -Path $licenseFile)) {
            throw "Required Real-RawVSR license file is missing or empty: $licenseFile"
        }
    }
    return $paths
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
