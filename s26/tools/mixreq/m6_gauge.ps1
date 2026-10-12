param([Parameter(Mandatory=$true)][string]$Run, [int]$Attempt = 1, [int]$LoopOnlyS = 0, [switch]$DryRun, [string]$ResultsBase = "")
# M6-A gauge diagnostic E: one run of GaugeDiagActivity (E1 / E2 / E3 / ET / E_smoke) via m6_gauge.py (start conditions, push, logcat,
# watches, [E-T device loop], am start, pull, gauge_validated.json). ET = with the device-side loop:
#   adb shell "while true; do cat /proc/uptime; dumpsys thermalservice | sed -n '/Current temperatures from HAL/,/Current cooling devices/p';
#              for z in /sys/class/thermal/thermal_zone*; do echo $z $(cat $z/type 2>&1) $(cat $z/temp 2>&1); done; done"  -> host\et_loop.txt
#   (unreadable files are recorded as the shell prints them). -LoopOnlyS N = the E-T loop alone for N s (smoke: output form / read interval).
# The E sequence with retry / invalid_twice is m6_driver.ps1 -Kind e. Serial only from $env:ANDROID_SERIAL. No screen restore. ASCII only.
$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
if (-not $ResultsBase) { $ResultsBase = "$REPO\results" }
Set-Location $REPO
$argList = @("-X","utf8","$REPO\s26\tools\mixreq\m6_gauge.py","--plan","$REPO\s26\results\m6_1012\plan_m6e","--run",$Run,"--attempt",$Attempt,
             "--results","$ResultsBase\S26_M6_GAUGE","--runlog","$ResultsBase\S26_M6_runs.jsonl")
if ($Run -eq "ET") { $argList += "--et-loop" }
if ($LoopOnlyS -gt 0) { $argList += @("--loop-only-s", $LoopOnlyS) }
if ($DryRun) { $argList += "--dry-run" }
& py @argList
exit $LASTEXITCODE
