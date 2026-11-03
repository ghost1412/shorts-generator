<#
.SYNOPSIS
  One-time setup of ShortsFlow on Windows. No admin rights and no Python or Node install needed beforehand.

.DESCRIPTION
  Everything goes into one folder (default %LOCALAPPDATA%\ShortsFlow):
    tools\uv.exe      small package manager that fetches Python itself
    python\, venv\    Python 3.12 and the ShortsFlow packages (CUDA torch on NVIDIA GPUs, CPU torch otherwise)
    node\             portable Node.js (animated captions)
    ffmpeg\           FFmpeg + ffprobe (video tools)
    workspace\        your .env, outputs and the Remotion renderer
  Then it creates "ShortsFlow" shortcuts that open the browser app.
  Re-running it updates an existing install.

.PARAMETER Wheel
  Install ShortsFlow from this local .whl instead of PyPI (used for testing a build).
#>
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "ShortsFlow"),
    [string]$Wheel = "",
    [switch]$Cpu,
    [switch]$NoNode,
    [switch]$NoShortcuts,
    [switch]$SkipRemotion
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"     # Invoke-WebRequest is much faster without the progress bar
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$NodeVersion = "v20.18.1"
$UvUrl = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
$TotalSteps = 6

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$Log = Join-Path $InstallDir "install.log"
Start-Transcript -Path $Log -Append | Out-Null

function Step($n, $text) {
    Write-Host ""
    Write-Host "[$n/$TotalSteps] $text" -ForegroundColor Cyan
}

function Download($url, $dest) {
    for ($i = 1; $i -le 3; $i++) {
        try {
            Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
            return
        } catch {
            if ($i -eq 3) { throw "Could not download $url. Check your internet connection and run the installer again. ($($_.Exception.Message))" }
            Start-Sleep -Seconds (2 * $i)
        }
    }
}

function Sha256File($path) {
    # plain .NET instead of Get-FileHash: no dependence on PowerShell module autoloading (breaks when launched from PowerShell 7)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($path)
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream)) -replace "-", "").ToLower() }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Run($exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "'$exe $($arguments -join ' ')' failed with exit code $LASTEXITCODE" }
}

try {
    Write-Host "ShortsFlow setup - installing into $InstallDir" -ForegroundColor Green
    Write-Host "This downloads about 1-3 GB the first time. You can leave it running."

    # 1. uv ---------------------------------------------------------------------------------------------------
    Step 1 "Getting the package manager (uv)"
    $Tools = Join-Path $InstallDir "tools"
    $Uv = Join-Path $Tools "uv.exe"
    if (-not (Test-Path $Uv)) {
        New-Item -ItemType Directory -Force -Path $Tools | Out-Null
        $zip = Join-Path $Tools "uv.zip"
        Download $UvUrl $zip
        Expand-Archive -Path $zip -DestinationPath $Tools -Force
        Remove-Item $zip
        if (-not (Test-Path $Uv)) {   # some releases nest the exe in a folder
            $found = Get-ChildItem -Path $Tools -Recurse -Filter uv.exe | Select-Object -First 1
            if (-not $found) { throw "uv.exe was not found in the download." }
            Copy-Item $found.FullName $Uv
        }
    }

    # 2. Python -----------------------------------------------------------------------------------------------
    Step 2 "Setting up Python 3.12 (private copy, does not touch your system Python)"
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $InstallDir "python"
    $env:UV_CACHE_DIR = Join-Path $InstallDir "cache"
    $Venv = Join-Path $InstallDir "venv"
    $Py = Join-Path $Venv "Scripts\python.exe"
    if (-not (Test-Path $Py)) {
        Run $Uv @("venv", $Venv, "--python", "3.12", "--managed-python", "--seed")
    }

    # 3. Packages ---------------------------------------------------------------------------------------------
    Step 3 "Installing ShortsFlow and its AI components (the slow step)"
    # Pick the newest PyTorch CUDA build the installed NVIDIA driver supports (its header reports the highest CUDA version it can run).
    $cudaTag = $null
    if (-not $Cpu) {
        $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
        if ($smi) {
            $header = (& $smi.Source 2>$null) -join "`n"
            if ($LASTEXITCODE -eq 0 -and $header -match "CUDA (?:UMD )?Version:\s*(\d+)\.(\d+)") {
                $driverCuda = [double]("$($Matches[1]).$($Matches[2])")
                if ($driverCuda -ge 13.0) { $cudaTag = "cu130" }
                elseif ($driverCuda -ge 12.6) { $cudaTag = "cu126" }
                elseif ($driverCuda -ge 12.4) { $cudaTag = "cu124" }
                else { Write-Host "NVIDIA driver is old (CUDA $driverCuda): update it from nvidia.com for GPU speed. Using the CPU build for now." -ForegroundColor Yellow }
            }
        }
    }
    if ($cudaTag) {
        Write-Host "NVIDIA graphics card found: using the GPU build $cudaTag (faster speech recognition)."
        $torchIndex = "https://download.pytorch.org/whl/$cudaTag"
    } else {
        Write-Host "No usable NVIDIA graphics card: using the CPU build (works, but transcription is slower)."
        $torchIndex = "https://download.pytorch.org/whl/cpu"
    }
    # torch and torchaudio together from that index; later installs must not touch them (PyPI's Windows torch is CPU-only)
    Run $Uv @("pip", "install", "--python", $Py, "torch", "torchaudio", "--extra-index-url", $torchIndex)
    if ($Wheel) {
        $spec = "shortsflow[clip,webui] @ " + ([Uri](Resolve-Path $Wheel).Path).AbsoluteUri
    } else {
        $spec = "shortsflow[clip,webui]"
    }
    # No extra index here: torch is already installed and satisfies the requirement, and the PyTorch index only carries stale copies
    # of ordinary packages (requests 2.28) that would shadow PyPI's.
    Run $Uv @("pip", "install", "--python", $Py, "--upgrade-package", "shortsflow", $spec)
    if ($cudaTag) {
        & $Py -c "import sys, torch; sys.exit(0 if torch.cuda.is_available() else 1)"
        if ($LASTEXITCODE -ne 0) {
            # an earlier install may have left a CPU-only torch that counts as "already satisfied": replace it once
            Write-Host "Replacing the CPU build of PyTorch with the GPU build..."
            Run $Uv @("pip", "install", "--python", $Py, "--reinstall-package", "torch", "--reinstall-package", "torchaudio", "torch", "torchaudio", "--extra-index-url", $torchIndex)
            & $Py -c "import sys, torch; sys.exit(0 if torch.cuda.is_available() else 1)"
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "The GPU build was installed but CUDA is not usable on this PC; ShortsFlow will run on the CPU (slower). Update your NVIDIA driver and run this installer again." -ForegroundColor Yellow
        } else {
            Write-Host "GPU check passed: CUDA is available to PyTorch."
        }
    }

    # 4. Node -------------------------------------------------------------------------------------------------
    $NodeDir = Join-Path $InstallDir "node"
    if (-not $NoNode) {
        Step 4 "Getting Node.js (needed for animated captions)"
        if (-not (Test-Path (Join-Path $NodeDir "node.exe"))) {
            $name = "node-$NodeVersion-win-x64"
            $zip = Join-Path $InstallDir "$name.zip"
            Download "https://nodejs.org/dist/$NodeVersion/$name.zip" $zip
            $sums = (Invoke-WebRequest -Uri "https://nodejs.org/dist/$NodeVersion/SHASUMS256.txt" -UseBasicParsing).Content
            $expected = ($sums -split "`n" | Where-Object { $_ -match "$name.zip" } | Select-Object -First 1).Split(" ")[0].Trim()
            $actual = (Sha256File $zip)
            if ($expected -and $actual -ne $expected.ToLower()) { Remove-Item $zip; throw "Node.js download is corrupt (checksum mismatch). Run the installer again." }
            Expand-Archive -Path $zip -DestinationPath $InstallDir -Force
            if (Test-Path $NodeDir) { Remove-Item -Recurse -Force $NodeDir }
            Rename-Item (Join-Path $InstallDir $name) "node"
            Remove-Item $zip
        }
    } else {
        Step 4 "Skipping Node.js (-NoNode)"
    }

    # FFmpeg: Whisper and several pipeline steps run `ffmpeg` / `ffprobe` by name, and a clean PC has neither.
    $FfmpegDir = Join-Path $InstallDir "ffmpeg"
    if (-not (Test-Path (Join-Path $FfmpegDir "bin\ffmpeg.exe"))) {
        Write-Host "Getting FFmpeg (video tools)..."
        $zip = Join-Path $InstallDir "ffmpeg.zip"
        $ffUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        Download $ffUrl $zip
        $content = (Invoke-WebRequest -Uri "$ffUrl.sha256" -UseBasicParsing).Content
        if ($content -is [byte[]]) { $content = [Text.Encoding]::ASCII.GetString($content) }
        $expected = $content.Trim().Split(" ")[0].ToLower()
        $actual = (Sha256File $zip)
        if ($expected -and $actual -ne $expected) { Remove-Item $zip; throw "FFmpeg download is corrupt (checksum mismatch). Run the installer again." }
        $tmp = Join-Path $InstallDir "ffmpeg_tmp"
        if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
        Expand-Archive -Path $zip -DestinationPath $tmp -Force
        $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
        if (-not $inner -or -not (Test-Path (Join-Path $inner.FullName "bin\ffmpeg.exe"))) { throw "ffmpeg.exe was not found in the download." }
        if (Test-Path $FfmpegDir) { Remove-Item -Recurse -Force $FfmpegDir }
        Move-Item $inner.FullName $FfmpegDir
        Remove-Item -Recurse -Force $tmp
        Remove-Item $zip
    }

    # 5. Workspace + launchers --------------------------------------------------------------------------------
    Step 5 "Preparing your workspace"
    $Workspace = Join-Path $InstallDir "workspace"
    New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
    $ShortsFlow = Join-Path $Venv "Scripts\shortsflow.exe"

    $launcher = @"
@echo off
title ShortsFlow
set "SF=%~dp0"
set "PATH=%SF%ffmpeg\bin;%SF%node;%PATH%"
set "SHORTSFLOW_HOME=%SF%workspace"
echo Starting ShortsFlow... your browser opens in a moment.
echo Keep this window open while you use it. Close it to stop ShortsFlow.
echo.
"%SF%venv\Scripts\shortsflow.exe" webui --open
echo.
echo ShortsFlow stopped.
pause
"@
    Set-Content -Path (Join-Path $InstallDir "ShortsFlow.cmd") -Value $launcher -Encoding Ascii

    $terminal = @"
@echo off
title ShortsFlow (command line)
set "SF=%~dp0"
set "PATH=%SF%venv\Scripts;%SF%ffmpeg\bin;%SF%node;%PATH%"
set "SHORTSFLOW_HOME=%SF%workspace"
echo ShortsFlow command line. Try:  shortsflow clip "C:\path\to\video.mp4"
echo.
cmd /k
"@
    Set-Content -Path (Join-Path $InstallDir "ShortsFlow Terminal.cmd") -Value $terminal -Encoding Ascii

    $env:SHORTSFLOW_HOME = $Workspace
    if (Test-Path $NodeDir) { $env:PATH = "$NodeDir;$env:PATH" }
    if (Test-Path $FfmpegDir) { $env:PATH = "$(Join-Path $FfmpegDir 'bin');$env:PATH" }
    Run $ShortsFlow @("--version")
    if (-not $SkipRemotion -and (Test-Path (Join-Path $NodeDir "node.exe"))) {
        Write-Host "Installing the caption renderer (one time, 1-2 minutes)..."
        try { Run $ShortsFlow @("init") } catch { Write-Host "Caption renderer setup failed ($($_.Exception.Message)). Shorts still work without captions; run 'shortsflow init' later." -ForegroundColor Yellow }
    }

    # 6. Shortcuts --------------------------------------------------------------------------------------------
    Step 6 "Creating shortcuts"
    if (-not $NoShortcuts) {
        $shell = New-Object -ComObject WScript.Shell
        $targets = @(
            (Join-Path ([Environment]::GetFolderPath("Desktop")) "ShortsFlow.lnk"),
            (Join-Path ([Environment]::GetFolderPath("Programs")) "ShortsFlow.lnk")
        )
        foreach ($lnk in $targets) {
            $s = $shell.CreateShortcut($lnk)
            $s.TargetPath = Join-Path $InstallDir "ShortsFlow.cmd"
            $s.WorkingDirectory = $Workspace
            $s.Description = "ShortsFlow - turn long videos into shorts"
            $s.Save()
        }
    }
    Set-Content -Path (Join-Path $InstallDir "installed.txt") -Value (Get-Date -Format s)

    Write-Host ""
    Write-Host "All done! Open ShortsFlow from the Desktop or Start menu shortcut." -ForegroundColor Green
    Write-Host "Your videos and settings live in: $Workspace"
    Stop-Transcript | Out-Null
    exit 0
}
catch {
    Write-Host ""
    Write-Host "Setup did not finish: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Run the installer again to resume (it keeps what was already downloaded). Details: $Log"
    Stop-Transcript | Out-Null
    exit 1
}
