# TTS pipeline check: Core, Stage4, tts-xtts
# Run from project root: powershell -ExecutionPolicy Bypass -File scripts/check-tts-pipeline.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $root "docker-compose.yml"))) { $root = (Get-Location).Path }

Write-Host "=== 1. Containers (docker compose ps) ===" -ForegroundColor Cyan
Push-Location -LiteralPath $root
docker compose ps -a 2>$null
Pop-Location
Write-Host ""

Push-Location -LiteralPath $root
try {
Write-Host "=== 2. Core logs (last 80) ===" -ForegroundColor Cyan
docker compose logs core --tail 80 2>$null
Write-Host ""

Write-Host "=== 3. Stage4 logs (last 80) ===" -ForegroundColor Cyan
docker compose logs stage4 --tail 80 2>$null
Write-Host ""

Write-Host "=== 4. tts-xtts logs (last 80) ===" -ForegroundColor Cyan
docker compose logs tts-xtts --tail 80 2>$null
Write-Host ""
} finally { Pop-Location }

Write-Host "=== 5. Core GET /books ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/books" -Method GET -TimeoutSec 5 -UseBasicParsing
    Write-Host "Core GET /books: $($r.StatusCode)"
} catch { Write-Host "Core GET /books: $($_.Exception.Message)" }
Write-Host ""

Write-Host "=== 6. tts-xtts GET /health ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8021/health" -Method GET -TimeoutSec 10 -UseBasicParsing
    Write-Host "tts-xtts GET /health: $($r.StatusCode) $($r.Content)"
} catch { Write-Host "tts-xtts GET /health: $($_.Exception.Message)" }
Write-Host ""

Write-Host "=== Done. Copy output above and paste to chat. ===" -ForegroundColor Green
