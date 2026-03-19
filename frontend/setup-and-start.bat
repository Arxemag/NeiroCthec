@echo off
chcp 65001 >nul
echo ========================================
echo Настройка НейроЧтец - Применение миграций
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Проверка Docker контейнеров...
docker-compose ps
echo.
echo Если контейнеры не запущены, выполните: docker-compose up -d
echo.

if not exist "apps\api\.env" if exist "apps\api\.env.example" (
    echo Создаю apps\api\.env из .env.example для Prisma DATABASE_URL...
    copy "apps\api\.env.example" "apps\api\.env" >nul
    echo     Файл .env создан. При необходимости отредактируйте apps\api\.env
) else if not exist "apps\api\.env" (
    echo ОШИБКА: Нет файла apps\api\.env и нет apps\api\.env.example. Скопируйте .env.example в .env и задайте DATABASE_URL.
    pause
    exit /b 1
)
echo.

echo [2/4] Применение миграций Prisma...
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

echo [3/4] Генерация Prisma Client...
call npx prisma@6 generate
if errorlevel 1 (
    echo.
    echo ОШИБКА: Не удалось сгенерировать Prisma Client
    pause
    exit /b 1
)
echo.

echo [4/4] Seed (планы, голоса, тестовый admin)...
call npm run seed
if errorlevel 1 (
    echo.
    echo ПРЕДУПРЕЖДЕНИЕ: Seed не выполнен. Голоса и admin могут отсутствовать. Запустите вручную: cd apps\api ^&^& npm run seed
) else (
    echo     Голоса и тестовый пользователь admin созданы.
)
echo.

echo ========================================
echo Готово! Миграции применены, seed выполнен.
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
