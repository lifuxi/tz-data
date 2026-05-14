$gbk = [System.Text.Encoding]::GetEncoding(936)

function CStr {
    param([string]$hex)
    $chars = @()
    $hex -split ' ' | ForEach-Object { $chars += [char][Convert]::ToInt32($_, 16) }
    return -join $chars
}

$TD = "C:\myspace\tz-data"
$T2 = "C:\myspace\tz2.0"

function Search-Bytes {
    param([string]$path, [byte[]]$pattern)
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $found_count = 0
    for ($i = 0; $i -le $bytes.Length - $pattern.Length; $i++) {
        $found = $true
        for ($k = 0; $k -lt $pattern.Length; $k++) {
            if ($bytes[$i+$k] -ne $pattern[$k]) { $found = $false; break }
        }
        if ($found) {
            Write-Host "  Found at byte $i in $(Split-Path $path -Leaf)"
            $found_count++
        }
    }
    if ($found_count -eq 0) {
        Write-Host "  NOT FOUND: pattern $($pattern -join ',') in $(Split-Path $path -Leaf)"
    }
}

Write-Host "=== stop.bat checks ==="
Search-Bytes "$TD\stop.bat" @(206,215,212,190,186,194)  # 未运行
Search-Bytes "$TD\stop.bat" @(200,219,205,163,214,185)  # 已停止
Search-Bytes "$TD\stop.bat" @(200,171,177,231)          # 全部
Search-Bytes "$TD\stop.bat" @(183,191,210,241)          # 服务

Write-Host "`n=== port-manager.bat checks ==="
Search-Bytes "$T2\port-manager.bat" @(214,191,200,187)  # 统一
Search-Bytes "$T2\port-manager.bat" @(181,169,191,233)  # 端口
Search-Bytes "$T2\port-manager.bat" @(185,184,192,173)  # 管理

Write-Host "`n=== backup-databases.bat checks ==="
Search-Bytes "$TD\backup-databases.bat" @(202,173,190,211)  # 数据
Search-Bytes "$TD\backup-databases.bat" @(191,162)          # 库
Search-Bytes "$TD\backup-databases.bat" @(207,196,183,238)  # 备份

Write-Host "`n=== port-manager.bat: all high bytes ==="
$bytes = [System.IO.File]::ReadAllBytes("$T2\port-manager.bat")
$hi = ($bytes | Where-Object { $_ -gt 127 })
Write-Host "  High bytes: $($hi -join ',')"
Write-Host "  Count: $($hi.Count)"
