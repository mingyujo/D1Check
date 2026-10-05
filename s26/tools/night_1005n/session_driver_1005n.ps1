param([int]$StartBlock = 1, [string]$StartQueue = "", [int]$EmergStart = 0, [switch]$DryRun)
# NIGHT 1005n session driver (after session_driver_1005.ps1, with the 07:40 $c/$C bug avoided: every name below is unique ignoring case).
# Prereg night 1005 s2 order: block 1 = NA -> GB -> NB -> GA, block 2 = GA -> NB -> GB -> NA. Block 2 only if all 4 block-1 cells are valid.
# s1 lower rule: upper pass + lower fail -> do not wait, swap that cell with the NEXT cell of the same block ONCE (both cells marked swapped);
#   a swapped cell (or the last cell of the block) runs with policy "mark" = runs and is marked lower-fail.
# Per cell: run_cell_1005n.ps1 (SOC >= 41, now + 0.5 h + 30 min <= deadline) -> post_cell_1005n.ps1 (frozen judge run).
# 1004 retry rule: slot invalid (not emergency) -> gate again -> 1 retry (<out>_re, label <cell>_b<k>_re). Emergency -> FAILED, no retry.
# Session end: adb reconnect fails 3x (1 min apart) / 2nd emergency of the night / SOC < 30.
# Pair judge when both cells of a resource in a block are valid. resource / cmp are run by the session afterwards.
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_night_1005n_host"
$SIM = "C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$S = $env:ANDROID_SERIAL
if (-not $S -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
$log = "$H\driver_1005n_log.txt"
function Log([string]$m) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $m
  if ($S) { $line = $line -replace [regex]::Escape($S), "<SERIAL>" }
  if ($DryRun) { $line; return }
  for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $log -Encoding UTF8 -Value $line -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 } }
}
$common = "--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --logger-keep-files-open --analyze-timeout-seconds 600 --cooling-min-seconds 600 --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
$CELLSPEC = @{
  NA = @{ Chain="npu_work100_v1"; Spans=1000000; Sha="3f331010644eadc3d64a46c98c674e0ee9c2995ddd6c58ad9a6cc91c525126e4" }
  NB = @{ Chain="npu_work50_v1";  Spans=1000000; Sha="8f476e364dd0ac93389e6fdc4e92eee3612e096276f5214d0cc729530278f327" }
  GA = @{ Chain="gpu_work100_v1"; Spans=400000;  Sha="411513fb9815b6a8510c217d9ea6075d3cffc5e207dc4dff84adfeecb7d0a1d1" }
  GB = @{ Chain="gpu_work50_v1";  Spans=400000;  Sha="3a4334f1cc336bd1727d43926410b52f8f5642e8b1e3745b784168f4a55bf28b" }
}
$BLOCKORDER = @{ 1 = @("NA","GB","NB","GA"); 2 = @("GA","NB","GB","NA") }
function CellArgs([string]$cellName) {
  $cs = $CELLSPEC[$cellName]
  return "--npu-chain tools\chains\$($cs.Chain).json --duration 900 --npu-max-inference-spans $($cs.Spans) $common"
}
function AdbOk() {
  for ($k = 1; $k -le 3; $k++) {
    $st = "$(& $adb -s $S get-state 2>&1)".Trim()
    if ($st -eq "device") { return $true }
    Log "ADB state '$st' -> reconnect try $k"
    & $adb connect $S | Out-Null
    Start-Sleep -Seconds 60
  }
  return ("$(& $adb -s $S get-state 2>&1)".Trim() -eq "device")
}
function SocNow() { $l = (& $adb -s $S shell "dumpsys battery | grep -E '^  level:'") -replace "\s+", " "; try { return [int](("$l" -split ":")[1].Trim()) } catch { return -1 } }
function ReadSlot([string]$outName) {
  $mp = "$wd\results\$outName\experiment_manifest.json"
  $res = @{ valid = $false; emerg = $false; text = "no manifest" }
  if (Test-Path $mp) {
    try {
      $man = Get-Content -Raw -Encoding UTF8 $mp | ConvertFrom-Json
      $slot = $man.runs[0]
      $res.valid = [bool]$slot.validation.valid
      $res.emerg = ("$($slot.status)" -eq "emergency_aborted") -or ("$($man.halt_reason)" -match "emergency")
      $res.text = "manifest=$($man.status) slot=$($slot.status) valid=$($res.valid) failed=$(($slot.validation.failed_checks) -join ',') halt=$($man.halt_reason)"
    } catch { $res.text = "manifest parse error: $_" }
  }
  return $res
}
function RunOnce([string]$cellName, [int]$blk, [string]$outName, [string]$gateLabel, [string]$policy) {
  $cs = $CELLSPEC[$cellName]
  $null = & "$H\run_cell_1005n.ps1" -Tag "${cellName}_b${blk}" -Label $gateLabel -OutName $outName -CellArgs (CellArgs $cellName) -ChainSha $cs.Sha -MinSoc 41 -Hours 0.5 -LowerPolicy $policy
  return $LASTEXITCODE
}
function Post([string]$cellName, [int]$blk, [string]$outName, [string]$gateLabel) {
  $pc = & "$H\post_cell_1005n.ps1" -OutName $outName -Cell $cellName -Block $blk -GateLabel $gateLabel 2>&1 | ForEach-Object { "$_" }
  Log ("POST $outName :: " + ($pc -join " | "))
}
function TryPair([int]$blk, [hashtable]$status) {
  foreach ($pr in @(@("N","NA","NB"), @("G","GA","GB"))) {
    $pa = "$SIM\out_1005n\pair_$($pr[0])_b$blk.json"
    if ($status[$pr[1]] -eq "valid" -and $status[$pr[2]] -eq "valid" -and -not (Test-Path $pa)) {
      $po = & py -X utf8 "$SIM\night1005_judge.py" pair --a "$SIM\out_1005n\$($pr[1])_b$blk.json" --b "$SIM\out_1005n\$($pr[2])_b$blk.json" --out $pa 2>&1 | ForEach-Object { "$_" }
      $po | Set-Content -Encoding utf8 "$H\pair_$($pr[0])_b$blk.stdout.txt"
      Log "PAIR $($pr[0]) b$blk exit=$LASTEXITCODE out=$pa"
    }
  }
}

$emerg = $EmergStart
Log "DRIVER START pid=$PID startBlock=$StartBlock startQueue='$StartQueue' emerg=$emerg dry=$DryRun"
if ($DryRun) {
  foreach ($blk in 1, 2) { foreach ($cellName in $BLOCKORDER[$blk]) {
    $cs = $CELLSPEC[$cellName]
    Log "PLAN b$blk $cellName -> results\S26_${cellName}_b${blk}_1005n label=${cellName}_b${blk} sha=$($cs.Sha.Substring(0,8)) args=$(CellArgs $cellName)"
  } }
  exit 0
}
$sessionEnd = $false
for ($blk = $StartBlock; $blk -le 2 -and -not $sessionEnd; $blk++) {
  $queue = New-Object System.Collections.ArrayList
  if ($blk -eq $StartBlock -and $StartQueue) { [void]$queue.AddRange(@($StartQueue -split ",")) } else { [void]$queue.AddRange(@($BLOCKORDER[$blk])) }
  $swapped = @{}
  $status = @{}
  foreach ($cellName in $BLOCKORDER[$blk]) { if (Test-Path "$SIM\out_1005n\${cellName}_b${blk}.json") { if (-not ($queue -contains $cellName)) { $status[$cellName] = "valid" } } }
  Log "BLOCK $blk START queue=$($queue -join ',')"
  while ($queue.Count -gt 0) {
    $t = $queue[0]; $queue.RemoveAt(0)
    if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x"; $sessionEnd = $true; break }
    $socv = SocNow
    if ($socv -ge 0 -and $socv -lt 30) { Log "SESSION END: SOC $socv < 30"; $sessionEnd = $true; break }
    $policy = if ((-not $swapped[$t]) -and $queue.Count -gt 0) { "required" } else { "mark" }
    $outName = "S26_${t}_b${blk}_1005n"
    $gateLabel = "${t}_b${blk}"
    Log "CELL $t b$blk -> $outName policy=$policy remaining=$($queue -join ',')"
    $rc = RunOnce $t $blk $outName $gateLabel $policy
    Log "CELL $t b$blk rc=$rc"
    if ($rc -eq 7) {
      $nxt = $queue[0]
      $queue.Insert(1, $t); $swapped[$t] = $true; $swapped[$nxt] = $true
      Log "LOWER FAIL $t -> swapped with next $nxt (once): queue=$($queue -join ',')"
      continue
    }
    if ($rc -eq 3 -or $rc -eq 4) { $status[$t] = "skipped_rc$rc"; Log "SKIPPED $t (rc $rc)"; continue }
    if ($rc -ne 0) { $status[$t] = "stopped_rc$rc"; Log "CELL STOPPED $t (rc $rc) -> next cell"; continue }
    $sl = ReadSlot $outName
    Log "SLOT $outName :: $($sl.text) emerg=$($sl.emerg)"
    Post $t $blk $outName $gateLabel
    if ($sl.valid) { $status[$t] = "valid"; TryPair $blk $status; continue }
    if ($sl.emerg) {
      $emerg++; $status[$t] = "FAILED_emergency"; Log "EMERGENCY $t b$blk -> FAILED, no retry (emergencies tonight=$emerg)"
      if ($emerg -ge 2) { Log "SESSION END: 2nd emergency"; $sessionEnd = $true; break }
      continue
    }
    $j1 = "$SIM\out_1005n\${t}_b${blk}.json"
    if (Test-Path $j1) { Move-Item -Force $j1 "$SIM\out_1005n\${t}_b${blk}_attempt1_invalid.json" }
    Log "SLOT INVALID $t b$blk -> retry once after gate"
    if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x"; $sessionEnd = $true; break }
    $out2 = "${outName}_re"; $label2 = "${gateLabel}_re"
    $rc2 = RunOnce $t $blk $out2 $label2 "mark"
    Log "RETRY $t b$blk rc=$rc2"
    if ($rc2 -ne 0) { $status[$t] = "retry_not_run_rc$rc2"; continue }
    $sl2 = ReadSlot $out2
    Log "SLOT $out2 :: $($sl2.text) emerg=$($sl2.emerg)"
    Post $t $blk $out2 $label2
    if ($sl2.valid) { $status[$t] = "valid"; TryPair $blk $status; continue }
    if ($sl2.emerg) {
      $emerg++; Log "EMERGENCY on retry $t b$blk (emergencies tonight=$emerg)"
      if ($emerg -ge 2) { $status[$t] = "FAILED_emergency"; Log "SESSION END: 2nd emergency"; $sessionEnd = $true; break }
    }
    $status[$t] = "FAILED_invalid_twice"; Log "CELL FAILED $t b$blk (invalid twice) -> next cell"
  }
  $summary = ($BLOCKORDER[$blk] | ForEach-Object { "$_=$($status[$_])" }) -join " "
  Log "BLOCK $blk END $summary"
  if ($blk -eq 1 -and -not $sessionEnd) {
    $allOk = $true; foreach ($cellName in $BLOCKORDER[1]) { if ($status[$cellName] -ne "valid") { $allOk = $false } }
    if (-not $allOk) { Log "BLOCK 1 NOT COMPLETE -> block 2 NOT started (prereg s2)"; break }
  }
}
Log "DRIVER END emerg=$emerg sessionEnd=$sessionEnd"
