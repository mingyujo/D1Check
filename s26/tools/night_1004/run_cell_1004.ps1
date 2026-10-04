param(
  [Parameter(Mandatory=$true)][string]$Tag,
  [Parameter(Mandatory=$true)][string]$Label,
  [Parameter(Mandatory=$true)][string]$OutName,
  [Parameter(Mandatory=$true)][string]$CellArgs,
  [string]$ChainSha = "",
  [Parameter(Mandatory=$true)][int]$MinSoc,
  [Parameter(Mandatory=$true)][double]$Hours
)
# Night 1004: one cell, detached. SOC/time condition -> gate -> final dry-run (+chain SHA) -> launch -> wait -> validity. Single attempt
# (retry decisions are made by the session, per prompt rules). Serial only from $env:ANDROID_SERIAL, never written (<SERIAL>).
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_night_1004_host"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$S = $env:ANDROID_SERIAL
if (-not $S) { throw "ANDROID_SERIAL not set" }
$log = "$H\cell_${Tag}_log.txt"
function Log([string]$m) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $m
  for ($i = 0; $i -lt 5; $i++) {
    try { Add-Content -Path $log -Encoding UTF8 -Value ($line -replace [regex]::Escape($S), "<SERIAL>") -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 }
  }
}
function Soc() { $l = (& $adb -s $S shell "dumpsys battery | grep -E '^  level:'") -replace "\s+", " "; return [int](("$l" -split ":")[1].Trim()) }
Log "CELL START $Tag pid=$PID minSoc=$MinSoc hours=$Hours"
$soc = Soc
$endBy = (Get-Date).AddHours($Hours).AddMinutes(30)
Log "PRECHECK soc=$soc endBy+30m=$($endBy.ToString('HH:mm'))"
if ($soc -lt $MinSoc) { Log "SKIP: SOC $soc < $MinSoc"; exit 3 }
if ($endBy -gt (Get-Date "2026-10-05 10:00")) { Log "SKIP: time condition"; exit 4 }
$gout = & py -X utf8 "$wd\s26\tools\s26_start_gate.py" $S $Label "$H\gate_log_1004.csv" 2>&1
$grc = $LASTEXITCODE
Log ("GATE rc=$grc last=" + ($gout | Select-Object -Last 1))
if ($grc -ne 0) { Log "GATE BLOCKED rc=$grc"; exit 2 }
$soc2 = Soc
$endBy2 = (Get-Date).AddHours($Hours).AddMinutes(30)
Log "POSTGATE soc=$soc2 endBy+30m=$($endBy2.ToString('HH:mm'))"
if ($soc2 -lt $MinSoc) { Log "SKIP after gate: SOC $soc2 < $MinSoc"; exit 3 }
if ($endBy2 -gt (Get-Date "2026-10-05 10:00")) { Log "SKIP after gate: time condition"; exit 4 }
$dr = & "$H\dryrun_1004.ps1" -Label "${Label}_final" -OutName $OutName -CellArgs $CellArgs
Log "DRYRUN $dr"
if (-not ("$dr" -match "exit=0")) { Log "DRYRUN FAILED -> not launched"; exit 5 }
if ($ChainSha) {
  $f = (("$dr" -split "file=")[1] -split " lines")[0]
  $hit = (Select-String -Path $f -Pattern ('"sha256": "' + $ChainSha + '"') | Measure-Object).Count
  Log "CHAIN SHA match lines=$hit"
  if ($hit -lt 1) { Log "CHAIN SHA MISMATCH -> not launched"; exit 6 }
}
$lr = & "$H\launch_cell_1004.ps1" -Label $Label -OutName $OutName -Args $CellArgs
$pidLine = ($lr | Where-Object { "$_" -match "^pid=\d+" } | Select-Object -Last 1)
$opid = [int](("$pidLine" -replace "pid=", ""))
Log "LAUNCHED $Label -> $OutName pid=$opid"
Start-Sleep -Seconds 5
while (Get-Process -Id $opid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 15 }
Log "ORCH EXITED pid=$opid"
$mp = "$wd\results\$OutName\experiment_manifest.json"
if (Test-Path $mp) {
  try {
    $m = Get-Content -Raw -Encoding UTF8 $mp | ConvertFrom-Json
    $r = $m.runs[0]; $v = $r.validation
    Log "DONE manifest_status=$($m.status) halt=$($m.halt_reason) slot=$($r.status) attempts=$($r.attempts) valid=$($v.valid) failed=$(($v.failed_checks) -join ',') flags=$(($v.chain_conservation_flags) -join ',') error=$($r.error)"
  } catch { Log "DONE manifest parse error: $_" }
} else { Log "DONE no manifest" }
Log "CELL END $Tag"
