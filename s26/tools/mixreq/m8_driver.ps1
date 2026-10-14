param([Parameter(Mandatory=$true)][ValidateSet("smoke","p0","dev")][string]$Stage, [int]$Block = 1, [string]$Only = "", [string]$ResultsBase = "", [int]$RetryRestS = 600, [int]$ChargeToSoc = 60)
# M8 (2026-10-14) launcher for m8_driver.py (logic in Python: Tref gate · charge rule · HAL · retries · lock · process tree kill). This file only
# builds the argument list and sends ALL output to a console file (never to a pipe). Start it detached and watch the files:
#   Start-Process powershell -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",<this>,"-Stage","dev","-Block","1"
#   console: results\driver_m8_<stage>_console_<MMdd_HHmmss>.txt · driver log: results\S26_M8_<STAGE>\driver_log_<stage>.txt · events: results\S26_M8_driver_events.jsonl
#   prestart ledger: results\S26_M8_prestart_ledger.jsonl · Tref: results\S26_M8_tref.json · lock: results\S26_M8_driver.lock (pid)
# Stop: create no file — kill the driver process; it kills the session subprocess tree (taskkill /T) and stops HAL. Serial only from $env:ANDROID_SERIAL (logged as <SERIAL>). ASCII only.
$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
if (-not $ResultsBase) { $ResultsBase = "$REPO\results" }
if (-not $env:ANDROID_SERIAL) { throw "ANDROID_SERIAL not set" }
Set-Location $REPO
New-Item -ItemType Directory -Force $ResultsBase | Out-Null
$console = "$ResultsBase\driver_m8_" + $Stage + "_console_" + (Get-Date -Format "MMdd_HHmmss") + ".txt"
$argList = @("-X","utf8","$REPO\s26\tools\mixreq\m8_driver.py","--stage",$Stage,"--block",$Block,"--results-base",$ResultsBase,"--retry-rest-s",$RetryRestS,"--charge-to-soc",$ChargeToSoc)
if ($Only) { $argList += @("--only",$Only) }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] launcher stage=$Stage block=$Block only=[$Only] console=$console" | Out-File -FilePath $console -Encoding UTF8 -Append
& py @argList 2>&1 | Out-File -FilePath $console -Encoding UTF8 -Append
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] launcher end rc=$LASTEXITCODE" | Out-File -FilePath $console -Encoding UTF8 -Append
exit $LASTEXITCODE
