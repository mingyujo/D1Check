param([switch]$Full)
# Energy C (P1i 1008) copy of s26\tools\v3_1006\restore_v3b.ps1 — changed only: host dir S26_host_energy_1008 · settings log phone_settings_log_c.txt ·
#   + brightness restore from brightness_orig_c.json (energy prereg v1 §6-6) · stop files: watchers always, keep-awake (keepawake_c / keepawake_c_screen)
#   only with -Full (session end or measurement stop; between C1 and C2 the PC must stay awake through the charge).
# Phone screen_off_timeout -> 600000, record airplane / wifi / zen / battery. Airplane mode and DND are NOT touched (prompt 4단계: left on).
# Serial only from $env:ANDROID_SERIAL, never written.
$H = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_energy_1008"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER) { throw "ANDROID_SERIAL not set" }
$stops = @("phone_watch.stop", "skin_watch.stop")
if ($Full) { $stops += @("keepawake_c.stop", "keepawake_c_screen.stop") }
foreach ($stopName in $stops) { New-Item -ItemType File -Force "$H\$stopName" | Out-Null }
& $adb -s $DEVSER shell "settings put system screen_off_timeout 600000" 2>&1 | Out-Null
$bnote = "no brightness_orig_c.json"
if (Test-Path "$H\brightness_orig_c.json") {
  $orig = Get-Content -Raw -Encoding UTF8 "$H\brightness_orig_c.json" | ConvertFrom-Json
  & $adb -s $DEVSER shell "settings put system screen_brightness_mode $($orig.screen_brightness_mode)" 2>&1 | Out-Null
  & $adb -s $DEVSER shell "settings put system screen_brightness $($orig.screen_brightness)" 2>&1 | Out-Null
  $bnote = "brightness restored to mode=$($orig.screen_brightness_mode) brightness=$($orig.screen_brightness) (recorded $($orig.recorded))"
}
$vals = @(& $adb -s $DEVSER shell "settings get global airplane_mode_on; settings get global wifi_on; settings get global zen_mode; settings get system screen_off_timeout; settings get system screen_brightness_mode; settings get system screen_brightness")
$batt = (@(& $adb -s $DEVSER shell "dumpsys battery | grep -E '^  (AC|USB|Wireless) powered|^  level|^  temperature'") | ForEach-Object { "$_".Trim() }) -join " ; "
$line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] restore (energy C, full=$Full): stop files " + ($stops -join "/") + " ; screen_off_timeout -> " + $vals[3] + " ; " + $bnote + " -> now mode=" + $vals[4] + " brightness=" + $vals[5] + " ; airplane_mode_on=" + $vals[0] + " wifi_on=" + $vals[1] + " zen_mode=" + $vals[2] + " (not touched) ; battery: " + $batt
$line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>"
Add-Content -Encoding UTF8 "$H\phone_settings_log_c.txt" $line
$line
