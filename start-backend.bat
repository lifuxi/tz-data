@echo off
chcp 65001 >NUL
REM 启动后端服务
echo 正在启动后端服务...
cd /d %~dp0

set VENV_ACTIVATE=%~dp0.venv\Scripts\activate.bat
set PYTHONPATH=%~dp0src

REM 启动 Celery Worker (gevent pool for Windows)
start "Celery Worker" cmd /k "cd /d %~dp0 && call %VENV_ACTIVATE% && celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info --pool=gevent"

timeout /t 3 /nobreak >NUL

REM 启动 Celery Beat (定时任务调度)
start "Celery Beat" cmd /k "cd /d %~dp0 && call %VENV_ACTIVATE% && celery -A tzdata_pkg.scheduler.celery_app beat --loglevel=info"

timeout /t 2 /nobreak >NUL

REM 启动 Celery Flower (实时监控)
start "Celery Flower" cmd /k "cd /d %~dp0 && call %VENV_ACTIVATE% && celery -A tzdata_pkg.scheduler.celery_app flower --port=5555"

timeout /t 2 /nobreak >NUL

REM 启动 FastAPI (端口 8000)
start "FastAPI Backend" cmd /k "cd /d %~dp0 && call %VENV_ACTIVATE% && uvicorn tzdata_pkg.api.server:app --reload --host 0.0.0.0 --port 8000"

echo 后端服务已启动
echo API 文档: http://localhost:8000/docs
echo Celery Flower: http://localhost:5555
pause
