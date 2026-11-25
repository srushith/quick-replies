# Build the walkthrough video end to end.
#   .\video\make.ps1            split narration -> record demo -> assemble MP4
#   .\video\make.ps1 -NoRecord  re-assemble from the last recording (e.g. new end card)
# Before recording: quit Quick Replies, turn on Do Not Disturb, don't touch the PC (~1.5 min).
param([switch]$NoRecord)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
Set-Location $root
& $py video\split_audio.py; if ($LASTEXITCODE) { throw "split_audio failed" }
if (-not $NoRecord) {
    & $py video\demo.py; if ($LASTEXITCODE) { throw "demo recording failed" }
}
& $py video\make_video.py; if ($LASTEXITCODE) { throw "make_video failed" }
