# NIGHT 1005e: dot-source to set $env:ANDROID_SERIAL from the single IP:PORT entry of `adb devices` (never printed or written).
# Drops an mDNS `_adb-tls-connect` duplicate if present.
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$mdns = @(& $adb devices | Select-String '_adb-tls-connect' | ForEach-Object { ("$_" -split '\s+')[0] })
foreach ($x in $mdns) { & $adb disconnect $x 2>&1 | Out-Null }
$ser = @(& $adb devices | Select-String '^\d+\.\d+\.\d+\.\d+:\d+\s+device$' | ForEach-Object { ("$_" -split '\s+')[0] })
if ($ser.Count -eq 1) { $env:ANDROID_SERIAL = $ser[0] } else { Write-Output "SERIAL count=$($ser.Count)" }
