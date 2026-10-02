param(
  [Parameter(Mandatory=$true)][string]$Label,
  [Parameter(Mandatory=$true)][string]$OutName,
  [Parameter(Mandatory=$true)][string]$Args
)
# Launch one orchestrator cell as a detached process (0928 style) and record the covariates.
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$hostDir = "$wd\results\S26_night_1002_host"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$S = "<IP:PORT>"
$mem = (& $adb -s $S shell "grep MemAvailable /proc/meminfo") -replace "\s+", " "
$bat = (& $adb -s $S shell "dumpsys battery | grep -E '^  level:'") -replace "\s+", " "
$full = "tools\d1_experiment_orchestrator.py --serial $S $Args --output-dir $wd\results\$OutName"
$p = Start-Process -FilePath "py" -ArgumentList $full -WorkingDirectory $wd -RedirectStandardOutput "$wd\results\$OutName.console.txt" -RedirectStandardError "$wd\results\$OutName.stderr.txt" -WindowStyle Hidden -PassThru
$line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] $Label pid=" + $p.Id + " out=$OutName $mem $bat"
Add-Content -Path "$hostDir\session_log.txt" -Encoding UTF8 -Value $line
Add-Content -Path "$hostDir\session_log.txt" -Encoding UTF8 -Value ("    CMD: py " + $full)
$line
"pid=" + $p.Id
