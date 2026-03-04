@echo off
REM При двойном клике перезапускаем себя в окне, которое не закроется после выполнения
if not "%~1"=="_run_" (
    start "НейроЧтец" cmd /k "cd /d "%~dp0" && "%~f0" _run_"
    exit /b 0
)

chcp 65001 >nul
cd /d "%~dp0"
set "ROOT=%~dp0"

echo ========================================
echo   НейроЧтец — запуск всех сервисов
echo ========================================
echo.

REM При первом запуске: выполните frontend\setup-and-start.bat для миграций Prisma и seed.
echo [1/7] Docker (Postgres, Redis, MinIO)...
cd frontend
docker compose up -d 2>nul
if errorlevel 1 (
    echo      Docker не запущен или compose недоступен. Запустите контейнеры вручную: cd frontend ^&^& docker compose up -d
) else (
    echo      Контейнеры подняты.
)
cd ..
timeout /t 2 /nobreak >nul

set "TTS_PATH=%ROOT%app\tts_engine_service\app.py"
REM CORE_API_MODE: docker = Core API в контейнере, local = локально (Python). Если не задан — спрашиваем.
if not defined CORE_API_MODE (
    echo.
    echo Core API: как запускать?
    echo   [1] Docker ^(не нужен Python на ПК^)
    echo   [2] Локально ^(нужен Python 3.10-3.12^)
    choice /C 12 /N /M "Ваш выбор (1 или 2): "
    if errorlevel 2 set "CORE_API_MODE=local"
    if errorlevel 1 set "CORE_API_MODE=docker"
    echo.
)

echo [2/7] Core API (http://localhost:8000)...
if /i "%CORE_API_MODE%"=="docker" (
    echo      Запуск Core API в Docker...
    cd /d "%ROOT%app"
    docker compose up -d core 2>nul
    if errorlevel 1 (
        echo      Не удалось запустить Core API в Docker. Запустите вручную: cd app ^&^& docker compose up -d core
    ) else (
        echo      Контейнер core запущен.
    )
    cd /d "%ROOT%"
    timeout /t 4 /nobreak >nul
) else (
    set "APP_VENV=%ROOT%app\.venv\Scripts\python.exe"
    if not exist "%APP_VENV%" (
        echo      Создаю виртуальное окружение app\.venv и устанавливаю зависимости...
        cd /d "%ROOT%app"
        python -m venv .venv 2>nul
        if errorlevel 1 py -3 -m venv .venv 2>nul
        if not exist ".venv\Scripts\python.exe" (
            echo      ОШИБКА: Не найден Python. Установите Python 3.10+ или задайте CORE_API_MODE=docker для запуска в Docker.
            echo      Вручную: cd app ^&^& docker compose up -d core
            cd /d "%ROOT%"
        ) else (
            call .venv\Scripts\activate.bat
            pip install -r requirements.txt -q
            cd /d "%ROOT%"
            echo      Окружение готово.
        )
    )
    start "Core API" cmd /k "cd /d %ROOT%app && (if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat) && python main.py"
    timeout /t 4 /nobreak >nul
)

if /i "%TTS_MODE%"=="docker" goto :tts_docker
if /i "%TTS_MODE%"=="local" goto :tts_local
nvidia-smi >nul 2>&1
if errorlevel 1 goto :tts_local
:tts_docker
echo [3/7] TTS Qwen3 (Docker, NVIDIA, http://localhost:8020)...
cd /d "%ROOT%app"
docker compose up -d tts 2>nul
if errorlevel 1 (
    echo      Docker TTS не запустился. Запускаю локальный TTS...
    goto :tts_local
)
cd /d "%ROOT%"
timeout /t 5 /nobreak >nul
goto :tts_done
:tts_local
echo [3/7] TTS Qwen3 (локально, http://localhost:8020)...
if exist "%TTS_PATH%" (
    echo      Запуск TTS Qwen3: app\tts_engine_service...
    start "TTS Qwen3" cmd /k "cd /d %ROOT%app && (if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat) && python -m tts_engine_service.app & echo. & echo Код выхода: %%errorlevel%% & pause"
    timeout /t 3 /nobreak >nul
) else (
    echo      Не найден app\tts_engine_service\app.py. Озвучка будет недоступна.
    echo      См. docs\TTS_QWEN3.md — как поднять Qwen3 на порту 8020.
)
:tts_done

echo [4/7] Stage4 TTS Worker (только Qwen3, http://localhost:8001)...
start "Stage4 Worker" cmd /k "cd /d %ROOT%app && set "CORE_INTERNAL_URL=http://localhost:8000/internal" && set "STAGE4_SYNTH_MODE=external" && set "EXTERNAL_TTS_URL=http://localhost:8020" && (if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat) && python -m stage4_service.app"

echo [5/7] Frontend API (NestJS, http://localhost:4000)...
start "Frontend API" cmd /k "cd /d %ROOT%frontend && npm run -w apps/api dev"

echo [6/7] Frontend Worker (BullMQ)...
start "Frontend Worker" cmd /k "cd /d %ROOT%frontend && npm run -w apps/api worker"

echo [7/7] Frontend Web (Next.js, http://localhost:3000)...
start "Frontend Web" cmd /k "cd /d %ROOT%frontend && npm run -w apps/web dev"

echo.
echo ========================================
echo   Сервисы: Core API, TTS Engine, Stage4, Frontend API, Worker, Web
echo   Сайт: http://localhost:3000   API: http://localhost:4000
echo   Core: http://localhost:8000   TTS: http://localhost:8020
echo ========================================
echo.
echo При первом запуске фронтенда выполните: frontend\setup-and-start.bat
echo (миграции Prisma и seed).
echo.
echo При первом запуске Core API батник спросит: Docker или локально.
echo Без выбора: set CORE_API_MODE=docker  или  set CORE_API_MODE=local
echo TTS: при наличии NVIDIA — Docker, иначе локально. Принудительно: set TTS_MODE=docker  или  set TTS_MODE=local
echo.
pause
