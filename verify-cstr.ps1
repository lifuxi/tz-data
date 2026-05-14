$gbk = [System.Text.Encoding]::GetEncoding(936)

function CStr {
    param([string]$hex)
    $chars = @()
    $hex -split ' ' | ForEach-Object { $chars += [char][Convert]::ToInt32($_, 16) }
    return -join $chars
}

$TD = "C:\myspace\tz-data"

# Verify the CStr -> GBK pipeline for key characters
Write-Host "=== CStr to GBK verification ==="

$items = @(
    "672A 8FD0 884C",
    "5DF2 505C 6B62",
    "670D 52A1",
    "9879 76EE",
    "505C 6B62",
    "811A 672C",
    "6B63 5728",
    "524D 7AEF",
    "540E 7AEF",
    "542F 52A8",
    "5168 90E8",
    "6570 636E",
    "5E93",
    "7EDF 4E00",
    "7AEF 53E3",
    "7BA1 7406",
    "5907 4EFD",
    "9996 6B21"
)

foreach ($hex in $items) {
    $s = CStr $hex
    $bytes = $gbk.GetBytes($s)
    Write-Host "$hex -> $($bytes -join ',') = [$s]"
}

# Now verify against actual file bytes
Write-Host "`n=== File byte check: stop.bat ==="
$bytes = [System.IO.File]::ReadAllBytes("$TD\stop.bat")

# Get what CStr produces for key strings
$wyy = $gbk.GetBytes((CStr "672A 8FD0 884C"))  # 未运行
Write-Host "Expected WYY bytes: $($wyy -join ',')"

# Search
for ($i = 0; $i -le $bytes.Length - $wyy.Length; $i++) {
    $found = $true
    for ($k = 0; $k -lt $wyy.Length; $k++) {
        if ($bytes[$i+$k] -ne $wyy[$k]) { $found = $false; break }
    }
    if ($found) {
        Write-Host "Found at byte $i in stop.bat"
    }
}
