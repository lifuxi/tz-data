$gbk = [System.Text.Encoding]::GetEncoding(936)

# Build Chinese strings using Unicode code points
function CStr {
    param([int[]]$codes)
    $chars = @()
    foreach ($c in $codes) { $chars += [char]$c }
    return -join $chars
}

$item    = CStr 0x9879,0x76EE        # 项目
$stop    = CStr 0x505C,0x6B62        # 停止
$script  = CStr 0x811A,0x672C        # 脚本
$stopping = CStr 0x6B63,0x5728,0x505C,0x6B62  # 正在停止
$svc     = CStr 0x670D,0x52A1        # 服务
$stopped = CStr 0x5DF2,0x505C,0x6B62  # 已停止
$notrun  = CStr 0x672A,0x8FD0,0x884C   # 未运行
$fe      = CStr 0x524D,0x7AEF         # 前端
$all     = CStr 0x5168,0x90E8         # 全部

$lines = @(
    "@echo off",
    "chcp 65001 >NUL",
    "REM ============================================",
    "REM tz-data $item$stop$script (Windows)",
    "REM ============================================",
    "",
    "echo.",
    "echo ========================================",
    "echo   $stopping tz-data $item$svc...",
    "echo ========================================",
    "echo.",
    "",
    "echo [1/3] $stop Celery Worker...",
    "taskkill /F /FI `"WINDOWTITLE eq Celery Worker*`" /T 2>NUL",
    "if errorlevel 1 (echo   - Celery Worker $notrun) else (echo   [OK] Celery Worker $stopped)",
    "",
    "echo [2/3] $stop FastAPI Backend...",
    "taskkill /F /FI `"WINDOWTITLE eq FastAPI Backend*`" /T 2>NUL",
    "if errorlevel 1 (echo   - FastAPI Backend $notrun) else (echo   [OK] FastAPI Backend $stopped)",
    "",
    "echo [3/3] $stop$fe$svc...",
    "taskkill /F /FI `"WINDOWTITLE eq Frontend Dev Server*`" /T 2>NUL",
    "if errorlevel 1 (echo   - $fe$svc$notrun) else (echo   [OK] $fe$svc$stopped)",
    "",
    "echo.",
    "echo ========================================",
    "echo   $all$svc$stopped",
    "echo ========================================",
    "echo.",
    "pause",
    "exit /b 0"
)

$content = ($lines -join "`r`n") + "`r`n"
$bytes = $gbk.GetBytes($content)

$target = if ($args.Count -gt 0) { $args[0] } else { "C:\myspace\tz-data\stop.bat" }
[System.IO.File]::WriteAllBytes($target, $bytes)

# Verify by reading back as GBK
$raw = [System.IO.File]::ReadAllBytes($target)
$verify = $gbk.GetString($raw)
Write-Host "Written $($raw.Length) bytes to $target"
Write-Host ""
Write-Host "=== File content (GBK decoded) ==="
$verifyLines = $verify -split "`r`n"
for ($i = 0; $i -lt $verifyLines.Length; $i++) {
    Write-Host ("{0,2}: {1}" -f ($i+1), $verifyLines[$i])
}

# Verify specific GBK bytes
$correctGbk = $gbk.GetBytes("项目停止脚本")
$fileChunk = $raw[33..44]
Write-Host ""
Write-Host "GBK bytes at position 33-44: $($fileChunk -join ',')"
Write-Host "Expected GBK for '项目停止脚本': $($correctGbk -join ',')"
$match = $true
for ($i = 0; $i -lt $correctGbk.Length; $i++) {
    if ($fileChunk[$i] -ne $correctGbk[$i]) { $match = $false; break }
}
Write-Host "GBK match: $match"
