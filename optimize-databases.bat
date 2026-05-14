@echo off
chcp 936 >NUL
REM ============================================
REM tz-data 数据库优化脚本 (Windows)
REM 版本 : 1.0
REM 日期 : 2026-05-11
REM 说明 : 优化 tz-data 数据库性能
REM ============================================

setlocal EnableDelayedExpansion

REM 选项
set "PROJECT_ROOT=%~dp0"
set "DATA_DIR=%PROJECT_ROOT%data"

REM 数据库文件列表
set "DB_FILES=tzdata_market.db tzdata_trading.db tzdata_analysis.db"

echo.
echo ========================================
echo   tz-data 数据库优化工程
echo ========================================
echo.
echo 优化项目 :
echo   - WAL 模式
echo   - 缓存大小 (64 MB)
echo   - 同步方式 (NORMAL)
echo   - 临时存在 (MEMORY)
echo   - 数据库统计 (ANALYZE)
echo   - 碎片整理 (VACUUM)
echo.

REM 优化每个数据库
set SUCCESS=0
set FAILED=0

for %%F in (%DB_FILES%) do (
    set "DB_FILE=%DATA_DIR%\%%F"
    
    if exist "!DB_FILE!" (
        echo [%%F] 正在优化...
        
        python "%PROJECT_ROOT%scripts\optimize_sqlite.py" --database "%%F" >nul 2>&1
        
        if errorlevel 1 (
            echo   [!] 优化失败
            set /a FAILED+=1
        ) else (
            echo   [OK] 优化成功
            set /a SUCCESS+=1
        )
    ) else (
        echo [%%F] 文件不存在，跳过
    )
)

echo.
echo ========================================
echo 优化完成!
echo   成功 : %SUCCESS%
echo   失败 : %FAILED%
echo ========================================
echo.

pause
exit /b 0
