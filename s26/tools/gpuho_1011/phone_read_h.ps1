# GPU holdout (GH 1011) copy of s26\tools\energy_1008\phone_read_c.ps1 - changed only: host dir S26_host_gpuho_1011 . csv / stop / log names *_h . helper names *_h (logic unchanged).
# phone_read_c.ps1 - energy C (P1i) stage 0 item 5: read-only phone check.
# Serial comes only from $env:ANDROID_SERIAL; log never contains address/serial.
param([string]$Tag = "stage0")
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER) { Write-Output "NO SERIAL"; exit 2 }
$H = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_gpuho_1011"
New-Item -ItemType Directory -Force $H | Out-Null
function Q([string]$cmd) { return ("$(& $adb -s $DEVSER shell $cmd 2>$null)").Trim() }
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss K"
$apk = Q "pm path com.example.d1check.npurunner"
$apkPath = ($apk -replace '^package:', '').Trim()
$apkSha = ""
if ($apkPath) { $apkSha = Q "sha256sum $apkPath" }
$bat = (& $adb -s $DEVSER shell "dumpsys battery" 2>$null)
$soc = (($bat | Select-String '^\s+level:') -replace '\s+', ' ').Trim()
$plg = (($bat | Select-String '^\s+(AC|USB|Wireless) powered:') | ForEach-Object { ($_ -replace '\s+', ' ').Trim() }) -join ' ; '
$lines = @(
  "[$ts] $Tag (GH stage 0 / 4-1, read only)",
  "  npurunner apk sha256 = $(($apkSha -split '\s+')[0])",
  "  screen_brightness_mode (original) = $(Q 'settings get system screen_brightness_mode')",
  "  screen_brightness (original) = $(Q 'settings get system screen_brightness')",
  "  screen_off_timeout = $(Q 'settings get system screen_off_timeout')",
  "  airplane_mode_on = $(Q 'settings get global airplane_mode_on')",
  "  wifi_on = $(Q 'settings get global wifi_on')",
  "  zen_mode = $(Q 'settings get global zen_mode')",
  "  df /data = $((Q 'df -h /data') -replace '\s+', ' ')",
  "  battery $soc ; $plg"
)
Add-Content -Encoding UTF8 "$H\phone_settings_log_h.txt" ($lines -join "`r`n")
$lines | ForEach-Object { Write-Output $_ }
