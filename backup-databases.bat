@echo off
chcp 936 >NUL
REM ============================================
REM tz-data 数据库备份脚本 (Windows)
REM 版本 : 1.0
REM 日期 : 2026-05-11
REM 说明 : 备份 tz-data 数据库文件
REM ============================================

setlocal EnableDelayedExpansion

REM 选项
set "PROJECT_ROOT=%~dp0"
set "DATA_DIR=%PROJECT_ROOT%data"
set "BACKUP_DIR=%PROJECT_ROOT%backups"
set "TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"

REM 数据库文件列表
set "DB_FILES=tzdata_market.db tzdata_trading.db tzdata_analysis.db"

echo.
echo ========================================
echo   tz-data 数据库备份管理
echo ========================================
echo.
echo 备份目录 : %BACKUP_DIR%
echo 时间戳 : %TIMESTAMP%
echo.

REM 创建备份目录
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM 备份每个数据库
set SUCCESS=0
set FAILED=0

for %%F in (%DB_FILES%) do (
    set "DB_FILE=%DATA_DIR%\%%F"
    set "BACKUP_FILE=%BACKUP_DIR%\%%~nF.bak.%TIMESTAMP%%%~xF"
    
    if exist "!DB_FILE!" (
        echo [%%F] 正在备份...
        copy "!DB_FILE!" "!BACKUP_FILE!" >nul 2>&1
        
        if errorlevel 1 (
            echo   [!] 备份失败
            set /a FAILED+=1
        ) else (
            echo   [OK] 备份成功 - !BACKUP_FILE!
            set /a SUCCESS+=1
        )
    ) else (
        echo [%%F] 文件不存在，跳过
    )
)

echo.
echo ========================================
echo 备份完成!
echo   成功 : %SUCCESS%
echo   失败 : %FAILED%
echo ========================================
echo.

REM 首次七天之前旧备份
echo 首次七天之前旧备份...
forfiles /p "%BACKUP_DIR%" /s /m *.bak.* /d -7 /c "cmd /c del @path" 2>nul
echo.

pause
exit /b 0
