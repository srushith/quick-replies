# Run Quick Replies from source using the project venv (creates it if missing).
# Usage: .\run.ps1          (normal)
#        .\run.ps1 --debug  (console logs)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Creating .venv and installing requirements..."
    py -m venv .venv
    & $py -m pip install -r requirements.txt
}
& $py -m app.main @args
