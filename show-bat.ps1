$gbk = [System.Text.Encoding]::GetEncoding(936)

function CStr {
    param([string]$hex)
    $chars = @()
    $hex -split ' ' | ForEach-Object { $chars += [char][Convert]::ToInt32($_, 16) }
    return -join $chars
}

function Check-File {
    param([string]$path)
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $text = $gbk.GetString($bytes)
    $lines = $text -split "`r`n"
    $i = 0
    foreach ($line in $lines) {
        $i++
        $hi = 0
        foreach ($ch in $line.ToCharArray()) {
            if ([int]$ch -gt 127) { $hi++ }
        }
        if ($hi -gt 0) {
            Write-Host "  L$i ($hi hi): $line"
        }
    }
}

$TD = "C:\myspace\tz-data"
$T2 = "C:\myspace\tz2.0"

Write-Host "=== stop.bat ==="
Check-File "$TD\stop.bat"

Write-Host "`n=== start.bat ==="
Check-File "$TD\start.bat"

Write-Host "`n=== start_temp.bat ==="
Check-File "$TD\start_temp.bat"

Write-Host "`n=== tz2.0 port-manager.bat ==="
Check-File "$T2\port-manager.bat"

Write-Host "`n=== tz2.0 backup-databases.bat ==="
# Actually this is in tz-data
Check-File "$TD\backup-databases.bat"
