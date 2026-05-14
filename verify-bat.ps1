$gbk = [System.Text.Encoding]::GetEncoding(936)

$files = @(
    "C:\myspace\tz-data\stop.bat",
    "C:\myspace\tz-data\start.bat",
    "C:\myspace\tz-data\start-backend.bat",
    "C:\myspace\tz-data\start-frontend.bat",
    "C:\myspace\tz-data\quick-start.bat",
    "C:\myspace\tz-data\start_temp.bat",
    "C:\myspace\tz-data\backup-databases.bat",
    "C:\myspace\tz-data\optimize-databases.bat",
    "C:\myspace\tz2.0\start-all.bat",
    "C:\myspace\tz2.0\stop.bat",
    "C:\myspace\tz2.0\status.bat",
    "C:\myspace\tz2.0\stop-dev.bat",
    "C:\myspace\tz2.0\status-dev.bat",
    "C:\myspace\tz2.0\stop-prod.bat",
    "C:\myspace\tz2.0\status-prod.bat",
    "C:\myspace\tz2.0\health-check.bat",
    "C:\myspace\tz2.0\port-manager.bat"
)

Write-Host "=== GBK Encoding Verification ==="
Write-Host ""
$allOk = $true

foreach ($f in $files) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($f)
        $text = $gbk.GetString($bytes)
        $lines = $text -split "`r`n"
        $hasChinese = $false
        foreach ($line in $lines) {
            foreach ($ch in $line.ToCharArray()) {
                if ([int]$ch -gt 127) { $hasChinese = $true; break }
            }
            if ($hasChinese) { break }
        }
        $status = if ($hasChinese) { "OK (has Chinese)" } else { "OK (ASCII only)" }
        Write-Host "[$status] $($bytes.Length) bytes - $(Split-Path $f -Leaf)"

        # Check for chcp 936
        $hasChcp936 = ($lines -match "chcp 936").Count -gt 0
        if ($hasChinese -and -not $hasChcp936) {
            Write-Host "  WARNING: Has Chinese but no 'chcp 936' line!"
            $allOk = $false
        }
    } catch {
        Write-Host "[FAIL] $f - $_"
        $allOk = $false
    }
}

Write-Host ""
if ($allOk) {
    Write-Host "RESULT: All files passed GBK verification."
} else {
    Write-Host "RESULT: Some files have issues."
}

# Decode first 5 lines of start.bat as sample
Write-Host ""
Write-Host "=== Sample: start.bat decoded ==="
$bytes = [System.IO.File]::ReadAllBytes("C:\myspace\tz-data\start.bat")
$text = $gbk.GetString($bytes)
$text -split "`r`n" | Select-Object -First 5 | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "=== Sample: stop.bat decoded ==="
$bytes = [System.IO.File]::ReadAllBytes("C:\myspace\tz-data\stop.bat")
$text = $gbk.GetString($bytes)
$text -split "`r`n" | Select-Object -First 10 | ForEach-Object { Write-Host $_ }
