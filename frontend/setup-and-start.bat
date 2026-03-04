@echo off
chcp 65001 >nul
echo ========================================
echo Настройка НейроЧтец - Применение миграций
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Проверка Docker контейнеров...
docker-compose ps
echo.
echo Если контейнеры не запущены, выполните: docker-compose up -d
echo.

echo [2/3] Применение миграций Prisma...
cd apps\api
call npx prisma@6 migrate deploy
if errorlevel 1 (
    echo.
    echo ОШИБКА: Не удалось применить миграции
    echo Проверьте что Docker контейнеры запущены и PostgreSQL доступен
    pause
    exit /b 1
)
echo.

echo [3/3] Генерация Prisma Client...
call npx prisma@6 generate
if errorlevel 1 (
    echo.
    echo ОШИБКА: Не удалось сгенерировать Prisma Client
    pause
    exit /b 1
)
echo.

echo ========================================
echo Готово! Миграции применены.
echo ========================================
echo.
echo Теперь запустите сервисы в отдельных терминалах:
echo.
echo   Терминал 1 - API:
echo     cd apps\api
echo     npm run dev
echo.
echo   Терминал 2 - Worker:
echo     cd apps\api
echo     npm run worker
echo.
echo   Терминал 3 - Web:
echo     cd apps\web
echo     npm run dev
echo.
pause
