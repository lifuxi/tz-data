$gbk = [System.Text.Encoding]::GetEncoding(936)

function CStr {
    param([string]$hex)
    $chars = @()
    $hex -split ' ' | ForEach-Object { $chars += [char][Convert]::ToInt32($_, 16) }
    return -join $chars
}

function Verify-String {
    param([string]$path, [string]$chinese)
    $expected = $gbk.GetBytes($chinese)
    $bytes = [System.IO.File]::ReadAllBytes($path)
    # Search for expected byte sequence
    for ($i = 0; $i -le $bytes.Length - $expected.Length; $i++) {
        $found = $true
        for ($k = 0; $k -lt $expected.Length; $k++) {
            if ($bytes[$i+$k] -ne $expected[$k]) { $found = $false; break }
        }
        if ($found) {
            Write-Host "[OK] Found at byte $i in $(Split-Path $path -Leaf)"
            return $true
        }
    }
    Write-Host "[FAIL] NOT FOUND in $(Split-Path $path -Leaf) (expected: $($expected -join ','))"
    return $false
}

$TD = "C:\myspace\tz-data"
$T2 = "C:\myspace\tz2.0"

Write-Host "=== Chinese String Verification ==="
Write-Host ""

# stop.bat checks
Write-Host "stop.bat:"
Verify-String "$TD\stop.bat" (CStr "9879 76EE 505C 6B62 811A 672C")    # 项目停止脚本
Verify-String "$TD\stop.bat" (CStr "6B63 5728 505C 6B62")              # 正在停止
Verify-String "$TD\stop.bat" (CStr "5168 90E8 670D 52A1 5DF2 505C 6B62") # 全部服务已停止

# start.bat checks
Write-Host "start.bat:"
Verify-String "$TD\start.bat" (CStr "9879 76EE 542F 52A8 811A 672C")    # 项目启动脚本
Verify-String "$TD\start.bat" (CStr "6B63 5728 542F 52A8")              # 正在启动

# start-all.bat checks
Write-Host "start-all.bat:"
Verify-String "$T2\start-all.bat" (CStr "5B8C 6574 542F 52A8 811A 672C") # 完整启动脚本

# tz2.0 stop.bat checks
Write-Host "tz2.0 stop.bat:"
Verify-String "$T2\stop.bat" (CStr "505C 6B62 5168 90E8 670D 52A1")     # 停止全部服务

# port-manager.bat checks
Write-Host "port-manager.bat:"
Verify-String "$T2\port-manager.bat" (CStr "7EDF 4E00 7AEF 53E3 7BA1 7406") # 统一端口管理

# start-frontend.bat checks
Write-Host "start-frontend.bat:"
Verify-String "$TD\start-frontend.bat" (CStr "9996 6B21 8FD0 884C")      # 首次运行

# backup-databases.bat checks
Write-Host "backup-databases.bat:"
Verify-String "$TD\backup-databases.bat" (CStr "6570 636E 5E93 5907 4EFD") # 数据库备份
