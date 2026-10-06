# N4 1006r step 3 restore (same items as 1005e): stop PC keep-awake / host SKIN watch / call-screen watch (stop files),
# phone screen_off_timeout -> 600000, record airplane / wifi / zen / battery. Airplane mode and DND are NOT touched.
# Serial only from $env:ANDROID_SERIAL (set from `adb devices`), never written.
$H = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_1006r"
if (-not $env:ANDROID_SERIAL) { . "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\s26\tools\night_1005e\serial_1005e.ps1" }
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
foreach ($stopName in @("phone_watch.stop", "skin_watch.stop", "keepawake.stop")) { New-Item -ItemType File -Force "$H\$stopName" | Out-Null }
& $adb -s $DEVSER shell "settings put system screen_off_timeout 600000" 2>&1 | Out-Null
$vals = @(& $adb -s $DEVSER shell "settings get global airplane_mode_on; settings get global wifi_on; settings get global zen_mode; settings get system screen_off_timeout")
$batt = (@(& $adb -s $DEVSER shell "dumpsys battery | grep -E '^  (AC|USB|Wireless) powered|^  level|^  temperature'") | ForEach-Object { "$_".Trim() }) -join " ; "
$line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] restore (step 3, after GB_b2_re orchestrator exit, before reports): stop files keepawake/skin/phone watch ; screen_off_timeout -> " + $vals[3] + " ; airplane_mode_on=" + $vals[0] + " wifi_on=" + $vals[1] + " zen_mode=" + $vals[2] + " (not touched) ; battery: " + $batt
if ($DEVSER) { $line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>" }
Add-Content -Encoding UTF8 "$H\phone_settings_log_1006r.txt" $line
$line
