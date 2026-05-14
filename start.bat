@echo off
chcp 936 >NUL
REM tz-data 项目启动脚本 (Windows)
echo.
echo 正在启动 tz-data 项目...
cd /d %~dp0

REM 启动 Celery Worker
start "Celery Worker" cmd /k "cd /d %~dp0 && celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info"

timeout /t 2 /nobreak >NUL

REM 启动 FastAPI (后端 8000)
start "FastAPI Backend" cmd /k "cd /d %~dp0 && uvicorn tzdata_pkg.api.server:app --reload --host 0.0.0.0 --port 8000"

echo 后端服务已启动
echo API 提示 : http://localhost:8000/docs
pause
