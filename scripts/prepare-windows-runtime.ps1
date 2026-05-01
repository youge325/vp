param(
    [string]$PythonRoot = $env:VP_RELEASE_PYTHON_ROOT,
    [string]$PythonExe = $env:VP_RELEASE_PYTHON_EXE,
    [string]$FfmpegDir = $env:VP_RELEASE_FFMPEG_DIR,
    [string]$ModelDir = $env:VP_RELEASE_MODEL_DIR,
    [string]$OutputRoot = "",
    [string]$PythonCopyMode = $env:VP_RELEASE_PYTHON_COPY_MODE,
    [string]$ExtraPythonPackages = $env:VP_RELEASE_PYTHON_PACKAGES,
    [switch]$SkipPython
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)

    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Format-ByteSize {
    param([double]$Bytes)

    if ($Bytes -ge 1GB) {
        return "{0:N2} GB" -f ($Bytes / 1GB)
    }
    if ($Bytes -ge 1MB) {
        return "{0:N1} MB" -f ($Bytes / 1MB)
    }
    if ($Bytes -ge 1KB) {
        return "{0:N1} KB" -f ($Bytes / 1KB)
    }
    return "$Bytes bytes"
}

function Get-TextTail {
    param(
        [string]$Text,
        [int]$MaxChars = 4000
    )

    if ([string]::IsNullOrEmpty($Text) -or $Text.Length -le $MaxChars) {
        return $Text
    }
    return "...$($Text.Substring($Text.Length - $MaxChars))"
}

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

    $defaultModel = Join-Path $resolvedDir "rife_v4.25.onnx"
    $interpModel = Join-Path $resolvedDir "interpolation\rife_v4.25.onnx"
    $foundModel = ""
    if ((Test-Path -LiteralPath $defaultModel -PathType Leaf) -and (Get-Item -LiteralPath $defaultModel).Length -gt 0) {
        $foundModel = $defaultModel
    } elseif ((Test-Path -LiteralPath $interpModel -PathType Leaf) -and (Get-Item -LiteralPath $interpModel).Length -gt 0) {
        $foundModel = $interpModel
    } else {
        throw "Default model is missing. Expected rife_v4.25.onnx in `$resolvedDir` or `$resolvedDir\interpolation`. Set VP_RELEASE_MODEL_DIR to a directory containing rife_v4.25.onnx."
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

function Copy-FileFast {
    param(
        [string]$Source,
        [string]$Destination
    )

    $destinationDir = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $destinationDir -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    }
    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        Remove-Item -LiteralPath $Destination -Force
    }

    try {
        New-Item -ItemType HardLink -Path $Destination -Target $Source -ErrorAction Stop | Out-Null
        return "linked"
    } catch {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        return "copied"
    }
}

function Copy-DirectoryTree {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$SkipDirectoryNames = @(),
        [string]$Label,
        [int]$ProgressEvery = 1000
    )

    $sourceFull = (Resolve-Path -LiteralPath $Source).Path
    $stats = [ordered]@{
        Files = 0
        Bytes = [int64]0
        Linked = 0
        Copied = 0
    }
    $stack = New-Object System.Collections.Stack
    $stack.Push(@{ Source = $sourceFull; Destination = $Destination })

    while ($stack.Count -gt 0) {
        $current = $stack.Pop()
        New-Item -ItemType Directory -Force -Path $current.Destination | Out-Null

        foreach ($item in Get-ChildItem -LiteralPath $current.Source -Force) {
            $target = Join-Path $current.Destination $item.Name
            if ($item.PSIsContainer) {
                if ($SkipDirectoryNames -contains $item.Name) {
                    continue
                }
                $stack.Push(@{ Source = $item.FullName; Destination = $target })
                continue
            }

            $copyResult = Copy-FileFast -Source $item.FullName -Destination $target
            $stats.Files += 1
            $stats.Bytes += [int64]$item.Length
            if ($copyResult -eq "linked") {
                $stats.Linked += 1
            } else {
                $stats.Copied += 1
            }

            if ($ProgressEvery -gt 0 -and ($stats.Files % $ProgressEvery) -eq 0) {
                Write-Step "${Label}: $($stats.Files) files, $(Format-ByteSize $stats.Bytes)"
            }
        }
    }

    Write-Step "${Label} complete: $($stats.Files) files, $(Format-ByteSize $stats.Bytes), hardlinks=$($stats.Linked), copies=$($stats.Copied)"
    return [pscustomobject]$stats
}

function Copy-RootFiles {
    param(
        [string]$PythonRoot,
        [string]$PythonExe,
        [string]$Destination
    )

    Write-Step "Copying Python root files"
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $stats = [ordered]@{
        Files = 0
        Bytes = [int64]0
        Linked = 0
        Copied = 0
    }

    foreach ($file in Get-ChildItem -LiteralPath $PythonRoot -Force -File) {
        $target = Join-Path $Destination $file.Name
        $copyResult = Copy-FileFast -Source $file.FullName -Destination $target
        $stats.Files += 1
        $stats.Bytes += [int64]$file.Length
        if ($copyResult -eq "linked") {
            $stats.Linked += 1
        } else {
            $stats.Copied += 1
        }
    }

    $destPythonExe = Join-Path $Destination "python.exe"
    if (-not (Test-Path -LiteralPath $destPythonExe -PathType Leaf)) {
        $copyResult = Copy-FileFast -Source $PythonExe -Destination $destPythonExe
        $stats.Files += 1
        $stats.Bytes += [int64](Get-Item -LiteralPath $PythonExe).Length
        if ($copyResult -eq "linked") {
            $stats.Linked += 1
        } else {
            $stats.Copied += 1
        }
    }

    $pythonw = Join-Path (Split-Path -Parent $PythonExe) "pythonw.exe"
    if ((Test-Path -LiteralPath $pythonw -PathType Leaf) -and -not (Test-Path -LiteralPath (Join-Path $Destination "pythonw.exe") -PathType Leaf)) {
        $copyResult = Copy-FileFast -Source $pythonw -Destination (Join-Path $Destination "pythonw.exe")
        $stats.Files += 1
        $stats.Bytes += [int64](Get-Item -LiteralPath $pythonw).Length
        if ($copyResult -eq "linked") {
            $stats.Linked += 1
        } else {
            $stats.Copied += 1
        }
    }

    Write-Step "Python root files complete: $($stats.Files) files, $(Format-ByteSize $stats.Bytes), hardlinks=$($stats.Linked), copies=$($stats.Copied)"
}

function Get-PythonPackagePatterns {
    param([string]$ExtraPatterns)

    $patterns = @(
        "annotated_types*",
        "anyio*",
        "astor*",
        "certifi*",
        "charset_normalizer*",
        "coloredlogs*",
        "decorator*",
        "dotenv",
        "filelock*",
        "flatbuffers*",
        "fsspec*",
        "gast*",
        "google",
        "h11*",
        "httpcore*",
        "httpx*",
        "humanfriendly*",
        "idna*",
        "isympy.py",
        "jinja2*",
        "markupsafe*",
        "mpmath*",
        "networkx*",
        "numpy*",
        "numpy.libs",
        "opt_einsum*",
        "onnxruntime*",
        "packaging*",
        "PIL",
        "pillow*",
        "protobuf*",
        "pydantic*",
        "pydantic_core*",
        "pydantic_settings*",
        "python_dotenv*",
        "requests*",
        "safetensors*",
        "setuptools*",
        "setuptools.pth",
        "six*",
        "sniffio*",
        "sympy*",
        "typing_extensions*",
        "typing_extensions.py",
        "typing_inspect*",
        "typing_inspect.py",
        "typing_inspection*",
        "urllib3*",
        "wheel*",
        "yaml",
        "_yaml",
        "PyYAML*"
    )

    if (-not [string]::IsNullOrWhiteSpace($ExtraPatterns)) {
        $extra = $ExtraPatterns -split "[,;]" | ForEach-Object { $_.Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        $patterns += $extra
    }

    return $patterns | Select-Object -Unique
}

function Copy-SitePackagesSlim {
    param(
        [string]$PythonRoot,
        [string]$Destination,
        [string]$ExtraPatterns
    )

    $sitePackages = Join-Path $PythonRoot "Lib\site-packages"
    if (-not (Test-Path -LiteralPath $sitePackages -PathType Container)) {
        Write-Step "No source site-packages found at $sitePackages"
        return
    }

    $destinationSitePackages = Join-Path $Destination "Lib\site-packages"
    New-Item -ItemType Directory -Force -Path $destinationSitePackages | Out-Null

    $wildcards = Get-PythonPackagePatterns -ExtraPatterns $ExtraPatterns | ForEach-Object {
        [System.Management.Automation.WildcardPattern]::new($_, [System.Management.Automation.WildcardOptions]::IgnoreCase)
    }

    $entries = Get-ChildItem -LiteralPath $sitePackages -Force | Where-Object {
        $entryName = $_.Name
        $matched = $false
        foreach ($wildcard in $wildcards) {
            if ($wildcard.IsMatch($entryName)) {
                $matched = $true
                break
            }
        }
        $matched
    } | Sort-Object Name -Unique

    Write-Step "Copying slim site-packages: $($entries.Count) selected entries"
    foreach ($entry in $entries) {
        $target = Join-Path $destinationSitePackages $entry.Name
        if ($entry.PSIsContainer) {
            Copy-DirectoryTree -Source $entry.FullName -Destination $target -SkipDirectoryNames @("__pycache__", "test", "tests", ".pytest_cache") -Label "site-packages\$($entry.Name)" -ProgressEvery 3000 | Out-Null
        } else {
            $copyResult = Copy-FileFast -Source $entry.FullName -Destination $target
            Write-Step "site-packages\$($entry.Name) complete: 1 file, $(Format-ByteSize $entry.Length), $copyResult"
        }
    }
}

function Copy-PythonRuntime {
    param(
        [hashtable]$PythonSource,
        [string]$Destination,
        [string]$Mode,
        [string]$ExtraPatterns
    )

    if ([string]::IsNullOrWhiteSpace($Mode)) {
        $Mode = "slim"
    }
    $Mode = $Mode.ToLowerInvariant()
    if ($Mode -notin @("slim", "full")) {
        throw "Invalid VP_RELEASE_PYTHON_COPY_MODE '$Mode'. Expected 'slim' or 'full'."
    }

    Write-Step "Copying Python runtime in $Mode mode"
    if ($Mode -eq "full") {
        Copy-DirectoryTree -Source $PythonSource.Root -Destination $Destination -SkipDirectoryNames @("__pycache__", ".pytest_cache") -Label "python full runtime" -ProgressEvery 3000 | Out-Null
        $destPythonExe = Join-Path $Destination "python.exe"
        if (-not (Test-Path -LiteralPath $destPythonExe -PathType Leaf)) {
            Copy-FileFast -Source $PythonSource.Exe -Destination $destPythonExe | Out-Null
        }
        return
    }

    Copy-RootFiles -PythonRoot $PythonSource.Root -PythonExe $PythonSource.Exe -Destination $Destination

    $dlls = Join-Path $PythonSource.Root "DLLs"
    if (Test-Path -LiteralPath $dlls -PathType Container) {
        Copy-DirectoryTree -Source $dlls -Destination (Join-Path $Destination "DLLs") -SkipDirectoryNames @("__pycache__", "test", "tests") -Label "Python DLLs" -ProgressEvery 1000 | Out-Null
    }

    $lib = Join-Path $PythonSource.Root "Lib"
    if (-not (Test-Path -LiteralPath $lib -PathType Container)) {
        throw "Python standard library is missing: $lib"
    }

    $libOut = Join-Path $Destination "Lib"
    New-Item -ItemType Directory -Force -Path $libOut | Out-Null
    foreach ($entry in Get-ChildItem -LiteralPath $lib -Force) {
        if ($entry.Name -in @("site-packages", "test", "tests", "__pycache__")) {
            continue
        }
        $target = Join-Path $libOut $entry.Name
        if ($entry.PSIsContainer) {
            Copy-DirectoryTree -Source $entry.FullName -Destination $target -SkipDirectoryNames @("__pycache__", "test", "tests", ".pytest_cache") -Label "stdlib\$($entry.Name)" -ProgressEvery 3000 | Out-Null
        } else {
            Copy-FileFast -Source $entry.FullName -Destination $target | Out-Null
        }
    }
    Write-Step "Python standard library copy complete"

    Copy-SitePackagesSlim -PythonRoot $PythonSource.Root -Destination $Destination -ExtraPatterns $ExtraPatterns
}

function Copy-ModelFiles {
    param(
        [string]$SourceDir,
        [string]$DestinationDir
    )

    Write-Step "Copying ONNX model files"
    $bytes = [int64]0
    $linked = 0
    $copied = 0

    # Copy top-level ONNX models (legacy layout)
    $onnxModels = Get-ChildItem -LiteralPath $SourceDir -Filter "*.onnx" -File
    foreach ($model in $onnxModels) {
        $result = Copy-FileFast -Source $model.FullName -Destination (Join-Path $DestinationDir $model.Name)
        $bytes += [int64]$model.Length
        if ($result -eq "linked") {
            $linked += 1
        } else {
            $copied += 1
        }
        Write-Step "model $($model.Name) complete: $(Format-ByteSize $model.Length), $result"
    }

    foreach ($subdirName in @("interpolation", "super_resolution")) {
        $sourceSubdir = Join-Path $SourceDir $subdirName
        if (-not (Test-Path -LiteralPath $sourceSubdir -PathType Container)) {
            continue
        }

        $destinationSubdir = Join-Path $DestinationDir $subdirName
        New-Item -ItemType Directory -Force -Path $destinationSubdir | Out-Null
        $onnxModels = Get-ChildItem -LiteralPath $sourceSubdir -Filter "*.onnx" -File
        foreach ($model in $onnxModels) {
            $result = Copy-FileFast -Source $model.FullName -Destination (Join-Path $destinationSubdir $model.Name)
            $bytes += [int64]$model.Length
            if ($result -eq "linked") {
                $linked += 1
            } else {
                $copied += 1
            }
            Write-Step "model $subdirName\$($model.Name) complete: $(Format-ByteSize $model.Length), $result"
        }
    }

    $totalModels = $linked + $copied
    if ($totalModels -eq 0) {
        throw "No ONNX model files found in $SourceDir"
    }

    Write-Step "ONNX models complete: hardlinks=$linked, copies=$copied, total=$(Format-ByteSize $bytes)"
}

function Optimize-PythonRuntime {
    param([string]$PythonOutDir)

    Write-Step "Optimizing Python runtime: removing development artifacts"

    $devExtensions = @(".h", ".hpp", ".c", ".cpp", ".cuh", ".lib", ".pdb", ".cmake", ".jinja", ".al", ".ld", ".mjs", ".thrift", ".pyi", ".typed")
    $devDirectoryNames = @("include", "csrc", "test", "tests", "__pycache__", ".pytest_cache", "docs", "doc", "examples", "demos", "benchmarks", "idlelib", ".egg-info")

    $filesToRemove = [System.Collections.Generic.List[System.IO.FileSystemInfo]]::new()
    $dirsToRemove = [System.Collections.Generic.List[System.IO.DirectoryInfo]]::new()

    $items = Get-ChildItem -LiteralPath $PythonOutDir -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($item in $items) {
        if ($item.PSIsContainer) {
            if ($devDirectoryNames -contains $item.Name) {
                $dirsToRemove.Add($item)
            }
        } else {
            if ($devExtensions -contains $item.Extension) {
                $filesToRemove.Add($item)
            }
        }
    }

    $removedBytes = [int64]0
    foreach ($file in $filesToRemove) {
        $removedBytes += [int64]$file.Length
        Remove-Item -LiteralPath $file.FullName -Force
    }

    # Sort directories by depth (descending) so children are removed before parents
    $sortedDirs = $dirsToRemove | Sort-Object { $_.FullName.Split([System.IO.Path]::DirectorySeparatorChar).Length } -Descending
    foreach ($dir in $sortedDirs) {
        if (Test-Path -LiteralPath $dir.FullName) {
            Remove-Item -LiteralPath $dir.FullName -Recurse -Force
        }
    }

    Write-Step "Python runtime optimized: removed $($filesToRemove.Count) development files ($(Format-ByteSize $removedBytes)) and $($dirsToRemove.Count) development directories"
}

function Invoke-CheckedProcess {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = "",
        [int]$TimeoutSeconds = 120
    )

    Write-Step "${Label}: starting with ${TimeoutSeconds}s timeout"
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    foreach ($argument in $Arguments) {
        $psi.ArgumentList.Add($argument)
    }
    if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
        $psi.WorkingDirectory = $WorkingDirectory
    }
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    $null = $process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try {
            $process.Kill($true)
        } catch {
            $process.Kill()
        }
        $process.WaitForExit()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        throw "$Label timed out after ${TimeoutSeconds}s.`nstdout:`n$(Get-TextTail $stdout)`nstderr:`n$(Get-TextTail $stderr)"
    }

    $stdoutText = $stdoutTask.GetAwaiter().GetResult()
    $stderrText = $stderrTask.GetAwaiter().GetResult()
    if (-not [string]::IsNullOrWhiteSpace($stdoutText)) {
        Write-Host (Get-TextTail $stdoutText)
    }
    if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
        Write-Host (Get-TextTail $stderrText)
    }
    if ($process.ExitCode -ne 0) {
        throw "$Label failed with exit code $($process.ExitCode)."
    }
    Write-Step "$Label complete"
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
$displayMode = if ([string]::IsNullOrWhiteSpace($PythonCopyMode)) { 'slim' } else { $PythonCopyMode }
Write-Host "  python mode: $displayMode"
Write-Host "  ffmpeg:      $($ffmpegSource.Ffmpeg)"
Write-Host "  ffprobe:     $($ffmpegSource.Ffprobe)"
Write-Host "  model dir:   $modelSourceDir"
Write-Host "  output root: $outputRootFull"

if (Test-Path -LiteralPath $outputRootFull) {
    Write-Step "Cleaning existing runtime output"
    Remove-Item -LiteralPath $outputRootFull -Recurse -Force
}

$ffmpegOut = Join-Path $outputRootFull "ffmpeg\bin"
$modelsOut = Join-Path $outputRootFull "models"

if (-not $SkipPython) {
    $pythonOut = Join-Path $outputRootFull "python"
    New-Item -ItemType Directory -Force -Path $pythonOut, $ffmpegOut, $modelsOut | Out-Null

    Copy-PythonRuntime -PythonSource $pythonSource -Destination $pythonOut -Mode $PythonCopyMode -ExtraPatterns $ExtraPythonPackages
    Optimize-PythonRuntime -PythonOutDir $pythonOut
} else {
    New-Item -ItemType Directory -Force -Path $ffmpegOut, $modelsOut | Out-Null
    Write-Step "Skipping Python runtime copy (SkipPython switch enabled)"
}

Write-Step "Copying FFmpeg binaries"
Copy-FileFast -Source $ffmpegSource.Ffmpeg -Destination (Join-Path $ffmpegOut "ffmpeg.exe") | Out-Null
Copy-FileFast -Source $ffmpegSource.Ffprobe -Destination (Join-Path $ffmpegOut "ffprobe.exe") | Out-Null
Write-Step "FFmpeg binaries complete"

Copy-ModelFiles -SourceDir $modelSourceDir -DestinationDir $modelsOut

$destFfmpeg = Join-Path $ffmpegOut "ffmpeg.exe"
$destFfprobe = Join-Path $ffmpegOut "ffprobe.exe"
$destDefaultModel = Join-Path $modelsOut "rife_v4.25.onnx"
$requiredFiles = @($destFfmpeg, $destFfprobe, $destDefaultModel)
if (-not $SkipPython) {
    $destPythonExe = Join-Path $pythonOut "python.exe"
    $requiredFiles = @($destPythonExe) + $requiredFiles
}
foreach ($required in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Runtime validation failed; missing $required"
    }
}

$env:VP_RUNTIME_ROOT = $outputRootFull
$env:VP_FFMPEG_PATH = $destFfmpeg
$env:VP_FFPROBE_PATH = $destFfprobe
$env:VP_RIFE_MODEL_DIR = $modelsOut

if (-not $SkipPython) {
    $env:VP_PYTHON_EXECUTABLE = $destPythonExe
    $env:PYTHONNOUSERSITE = "1"
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

    $importSmokeScript = "import importlib; [importlib.import_module(name) for name in ['pydantic','pydantic_settings','numpy','PIL','onnxruntime']]; print('python runtime imports ok', flush=True)"
    Invoke-CheckedProcess -Label "Python runtime import smoke" -FilePath $destPythonExe -Arguments @("-s", "-c", $importSmokeScript) -TimeoutSeconds 180
    Invoke-CheckedProcess -Label "Bundled backend check" -FilePath $destPythonExe -Arguments @("-s", "-m", "app", "check") -WorkingDirectory (Join-Path $repoRoot "backend") -TimeoutSeconds 180
} else {
    $systemPython = Get-FirstCommandPath -Names @("python.exe", "python")
    if (-not [string]::IsNullOrWhiteSpace($systemPython)) {
        Write-Step "Running backend check with system Python: $systemPython"
        $env:VP_PYTHON_EXECUTABLE = $systemPython
        Invoke-CheckedProcess -Label "System Python backend check" -FilePath $systemPython -Arguments @("-s", "-m", "app", "check") -WorkingDirectory (Join-Path $repoRoot "backend") -TimeoutSeconds 180
    } else {
        Write-Step "Warning: No system Python found for backend check"
    }
}

Write-Step "Windows runtime prepared successfully."
