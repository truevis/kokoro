# Stops Kokoro-FastAPI (uvicorn listening on port 8880). Run from repo root or Kokoro-FastAPI.
param(
    [int]$Port = 8880
)

$ErrorActionPreference = "Stop"

$connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($connections.Count -eq 0) {
    Write-Host "No Kokoro-FastAPI server is listening on port $Port."
    exit 0
}

$pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $pids) {
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    $name = if ($proc) { $proc.ProcessName } else { "process" }
    Write-Host "Stopping $name (PID $procId) on port $Port..."
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Milliseconds 500

if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Error "Port $Port is still in use. Stop any remaining processes manually."
    exit 1
}

Write-Host "Kokoro-FastAPI stopped."

try {
    Invoke-WebRequest -Uri "http://localhost:$Port/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop | Out-Null
    Write-Warning "http://localhost:$Port/health still responded; the server may not have fully stopped."
}
catch {
    # Expected once the server is down.
}