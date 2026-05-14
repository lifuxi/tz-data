@echo off
chcp 936 >NUL
REM 启动前端服务
echo 正在启动前端服务...
cd /d %~dp0frontend

if not exist "node_modules" (echo 首次运行，正在安装依赖.. & call npm install)

start "Frontend Dev Server" cmd /k "cd /d %~dp0frontend && npm run dev"

echo 前端服务已启动
echo 提示 : http://localhost:3000
pause
