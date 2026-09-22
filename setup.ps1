$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
& .\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if (-not (Test-Path -LiteralPath 'data\calendar.db')) {
    & .\.venv\Scripts\python.exe -m scripts.generate_calendar
    if ($LASTEXITCODE -ne 0) { throw 'Calendar generation failed.' }
}
if (-not (Test-Path -LiteralPath 'frontend\vendor\lightweight-charts.js')) {
    npm ci --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw 'Chart dependency installation failed.' }
    npm run vendor
    if ($LASTEXITCODE -ne 0) { throw 'Chart vendoring failed.' }
}
Write-Host 'Ready. Run .\start.ps1 or double-click start.cmd.'
