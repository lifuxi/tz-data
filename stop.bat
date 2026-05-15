@echo off
chcp 65001 >NUL
REM ============================================
REM tz-data 项目停止脚本 (Windows)
REM ============================================

echo.
echo ========================================
echo   正在停止 tz-data 项目服务...
echo ========================================

echo [1/4] 停止 Celery Worker...
taskkill /F /FI "WINDOWTITLE eq Celery Worker*" /T 2>NUL
if errorlevel 1 (echo   - Celery Worker 未运行) else (echo   [OK] Celery Worker 已停止)

echo [2/4] 停止 Celery Beat...
taskkill /F /FI "WINDOWTITLE eq Celery Beat*" /T 2>NUL
if errorlevel 1 (echo   - Celery Beat 未运行) else (echo   [OK] Celery Beat 已停止)

echo [3/4] 停止 FastAPI Backend...
taskkill /F /FI "WINDOWTITLE eq FastAPI Backend*" /T 2>NUL
if errorlevel 1 (echo   - FastAPI Backend 未运行) else (echo   [OK] FastAPI Backend 已停止)

echo [4/4] 停止前端服务...
taskkill /F /FI "WINDOWTITLE eq Frontend Dev Server*" /T 2>NUL
if errorlevel 1 (echo   - 前端服务 未运行) else (echo   [OK] 前端服务 已停止)

echo.
echo ========================================
echo   全部服务已停止
echo ========================================

pause
exit /b 0
