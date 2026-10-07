param([switch]$DryRun, [string]$WatchMode = "on", [int]$SeqStart = 1, [Parameter(Mandatory=$true)][ValidateSet("A2","B2")][string]$Cond,
      [Parameter(Mandatory=$true)][string]$SessionEnd, [string]$QueueSpec = "", [int]$RetryRestS = 600)
# V3 v2 (P1h 1007) session driver = copy of s26\tools\v3_1006\session_driver_v3.ps1. Changed only (P1h report s8; prereg v2 s3 운영 보강):
#   (1) -Cond A2|B2 · cell table A2_base (v3_A_base_v2) · A2_ours (v3_A_ours_v1) · B2_base (v3_B_base_v2) · B2_ours (v3_B_ours_v1) ·
#       folders results\S26_V3_<cell>_b<block>_1007 · labels NN_<cell>_b<block> (-SeqStart continues the numbering) ·
#       host dir S26_host_v3_1007 · csv *_v3b · judge = OneDrive sim\v3_judge_v2.py · out sim\out_v3_1007 · pred d1sim\out\v3_prediction_v2.json ·
#       optional -QueueSpec "A2_base:2,..." (cells left from an earlier session; default = the 4-cell mirror of -Cond).
#   (2) cell stall detection inside run_cell_v3b.ps1 (exit 8 = FAILED "멈춤 — 연결").
#   (3) reconnect = adb disconnect -> adb connect (max 3, 30 s apart; all fail -> measurement stops).
#   (4) retry = the same cell once (_re) after a slot-invalid or stall result, with >= RetryRestS (600) s rest since the failed cell ended,
#       then the gate; a failed retry STOPS the measurement (no next cell — block pair protection). Watch-event reruns (_re) keep the
#       P1g rule (right after; the slot already had the orchestrator cooling). Emergency = FAILED, no retry (v1 rule), next cell.
#   (5) adb get-state every 60 s inside the cell wait (adb_state_v3b.csv).
#   (6) cell condition = SOC >= 45 and now + Σ + 45 min <= -SessionEnd (run_cell_v3b -Deadline) — replaces the fixed 2026-10-07 11:00.
# Kept as P1g: gate = start_gate_1005e.py + lower (SKIN >= 29.1 and BAT >= 27.5) inside run_cell; lower fail -> swap with the next
#   cell of the SAME block once; watch "on" + events -> _re once; SOC < 30 -> session end; SOC / time fail (rc 3/4) -> stop.
# Every variable name is unique ignoring case. Serial only from $env:ANDROID_SERIAL, logged as <SERIAL>.
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_host_v3_1007"
$TOOLSV = "$wd\s26\tools\v3_1006"
$SIM = "C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
$OUTV = "$SIM\out_v3_1007"
$PREDJ = "$wd\d1sim\out\v3_prediction_v2.json"
$JUDGEPY = "$SIM\v3_judge_v2.py"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
New-Item -ItemType Directory -Force $OUTV | Out-Null
$logFile = "$H\driver_v3b_log.txt"
$stateFile = "$H\driver_state_v3b_$Cond.json"
$skinCsv = "$H\skin_watch_v3b.csv"
$phoneCsv = "$H\phone_watch_v3b.csv"
$gateCsvPath = "$H\gate_log_v3b.csv"
function Log([string]$msg) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $msg
  if ($DEVSER) { $line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>" }
  if ($DryRun) { $line; return }
  for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $logFile -Encoding UTF8 -Value $line -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 } }
}
$COMMONARGS = "--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
$MODELSHA = "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31"
$CELLSPEC = @{
  A2_base = @{ Chain="v3_A_base_v2"; Dur=3010; Spans=1400000; Sha="8792180762f9e1fb327cf5854d6379fc92f9001e608f7f7d144f4280b175c020" }
  A2_ours = @{ Chain="v3_A_ours_v1"; Dur=3010; Spans=1400000; Sha="3bb185fc0633f0a1da5d5407e7402b9112924f8c1cce033ee6c0780e88c3e9e0" }
  B2_base = @{ Chain="v3_B_base_v2"; Dur=2729; Spans=1500000; Sha="f8529443fb695f97d7835c09823e93e1341f4f784ca8c7ccfc539e01efcb03f0" }
  B2_ours = @{ Chain="v3_B_ours_v1"; Dur=2729; Spans=1400000; Sha="d0753f48f28e5f1f8995f3449403a72c7f7cd13fa223a26a9033d1e10b644b75" }
}
$MINSOC = 45
function NewItem([string]$cellName, [int]$blk) {
  return [pscustomobject]@{ Cell = $cellName; Block = $blk; Key = "${cellName}_b$blk"; OutName = "S26_V3_${cellName}_b${blk}_1007"; Swapped = $false; IsRe = $false; RetryOf = "" }
}
$QUEUE = New-Object System.Collections.ArrayList
if ($QueueSpec) {
  foreach ($qq in ($QueueSpec -split ",")) { $pp = $qq.Trim() -split ":"; if (-not $CELLSPEC.ContainsKey($pp[0])) { throw "unknown cell $($pp[0])" }; [void]$QUEUE.Add((NewItem $pp[0] ([int]$pp[1]))) }
} else {
  [void]$QUEUE.Add((NewItem "${Cond}_base" 1))
  [void]$QUEUE.Add((NewItem "${Cond}_ours" 1))
  [void]$QUEUE.Add((NewItem "${Cond}_ours" 2))
  [void]$QUEUE.Add((NewItem "${Cond}_base" 2))
}
$STATE = [ordered]@{ cond = $Cond; watch = $WatchMode; session_end = $SessionEnd; cells = [ordered]@{}; valid_json = [ordered]@{}; pairs = [ordered]@{}; cond_json = ""; spare_next_session = @(); emergencies = 0; stop_reason = ""; notes = @() }
$script:seqNo = $SeqStart
$script:lastCellEnd = $null
function SaveState() { if (-not $DryRun) { ($STATE | ConvertTo-Json -Depth 8) | Set-Content -Encoding UTF8 $stateFile } }
function CellArgsOf([string]$cellName) { $cs = $CELLSPEC[$cellName]; return "--npu-chain tools\chains\$($cs.Chain).json --duration $($cs.Dur) --npu-max-inference-spans $($cs.Spans) --runner-timeout-seconds $($cs.Dur + 1800) --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600 $COMMONARGS" }
function HoursOf([string]$cellName) { return [math]::Round(($CELLSPEC[$cellName].Dur + 900) / 3600.0, 3) }
function NextLabel([string]$core) { $lab = ("{0:D2}_{1}" -f $script:seqNo, $core); $script:seqNo++; return $lab }
function AdbOk() {
  $st0 = "$(& $adb -s $DEVSER get-state 2>$null)".Trim()
  if ($st0 -eq "device") { return $true }
  for ($k = 1; $k -le 3; $k++) {
    Log "ADB state not device -> disconnect / connect try $k"
    & $adb disconnect $DEVSER 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    & $adb connect $DEVSER 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    $stk = "$(& $adb -s $DEVSER get-state 2>$null)".Trim()
    if ($stk -eq "device") { Log "ADB reconnected (try $k)"; return $true }
    if ($k -lt 3) { Start-Sleep -Seconds 30 }
  }
  return $false
}
function SocNow() { $l = (& $adb -s $DEVSER shell "dumpsys battery | grep -E '^  level:'") -replace "\s+", " "; try { return [int](("$l" -split ":")[1].Trim()) } catch { return -1 } }
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
function RunDirOf([string]$outName) { $dirs = @(Get-ChildItem "$wd\results\$outName\runs" -Directory -ErrorAction SilentlyContinue); if ($dirs.Count -eq 1) { return $dirs[0].FullName } else { return $null } }
function GateAction([string]$gateLabel) {
  if (-not (Test-Path $gateCsvPath)) { return "" }
  $row = @(Import-Csv $gateCsvPath -Encoding UTF8 | Where-Object { $_.label -eq $gateLabel }) | Select-Object -Last 1
  if ($row) { return "$($row.action)" } else { return "" }
}
function WatchCheck([string]$outName, [string]$outJson) {
  $rd = RunDirOf $outName
  if (-not $rd) { Log "WATCHCHECK $outName : no single run dir"; return -1 }
  & py -X utf8 "$SIM\night1005e_judge.py" watchcheck $rd --phone-watch $phoneCsv --out $outJson > "$H\watch_$outName.stdout.txt" 2> "$H\watch_$outName.stderr.txt"
  $wrc = $LASTEXITCODE
  if ($wrc -ne 0 -or -not (Test-Path $outJson)) { Log "WATCHCHECK $outName rc=$wrc (failed)"; return -1 }
  $wj = Get-Content -Raw -Encoding UTF8 $outJson | ConvertFrom-Json
  $nev = [int]$wj.phone_watch.n_events
  Log "WATCHCHECK $outName events=$nev samples=$($wj.phone_watch.n_samples) max_gap_s=$($wj.phone_watch.max_gap_s) ref_focus='$($wj.phone_watch.reference_focus)'"
  return $nev
}
function SlotReport([string]$outName) {
  $rep = & py -X utf8 "$wd\results\S26_night_1004_host\chain_slot_report.py" "$wd\results\$outName" 2>&1 | ForEach-Object { "$_" }
  if ($DEVSER) { $rep = $rep | ForEach-Object { $_ -replace [regex]::Escape($DEVSER), "<SERIAL>" } }
  $rep | Set-Content -Encoding utf8 "$H\slot_$outName.txt"
}
function RunCheck([string]$outName, [string]$outJson) {
  $rcOut = & py -X utf8 "$TOOLSV\run_check_v3.py" "$wd\results\$outName" NPU --exp-sha $MODELSHA --input lcg-rgb-127-128 2>&1 | ForEach-Object { "$_" }
  $rcCode = $LASTEXITCODE
  ($rcOut | Select-Object -Last 1) | Set-Content -Encoding utf8 $outJson
  Log "RUNCHECK $outName rc=$rcCode :: $(($rcOut | Select-Object -Last 1))"
  return $rcCode
}
function JudgeRun($it, [string]$keyName, [string]$outName, [string]$gateLabel) {
  $rd = RunDirOf $outName
  if (-not $rd) { Log "JUDGE $outName : no single run dir"; return 9 }
  $jout = "$OUTV\$keyName.json"
  & py -X utf8 $JUDGEPY run $rd --cell $it.Cell --block $it.Block --gate-label $gateLabel --watch $skinCsv --gate-log $gateCsvPath --phone-watch $phoneCsv --out $jout > "$H\judge_$outName.stdout.txt" 2> "$H\judge_$outName.stderr.txt"
  $jrc = $LASTEXITCODE
  Log "JUDGE $outName rc=$jrc out=$jout :: $((Get-Content -Encoding UTF8 "$H\judge_$outName.stdout.txt" | Select-Object -First 1) -join ' ')"
  return $jrc
}
function PairAndCond([int]$blk) {
  $bk = "${Cond}_base_b$blk"; $ok = "${Cond}_ours_b$blk"
  if (-not ($STATE.valid_json.Contains($bk) -and $STATE.valid_json.Contains($ok))) { return }
  $pj = "$OUTV\pair_${Cond}_b$blk.json"
  & py -X utf8 $JUDGEPY pair --base $STATE.valid_json[$bk] --ours $STATE.valid_json[$ok] --out $pj > "$H\pair_${Cond}_b$blk.stdout.txt" 2> "$H\pair_${Cond}_b$blk.stderr.txt"
  $prc = $LASTEXITCODE
  Log "PAIR $Cond b$blk rc=$prc out=$pj"
  if ($prc -eq 0) { $STATE.pairs["b$blk"] = $pj }
  if ($STATE.pairs.Contains("b1") -and $STATE.pairs.Contains("b2")) {
    $cj = "$OUTV\cond_$Cond.json"
    & py -X utf8 $JUDGEPY cond --pairs $STATE.pairs["b1"] $STATE.pairs["b2"] --pred $PREDJ --out $cj > "$H\cond_$Cond.stdout.txt" 2> "$H\cond_$Cond.stderr.txt"
    Log "COND $Cond rc=$LASTEXITCODE out=$cj"
    if ($LASTEXITCODE -eq 0) { $STATE.cond_json = $cj }
  }
}
function QueueRetry($it, [string]$why) {
  $reIt = NewItem $it.Cell $it.Block; $reIt.IsRe = $true; $reIt.Swapped = $it.Swapped; $reIt.RetryOf = $why
  $QUEUE.Insert(0, $reIt)
}

Log "DRIVER START pid=$PID cond=$Cond watch=$WatchMode dry=$DryRun sessionEnd=$SessionEnd retryRest=${RetryRestS}s queue=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
if ($DryRun) {
  foreach ($it in $QUEUE) { Log "PLAN $($it.Key) -> results\$($it.OutName) label=$('{0:D2}' -f $script:seqNo)_$($it.Key) chain=$($CELLSPEC[$it.Cell].Chain) sha=$($CELLSPEC[$it.Cell].Sha.Substring(0,8)) soc>=$MINSOC hours=$(HoursOf $it.Cell) deadline=$SessionEnd args=$(CellArgsOf $it.Cell)"; $script:seqNo++ }
  exit 0
}
$null = Get-Date $SessionEnd
& $adb -s $DEVSER shell "settings put system screen_off_timeout 86400000" 2>&1 | Out-Null
Add-Content -Encoding UTF8 "$H\phone_settings_log_v3b.txt" ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] screen_off_timeout -> 86400000 (driver $Cond start, before first cell) now=" + "$(& $adb -s $DEVSER shell 'settings get system screen_off_timeout')")
$emergCount = 0
$stopAll = $false
while ($QUEUE.Count -gt 0 -and -not $stopAll) {
  $it = $QUEUE[0]; $QUEUE.RemoveAt(0)
  $cs = $CELLSPEC[$it.Cell]
  if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x"; $STATE.stop_reason = "adb"; $QUEUE.Insert(0, $it); $stopAll = $true; break }
  $socv = SocNow
  if ($socv -ge 0 -and $socv -lt 30) { Log "SESSION END: SOC $socv < 30"; $STATE.stop_reason = "soc<30"; $QUEUE.Insert(0, $it); $stopAll = $true; break }
  if ($it.IsRe -and $it.RetryOf -and $script:lastCellEnd) {
    $restDone = ((Get-Date) - $script:lastCellEnd).TotalSeconds
    if ($restDone -lt $RetryRestS) { $wait = [int][math]::Ceiling($RetryRestS - $restDone); Log "REST before retry $($it.Key)_re ($($it.RetryOf)): ${wait}s more (rest so far $([int]$restDone)s, min ${RetryRestS}s)"; Start-Sleep -Seconds $wait }
    Log "REST done $([int](((Get-Date) - $script:lastCellEnd).TotalSeconds))s since the failed cell ended -> gate"
  }
  $nextIt = if ($QUEUE.Count -gt 0) { $QUEUE[0] } else { $null }
  $sameBlockNext = ($nextIt -ne $null) -and ($nextIt.Block -eq $it.Block) -and (-not $nextIt.IsRe)
  $policy = if ((-not $it.Swapped) -and $sameBlockNext) { "required" } else { "mark" }
  $sfx = if ($it.IsRe) { "_re" } else { "" }
  $outName = "$($it.OutName)$sfx"
  $keyName = "$($it.Key)$sfx"
  $gl = NextLabel $keyName
  Log "CELL $keyName -> $outName label=$gl policy=$policy remaining=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
  $null = & "$TOOLSV\run_cell_v3b.ps1" -Tag $keyName -Label $gl -OutName $outName -CellArgs (CellArgsOf $it.Cell) -ChainSha $cs.Sha -Duration $cs.Dur -MinSoc $MINSOC -Hours (HoursOf $it.Cell) -LowerPolicy $policy -Deadline $SessionEnd
  $rc = $LASTEXITCODE
  Log "CELL $keyName rc=$rc"
  if ($rc -eq 7) {
    if ((-not $it.Swapped) -and $sameBlockNext) {
      $it.Swapped = $true; $nextIt.Swapped = $true; $QUEUE.Insert(1, $it)
      Log "LOWER FAIL $keyName -> swapped with next $($nextIt.Key) in the same block (once): queue=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
    } else {
      $STATE.cells[$keyName] = "lower_fail_unexpected_rc7"; Log "UNEXPECTED rc7 for $keyName (policy should have been mark)"
    }
    SaveState; continue
  }
  if ($rc -eq 2 -or $rc -eq 3 -or $rc -eq 4) {
    $STATE.cells[$keyName] = "not_run_rc$rc"; $STATE.stop_reason = "rc$rc at $keyName"
    Log "STOP: $keyName not run (rc ${rc} - 2 gate blocked / 3 SOC / 4 time) -> this and later cells to the next session"
    $QUEUE.Insert(0, $it)
    $stopAll = $true; SaveState; break
  }
  if ($rc -eq 8) {
    $script:lastCellEnd = Get-Date
    $STATE.cells[$keyName] = "FAILED_stall_connection"
    Log "CELL FAILED $keyName (멈춤 — 연결, stall detection)"
    if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x after stall"; $STATE.stop_reason = "adb after stall at $keyName"; if (-not $it.IsRe) { QueueRetry $it "stall" }; $stopAll = $true; SaveState; break }
    if (-not $it.IsRe) { QueueRetry $it "stall"; Log "STALL $keyName -> retry once after >= ${RetryRestS}s rest + gate (_re)"; SaveState; continue }
    $STATE.stop_reason = "retry failed (stall) at $keyName"; Log "MEASUREMENT STOP: retry $keyName failed (stall) -> no next cell (block pair protection)"
    $stopAll = $true; SaveState; break
  }
  if ($rc -ne 0) {
    $STATE.cells[$keyName] = "stopped_rc$rc"; $STATE.stop_reason = "rc$rc at $keyName"
    Log "MEASUREMENT STOP: $keyName stopped before launch (rc $rc)"
    $QUEUE.Insert(0, $it); $stopAll = $true; SaveState; break
  }
  $script:lastCellEnd = Get-Date
  $sl = ReadSlot $outName
  Log "SLOT $outName :: $($sl.text) emerg=$($sl.emerg)"
  $nev = WatchCheck $outName "$OUTV\$($keyName)_watch.json"
  SlotReport $outName
  $null = RunCheck $outName "$OUTV\$($keyName)_check.json"
  $null = JudgeRun $it $keyName $outName $gl
  $gact = GateAction $gl
  if ($gact -eq "run_marked_lower_fail") { $STATE.spare_next_session += "$keyName : lower fail marked run"; Log "SPARE-NEXT $keyName lower-fail marked run" }
  if ($sl.valid) {
    if ($STATE.watch -eq "on" -and $nev -gt 0) {
      if (-not $it.IsRe) {
        QueueRetry $it ""; $STATE.cells[$keyName] = "watch_event_invalid"; Log "WATCH EVENT $keyName ($nev) -> same cell again next (_re)"; SaveState; continue
      }
      $STATE.cells[$keyName] = "watch_event_invalid"; $STATE.spare_next_session += "$($it.Key) : watch event twice"
      Log "WATCH EVENT $keyName ($nev) -> invalid, no further rerun"; SaveState; continue
    }
    $STATE.cells[$keyName] = "valid"
    if (Test-Path "$OUTV\$keyName.json") { $STATE.valid_json[$it.Key] = "$OUTV\$keyName.json" } else { Log "NO JUDGE JSON for valid $keyName" }
    PairAndCond $it.Block
    SaveState; continue
  }
  if ($sl.emerg) {
    $emergCount++; $STATE.emergencies = $emergCount; $STATE.cells[$keyName] = "FAILED_emergency"
    $STATE.spare_next_session += "$($it.Key) : emergency (spare once)"
    Log "EMERGENCY $keyName -> FAILED, no retry (emergencies=$emergCount)"; SaveState
    if ($emergCount -ge 2) { Log "SESSION END: 2nd emergency"; $STATE.stop_reason = "2nd emergency"; $stopAll = $true; break }
    continue
  }
  if (-not $it.IsRe) {
    QueueRetry $it "slot_invalid"; $STATE.cells[$keyName] = "slot_invalid"; Log "SLOT INVALID $keyName -> retry once after >= ${RetryRestS}s rest + gate (_re)"; SaveState; continue
  }
  $STATE.cells[$keyName] = "slot_invalid"; $STATE.stop_reason = "retry failed (slot invalid) at $keyName"
  Log "MEASUREMENT STOP: retry $keyName failed (slot invalid) -> no next cell (block pair protection)"; $stopAll = $true; SaveState; break
}
if ($QUEUE.Count -gt 0) { $STATE.notes += "left: $(($QUEUE | ForEach-Object { $_.Key }) -join ',')" }
$STATE.emergencies = $emergCount
SaveState
& $adb -s $DEVSER shell "settings put system screen_off_timeout 600000" 2>&1 | Out-Null
Add-Content -Encoding UTF8 "$H\phone_settings_log_v3b.txt" ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] restore (driver $Cond end): screen_off_timeout -> 600000 now=" + "$(& $adb -s $DEVSER shell 'settings get system screen_off_timeout')")
Log "DRIVER END emerg=$emergCount stop='$($STATE.stop_reason)' left=$(($QUEUE | ForEach-Object { $_.Key }) -join ',') cells=$(($STATE.cells.Keys | ForEach-Object { "$_=$($STATE.cells[$_])" }) -join ' ')"
