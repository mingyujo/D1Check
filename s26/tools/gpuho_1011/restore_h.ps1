param([switch]$Full)
# GPU holdout (GH 1011) copy of s26\tools\energy_1008\restore_c.ps1 — changed only: host dir S26_host_gpuho_1011 · settings log phone_settings_log_h.txt ·
#   brightness restore from brightness_orig_h.json · stop files: watchers always, keep-awake (keepawake_h / keepawake_h_screen) only with -Full ·
#   screen_off_timeout is KEPT at 86400000 (GH prompt 5단계-1 · 영훈 10/9 결정) — not restored to 600000.
# Airplane mode and DND are NOT touched (left on). Serial only from $env:ANDROID_SERIAL, never written.
$H = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_gpuho_1011"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER) { throw "ANDROID_SERIAL not set" }
$stops = @("phone_watch.stop", "skin_watch.stop")
if ($Full) { $stops += @("keepawake_h.stop", "keepawake_h_screen.stop") }
foreach ($stopName in $stops) { New-Item -ItemType File -Force "$H\$stopName" | Out-Null }
& $adb -s $DEVSER shell "settings put system screen_off_timeout 86400000" 2>&1 | Out-Null
$bnote = "no brightness_orig_h.json"
if (Test-Path "$H\brightness_orig_h.json") {
  $orig = Get-Content -Raw -Encoding UTF8 "$H\brightness_orig_h.json" | ConvertFrom-Json
  & $adb -s $DEVSER shell "settings put system screen_brightness_mode $($orig.screen_brightness_mode)" 2>&1 | Out-Null
  & $adb -s $DEVSER shell "settings put system screen_brightness $($orig.screen_brightness)" 2>&1 | Out-Null
  $bnote = "brightness restored to mode=$($orig.screen_brightness_mode) brightness=$($orig.screen_brightness) (recorded $($orig.recorded))"
}
$vals = @(& $adb -s $DEVSER shell "settings get global airplane_mode_on; settings get global wifi_on; settings get global zen_mode; settings get system screen_off_timeout; settings get system screen_brightness_mode; settings get system screen_brightness")
$batt = (@(& $adb -s $DEVSER shell "dumpsys battery | grep -E '^  (AC|USB|Wireless) powered|^  level|^  temperature'") | ForEach-Object { "$_".Trim() }) -join " ; "
$line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] restore (GH, full=$Full): stop files " + ($stops -join "/") + " ; screen_off_timeout kept -> " + $vals[3] + " ; " + $bnote + " -> now mode=" + $vals[4] + " brightness=" + $vals[5] + " ; airplane_mode_on=" + $vals[0] + " wifi_on=" + $vals[1] + " zen_mode=" + $vals[2] + " (not touched) ; battery: " + $batt
$line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>"
Add-Content -Encoding UTF8 "$H\phone_settings_log_h.txt" $line
$line
