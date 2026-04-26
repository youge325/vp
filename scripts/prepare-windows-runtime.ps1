param(
    [string]$PythonRoot = $env:VP_RELEASE_PYTHON_ROOT,
    [string]$PythonExe = $env:VP_RELEASE_PYTHON_EXE,
    [string]$FfmpegDir = $env:VP_RELEASE_FFMPEG_DIR,
    [string]$ModelDir = $env:VP_RELEASE_MODEL_DIR,
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-RequiredPath {
    param(
        [string]$Label,
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "$Label was not provided."
    }
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label does not exist: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-FirstCommandPath {
    param([string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $command -and -not [string]::IsNullOrWhiteSpace($command.Source)) {
            return $command.Source
        }
    }
    return ""
}

function Find-FirstFile {
    param(
        [string]$Label,
        [string[]]$Candidates
    )

    foreach ($candidate in $Candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "Unable to locate $Label. Checked: $($Candidates -join ', ')"
}

function Resolve-PythonSource {
    param(
        [string]$Root,
        [string]$Exe
    )

    if (-not [string]::IsNullOrWhiteSpace($Exe)) {
        $resolvedExe = Resolve-RequiredPath -Label "VP_RELEASE_PYTHON_EXE" -Path $Exe
        if (-not [string]::IsNullOrWhiteSpace($Root)) {
            $resolvedRoot = Resolve-RequiredPath -Label "VP_RELEASE_PYTHON_ROOT" -Path $Root
        } else {
            $exeDir = Split-Path -Parent $resolvedExe
            $exeDirName = Split-Path -Leaf $exeDir
            if ($exeDirName -ieq "Scripts" -or $exeDirName -ieq "bin") {
                $resolvedRoot = Split-Path -Parent $exeDir
            } else {
                $resolvedRoot = $exeDir
            }
        }
        return @{ Root = $resolvedRoot; Exe = $resolvedExe }
    }

    if (-not [string]::IsNullOrWhiteSpace($Root)) {
        $resolvedRoot = Resolve-RequiredPath -Label "VP_RELEASE_PYTHON_ROOT" -Path $Root
        $resolvedExe = Find-FirstFile -Label "python.exe" -Candidates @(
            (Join-Path $resolvedRoot "python.exe"),
            (Join-Path $resolvedRoot "Scripts\python.exe"),
            (Join-Path $resolvedRoot "bin\python.exe")
        )
        return @{ Root = $resolvedRoot; Exe = $resolvedExe }
    }

    $pathPython = Get-FirstCommandPath -Names @("python.exe", "python")
    if ([string]::IsNullOrWhiteSpace($pathPython)) {
        throw "Unable to locate Python. Set VP_RELEASE_PYTHON_ROOT or VP_RELEASE_PYTHON_EXE on the self-hosted runner."
    }

    return Resolve-PythonSource -Exe $pathPython
}

function Resolve-FfmpegSource {
    param([string]$Dir)

    if (-not [string]::IsNullOrWhiteSpace($Dir)) {
        $resolvedDir = Resolve-RequiredPath -Label "VP_RELEASE_FFMPEG_DIR" -Path $Dir
        $ffmpeg = Find-FirstFile -Label "ffmpeg.exe" -Candidates @(
            (Join-Path $resolvedDir "ffmpeg.exe"),
            (Join-Path $resolvedDir "bin\ffmpeg.exe")
        )
        $ffprobe = Find-FirstFile -Label "ffprobe.exe" -Candidates @(
            (Join-Path $resolvedDir "ffprobe.exe"),
            (Join-Path $resolvedDir "bin\ffprobe.exe")
        )
        return @{ Ffmpeg = $ffmpeg; Ffprobe = $ffprobe }
    }

    $ffmpegPath = Get-FirstCommandPath -Names @("ffmpeg.exe", "ffmpeg")
    $ffprobePath = Get-FirstCommandPath -Names @("ffprobe.exe", "ffprobe")
    if ([string]::IsNullOrWhiteSpace($ffmpegPath) -or [string]::IsNullOrWhiteSpace($ffprobePath)) {
        throw "Unable to locate FFmpeg/FFprobe. Set VP_RELEASE_FFMPEG_DIR on the self-hosted runner."
    }

    return @{
        Ffmpeg = (Resolve-Path -LiteralPath $ffmpegPath).Path
        Ffprobe = (Resolve-Path -LiteralPath $ffprobePath).Path
    }
}

function Resolve-ModelSource {
    param(
        [string]$Dir,
        [string]$RepoRoot
    )

    if (-not [string]::IsNullOrWhiteSpace($Dir)) {
        $resolvedDir = Resolve-RequiredPath -Label "VP_RELEASE_MODEL_DIR" -Path $Dir
    } else {
        $resolvedDir = Join-Path $RepoRoot "backend\models"
        if (-not (Test-Path -LiteralPath $resolvedDir -PathType Container)) {
            throw "Unable to locate model directory. Set VP_RELEASE_MODEL_DIR on the self-hosted runner."
        }
        $resolvedDir = (Resolve-Path -LiteralPath $resolvedDir).Path
    }

    $defaultModel = Join-Path $resolvedDir "flownet_v4.25.pkl"
    if (-not (Test-Path -LiteralPath $defaultModel -PathType Leaf)) {
        throw "Default model is missing: $defaultModel. Set VP_RELEASE_MODEL_DIR to a directory containing flownet_v4.25.pkl."
    }
    if ((Get-Item -LiteralPath $defaultModel).Length -le 0) {
        throw "Default model is empty: $defaultModel"
    }
    return $resolvedDir
}

function Assert-OutputRootIsSafe {
    param(
        [string]$RepoRoot,
        [string]$Target
    )

    $resourcesRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "frontend\src-tauri\resources"))
    $targetFull = [System.IO.Path]::GetFullPath($Target)
    if (-not $targetFull.StartsWith($resourcesRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean runtime output outside frontend/src-tauri/resources: $targetFull"
    }
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot "frontend\src-tauri\resources\runtime"
}
$outputRootFull = [System.IO.Path]::GetFullPath($OutputRoot)
Assert-OutputRootIsSafe -RepoRoot $repoRoot -Target $outputRootFull

$pythonSource = Resolve-PythonSource -Root $PythonRoot -Exe $PythonExe
$ffmpegSource = Resolve-FfmpegSource -Dir $FfmpegDir
$modelSourceDir = Resolve-ModelSource -Dir $ModelDir -RepoRoot $repoRoot

Write-Host "Preparing Windows runtime:"
Write-Host "  python root: $($pythonSource.Root)"
Write-Host "  python exe:  $($pythonSource.Exe)"
Write-Host "  ffmpeg:      $($ffmpegSource.Ffmpeg)"
Write-Host "  ffprobe:     $($ffmpegSource.Ffprobe)"
Write-Host "  model dir:   $modelSourceDir"
Write-Host "  output root: $outputRootFull"

if (Test-Path -LiteralPath $outputRootFull) {
    Remove-Item -LiteralPath $outputRootFull -Recurse -Force
}

$pythonOut = Join-Path $outputRootFull "python"
$ffmpegOut = Join-Path $outputRootFull "ffmpeg\bin"
$modelsOut = Join-Path $outputRootFull "models"
New-Item -ItemType Directory -Force -Path $pythonOut, $ffmpegOut, $modelsOut | Out-Null

Get-ChildItem -LiteralPath $pythonSource.Root -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $pythonOut -Recurse -Force
}
$destPythonExe = Join-Path $pythonOut "python.exe"
if (-not (Test-Path -LiteralPath $destPythonExe -PathType Leaf)) {
    Copy-Item -LiteralPath $pythonSource.Exe -Destination $destPythonExe -Force
}

Copy-Item -LiteralPath $ffmpegSource.Ffmpeg -Destination (Join-Path $ffmpegOut "ffmpeg.exe") -Force
Copy-Item -LiteralPath $ffmpegSource.Ffprobe -Destination (Join-Path $ffmpegOut "ffprobe.exe") -Force

$models = Get-ChildItem -LiteralPath $modelSourceDir -Filter "flownet_*.pkl" -File
if ($models.Count -eq 0) {
    throw "No RIFE model files found in $modelSourceDir"
}
foreach ($model in $models) {
    Copy-Item -LiteralPath $model.FullName -Destination (Join-Path $modelsOut $model.Name) -Force
}

$destFfmpeg = Join-Path $ffmpegOut "ffmpeg.exe"
$destFfprobe = Join-Path $ffmpegOut "ffprobe.exe"
$destDefaultModel = Join-Path $modelsOut "flownet_v4.25.pkl"
foreach ($required in @($destPythonExe, $destFfmpeg, $destFfprobe, $destDefaultModel)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Runtime validation failed; missing $required"
    }
}

$env:VP_RUNTIME_ROOT = $outputRootFull
$env:VP_PYTHON_EXECUTABLE = $destPythonExe
$env:VP_FFMPEG_PATH = $destFfmpeg
$env:VP_FFPROBE_PATH = $destFfprobe
$env:VP_RIFE_MODEL_DIR = $modelsOut
$env:PYTHONNOUSERSITE = "1"
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

& $destPythonExe -s -c "import importlib; [importlib.import_module(name) for name in ['pydantic','pydantic_settings','numpy','PIL','torch']]; print('python runtime imports ok', flush=True)"
if ($LASTEXITCODE -ne 0) {
    throw "Bundled Python import smoke failed."
}

Push-Location (Join-Path $repoRoot "backend")
try {
    & $destPythonExe -s -m app check
    if ($LASTEXITCODE -ne 0) {
        throw "Bundled backend check failed."
    }
} finally {
    Pop-Location
}

Write-Host "Windows runtime prepared successfully."
