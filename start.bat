@echo off
chcp 65001 >NUL
REM tz-data 项目启动脚本 (Windows)
echo.
echo 正在启动 tz-data 项目...
cd /d %~dp0

echo [1/3] 启动 Celery Worker (gevent pool)...
start "Celery Worker" cmd /k "cd /d %~dp0 && celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info --pool=gevent"

timeout /t 3 /nobreak >NUL

echo [2/3] 启动 Celery Beat (定时调度)...
start "Celery Beat" cmd /k "cd /d %~dp0 && celery -A tzdata_pkg.scheduler.celery_app beat --loglevel=info"

timeout /t 2 /nobreak >NUL

echo [3/3] 启动 FastAPI (端口 8000)...
start "FastAPI Backend" cmd /k "cd /d %~dp0 && uvicorn tzdata_pkg.api.server:app --reload --host 0.0.0.0 --port 8000"

echo.
echo 后端服务已启动
echo API 文档: http://localhost:8000/docs
echo Celery 调度: 查看 Celery Beat 窗口日志
echo.
pause
