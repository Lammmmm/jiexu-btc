param([int]$Port = 8000, [switch]$DebugMode, [switch]$NoSync)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Run setup.ps1 first to create the local environment.' }
if ($DebugMode) { $env:DEBUG_MODE = 'true' }
if ($NoSync) { $env:AUTO_SYNC = 'false' }
Write-Host "Open http://127.0.0.1:$Port (Ctrl+C to stop)"
& $pythonExe -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port $Port
