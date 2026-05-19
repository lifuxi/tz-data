@echo off
chcp 65001 >NUL
REM tz-data 快速启动脚本
echo.
echo ========================================
echo   tz-data 项目快速启动
echo ========================================
echo.

cd /d %~dp0

REM 检查是否已有 Celery 进程在运行（防止重复调度导致任务重复执行）
tasklist /FI "WINDOWTITLE eq Celery Beat*" 2>NUL | find /I "Celery Beat" >NUL
if not errorlevel 1 (
    echo [警告] 检测到已有 Celery Beat 进程在运行，请先执行 stop.bat 停止旧服务
    pause
    exit /b 1
)

tasklist /FI "WINDOWTITLE eq Celery Worker*" 2>NUL | find /I "Celery Worker" >NUL
if not errorlevel 1 (
    echo [警告] 检测到已有 Celery Worker 进程在运行，请先执行 stop.bat 停止旧服务
    pause
    exit /b 1
)

set VENV_ACTIVATE=%~dp0.venv\Scripts\activate.bat
set PYTHONPATH=%~dp0src

echo [1/5] 启动 Celery Worker (gevent pool)...
start "Celery Worker" cmd /k "cd /d %~dp0 && call %VENV_ACTIVATE% && celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info --pool=gevent"

timeout /t 3 /nobreak >NUL

echo [2/5] 启动 Celery Beat (redbeat)...
start "Celery Beat" cmd /k "cd /d %~dp0 && call %VENV_ACTIVATE% && celery -A tzdata_pkg.scheduler.celery_app beat --loglevel=info"

timeout /t 2 /nobreak >NUL

echo [3/5] 启动 Celery Flower (实时监控)...
start "Celery Flower" cmd /k "cd /d %~dp0 && call %VENV_ACTIVATE% && celery -A tzdata_pkg.scheduler.celery_app flower --port=5555"

timeout /t 2 /nobreak >NUL

echo [4/5] 启动 FastAPI (端口 8000)...
start "FastAPI Backend" cmd /k "cd /d %~dp0 && call %VENV_ACTIVATE% && uvicorn tzdata_pkg.api.server:app --reload --host 0.0.0.0 --port 8000"

timeout /t 2 /nobreak >NUL

echo [5/5] 启动前端开发服务器...
start "Frontend Dev Server" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo   全部服务已启动
echo ========================================
echo API 文档: http://localhost:8000/docs
echo 前端地址: http://localhost:3000
echo Celery Flower: http://localhost:5555
echo.
pause
