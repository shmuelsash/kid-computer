# Run Kid Computer locally in a window (not fullscreen) for development.
# ASCII only by house rule. Uses uv so the environment stays isolated.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Syncing dependencies with uv..." -ForegroundColor Cyan
uv sync

# Windowed + DEBUG logging so you can iterate without locking your keyboard.
$env:KIDCOMPUTER_FULLSCREEN = "0"
$env:KIDCOMPUTER_AUTO_UPDATE = "0"
$env:LOG_LEVEL = "DEBUG"

Write-Host "Launching Kid Computer (windowed). Hold Ctrl+Alt+Q to exit." -ForegroundColor Green
uv run python -m kidcomputer
