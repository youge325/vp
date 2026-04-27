#Requires -Version 5.1
param(
    [switch]$Restore
)

$ErrorActionPreference = "Stop"

$nsisDir = Join-Path $env:LOCALAPPDATA "tauri\NSIS"
$nsisbiCacheDir = Join-Path $env:LOCALAPPDATA "tauri\NSISBI"
$nsisbiZip = Join-Path $nsisbiCacheDir "nsis-binary-7423-3.zip"
$nsisbiExtractDir = Join-Path $env:TEMP "nsisbi-extract-$([System.Guid]::NewGuid().ToString('N'))"

$swapMap = @(
    @{ Target = Join-Path $nsisDir "makensis.exe";       Backup = Join-Path $nsisDir "makensis.exe.standard" },
    @{ Target = Join-Path $nsisDir "Bin\makensis.exe";   Backup = Join-Path $nsisDir "Bin\makensis.exe.standard" }
)

function Restore-StandardNSIS {
    Write-Host "[install-nsisbi] Restoring standard NSIS compiler..."
    foreach ($entry in $swapMap) {
        $target = $entry.Target
        $backup = $entry.Backup
        if (Test-Path -LiteralPath $backup -PathType Leaf) {
            Copy-Item -LiteralPath $backup -Destination $target -Force
            Remove-Item -LiteralPath $backup -Force
            Write-Host "  restored: $target"
        } else {
            Write-Host "  backup not found, skipping: $target"
        }
    }
}

if ($Restore) {
    Restore-StandardNSIS
    exit 0
}

# Ensure standard NSIS cache directory exists
if (-not (Test-Path -LiteralPath $nsisDir -PathType Container)) {
    Write-Host "[install-nsisbi] Standard NSIS cache not found at $nsisDir"
    Write-Host "[install-nsisbi] Tauri will download it on first build. Please run a build once to populate the cache, then re-run this script."
    exit 1
}

# Download NSISBI if not cached
if (-not (Test-Path -LiteralPath $nsisbiZip -PathType Leaf)) {
    New-Item -ItemType Directory -Force -Path $nsisbiCacheDir | Out-Null
    $url = "https://sourceforge.net/projects/nsisbi/files/nsisbi3.10.3/nsis-binary-7423-3.zip/download"
    Write-Host "[install-nsisbi] Downloading NSISBI from SourceForge..."

    # Use curl.exe instead of Invoke-WebRequest because SourceForge's redirect
    # chain (HTML meta refresh -> mirror selection -> actual file) is not
    # handled correctly by Invoke-WebRequest on this runner.
    $curl = Get-Command "curl.exe" -ErrorAction SilentlyContinue
    if (-not $curl) {
        throw "curl.exe is required to download from SourceForge but was not found in PATH."
    }

    $proc = Start-Process -FilePath $curl.Source -ArgumentList @("-L", "-o", $nsisbiZip, $url) -NoNewWindow -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        throw "curl.exe failed to download NSISBI (exit code $($proc.ExitCode))."
    }

    # Verify we got a real ZIP, not an HTML error page
    $first2 = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($nsisbiZip)[0..1])
    if ($first2 -ne "PK") {
        throw "Downloaded file is not a valid ZIP (got '$first2'). SourceForge may have returned an error page."
    }

    $dlSize = (Get-Item -LiteralPath $nsisbiZip).Length
    if ($dlSize -ge 1MB) { $dlSizeStr = "{0:N1} MB" -f ($dlSize / 1MB) } else { $dlSizeStr = "$dlSize bytes" }
    Write-Host "[install-nsisbi] Download complete: $nsisbiZip ($dlSizeStr)"
}

# Extract NSISBI
if (Test-Path -LiteralPath $nsisbiExtractDir) {
    Remove-Item -LiteralPath $nsisbiExtractDir -Recurse -Force
}
Write-Host "[install-nsisbi] Extracting NSISBI..."
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($nsisbiZip, $nsisbiExtractDir)

# The archive contains a root folder like "nsis-binary-7423-3"
$extractedRoot = Get-ChildItem -LiteralPath $nsisbiExtractDir -Directory | Select-Object -First 1
if (-not $extractedRoot) {
    $extractedRoot = Get-Item -LiteralPath $nsisbiExtractDir
}

# Validate extracted files
$nsisbiRootExe = Join-Path $extractedRoot.FullName "makensis.exe"
$nsisbiBinExe  = Join-Path $extractedRoot.FullName "Bin\makensis.exe"
foreach ($f in @($nsisbiRootExe, $nsisbiBinExe)) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) {
        throw "NSISBI archive missing expected file: $f"
    }
}

# Backup and swap
Write-Host "[install-nsisbi] Backing up standard makensis.exe and swapping in NSISBI..."
foreach ($entry in $swapMap) {
    $target = $entry.Target
    $backup = $entry.Backup

    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        Write-Host "  WARNING: target not found, skipping: $target"
        continue
    }

    # Backup
    if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
        Copy-Item -LiteralPath $target -Destination $backup -Force
        Write-Host "  backed up: $target -> $backup"
    }

    # Determine source from extracted archive
    $source = if ($target -like "*\Bin\makensis.exe") { $nsisbiBinExe } else { $nsisbiRootExe }
    Copy-Item -LiteralPath $source -Destination $target -Force
    $size = (Get-Item -LiteralPath $target).Length
    if ($size -ge 1MB) { $sizeStr = "{0:N1} MB" -f ($size / 1MB) } else { $sizeStr = "$size bytes" }
    Write-Host "  swapped: $target ($sizeStr)"
}

# Cleanup extract dir
Remove-Item -LiteralPath $nsisbiExtractDir -Recurse -Force

Write-Host "[install-nsisbi] NSISBI compiler installed successfully."
