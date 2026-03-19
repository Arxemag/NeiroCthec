# Проверка и запуск контейнеров НейроЧтец.
# Запуск из корня: powershell -ExecutionPolicy Bypass -File scripts/docker-debug.ps1
# Или из папки scripts: .\docker-debug.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = if ($PSScriptRoot) { Join-Path $PSScriptRoot ".." } else { (Get-Location).Path }
try { Set-Location -LiteralPath $ProjectRoot } catch { Set-Location $ProjectRoot }

Write-Host "=== 1. Конфигурация docker-compose ===" -ForegroundColor Cyan
docker compose config 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "Ошибка конфигурации" -ForegroundColor Red; exit 1 }
Write-Host "OK`n" -ForegroundColor Green

Write-Host "=== 2. Файлы .env ===" -ForegroundColor Cyan
$apiEnv = Join-Path $ProjectRoot "frontend\apps\api\.env"
$webEnv = Join-Path $ProjectRoot "frontend\apps\web\.env"
foreach ($path in @($apiEnv, $webEnv)) {
    $ex = $path -replace [regex]::Escape($ProjectRoot), ""
    if (-not (Test-Path -LiteralPath $path)) {
        $example = $path -replace "\.env$", ".env.example"
        if (Test-Path -LiteralPath $example) {
            Copy-Item -LiteralPath $example -Destination $path
            Write-Host "  Создан $ex из .env.example" -ForegroundColor Green
        } else { Write-Host "  Нет $ex и .env.example" -ForegroundColor Yellow }
    } else { Write-Host "  $ex есть" -ForegroundColor Green }
}

Write-Host "`n=== 3. Остановка старых контейнеров ===" -ForegroundColor Cyan
docker compose down 2>&1

Write-Host "`n=== 4. Запуск стека (postgres, redis, minio, frontend_deps, core, stage4, api, worker, web) ===" -ForegroundColor Cyan
docker compose up -d 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ошибка запуска. Проверьте логи: docker compose logs frontend_deps" -ForegroundColor Red
    exit 1
}

Write-Host "`nОжидание готовности (30 сек)..." -ForegroundColor Gray
Start-Sleep -Seconds 30

Write-Host "`n=== 5. Статус сервисов ===" -ForegroundColor Cyan
docker compose ps -a 2>&1

Write-Host "`n=== 6. Логи api (последние 40 строк) ===" -ForegroundColor Cyan
docker compose logs --tail=40 api 2>&1

$apiLogs = docker compose logs --tail=5 api 2>&1
if ($apiLogs -match "error|Error|ERROR|Exception|Missing env") {
    Write-Host "`nВнимание: в логах api возможны ошибки. Полные логи: docker compose logs api" -ForegroundColor Yellow
}

Write-Host "`n=== Готово ===" -ForegroundColor Green
Write-Host "Порты: postgres 5432, redis 6379, minio 9000/9001, core 8000, api 4000, web 3000" -ForegroundColor White
Write-Host "Логи: docker compose logs -f api" -ForegroundColor White
