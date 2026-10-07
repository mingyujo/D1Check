# V3 v2 (P1h 1007) after the A2 -> B2 charge: (1) the A2 cell left by SOC (A2_ours_b2, block 2 -> "짝 세션 다름") then (2) B2 4 cells.
# Runs session_driver_v3b.ps1 twice, unchanged. B2 starts only when the A2 driver ended with no stop reason (prompt: a failed retry or
# adb loss stops the measurement). Labels: A2 continues at 07 (06 = gate-blocked try 19:38, phone was plugged), B2 starts at 10 (gaps allowed; labels stay unique).
# Serial only from $env:ANDROID_SERIAL.
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$T = "$wd\s26\tools\v3_1006"
$H = "$wd\results\S26_host_v3_1007"
$wlog = "$H\after_charge_log.txt"
function WLog([string]$m) { Add-Content -Encoding UTF8 -Path $wlog -Value ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $m) }
if (-not $env:ANDROID_SERIAL) { WLog "ANDROID_SERIAL not set -> exit"; exit 2 }
WLog "WRAPPER START pid=${PID} - A2 leftover (A2_ours block 2) then B2"
& "$T\session_driver_v3b.ps1" -Cond A2 -SessionEnd "2026-10-08 12:00" -MinSocCell 30 -SeqStart 7 -QueueSpec "A2_ours:2"
$stA = Get-Content -Raw -Encoding UTF8 "$H\driver_state_v3b_A2.json" | ConvertFrom-Json
WLog "A2 leftover driver ended: stop='$($stA.stop_reason)' cells=$(($stA.cells.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')"
if ($stA.stop_reason) { WLog "B2 NOT started (A2 stop reason) -> WRAPPER END"; exit 3 }
& "$T\session_driver_v3b.ps1" -Cond B2 -SessionEnd "2026-10-08 12:00" -MinSocCell 30 -SeqStart 10
$stB = Get-Content -Raw -Encoding UTF8 "$H\driver_state_v3b_B2.json" | ConvertFrom-Json
WLog "B2 driver ended: stop='$($stB.stop_reason)' cells=$(($stB.cells.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')"
WLog "WRAPPER END"
