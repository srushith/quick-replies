# Build dist\QuickReplies.msix for the Microsoft Store.
#   .\build-msix.ps1                    # build (version 1.0.0.0)
#   .\build-msix.ps1 -Version 1.0.1.0   # bump for each Store update (last part must be 0)
#   .\build-msix.ps1 -Register          # also install it locally for testing (Developer Mode)
#   .\build-msix.ps1 -Unregister        # remove the local test install
# The .msix is unsigned on purpose: the Store signs it after certification.
param(
    [string]$Version = "1.0.0.0",
    [switch]$Register,
    [switch]$Unregister
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$PackageName = "SrushithKumar.QuickRepliesforWindows"

if ($Unregister) {
    Get-AppxPackage -Name $PackageName | Remove-AppxPackage
    Write-Host "Removed local test install."
    return
}
if ($Version -notmatch '^\d+\.\d+\.\d+\.0$') { throw "Version must look like 1.2.3.0 (Store requires the last part to be 0)." }

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    py -m venv .venv
    & $py -m pip install -r requirements.txt
}

# Windows SDK tools (latest installed version)
$sdk = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.*\x64" -Directory -ErrorAction SilentlyContinue |
    Where-Object { (Test-Path (Join-Path $_.FullName "makeappx.exe")) -and (Test-Path (Join-Path $_.FullName "makepri.exe")) } |
    Sort-Object { [version]$_.Parent.Name } | Select-Object -Last 1
if (-not $sdk) { throw "Windows SDK not found. Install it (it provides makeappx.exe and makepri.exe)." }
Write-Host "Windows SDK: $($sdk.Parent.Name)"
$makeappx = Join-Path $sdk.FullName "makeappx.exe"
$makepri = Join-Path $sdk.FullName "makepri.exe"

Write-Host "Running unit tests..."
& $py -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw "Unit tests failed; not building." }

$out = Join-Path $PSScriptRoot "build\msix"
$layout = Join-Path $out "layout"
$pri = Join-Path $out "pri"
Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $layout, $pri | Out-Null

Write-Host "Building app (one folder)..."
$root = $PSScriptRoot
& $py -m PyInstaller --noconfirm --clean --onedir --noconsole `
    --name QuickReplies `
    --icon "$root\assets\icon.ico" `
    --add-data "$root\assets;assets" `
    --hidden-import pystray._win32 `
    --distpath "$out\bin" --workpath "$out\work" --specpath $out `
    "$root\QuickReplies.pyw"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
Copy-Item -Recurse "$out\bin\QuickReplies" (Join-Path $layout "QuickReplies")

Write-Host "Manifest, logos, resources.pri..."
$manifest = (Get-Content "$root\packaging\AppxManifest.xml" -Raw).Replace("{VERSION}", $Version)
[IO.File]::WriteAllText((Join-Path $layout "AppxManifest.xml"), $manifest, (New-Object Text.UTF8Encoding $false))
& $py "$root\packaging\make_assets.py" (Join-Path $layout "Assets")
if ($LASTEXITCODE -ne 0) { throw "Logo generation failed." }
# Index only the manifest + Assets (not the thousands of app files).
Copy-Item (Join-Path $layout "AppxManifest.xml") $pri
Copy-Item -Recurse (Join-Path $layout "Assets") (Join-Path $pri "Assets")
& $makepri createconfig /cf "$pri\priconfig.xml" /dq en-US /o | Out-Null
& $makepri new /pr $pri /cf "$pri\priconfig.xml" /mn "$pri\AppxManifest.xml" /of (Join-Path $layout "resources.pri") /o | Out-Null
if ($LASTEXITCODE -ne 0) { throw "makepri failed." }

Write-Host "Packing..."
New-Item -ItemType Directory -Force (Join-Path $root "dist") | Out-Null
$msix = Join-Path $root "dist\QuickReplies.msix"
& $makeappx pack /d $layout /p $msix /o | Out-Null
if ($LASTEXITCODE -ne 0) { throw "makeappx failed." }
Write-Host "Built: $msix (version $Version)"

if ($Register) {
    Get-AppxPackage -Name $PackageName | Remove-AppxPackage
    Add-AppxPackage -Register (Join-Path $layout "AppxManifest.xml")
    Write-Host "Installed locally. Start 'Quick Replies' from the Start menu."
}
