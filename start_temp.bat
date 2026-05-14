@echo off
chcp 936 >NUL
REM ============================================
REM tz-data 项目启动脚本 (版本)
REM 后端 8000, 前端 3000
REM ============================================

set "BACKEND_PORT=8000"
set "FRONTEND_PORT=3000"
set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"

echo.
echo ========================================
echo   tz-data 项目启动
echo ========================================
echo.
echo 1. 启动全部服务
echo 2. 启动后端服务
echo 3. 启动前端服务
echo 4. 停止全部服务
echo 5. 退出
echo.
set /p choice="请输入选项 (1-5): "

if "%choice%"=="1" (start "" cmd /k "cd /d %PROJECT_ROOT% && call start.bat")
if "%choice%"=="2" (start "" cmd /k "cd /d %PROJECT_ROOT% && call start-backend.bat")
if "%choice%"=="3" (start "" cmd /k "cd /d %PROJECT_ROOT% && call start-frontend.bat")
if "%choice%"=="4" (start "" cmd /k "cd /d %PROJECT_ROOT% && call stop.bat")
if "%choice%"=="5" exit

echo.
pause
