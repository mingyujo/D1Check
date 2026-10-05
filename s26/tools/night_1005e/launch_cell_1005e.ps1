param(
  [Parameter(Mandatory=$true)][string]$Label,
  [Parameter(Mandatory=$true)][string]$OutName,
  [Parameter(Mandatory=$true)][string]$Args
)
# NIGHT 1005e (copy of the 1005n file, host dir only; 1005n was a copy of launch_cell_1005.ps1, host dir only): launch one orchestrator cell as a detached process and record covariates.
# The wireless adb address is read from $env:ANDROID_SERIAL and is NEVER written to any file (logged as <SERIAL>).
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$hostDir = "$wd\results\S26_host_1005e"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$S = $env:ANDROID_SERIAL
if (-not $S) { throw "ANDROID_SERIAL not set" }
$mem = (& $adb -s $S shell "grep MemAvailable /proc/meminfo") -replace "\s+", " "
$bat = (& $adb -s $S shell "dumpsys battery | grep -E '^  level:'") -replace "\s+", " "
$full = "-X utf8 tools\d1_experiment_orchestrator.py --serial $S $Args --output-dir $wd\results\$OutName"
$p = Start-Process -FilePath "py" -ArgumentList $full -WorkingDirectory $wd -RedirectStandardOutput "$wd\results\$OutName.console.txt" -RedirectStandardError "$wd\results\$OutName.stderr.txt" -WindowStyle Hidden -PassThru
$logged = $full -replace [regex]::Escape($S), "<SERIAL>"
$line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] $Label pid=" + $p.Id + " out=$OutName $mem $bat"
Add-Content -Path "$hostDir\session_log.txt" -Encoding UTF8 -Value $line
Add-Content -Path "$hostDir\session_log.txt" -Encoding UTF8 -Value ("    CMD: py " + $logged)
$line
"pid=" + $p.Id
