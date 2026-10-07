# V3 v2 (P1h 1008 00:4x): launch the last B2 cell (B2_base block 2 -> "짝 세션 다름") with the unchanged driver, after the unplug is seen.
# Serial from `adb devices` (single device) into $env:ANDROID_SERIAL; never written. Labels continue at 13.
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_host_v3_1007"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$devs = @((& $adb devices) | Select-Object -Skip 1 | Where-Object { $_ -match '\sdevice$' })
if ($devs.Count -ne 1) { Add-Content -Encoding UTF8 "$H\after_charge_log.txt" ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] last-B2 launch: devices=$($devs.Count) -> not launched"); exit 2 }
$env:ANDROID_SERIAL = $devs[0].Split("`t")[0]
Copy-Item "$H\driver_state_v3b_B2.json" "$H\driver_state_v3b_B2_part1.json" -Force
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"$wd\s26\tools\v3_1006\session_driver_v3b.ps1",'-Cond','B2','-SessionEnd','"2026-10-08 12:00"','-MinSocCell','30','-SeqStart','13','-QueueSpec','B2_base:2' -WorkingDirectory $wd -WindowStyle Hidden -PassThru
Add-Content -Encoding UTF8 "$H\after_charge_log.txt" ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] last-B2 driver launched pid=$($p.Id) (B2_base:2, label 13)")
"pid=$($p.Id)"
