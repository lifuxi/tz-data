@echo off
chcp 936 >NUL
REM 启动 tz-data 项目
echo 正在启动 tz-data 项目...
start "" cmd /k "cd /d %~dp0 && start.bat"
exit
