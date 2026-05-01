param(
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
}

function Get-EnvValue {
    param([string]$Name)

    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        return ""
    }
    return $value
}

function Find-FirstCommandPath {
    param([string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $command -and -not [string]::IsNullOrWhiteSpace($command.Source)) {
            return (Resolve-Path -LiteralPath $command.Source).Path
        }
    }
    return ""
}

function Add-GitHubEnv {
    param(
        [string]$Name,
        [string]$Value
    )

    [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_ENV)) {
        "$Name=$Value" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
    }
}

function Resolve-PythonSource {
    $candidates = @(
        @{
            Label = "default Python312"
            Root = "D:\Users\Lenovo\AppData\Local\Programs\Python\Python312"
            Exe = "D:\Users\Lenovo\AppData\Local\Programs\Python\Python312\python.exe"
        },
        @{
            Label = "VP_RELEASE_PYTHON_ROOT"
            Root = (Get-EnvValue "VP_RELEASE_PYTHON_ROOT")
            Exe = if (-not [string]::IsNullOrWhiteSpace((Get-EnvValue "VP_RELEASE_PYTHON_ROOT"))) {
                Join-Path (Get-EnvValue "VP_RELEASE_PYTHON_ROOT") "python.exe"
            } else {
                ""
            }
        },
        @{
            Label = "VP_RELEASE_PYTHON_EXE"
            Root = if (-not [string]::IsNullOrWhiteSpace((Get-EnvValue "VP_RELEASE_PYTHON_EXE"))) {
                Split-Path -Parent (Get-EnvValue "VP_RELEASE_PYTHON_EXE")
            } else {
                ""
            }
            Exe = (Get-EnvValue "VP_RELEASE_PYTHON_EXE")
        }
    )

    $checked = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate.Root) -or [string]::IsNullOrWhiteSpace($candidate.Exe)) {
            continue
        }
        if ((Test-Path -LiteralPath $candidate.Root -PathType Container) -and
            (Test-Path -LiteralPath $candidate.Exe -PathType Leaf)) {
            return @{
                Root = (Resolve-Path -LiteralPath $candidate.Root).Path
                Exe = (Resolve-Path -LiteralPath $candidate.Exe).Path
            }
        }
        $checked.Add("$($candidate.Label): root=$($candidate.Root), exe=$($candidate.Exe)")
    }

    throw "Unable to locate the required Python 3.12 runtime. Expected D:\Users\Lenovo\AppData\Local\Programs\Python\Python312\python.exe. Checked: $($checked -join '; ')"
}

function Resolve-ModelDir {
    $candidates = @(
        @{ Label = "VP_CI_MODEL_DIR"; Path = (Get-EnvValue "VP_CI_MODEL_DIR") },
        @{ Label = "VP_RELEASE_MODEL_DIR"; Path = (Get-EnvValue "VP_RELEASE_MODEL_DIR") },
        @{ Label = "VP_RIFE_MODEL_DIR"; Path = (Get-EnvValue "VP_RIFE_MODEL_DIR") },
        @{ Label = "default local repo"; Path = "D:\Lenovo\vp\backend\models" },
        @{ Label = "runner assets"; Path = "D:\actions-runner-vp\_assets\models" },
        @{ Label = "checkout backend models"; Path = (Join-Path $RepoRoot "backend\models") },
        @{ Label = "checkout backend models interpolation"; Path = (Join-Path $RepoRoot "backend\models"); ModelSubdir = "interpolation" }
    )

    $checked = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in $candidates) {
        $path = $candidate.Path
        if ([string]::IsNullOrWhiteSpace($path)) {
            continue
        }

        $defaultModel = Join-Path $path "rife_v4.25.onnx"
        if ($candidate.ContainsKey("ModelSubdir") -and -not [string]::IsNullOrWhiteSpace($candidate.ModelSubdir)) {
            $defaultModel = Join-Path (Join-Path $path $candidate.ModelSubdir) "rife_v4.25.onnx"
        }
        if ((Test-Path -LiteralPath $path -PathType Container) -and
            (Test-Path -LiteralPath $defaultModel -PathType Leaf) -and
            ((Get-Item -LiteralPath $defaultModel).Length -gt 0)) {
            return (Resolve-Path -LiteralPath $path).Path
        }

        $checked.Add("$($candidate.Label): $path")
    }

    throw "Unable to locate RIFE model weights. Expected non-empty rife_v4.25.onnx. Checked: $($checked -join '; ')"
}

function Find-FfmpegPairInDir {
    param([string]$Dir)

    if ([string]::IsNullOrWhiteSpace($Dir) -or -not (Test-Path -LiteralPath $Dir -PathType Container)) {
        return $null
    }

    $ffmpegCandidates = @(
        (Join-Path $Dir "ffmpeg.exe"),
        (Join-Path $Dir "bin\ffmpeg.exe")
    )
    $ffprobeCandidates = @(
        (Join-Path $Dir "ffprobe.exe"),
        (Join-Path $Dir "bin\ffprobe.exe")
    )

    $ffmpeg = $ffmpegCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    $ffprobe = $ffprobeCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if ($ffmpeg -and $ffprobe) {
        return @{
            Dir = (Resolve-Path -LiteralPath $Dir).Path
            Ffmpeg = (Resolve-Path -LiteralPath $ffmpeg).Path
            Ffprobe = (Resolve-Path -LiteralPath $ffprobe).Path
        }
    }
    return $null
}

function Resolve-FfmpegSource {
    $releaseDirPair = Find-FfmpegPairInDir -Dir (Get-EnvValue "VP_RELEASE_FFMPEG_DIR")
    if ($null -ne $releaseDirPair) {
        return $releaseDirPair
    }

    $ffmpegPath = Get-EnvValue "VP_FFMPEG_PATH"
    $ffprobePath = Get-EnvValue "VP_FFPROBE_PATH"
    if (-not [string]::IsNullOrWhiteSpace($ffmpegPath) -and
        -not [string]::IsNullOrWhiteSpace($ffprobePath) -and
        (Test-Path -LiteralPath $ffmpegPath -PathType Leaf) -and
        (Test-Path -LiteralPath $ffprobePath -PathType Leaf)) {
        $ffmpegResolved = (Resolve-Path -LiteralPath $ffmpegPath).Path
        $ffprobeResolved = (Resolve-Path -LiteralPath $ffprobePath).Path
        return @{
            Dir = (Split-Path -Parent $ffmpegResolved)
            Ffmpeg = $ffmpegResolved
            Ffprobe = $ffprobeResolved
        }
    }

    $defaultDirPair = Find-FfmpegPairInDir -Dir "D:\ffmpeg-2025-08-11-git-3542260376-full_build"
    if ($null -ne $defaultDirPair) {
        return $defaultDirPair
    }

    $pathFfmpeg = Find-FirstCommandPath -Names @("ffmpeg.exe", "ffmpeg")
    $pathFfprobe = Find-FirstCommandPath -Names @("ffprobe.exe", "ffprobe")
    if (-not [string]::IsNullOrWhiteSpace($pathFfmpeg) -and
        -not [string]::IsNullOrWhiteSpace($pathFfprobe)) {
        return @{
            Dir = (Split-Path -Parent $pathFfmpeg)
            Ffmpeg = $pathFfmpeg
            Ffprobe = $pathFfprobe
        }
    }

    throw "Unable to locate FFmpeg/FFprobe. Set VP_RELEASE_FFMPEG_DIR or VP_FFMPEG_PATH/VP_FFPROBE_PATH on the self-hosted runner."
}

$pythonSource = Resolve-PythonSource
$modelDir = Resolve-ModelDir
$ffmpegSource = Resolve-FfmpegSource

Add-GitHubEnv -Name "VP_RELEASE_PYTHON_ROOT" -Value $pythonSource.Root
Add-GitHubEnv -Name "VP_RELEASE_PYTHON_EXE" -Value $pythonSource.Exe
Add-GitHubEnv -Name "VP_RELEASE_MODEL_DIR" -Value $modelDir
Add-GitHubEnv -Name "VP_RIFE_MODEL_DIR" -Value $modelDir
Add-GitHubEnv -Name "VP_RELEASE_FFMPEG_DIR" -Value $ffmpegSource.Dir
Add-GitHubEnv -Name "VP_FFMPEG_PATH" -Value $ffmpegSource.Ffmpeg
Add-GitHubEnv -Name "VP_FFPROBE_PATH" -Value $ffmpegSource.Ffprobe

Write-Host "CI runtime environment resolved:"
Write-Host "  python root:   $($pythonSource.Root)"
Write-Host "  python exe:    $($pythonSource.Exe)"
Write-Host "  model dir:     $modelDir"
Write-Host "  default model: $(Join-Path $modelDir 'rife_v4.25.onnx')"
Write-Host "  ffmpeg dir:    $($ffmpegSource.Dir)"
Write-Host "  ffmpeg:        $($ffmpegSource.Ffmpeg)"
Write-Host "  ffprobe:       $($ffmpegSource.Ffprobe)"
