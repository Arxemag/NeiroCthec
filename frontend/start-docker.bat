@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker-compose up -d
echo.
echo Проверка статуса контейнеров:
docker-compose ps
pause
