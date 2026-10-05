param(
  [Parameter(Mandatory=$true)][string]$Tag,
  [Parameter(Mandatory=$true)][string]$Label,
  [Parameter(Mandatory=$true)][string]$OutName,
  [Parameter(Mandatory=$true)][string]$CellArgs,
  [string]$ChainSha = "",
  [Parameter(Mandatory=$true)][int]$MinSoc,
  [Parameter(Mandatory=$true)][double]$Hours,
  [Parameter(Mandatory=$true)][ValidateSet("required","mark")][string]$LowerPolicy,
  [string]$Deadline = "2026-10-06 11:00"
)
# NIGHT 1005n (copy of run_cell_1005.ps1 - host dir / gate csv / deadline / dry-run duration check only):
# SOC/time condition -> gate (upper, s26_start_gate.py unchanged) -> lower bound on the HAL values the gate read
# (SKIN >= 29.1 and BAT >= 27.5, prereg night 1005 s1) -> final dry-run (+chain SHA, duration_s 900) -> launch -> wait -> validity.
# Single attempt. Exit: 0 ran, 2 gate blocked, 3 SOC, 4 time, 5 dry-run, 6 chain SHA, 7 lower fail (required).
# Serial only from $env:ANDROID_SERIAL, never written (<SERIAL>).
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_night_1005n_host"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$S = $env:ANDROID_SERIAL
if (-not $S) { throw "ANDROID_SERIAL not set" }
$log = "$H\cell_${Tag}_log.txt"
$gateCsv = "$H\gate_log_1005n.csv"
function Log([string]$m) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $m
  for ($i = 0; $i -lt 5; $i++) {
    try { Add-Content -Path $log -Encoding UTF8 -Value ($line -replace [regex]::Escape($S), "<SERIAL>") -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 }
  }
}
function Soc() { $l = (& $adb -s $S shell "dumpsys battery | grep -E '^  level:'") -replace "\s+", " "; return [int](("$l" -split ":")[1].Trim()) }
$dl = Get-Date $Deadline
Log "CELL START $Tag label=$Label out=$OutName pid=$PID minSoc=$MinSoc hours=$Hours lower=$LowerPolicy deadline=$Deadline"
$soc = Soc
$endBy = (Get-Date).AddHours($Hours).AddMinutes(30)
Log "PRECHECK soc=$soc endBy+30m=$($endBy.ToString('MM-dd HH:mm'))"
if ($soc -lt $MinSoc) { Log "SKIP: SOC $soc < $MinSoc"; exit 3 }
if ($endBy -gt $dl) { Log "SKIP: time condition"; exit 4 }
$gout = & py -X utf8 "$wd\s26\tools\s26_start_gate.py" $S $Label "$H\gate_upper_raw_1005n.csv" 2>&1
$grc = $LASTEXITCODE
$last = "$($gout | Select-Object -Last 1)"
Log ("GATE rc=$grc last=" + $last)
if (-not (Test-Path $gateCsv)) { Add-Content -Path $gateCsv -Encoding UTF8 -Value "label,local_time,waited_s,SKIN,AP,BAT,thermal_status,soc,plugged,upper_pass,lower_skin_ge_29.1,lower_bat_ge_27.5,lower_pass,lower_policy,action" }
if ($grc -ne 0) {
  Add-Content -Path $gateCsv -Encoding UTF8 -Value ((($last -split "\s+") -join ",") + ",,,,$LowerPolicy,gate_blocked")
  Log "GATE BLOCKED rc=$grc"; exit 2
}
$f = $last -split "\s+"
$skin = [double]$f[3]; $bat = [double]$f[5]
$okS = $skin -ge 29.1; $okB = $bat -ge 27.5; $lowOk = $okS -and $okB
$action = if ($lowOk) { "run" } elseif ($LowerPolicy -eq "required") { "not_run_lower_required" } else { "run_marked_lower_fail" }
Add-Content -Path $gateCsv -Encoding UTF8 -Value ((($f) -join ",") + ",$okS,$okB,$lowOk,$LowerPolicy,$action")
Log "LOWER skin=$skin(>=29.1:$okS) bat=$bat(>=27.5:$okB) pass=$lowOk policy=$LowerPolicy -> $action"
if (-not $lowOk -and $LowerPolicy -eq "required") { exit 7 }
$soc2 = Soc
$endBy2 = (Get-Date).AddHours($Hours).AddMinutes(30)
Log "POSTGATE soc=$soc2 endBy+30m=$($endBy2.ToString('MM-dd HH:mm'))"
if ($soc2 -lt $MinSoc) { Log "SKIP after gate: SOC $soc2 < $MinSoc"; exit 3 }
if ($endBy2 -gt $dl) { Log "SKIP after gate: time condition"; exit 4 }
$dr = & "$H\dryrun_1005n.ps1" -Label "${Label}_final" -OutName $OutName -CellArgs $CellArgs
Log "DRYRUN $dr"
if (-not ("$dr" -match "exit=0")) { Log "DRYRUN FAILED -> not launched"; exit 5 }
$df = (("$dr" -split "file=")[1] -split " lines")[0]
if ($ChainSha) {
  $hit = (Select-String -Path $df -Pattern ('"sha256": "' + $ChainSha + '"') | Measure-Object).Count
  Log "CHAIN SHA match lines=$hit"
  if ($hit -lt 1) { Log "CHAIN SHA MISMATCH -> not launched"; exit 6 }
}
$dur = (Select-String -Path $df -Pattern '"duration_s": 900' | Measure-Object).Count
Log "DRYRUN duration_s 900 lines=$dur"
if ($dur -lt 1) { Log "DRYRUN duration_s != 900 -> not launched"; exit 5 }
$lr = & "$H\launch_cell_1005n.ps1" -Label $Label -OutName $OutName -Args $CellArgs
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
exit 0
