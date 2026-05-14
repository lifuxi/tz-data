# Rewrite stop.bat with correct GBK encoding
# NO Chinese characters in this script - only ASCII and byte values
# Run: powershell -ExecutionPolicy Bypass -File rewrite-stop.ps1

# Build byte array directly
$file = New-Object System.Collections.Generic.List[byte]
$ascii = [System.Text.Encoding]::ASCII
$CRLF = [byte[]](13, 10)

function Add-Line {
    param([object[]]$parts)
    foreach ($p in $parts) {
        if ($p -is [byte[]]) { $file.AddRange($p) }
        elseif ($p -is [string]) { $file.AddRange($ascii.GetBytes($p)) }
    }
    $file.AddRange($CRLF)
}

# GBK byte arrays for Chinese text (hardcoded)
# 项目 = xiang(207,238) mu(196,191)
$XM = [byte[]](207,238,196,191)
# 停止 = ting(205,163) zhi(214,185)
$TZ = [byte[]](205,163,214,185)
# 脚本 = jiao(189,197) ben(177,190)
$JB = [byte[]](189,197,177,190)
# 正在 = zheng(214,250) zai(212,190)
$ZZ = [byte[]](214,250,212,190)
# 服务 = fu(183,191) wu(210,241)
$FW = [byte[]](183,191,210,241)
# 未运行 = wei(206,215) yun(212,190) hang(186,194)
$WYX = [byte[]](206,215,212,190,186,194)
# 已停止 = yi(200,219) ting(205,163) zhi(214,185)
$YTZ = [byte[]](200,219,205,163,214,185)
# 前端 = qian(207,172) duan(181,169)
$QD = [byte[]](207,172,181,169)
# 全部 = quan(200,171) bu(177,231)
$QB = [byte[]](200,171,177,231)

# Build file
Add-Line @('@echo off')
Add-Line @('chcp 65001 >NUL')
Add-Line @('REM ============================================')
Add-Line @('REM tz-data ', $XM, $TZ, $JB, ' (Windows)')
Add-Line @('REM ============================================')
Add-Line @('')
Add-Line @('echo.')
Add-Line @('echo ========================================')
Add-Line @('echo   ', $ZZ, $TZ, ' tz-data ', $XM, $FW, '...')
Add-Line @('echo ========================================')
Add-Line @('')
Add-Line @('echo [1/3] ', $TZ, ' Celery Worker...')
Add-Line @('taskkill /F /FI "WINDOWTITLE eq Celery Worker*" /T 2>NUL')
Add-Line @('if errorlevel 1 (echo   - Celery Worker ', $WYX, ') else (echo   [OK] Celery Worker ', $YTZ, ')')
Add-Line @('')
Add-Line @('echo [2/3] ', $TZ, ' FastAPI Backend...')
Add-Line @('taskkill /F /FI "WINDOWTITLE eq FastAPI Backend*" /T 2>NUL')
Add-Line @('if errorlevel 1 (echo   - FastAPI Backend ', $WYX, ') else (echo   [OK] FastAPI Backend ', $YTZ, ')')
Add-Line @('')
Add-Line @('echo [3/3] ', $TZ, $QD, $FW, '...')
Add-Line @('taskkill /F /FI "WINDOWTITLE eq Frontend Dev Server*" /T 2>NUL')
Add-Line @('if errorlevel 1 (echo   - ', $QD, $FW, $WYX, ') else (echo   [OK] ', $QD, $FW, $YTZ, ')')
Add-Line @('')
Add-Line @('echo.')
Add-Line @('echo ========================================')
Add-Line @('echo   ', $QB, $FW, $YTZ)
Add-Line @('echo ========================================')
Add-Line @('')
Add-Line @('pause')
Add-Line @('exit /b 0')

# Write
$target = "C:\myspace\tz-data\stop.bat"
[System.IO.File]::WriteAllBytes($target, $file.ToArray())
Write-Host "Written $($file.Count) bytes"

# Verify raw bytes only - no Chinese display
$raw = [System.IO.File]::ReadAllBytes($target)
Write-Host "File size: $($raw.Length)"
Write-Host "First 5 bytes: $($raw[0..4] -join ',')"

# Find "tz-data " and show next 12 bytes
for ($i = 0; $i -lt $raw.Length - 8; $i++) {
    if ($raw[$i] -eq 116 -and $raw[$i+1] -eq 122 -and $raw[$i+2] -eq 45 -and $raw[$i+3] -eq 100 -and $raw[$i+4] -eq 97 -and $raw[$i+5] -eq 116 -and $raw[$i+6] -eq 97 -and $raw[$i+7] -eq 32) {
        $pos = $i + 8
        $expected = @(207,238,196,191,205,163,214,185,189,197,177,190)
        $actual = $raw[$pos..($pos+11)]
        Write-Host "Chinese bytes at $pos`: $($actual -join ',')"
        Write-Host "Expected:           $($expected -join ',')"
        $ok = $true
        for ($k = 0; $k -lt 12; $k++) { if ($actual[$k] -ne $expected[$k]) { $ok = $false } }
        Write-Host "MATCH: $ok"
        break
    }
}
