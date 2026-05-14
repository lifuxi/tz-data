$gbk = [System.Text.Encoding]::GetEncoding(936)

function CStr {
    param([string]$hex)
    $chars = @()
    $hex -split ' ' | ForEach-Object { $chars += [char][Convert]::ToInt32($_, 16) }
    return -join $chars
}

function Write-BatFile {
    param([string]$path, [string[]]$lines)
    $content = ($lines -join "`r`n") + "`r`n"
    $bytes = $gbk.GetBytes($content)
    [System.IO.File]::WriteAllBytes($path, $bytes)
    Write-Host "[OK] $($bytes.Length) bytes -> $path"
}

$TD = "C:\myspace\tz-data"
$T2 = "C:\myspace\tz2.0"

$x   = CStr "9879 76EE"
$tz  = CStr "505C 6B62"
$qd  = CStr "524D 7AEF"
$hd  = CStr "540E 7AEF"
$fw  = CStr "670D 52A1"
$jb  = CStr "811A 672C"
$ks  = CStr "542F 52A8"
$yy  = CStr "8FD0 884C"
$wyy = CStr "672A 8FD0 884C"
$ytz = CStr "5DF2 505C 6B62"
$zq  = CStr "6B63 5728"
$jc  = CStr "68C0 67E5"
$zt  = CStr "72B6 6001"
$sj  = CStr "6570 636E"
$ku  = CStr "5E93"
$bf  = CStr "5907 4EFD"
$yh  = CStr "4F18 5316"
$cb  = CStr "7248 672C"
$rq  = CStr "65E5 671F"
$sm  = CStr "8BF4 660E"
$xz  = CStr "9009 9879"
$sr  = CStr "8BF7 8F93 5165"
$ts  = CStr "63D0 793A"
$cg  = CStr "6210 529F"
$sb  = CStr "5931 8D25"
$cc  = CStr "5B58 5728"
$wncc = CStr "4E0D 5B58 5728"
$fc  = CStr "FF0C"
$tg  = CStr "8DF3 8FC7"
$sc  = CStr "9996 6B21"
$az  = CStr "5B89 88C5"
$yl  = CStr "4F9D 8D56"
$yqd = CStr "5DF2 542F 52A8"
$gl  = CStr "7BA1 7406"
$wz  = CStr "5B8C 6574"
$ty  = CStr "7EDF 4E00"
$dk  = CStr "7AEF 53E3"
$qb  = CStr "5168 90E8"
$wf  = CStr "6587 4EF6"
$yf  = CStr "7528 6CD5"
$dz  = CStr "5730 5740"
$wd  = CStr "6587 6863"
$an  = CStr "6309"
$ry  = CStr "4EFB 610F"
$jian = CStr "952E"
$tc  = CStr "9000 51FA"
$wc  = CStr "5B8C 6210"
$kfj = CStr "5F00 53D1 73AF 5883"
$cyj = CStr "751F 4EA7 73AF 5883"
$jk  = CStr "5065 5EB7"
$zqyy = CStr "6B63 5728 8FD0 884C"
$zqtz = CStr "6B63 5728 505C 6B62"
$ck  = CStr "67E5 770B"
$ms  = CStr "6A21 5F0F"
$hc  = CStr "7F13 5B58"
$dx  = CStr "5927 5C0F"
$tb  = CStr "540C 6B65"
$fs  = CStr "65B9 5F0F"
$ls  = CStr "4E34 65F6"
$tj  = CStr "7EDF 8BA1"
$fp  = CStr "788E 7247"
$zl  = CStr "6574 7406"
$xn  = CStr "6027 80FD"
$gc  = CStr "5DE5 7A0B"
$lb  = CStr "5217 8868"
$cj  = CStr "521B 5EFA"
$ml  = CStr "76EE 5F55"
$mg  = CStr "6BCF 4E2A"
$qitian = CStr "4E03 5929"
$jq  = CStr "4E4B 524D"
$jbf = CStr "65E7 5907 4EFD"
$sjc = CStr "65F6 95F4 6233"
$z = CStr "4E2D"
$xm  = $x
$yi = CStr "5DF2"
$y = CStr "5DF2"

Write-Host "=== TZ-DATA bat files ==="

# --- stop.bat ---
Write-BatFile "$TD\stop.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    'REM ============================================',
    "REM tz-data $x$tz$jb (Windows)",
    'REM ============================================',
    '',
    'echo.',
    'echo ========================================',
    "echo   $zq$tz tz-data $x$fw...",
    'echo ========================================',
    '',
    "echo [1/3] $tz Celery Worker...",
    'taskkill /F /FI "WINDOWTITLE eq Celery Worker*" /T 2>NUL',
    "if errorlevel 1 (echo   - Celery Worker $wyy) else (echo   [OK] Celery Worker $ytz)",
    '',
    "echo [2/3] $tz FastAPI Backend...",
    'taskkill /F /FI "WINDOWTITLE eq FastAPI Backend*" /T 2>NUL',
    "if errorlevel 1 (echo   - FastAPI Backend $wyy) else (echo   [OK] FastAPI Backend $ytz)",
    '',
    "echo [3/3] $tz$qd$fw...",
    'taskkill /F /FI "WINDOWTITLE eq Frontend Dev Server*" /T 2>NUL',
    "if errorlevel 1 (echo   - $qd$fw $wyy) else (echo   [OK] $qd$fw $ytz)",
    '',
    'echo.',
    'echo ========================================',
    "echo   $qb$fw$ytz",
    'echo ========================================',
    '',
    'pause',
    'exit /b 0'
)

# --- start.bat ---
Write-BatFile "$TD\start.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM tz-data $x$ks$jb (Windows)",
    'echo.',
    "echo $zq$ks tz-data $x...",
    'cd /d %~dp0',
    '',
    "REM $ks Celery Worker",
    'start "Celery Worker" cmd /k "cd /d %~dp0 && celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info"',
    '',
    'timeout /t 2 /nobreak >NUL',
    '',
    "REM $ks FastAPI ($hd 8000)",
    'start "FastAPI Backend" cmd /k "cd /d %~dp0 && uvicorn tzdata_pkg.api.server:app --reload --host 0.0.0.0 --port 8000"',
    '',
    "echo $hd$fw$yqd",
    "echo API $ts : http://localhost:8000/docs",
    'pause'
)

# --- start-backend.bat ---
Write-BatFile "$TD\start-backend.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM $ks$hd$fw",
    "echo $zq$ks$hd$fw...",
    'cd /d %~dp0',
    '',
    "REM $ks Celery Worker",
    'start "Celery Worker" cmd /k "cd /d %~dp0 && celery -A tzdata_pkg.scheduler.celery_app worker --loglevel=info"',
    '',
    'timeout /t 2 /nobreak >NUL',
    '',
    "REM $ks FastAPI ($hd 8000)",
    'start "FastAPI Backend" cmd /k "cd /d %~dp0 && uvicorn tzdata_pkg.api.server:app --reload --host 0.0.0.0 --port 8000"',
    '',
    "echo $hd$fw$yqd",
    "echo API $ts : http://localhost:8000/docs",
    'pause'
)

# --- start-frontend.bat ---
Write-BatFile "$TD\start-frontend.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM $ks$qd$fw",
    "echo $zq$ks$qd$fw...",
    'cd /d %~dp0frontend',
    '',
    "if not exist `"node_modules`" (echo $sc$yy$fc$zq$az$yl.. & call npm install)",
    '',
    'start "Frontend Dev Server" cmd /k "cd /d %~dp0frontend && npm run dev"',
    '',
    "echo $qd$fw$yqd",
    "echo $ts : http://localhost:3000",
    'pause'
)

# --- quick-start.bat ---
Write-BatFile "$TD\quick-start.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM $ks tz-data $x",
    "echo $zq$ks tz-data $x...",
    'start "" cmd /k "cd /d %~dp0 && start.bat"',
    'exit'
)

# --- start_temp.bat ---
Write-BatFile "$TD\start_temp.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    'REM ============================================',
    "REM tz-data $x$ks$jb ($cb)",
    "REM $hd 8000, $qd 3000",
    'REM ============================================',
    '',
    'set "BACKEND_PORT=8000"',
    'set "FRONTEND_PORT=3000"',
    'set "PROJECT_ROOT=%~dp0"',
    'set "BACKEND_DIR=%PROJECT_ROOT%"',
    'set "FRONTEND_DIR=%PROJECT_ROOT%frontend"',
    '',
    'echo.',
    'echo ========================================',
    "echo   tz-data $x$ks",
    'echo ========================================',
    'echo.',
    "echo 1. $ks$qb$fw",
    "echo 2. $ks$hd$fw",
    "echo 3. $ks$qd$fw",
    "echo 4. $tz$qb$fw",
    "echo 5. $tc",
    'echo.',
    "set /p choice=`"$sr$xz (1-5): `"",
    '',
    'if "%choice%"=="1" (start "" cmd /k "cd /d %PROJECT_ROOT% && call start.bat")',
    'if "%choice%"=="2" (start "" cmd /k "cd /d %PROJECT_ROOT% && call start-backend.bat")',
    'if "%choice%"=="3" (start "" cmd /k "cd /d %PROJECT_ROOT% && call start-frontend.bat")',
    'if "%choice%"=="4" (start "" cmd /k "cd /d %PROJECT_ROOT% && call stop.bat")',
    'if "%choice%"=="5" exit',
    '',
    'echo.',
    'pause'
)

# --- backup-databases.bat ---
Write-BatFile "$TD\backup-databases.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    'REM ============================================',
    "REM tz-data $sj$ku$bf$jb (Windows)",
    "REM $cb : 1.0",
    "REM $rq : 2026-05-11",
    "REM $sm : $bf tz-data $sj$ku$wf",
    'REM ============================================',
    '',
    'setlocal EnableDelayedExpansion',
    '',
    "REM $xz",
    'set "PROJECT_ROOT=%~dp0"',
    'set "DATA_DIR=%PROJECT_ROOT%data"',
    'set "BACKUP_DIR=%PROJECT_ROOT%backups"',
    'set "TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"',
    'set "TIMESTAMP=%TIMESTAMP: =0%"',
    '',
    "REM $sj$ku$wf$lb",
    'set "DB_FILES=tzdata_market.db tzdata_trading.db tzdata_analysis.db"',
    '',
    'echo.',
    'echo ========================================',
    "echo   tz-data $sj$ku$bf$gl",
    'echo ========================================',
    'echo.',
    "echo $bf$ml : %BACKUP_DIR%",
    "echo $sjc : %TIMESTAMP%",
    'echo.',
    '',
    "REM $cj$bf$ml",
    'if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"',
    '',
    "REM $bf$mg$sj$ku",
    'set SUCCESS=0',
    'set FAILED=0',
    '',
    'for %%F in (%DB_FILES%) do (',
    '    set "DB_FILE=%DATA_DIR%\%%F"',
    '    set "BACKUP_FILE=%BACKUP_DIR%\%%~nF.bak.%TIMESTAMP%%%~xF"',
    '    ',
    '    if exist "!DB_FILE!" (',
    "        echo [%%F] $zq$bf...",
    '        copy "!DB_FILE!" "!BACKUP_FILE!" >nul 2>&1',
    '        ',
    '        if errorlevel 1 (',
    "            echo   [!] $bf$sb",
    '            set /a FAILED+=1',
    '        ) else (',
    "            echo   [OK] $bf$cg - !BACKUP_FILE!",
    '            set /a SUCCESS+=1',
    '        )',
    '    ) else (',
    "        echo [%%F] $wf$wncc$fc$tg",
    '    )',
    ')',
    '',
    'echo.',
    'echo ========================================',
    "echo $bf$wc!",
    "echo   $cg : %SUCCESS%",
    "echo   $sb : %FAILED%",
    'echo ========================================',
    'echo.',
    '',
    "REM $sc$qitian$jq$jbf",
    "echo $sc$qitian$jq$jbf...",
    'forfiles /p "%BACKUP_DIR%" /s /m *.bak.* /d -7 /c "cmd /c del @path" 2>nul',
    'echo.',
    '',
    'pause',
    'exit /b 0'
)

# --- optimize-databases.bat ---
Write-BatFile "$TD\optimize-databases.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    'REM ============================================',
    "REM tz-data $sj$ku$yh$jb (Windows)",
    "REM $cb : 1.0",
    "REM $rq : 2026-05-11",
    "REM $sm : $yh tz-data $sj$ku$xn",
    'REM ============================================',
    '',
    'setlocal EnableDelayedExpansion',
    '',
    "REM $xz",
    'set "PROJECT_ROOT=%~dp0"',
    'set "DATA_DIR=%PROJECT_ROOT%data"',
    '',
    "REM $sj$ku$wf$lb",
    'set "DB_FILES=tzdata_market.db tzdata_trading.db tzdata_analysis.db"',
    '',
    'echo.',
    'echo ========================================',
    "echo   tz-data $sj$ku$yh$gc",
    'echo ========================================',
    'echo.',
    "echo $yh$xm :",
    "echo   - WAL $ms",
    "echo   - $hc$dx (64 MB)",
    "echo   - $tb$fs (NORMAL)",
    "echo   - $ls$cc (MEMORY)",
    "echo   - $sj$ku$tj (ANALYZE)",
    "echo   - $fp$zl (VACUUM)",
    'echo.',
    '',
    "REM $yh$mg$sj$ku",
    'set SUCCESS=0',
    'set FAILED=0',
    '',
    'for %%F in (%DB_FILES%) do (',
    '    set "DB_FILE=%DATA_DIR%\%%F"',
    '    ',
    '    if exist "!DB_FILE!" (',
    "        echo [%%F] $zq$yh...",
    '        ',
    '        python "%PROJECT_ROOT%scripts\optimize_sqlite.py" --database "%%F" >nul 2>&1',
    '        ',
    '        if errorlevel 1 (',
    "            echo   [!] $yh$sb",
    '            set /a FAILED+=1',
    '        ) else (',
    "            echo   [OK] $yh$cg",
    '            set /a SUCCESS+=1',
    '        )',
    '    ) else (',
    "        echo [%%F] $wf$wncc$fc$tg",
    '    )',
    ')',
    '',
    'echo.',
    'echo ========================================',
    "echo $yh$wc!",
    "echo   $cg : %SUCCESS%",
    "echo   $sb : %FAILED%",
    'echo ========================================',
    'echo.',
    '',
    'pause',
    'exit /b 0'
)

Write-Host "`n=== TZ2.0 bat files ==="

# --- start-all.bat ---
Write-BatFile "$T2\start-all.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    'REM ============================================',
    "REM TZ2 Quant Platform - $wz$ks$jb",
    "REM $hd 8200, $qd 3200",
    'REM ============================================',
    '',
    'set NODE_NO_WARNINGS=1',
    '',
    'echo.',
    'echo ========================================',
    "echo   TZ2 Quant Platform $ks$z...",
    'echo ========================================',
    'echo.',
    '',
    'netstat -ano | findstr :8200 >NUL 2>&1',
    'if %errorlevel% equ 0 (',
    "    echo [OK] $hd$fw$yi $zq$yy ($dk $hd 8200)",
    ') else (',
    "    echo [$ks] $hd$fw ($dk $hd 8200)...",
    '    start "TZ2 Backend" cmd /k "cd /d C:\myspace\tz2.0 && C:\myspace\tz2.0\.venv\Scripts\python.exe -m uvicorn src.main:app --host 0.0.0.0 --port 8200 --reload"',
    '    timeout /t 3 /nobreak >NUL',
    ')',
    '',
    'netstat -ano | findstr :3200 >NUL 2>&1',
    'if %errorlevel% equ 0 (',
    "    echo [OK] $qd$fw$yi $zq$yy ($dk $qd 3200)",
    ') else (',
    "    echo [$ks] $qd$fw ($dk $qd 3200)...",
    '    start "TZ2 Frontend" cmd /k "cd /d C:\myspace\tz2.0\frontend && npm run dev"',
    '    timeout /t 3 /nobreak >NUL',
    ')',
    '',
    'echo.',
    'echo ========================================',
    "echo   $fw$ks$wc",
    'echo ========================================',
    'echo.',
    "echo $fw$dz :",
    "echo   $qd : http://localhost:3200/",
    "echo   $hd API : http://localhost:8200/docs",
    "echo   API $wd : http://localhost:8200/redoc",
    'echo.',
    "echo $an$ry$jian$tc..",
    'pause >NUL'
)

# --- stop.bat ---
Write-BatFile "$T2\stop.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM TZ2 Quant Platform - $tz$qb$fw (Windows)",
    '',
    'echo.',
    "echo $zqtz$qb$fw...",
    'echo.',
    '',
    'cd /d "%~dp0"',
    'powershell -ExecutionPolicy Bypass -File ".\scripts\stop-all.ps1"',
    '',
    'echo.',
    'pause'
)

# --- status.bat ---
Write-BatFile "$T2\status.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM TZ2 Quant Platform - $ck$fw$zt (Windows)",
    '',
    'cd /d "%~dp0"',
    'powershell -ExecutionPolicy Bypass -File ".\scripts\check-status.ps1"',
    '',
    'echo.',
    'pause'
)

# --- stop-dev.bat ---
Write-BatFile "$T2\stop-dev.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM TZ2 Quant Platform - $tz$kfj$fw",
    'cd /d "%~dp0"',
    '',
    'echo.',
    "echo $zqtz$kfj$fw...",
    'echo.',
    '',
    'powershell -ExecutionPolicy Bypass -File ".\scripts\stop-dev.ps1"',
    '',
    'echo.',
    'pause'
)

# --- status-dev.bat ---
Write-BatFile "$T2\status-dev.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM TZ2 Quant Platform - $kfj$zt$jc",
    'cd /d "%~dp0"',
    '',
    'echo.',
    'powershell -ExecutionPolicy Bypass -File ".\scripts\status-dev.ps1"',
    '',
    'echo.',
    'pause'
)

# --- stop-prod.bat ---
Write-BatFile "$T2\stop-prod.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM TZ2 Quant Platform - $cyj$tz$fw",
    '',
    'cd /d "%~dp0"',
    '',
    'echo.',
    "echo $zqtz$cyj$fw...",
    'echo.',
    '',
    'powershell -ExecutionPolicy Bypass -File ".\scripts\start-prod.ps1" -Stop',
    '',
    'echo.',
    'pause'
)

# --- status-prod.bat ---
Write-BatFile "$T2\status-prod.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM TZ2 Quant Platform - $cyj$zt$jc",
    'cd /d "%~dp0"',
    '',
    'echo.',
    'powershell -ExecutionPolicy Bypass -File ".\scripts\start-prod.ps1" -Status',
    '',
    'echo.',
    'pause'
)

# --- health-check.bat ---
Write-BatFile "$T2\health-check.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM TZ2 Quant Platform - $kfj$jk$jc",
    'cd /d "%~dp0"',
    '',
    'echo.',
    "echo $zqyy$jk$jc...",
    'echo.',
    '',
    'powershell -ExecutionPolicy Bypass -File ".\scripts\health-check.ps1"',
    '',
    'echo.',
    'pause'
)

# --- port-manager.bat ---
Write-BatFile "$T2\port-manager.bat" @(
    '@echo off',
    'chcp 936 >NUL',
    "REM TZ Data ^& TZ2.0 - $ty$dk$gl",
    'REM $yf: port-manager.bat [status^|check^|free^|all]',
    '',
    'cd /d "%~dp0"',
    '',
    'if "%1"=="" (',
    '    powershell -ExecutionPolicy Bypass -File ".\scripts\port-manager.ps1" -Action all',
    ') else (',
    '    powershell -ExecutionPolicy Bypass -File ".\scripts\port-manager.ps1" -Action %1',
    ')',
    '',
    'echo.',
    'pause'
)

Write-Host "`n=== All bat files rewritten ==="
