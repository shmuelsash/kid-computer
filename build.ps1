# Build the standalone Windows exe locally with PyInstaller.
# ASCII only by house rule. CI builds the released exe; this is for local testing.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Syncing dependencies with uv..." -ForegroundColor Cyan
uv sync

Write-Host "Building KidComputer.exe..." -ForegroundColor Cyan
uv run pyinstaller --noconfirm --onefile --windowed --name KidComputer app_entry.py

Write-Host "Done. See dist\KidComputer.exe" -ForegroundColor Green
