$gbk = [System.Text.Encoding]::GetEncoding(936)
$TD = "C:\myspace\tz-data"
$T2 = "C:\myspace\tz2.0"

function Show-GBK {
    param([string]$path)
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $text = $gbk.GetString($bytes)
    Write-Host "=== $(Split-Path $path -Leaf) ($($bytes.Length) bytes) ==="
    $lines = $text -split "`r`n"
    $i = 0
    foreach ($line in $lines) {
        $i++
        if ($i -le 20) {
            Write-Host "$i`: $line"
        }
    }
    Write-Host ""
}

Show-GBK "$TD\stop.bat"
Show-GBK "$TD\start.bat"
Show-GBK "$TD\start_temp.bat"
Show-GBK "$T2\start-all.bat"
Show-GBK "$T2\stop.bat"
Show-GBK "$T2\port-manager.bat"
Show-GBK "$TD\backup-databases.bat"
