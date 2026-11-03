<#
.SYNOPSIS
  Removes ShortsFlow (for installs made with Install-ShortsFlow.ps1 directly; the .exe installer has its own uninstaller).
  Your workspace (videos, settings, .env) is kept unless you pass -RemoveData.
#>
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "ShortsFlow"),
    [switch]$RemoveData
)
$ErrorActionPreference = "Stop"

foreach ($lnk in @((Join-Path ([Environment]::GetFolderPath("Desktop")) "ShortsFlow.lnk"),
                   (Join-Path ([Environment]::GetFolderPath("Programs")) "ShortsFlow.lnk"))) {
    if (Test-Path $lnk) { Remove-Item $lnk -Force }
}
foreach ($name in @("venv", "python", "node", "ffmpeg", "tools", "cache")) {
    $p = Join-Path $InstallDir $name
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}
foreach ($name in @("ShortsFlow.cmd", "ShortsFlow Terminal.cmd", "installed.txt", "install.log")) {
    $p = Join-Path $InstallDir $name
    if (Test-Path $p) { Remove-Item -Force $p }
}
if ($RemoveData) {
    $ws = Join-Path $InstallDir "workspace"
    if (Test-Path $ws) { Remove-Item -Recurse -Force $ws }
    if ((Test-Path $InstallDir) -and -not (Get-ChildItem $InstallDir -Force)) { Remove-Item $InstallDir -Force }
    Write-Host "ShortsFlow and your data were removed."
} else {
    Write-Host "ShortsFlow was removed. Your videos and settings are still in $(Join-Path $InstallDir 'workspace') (delete that folder if you do not need them)."
}
