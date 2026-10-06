param([switch]$DryRun, [string]$WatchMode = "on", [int]$SeqStart = 1, [string]$Cond = "A")
# V3 1006 session driver = copy of s26\tools\n4_1006\session_driver_1006r.ps1 with the N4/spare/supp queue replaced by the V3 queue.
# Changed (reported in the session report): queue · cell table (V3 chains, Σ, spans, canonical SHA) · host dir S26_host_v3_1006 · csv names *_v3 ·
#   judge = OneDrive sim\v3_judge.py run (instead of night1004/night1005) + pair (block complete) + cond (both blocks) ·
#   lower-swap only inside the same block · MinSoc 45 · Hours = (Σ + 15 min) (run_cell adds 30 min) · deadline 2026-10-07 11:00.
# Kept as N4: gate = start_gate_1005e.py (upper, SOC 30..100) + lower (SKIN >= 29.1 and BAT >= 27.5) inside run_cell_v3.ps1;
#   lower fail -> swap with the next cell of the SAME block once (both marked); swapped / last cell of the block -> run marked ("lower fail" -> spare list);
#   watch "on" and events > 0 -> the same cell again right after (_re, once); _re with events -> spare list;
#   slot invalid (not emergency) -> _re once; emergency -> FAILED, no retry (spare night); 2nd emergency -> session end;
#   SOC < 30 or adb reconnect 3x fail -> session end; SOC / time condition fail (run_cell exit 3/4) -> stop (later cells to the next session).
# Queue (V3 prereg s3): block 1 = base -> ours · block 2 = ours -> base. Every variable name is unique ignoring case.
# Serial only from $env:ANDROID_SERIAL, logged as <SERIAL>.
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_host_v3_1006"
$TOOLSV = "$wd\s26\tools\v3_1006"
$SIM = "C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
$OUTV = "$SIM\out_v3_1006"
$PREDJ = "$wd\d1sim\out\v3_prediction_1006.json"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
$logFile = "$H\driver_v3_log.txt"
$stateFile = "$H\driver_state_v3_$Cond.json"
$skinCsv = "$H\skin_watch_v3.csv"
$phoneCsv = "$H\phone_watch_v3.csv"
$gateCsvPath = "$H\gate_log_v3.csv"
function Log([string]$msg) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $msg
  if ($DEVSER) { $line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>" }
  if ($DryRun) { $line; return }
  for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $logFile -Encoding UTF8 -Value $line -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 } }
}
$COMMONARGS = "--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
$MODELSHA = "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31"
$CELLSPEC = @{
  A_base = @{ Chain="v3_A_base_v1"; Dur=3010; Spans=1500000; Sha="25b12c3d0f3bea14dd513fe26508f2090aeb55b85b242eea9fd17600fbdac9b0" }
  A_ours = @{ Chain="v3_A_ours_v1"; Dur=3010; Spans=1400000; Sha="3bb185fc0633f0a1da5d5407e7402b9112924f8c1cce033ee6c0780e88c3e9e0" }
  B_base = @{ Chain="v3_B_base_v1"; Dur=2729; Spans=1500000; Sha="d6934e78373d5afccaa0d2ae31f41f90c3cc64835fe1cd39381907251d76d430" }
  B_ours = @{ Chain="v3_B_ours_v1"; Dur=2729; Spans=1400000; Sha="d0753f48f28e5f1f8995f3449403a72c7f7cd13fa223a26a9033d1e10b644b75" }
}
$MINSOC = 45
function NewItem([string]$cellName, [int]$blk) {
  return [pscustomobject]@{ Cell = $cellName; Block = $blk; Key = "${cellName}_b$blk"; OutName = "S26_V3_${cellName}_b${blk}_1006"; Swapped = $false; IsRe = $false }
}
$QUEUE = New-Object System.Collections.ArrayList
[void]$QUEUE.Add((NewItem "${Cond}_base" 1))
[void]$QUEUE.Add((NewItem "${Cond}_ours" 1))
[void]$QUEUE.Add((NewItem "${Cond}_ours" 2))
[void]$QUEUE.Add((NewItem "${Cond}_base" 2))
$STATE = [ordered]@{ cond = $Cond; watch = $WatchMode; cells = [ordered]@{}; valid_json = [ordered]@{}; pairs = [ordered]@{}; cond_json = ""; spare_next_session = @(); emergencies = 0; stop_reason = ""; notes = @() }
$script:seqNo = $SeqStart
function SaveState() { if (-not $DryRun) { ($STATE | ConvertTo-Json -Depth 8) | Set-Content -Encoding UTF8 $stateFile } }
function CellArgsOf([string]$cellName) { $cs = $CELLSPEC[$cellName]; return "--npu-chain tools\chains\$($cs.Chain).json --duration $($cs.Dur) --npu-max-inference-spans $($cs.Spans) --runner-timeout-seconds $($cs.Dur + 1800) --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600 $COMMONARGS" }
function HoursOf([string]$cellName) { return [math]::Round(($CELLSPEC[$cellName].Dur + 900) / 3600.0, 3) }
function NextLabel([string]$core) { $lab = ("{0:D2}_{1}" -f $script:seqNo, $core); $script:seqNo++; return $lab }
function AdbOk() {
  for ($k = 1; $k -le 3; $k++) {
    $st = "$(& $adb -s $DEVSER get-state 2>&1)".Trim()
    if ($st -eq "device") { return $true }
    Log "ADB state not device -> reconnect try $k"
    & $adb connect $DEVSER 2>&1 | Out-Null
    Start-Sleep -Seconds 60
  }
  return ("$(& $adb -s $DEVSER get-state 2>&1)".Trim() -eq "device")
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
  & py -X utf8 "$SIM\v3_judge.py" run $rd --cell $it.Cell --block $it.Block --gate-label $gateLabel --watch $skinCsv --gate-log $gateCsvPath --phone-watch $phoneCsv --out $jout > "$H\judge_$outName.stdout.txt" 2> "$H\judge_$outName.stderr.txt"
  $jrc = $LASTEXITCODE
  Log "JUDGE $outName rc=$jrc out=$jout :: $((Get-Content -Encoding UTF8 "$H\judge_$outName.stdout.txt" | Select-Object -First 1) -join ' ')"
  return $jrc
}
function PairAndCond([int]$blk) {
  $bk = "${Cond}_base_b$blk"; $ok = "${Cond}_ours_b$blk"
  if (-not ($STATE.valid_json.Contains($bk) -and $STATE.valid_json.Contains($ok))) { return }
  $pj = "$OUTV\pair_${Cond}_b$blk.json"
  & py -X utf8 "$SIM\v3_judge.py" pair --base $STATE.valid_json[$bk] --ours $STATE.valid_json[$ok] --out $pj > "$H\pair_${Cond}_b$blk.stdout.txt" 2> "$H\pair_${Cond}_b$blk.stderr.txt"
  $prc = $LASTEXITCODE
  Log "PAIR $Cond b$blk rc=$prc out=$pj"
  if ($prc -eq 0) { $STATE.pairs["b$blk"] = $pj }
  if ($STATE.pairs.Contains("b1") -and $STATE.pairs.Contains("b2")) {
    $cj = "$OUTV\cond_$Cond.json"
    & py -X utf8 "$SIM\v3_judge.py" cond --pairs $STATE.pairs["b1"] $STATE.pairs["b2"] --pred $PREDJ --out $cj > "$H\cond_$Cond.stdout.txt" 2> "$H\cond_$Cond.stderr.txt"
    Log "COND $Cond rc=$LASTEXITCODE out=$cj"
    if ($LASTEXITCODE -eq 0) { $STATE.cond_json = $cj }
  }
}

Log "DRIVER START pid=$PID cond=$Cond watch=$WatchMode dry=$DryRun queue=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
if ($DryRun) {
  foreach ($it in $QUEUE) { Log "PLAN $($it.Key) -> results\$($it.OutName) label=$('{0:D2}' -f $script:seqNo)_$($it.Key) chain=$($CELLSPEC[$it.Cell].Chain) sha=$($CELLSPEC[$it.Cell].Sha.Substring(0,8)) soc>=$MINSOC hours=$(HoursOf $it.Cell) args=$(CellArgsOf $it.Cell)"; $script:seqNo++ }
  exit 0
}
& $adb -s $DEVSER shell "settings put system screen_off_timeout 86400000" 2>&1 | Out-Null
Add-Content -Encoding UTF8 "$H\phone_settings_log_v3.txt" ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] screen_off_timeout 600000 -> 86400000 (driver start, before first cell) now=" + "$(& $adb -s $DEVSER shell 'settings get system screen_off_timeout')")
$emergCount = 0
$stopAll = $false
while ($QUEUE.Count -gt 0 -and -not $stopAll) {
  $it = $QUEUE[0]; $QUEUE.RemoveAt(0)
  $cs = $CELLSPEC[$it.Cell]
  if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x"; $STATE.stop_reason = "adb"; $stopAll = $true; break }
  $socv = SocNow
  if ($socv -ge 0 -and $socv -lt 30) { Log "SESSION END: SOC $socv < 30"; $STATE.stop_reason = "soc<30"; $stopAll = $true; break }
  $nextIt = if ($QUEUE.Count -gt 0) { $QUEUE[0] } else { $null }
  $sameBlockNext = ($nextIt -ne $null) -and ($nextIt.Block -eq $it.Block) -and (-not $nextIt.IsRe)
  $policy = if ((-not $it.Swapped) -and $sameBlockNext) { "required" } else { "mark" }
  $sfx = if ($it.IsRe) { "_re" } else { "" }
  $outName = "$($it.OutName)$sfx"
  $keyName = "$($it.Key)$sfx"
  $gl = NextLabel $keyName
  Log "CELL $keyName -> $outName label=$gl policy=$policy remaining=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
  $null = & "$TOOLSV\run_cell_v3.ps1" -Tag $keyName -Label $gl -OutName $outName -CellArgs (CellArgsOf $it.Cell) -ChainSha $cs.Sha -Duration $cs.Dur -MinSoc $MINSOC -Hours (HoursOf $it.Cell) -LowerPolicy $policy
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
  if ($rc -ne 0) {
    $STATE.cells[$keyName] = "stopped_rc$rc"; Log "CELL STOPPED $keyName (rc $rc) -> next cell"
    $STATE.notes += "$keyName stopped rc$rc"
    SaveState; continue
  }
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
        $reIt = NewItem $it.Cell $it.Block; $reIt.IsRe = $true; $reIt.Swapped = $it.Swapped
        $QUEUE.Insert(0, $reIt); $STATE.cells[$keyName] = "watch_event_invalid"; Log "WATCH EVENT $keyName ($nev) -> same cell again next (_re)"; SaveState; continue
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
    $STATE.spare_next_session += "$($it.Key) : emergency (spare night once)"
    Log "EMERGENCY $keyName -> FAILED, no retry (emergencies=$emergCount)"; SaveState
    if ($emergCount -ge 2) { Log "SESSION END: 2nd emergency"; $STATE.stop_reason = "2nd emergency"; $stopAll = $true; break }
    continue
  }
  if (-not $it.IsRe) {
    $reIt = NewItem $it.Cell $it.Block; $reIt.IsRe = $true; $reIt.Swapped = $it.Swapped
    $QUEUE.Insert(0, $reIt); $STATE.cells[$keyName] = "slot_invalid"; Log "SLOT INVALID $keyName -> retry once after gate (_re)"; SaveState; continue
  }
  $STATE.cells[$keyName] = "slot_invalid"; $STATE.spare_next_session += "$($it.Key) : slot invalid twice"
  Log "CELL FAILED $keyName (slot invalid)"; SaveState
}
if ($QUEUE.Count -gt 0) { $STATE.notes += "left for next session: $(($QUEUE | ForEach-Object { $_.Key }) -join ',')" }
$STATE.emergencies = $emergCount
SaveState
& $adb -s $DEVSER shell "settings put system screen_off_timeout 600000" 2>&1 | Out-Null
Add-Content -Encoding UTF8 "$H\phone_settings_log_v3.txt" ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] restore (driver end): screen_off_timeout -> 600000 now=" + "$(& $adb -s $DEVSER shell 'settings get system screen_off_timeout')")
Log "DRIVER END emerg=$emergCount stop='$($STATE.stop_reason)' left=$(($QUEUE | ForEach-Object { $_.Key }) -join ',') cells=$(($STATE.cells.Keys | ForEach-Object { "$_=$($STATE.cells[$_])" }) -join ' ')"
