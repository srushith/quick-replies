# Build dist\QuickReplies.exe (single file, no console). Unit tests must pass first.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    py -m venv .venv
    & $py -m pip install -r requirements.txt
}

Write-Host "Running unit tests..."
& $py -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw "Unit tests failed; not building." }

if (-not (Test-Path assets\icon.ico)) {
    & $py -c "from PIL import Image; Image.open('assets/icon128.png').convert('RGBA').save('assets/icon.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128)])"
}

Write-Host "Building..."
& $py -m PyInstaller --noconfirm --clean --onefile --noconsole `
    --name QuickReplies `
    --icon assets\icon.ico `
    --add-data "assets;assets" `
    --hidden-import pystray._win32 `
    QuickReplies.pyw
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

Write-Host "Built: $(Join-Path $PSScriptRoot 'dist\QuickReplies.exe')"
