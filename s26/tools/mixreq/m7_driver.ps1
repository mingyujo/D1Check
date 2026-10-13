param([Parameter(Mandatory=$true)][ValidateSet("p","prep","k","s","smoke")][string]$Kind, [string]$Items = "", [ValidateSet("","A","B","C")][string]$Cond = "",
      [ValidateSet("","p","k","s")][string]$Smoke = "", [string]$ResultsBase = "", [int]$RetryRestS = 600, [switch]$InBlockCharge)
# M7 (2026-10-13) launcher for m7_driver.py (the logic lives in Python: conditions A/B/C · continuous HAL · gaps · retries). This file only
# builds the argument list and sends ALL output to a console file (never to a pipe — M6-A 사고 6). Start it detached and watch the files:
#   Start-Process powershell -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",<this>,"-Kind","k","-Items","4,5,6"
#   console: results\driver_<kind>_console_<MMdd_HHmmss>.txt · driver log: results\S26_M7_<KIND>\driver_log_<kind>.txt · events: results\S26_M7_driver_events.jsonl
# Serial only from $env:ANDROID_SERIAL (logged as <SERIAL>). No screen_off_timeout restore. ASCII only.
$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
if (-not $ResultsBase) { $ResultsBase = "$REPO\results" }
if (-not $env:ANDROID_SERIAL) { throw "ANDROID_SERIAL not set" }
Set-Location $REPO
New-Item -ItemType Directory -Force $ResultsBase | Out-Null
$console = "$ResultsBase\driver_" + $Kind + "_console_" + (Get-Date -Format "MMdd_HHmmss") + ".txt"
$argList = @("-X","utf8","$REPO\s26\tools\mixreq\m7_driver.py","--kind",$Kind,"--results-base",$ResultsBase,"--retry-rest-s",$RetryRestS)
if ($Items) { $argList += @("--items",$Items) }
if ($Cond) { $argList += @("--cond",$Cond) }
if ($Smoke) { $argList += @("--smoke",$Smoke) }
if ($InBlockCharge) { $argList += "--in-block-charge" }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] launcher kind=$Kind items=[$Items] cond=$Cond smoke=$Smoke console=$console" | Out-File -FilePath $console -Encoding UTF8 -Append
& py @argList *>> $console
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] launcher end rc=$LASTEXITCODE" | Out-File -FilePath $console -Encoding UTF8 -Append
exit $LASTEXITCODE
