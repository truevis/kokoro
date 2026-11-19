# Installs and starts Kokoro-FastAPI natively on Windows (no Docker). Run in PowerShell.
# Optional: set $env:KOKORO_DIR to choose the clone location (default: .\Kokoro-FastAPI).
$ErrorActionPreference = "Stop"
$dir = if ($env:KOKORO_DIR) { $env:KOKORO_DIR } else { Join-Path $PSScriptRoot "Kokoro-FastAPI" }

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget not found. Install 'App Installer' from the Microsoft Store, then re-run."
}

# Install only what's missing (skips slow, redundant winget calls on re-runs).
$tools = @(
    @{ Cmd = "uv";  Id = "astral-sh.uv" },
    @{ Cmd = "git"; Id = "Git.Git" }
)
foreach ($t in $tools) {
    if (-not (Get-Command $t.Cmd -ErrorAction SilentlyContinue)) {
        winget install -e --id $t.Id --accept-package-agreements --accept-source-agreements
    }
}
$espeak = @("$env:ProgramFiles\eSpeak NG", "${env:ProgramFiles(x86)}\eSpeak NG") |
    Where-Object { Test-Path "$_\espeak-ng.exe" }
if (-not $espeak -and -not (Get-Command espeak-ng -ErrorAction SilentlyContinue)) {
    winget install -e --id eSpeak-NG.eSpeak-NG --accept-package-agreements --accept-source-agreements
}

# Pick up PATH changes made by winget in this session.
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

if (Test-Path "$dir\.git") { git -C $dir pull --ff-only }
else { git clone https://github.com/remsky/Kokoro-FastAPI.git $dir }

$startScript = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { "start-gpu.ps1" } else { "start-cpu.ps1" }
Write-Host "Using $startScript (first run downloads the model)"
Set-Location $dir
if (-not (Test-Path ".venv")) { uv venv }
& ".\$startScript"
