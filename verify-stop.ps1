# Quick verification of stop.bat encoding
$raw = [System.IO.File]::ReadAllBytes("C:\myspace\tz-data\stop.bat")
Write-Host "File size: $($raw.Length) bytes"

# Expected GBK bytes for the Chinese text on line 4 (after "tz-data ")
$expected = @(207,238,196,191,205,163,214,185,189,197,177,190)

# Find position of "tz-data " in the file
$found = $false
for ($i = 0; $i -lt $raw.Length - 8; $i++) {
    if ($raw[$i] -eq 116 -and $raw[$i+1] -eq 122 -and $raw[$i+2] -eq 45 -and $raw[$i+3] -eq 100 -and $raw[$i+4] -eq 97 -and $raw[$i+5] -eq 116 -and $raw[$i+6] -eq 97 -and $raw[$i+7] -eq 32) {
        $pos = $i + 8
        $actual = $raw[$pos..($pos+11)]
        Write-Host "Chinese bytes: $($actual -join ',')"
        Write-Host "Expected bytes: $($expected -join ',')"
        $match = $true
        for ($k = 0; $k -lt 12; $k++) {
            if ($actual[$k] -ne $expected[$k]) { $match = $false }
        }
        if ($match) {
            Write-Host "RESULT: GBK encoding is CORRECT. stop.bat should display Chinese properly."
        } else {
            Write-Host "RESULT: GBK encoding is WRONG. File needs to be rewritten."
        }
        $found = $true
        break
    }
}
if (-not $found) {
    Write-Host "ERROR: Could not find 'tz-data ' in file"
}
