param([switch]$DryRun, [string]$WatchMode = "on", [int]$SeqStart = 1)
# N4 1006r session driver (after s26\tools\night_1005e\session_driver_1005e.ps1 N4 part). Every variable name is unique ignoring case.
# Queue (prompt N4_1006 + prereg night1005e s6/s7/s1 + N1 supplementary prereg s1):
#   N4 block 2 (mirror of block 1):  GIe b2 -> NIe b2      (block 1 was done by 1005e: GIe b1 -> NIe b1 after a lower swap)
#   EffNet spare runs (1005e list):  GIe_b1 spare (reason "lower fail") -> folder S26_GIe_b1_1005r_spare, judge gi300 -> GIe_b1_spare.json
#   N1 supplementary runs (MobileNet): NB_b2 -> S26_NB_b2_1005n_re · GB_b2 -> S26_GB_b2_1005n_re, judge night1005_judge.py run/pair/resource (prereg s2)
# Gate = start_gate_1005e.py (upper, SOC 30..100) + lower (SKIN >= 29.1 and BAT >= 27.5) inside run_cell_1006r.ps1.
#   N4: lower fail -> swap with the next N4 cell once (both marked); swapped / last N4 cell -> run marked ("lower fail" -> spare list for a later session).
#   spare / supplementary: run ONLY when upper and lower both pass. Lower fail -> swap with the next spare/supp cell once;
#     a cell that was already swapped (or has no next) and fails again -> "not supplemented" (never a marked run).
# After each orchestrator exit, before the next gate: watchcheck (night1005e_judge.py). Watch "on" and events > 0:
#   N4 -> the same cell again right after (folder _re, once per cell); _re also with events -> spare list.
#   spare / supp -> recorded "watch event - invalid", no rerun (spare runs are one attempt each).
# Slot invalid (not emergency): N4 -> _re once; spare/supp -> recorded, no rerun. Emergency -> FAILED, no retry; 2nd emergency -> session end.
# SOC < 30 or adb reconnect 3x fail -> session end. SOC / time condition fail (run_cell exit 3/4) -> stop here (later cells to the next session).
# Serial only from $env:ANDROID_SERIAL, logged as <SERIAL>.
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_host_1006r"
$TOOLS6 = "$wd\s26\tools\n4_1006"
$TOOLS5 = "$wd\s26\tools\night_1005e"
$SIM = "C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
$OUTR = "$SIM\out_1005r"
$OUTN = "$SIM\out_1005n"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
$logFile = "$H\driver_1006r_log.txt"
$stateFile = "$H\driver_state_1006r.json"
$skinCsv = "$H\skin_watch_1006r.csv"
$phoneCsv = "$H\phone_watch_1006r.csv"
$gateCsvPath = "$H\gate_log_1006r.csv"
function Log([string]$msg) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $msg
  if ($DEVSER) { $line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>" }
  if ($DryRun) { $line; return }
  for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $logFile -Encoding UTF8 -Value $line -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 } }
}
$COMMONARGS = "--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
$LONGTMO = "--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600"
$CELLSPEC = @{
  NIe = @{ Chain="npu_eff_idle300_v1"; Dur=840;  Spans=1200000; Sha="db087cfabdc3503f0465c54a2bf589f1731c735625b5ae7a93aebf3cadea69fa"; Res="NPU"; Hrs=0.55; Soc=41; ModelSha="311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31"; Inp="lcg-rgb-127-128" }
  GIe = @{ Chain="gpu_eff_idle300_v1"; Dur=1260; Spans=400000;  Sha="25eea6a576694063ade211b633ef5965adf7a5b1be2fdf829119be6ac8fee454"; Res="GPU"; Hrs=0.65; Soc=40; ModelSha="6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0"; Inp="lcg-rgb-127-128" }
  NB  = @{ Chain="npu_work50_v1";      Dur=900;  Spans=1000000; Sha="8f476e364dd0ac93389e6fdc4e92eee3612e096276f5214d0cc729530278f327"; Res="NPU"; Hrs=0.5;  Soc=41; ModelSha="1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf"; Inp="lcg-unit" }
  GB  = @{ Chain="gpu_work50_v1";      Dur=900;  Spans=400000;  Sha="3a4334f1cc336bd1727d43926410b52f8f5642e8b1e3745b784168f4a55bf28b"; Res="GPU"; Hrs=0.5;  Soc=41; ModelSha="d95b3c5ea86750cef882fa867ca357dfe4d265d0b80b67e83277a0bda310cfbb"; Inp="lcg-unit" }
}
$PHONEGPUSHA = "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0"
function NewItem([string]$cellName, [string]$kindName, [int]$blk, [string]$keyName, [string]$outName) {
  return [pscustomobject]@{ Cell = $cellName; Kind = $kindName; Block = $blk; Key = $keyName; OutName = $outName; Swapped = $false; IsRe = $false }
}
$QUEUE = New-Object System.Collections.ArrayList
[void]$QUEUE.Add((NewItem "GIe" "n4" 2 "GIe_b2" "S26_GIe_b2_1005r"))
[void]$QUEUE.Add((NewItem "NIe" "n4" 2 "NIe_b2" "S26_NIe_b2_1005r"))
[void]$QUEUE.Add((NewItem "GIe" "spare" 1 "GIe_b1_spare" "S26_GIe_b1_1005r_spare"))
[void]$QUEUE.Add((NewItem "NB" "supp" 2 "NB_b2_re" "S26_NB_b2_1005n_re"))
[void]$QUEUE.Add((NewItem "GB" "supp" 2 "GB_b2_re" "S26_GB_b2_1005n_re"))
$STATE = [ordered]@{ watch = $WatchMode; cells = [ordered]@{}; spare_next_session = @(); not_supplemented = @(); emergencies = 0; stop_reason = ""; notes = @() }
$script:seqNo = $SeqStart
function SaveState() { if (-not $DryRun) { ($STATE | ConvertTo-Json -Depth 8) | Set-Content -Encoding UTF8 $stateFile } }
function CellArgsOf([string]$cellName) { $cs = $CELLSPEC[$cellName]; return "--npu-chain tools\chains\$($cs.Chain).json --duration $($cs.Dur) --npu-max-inference-spans $($cs.Spans) $LONGTMO $COMMONARGS" }
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
function RunCheck([string]$outName, [string]$cellName, [string]$outJson) {
  $cs = $CELLSPEC[$cellName]
  $rcOut = & py -X utf8 "$TOOLS6\run_check_1006r.py" "$wd\results\$outName" $cs.Res --phone-sha $PHONEGPUSHA --exp-sha $cs.ModelSha --input $cs.Inp 2>&1 | ForEach-Object { "$_" }
  $rcCode = $LASTEXITCODE
  ($rcOut | Select-Object -Last 1) | Set-Content -Encoding utf8 $outJson
  Log "RUNCHECK $outName rc=$rcCode :: $(($rcOut | Select-Object -Last 1))"
  return $rcCode
}
function JudgeItem($it, [string]$gateLabel) {
  $rd = RunDirOf $it.OutName
  if (-not $rd) { Log "JUDGE $($it.OutName) : no single run dir"; return 9 }
  if ($it.Kind -eq "supp") {
    $jout = "$OUTN\$($it.Key).json"
    & py -X utf8 "$SIM\night1005_judge.py" run $rd --cell $it.Cell --block $it.Block --gate-label $gateLabel --watch $skinCsv --gate-log $gateCsvPath --out $jout > "$H\judge_$($it.OutName).stdout.txt" 2> "$H\judge_$($it.OutName).stderr.txt"
  } else {
    $sub = if ($it.Cell -eq "NIe") { "ni300" } else { "gi300" }
    $jout = "$OUTR\$($it.Key).json"
    & py -X utf8 "$SIM\night1004_judge.py" $sub $rd --watch $skinCsv --out $jout > "$H\judge_$($it.OutName).stdout.txt" 2> "$H\judge_$($it.OutName).stderr.txt"
  }
  $jrc = $LASTEXITCODE
  Log "JUDGE $($it.Kind) $($it.OutName) rc=$jrc out=$jout :: $((Get-Content -Encoding UTF8 "$H\judge_$($it.OutName).stderr.txt" | Select-Object -First 2) -join ' | ')"
  return $jrc
}
function SuppPairResource($it) {
  $resLetter = if ($it.Cell -eq "NB") { "N" } else { "G" }
  $aJson = "$OUTN\$($resLetter)A_b2.json"
  $bJson = "$OUTN\$($it.Key).json"
  $pJson = "$OUTN\pair_$($resLetter)_b2s.json"
  $rJson = "$OUTN\resource_$($resLetter)_supp.json"
  & py -X utf8 "$SIM\night1005_judge.py" pair --a $aJson --b $bJson --out $pJson > "$H\pair_$($resLetter)_b2s.stdout.txt" 2> "$H\pair_$($resLetter)_b2s.stderr.txt"
  Log "SUPP PAIR $resLetter exit=$LASTEXITCODE out=$pJson"
  & py -X utf8 "$SIM\night1005_judge.py" resource --pairs "$OUTN\pair_$($resLetter)_b1.json" $pJson --out $rJson > "$H\resource_$($resLetter)_supp.stdout.txt" 2> "$H\resource_$($resLetter)_supp.stderr.txt"
  Log "SUPP RESOURCE $resLetter exit=$LASTEXITCODE out=$rJson"
}

Log "DRIVER START pid=$PID watch=$WatchMode dry=$DryRun queue=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
if ($DryRun) {
  foreach ($it in $QUEUE) { Log "PLAN $($it.Kind) $($it.Key) -> results\$($it.OutName) label=$('{0:D2}' -f $script:seqNo)_$($it.Key) chain=$($CELLSPEC[$it.Cell].Chain) sha=$($CELLSPEC[$it.Cell].Sha.Substring(0,8)) soc>=$($CELLSPEC[$it.Cell].Soc) hours=$($CELLSPEC[$it.Cell].Hrs) args=$(CellArgsOf $it.Cell)"; $script:seqNo++ }
  exit 0
}
& $adb -s $DEVSER shell "settings put system screen_off_timeout 86400000" 2>&1 | Out-Null
Add-Content -Encoding UTF8 "$H\phone_settings_log_1006r.txt" ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] screen_off_timeout 600000 -> 86400000 (driver start, before first cell) now=" + "$(& $adb -s $DEVSER shell 'settings get system screen_off_timeout')")
$emergCount = 0
$stopAll = $false
while ($QUEUE.Count -gt 0 -and -not $stopAll) {
  $it = $QUEUE[0]; $QUEUE.RemoveAt(0)
  $cs = $CELLSPEC[$it.Cell]
  if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x"; $STATE.stop_reason = "adb"; $stopAll = $true; break }
  $socv = SocNow
  if ($socv -ge 0 -and $socv -lt 30) { Log "SESSION END: SOC $socv < 30"; $STATE.stop_reason = "soc<30"; $stopAll = $true; break }
  $nextIt = if ($QUEUE.Count -gt 0) { $QUEUE[0] } else { $null }
  if ($it.Kind -eq "n4") {
    $policy = if ((-not $it.Swapped) -and $nextIt -and $nextIt.Kind -eq "n4") { "required" } else { "mark" }
  } else { $policy = "required" }
  $sfx = if ($it.IsRe) { "_re" } else { "" }
  $outName = "$($it.OutName)$sfx"
  $keyName = "$($it.Key)$sfx"
  $gl = NextLabel $keyName
  Log "CELL $($it.Kind) $keyName -> $outName label=$gl policy=$policy remaining=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
  $null = & "$TOOLS6\run_cell_1006r.ps1" -Tag $keyName -Label $gl -OutName $outName -CellArgs (CellArgsOf $it.Cell) -ChainSha $cs.Sha -Duration $cs.Dur -MinSoc $cs.Soc -Hours $cs.Hrs -LowerPolicy $policy
  $rc = $LASTEXITCODE
  Log "CELL $keyName rc=$rc"
  if ($rc -eq 7) {
    if ((-not $it.Swapped) -and $nextIt -and (($it.Kind -eq "n4" -and $nextIt.Kind -eq "n4") -or ($it.Kind -ne "n4" -and $nextIt.Kind -ne "n4"))) {
      $it.Swapped = $true; $nextIt.Swapped = $true; $QUEUE.Insert(1, $it)
      Log "LOWER FAIL $keyName -> swapped with next $($nextIt.Key) (once): queue=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
    } else {
      $STATE.cells[$keyName] = "not_supplemented_lower_fail"; $STATE.not_supplemented += "$keyName : lower fail (no marked run)"
      Log "NOT SUPPLEMENTED $keyName : lower fail again / no next cell (prereg s1: never a marked run)"
    }
    SaveState; continue
  }
  if ($rc -eq 2 -or $rc -eq 3 -or $rc -eq 4) {
    $STATE.cells[$keyName] = "not_run_rc$rc"; $STATE.stop_reason = "rc$rc at $keyName"
    Log "STOP: $keyName not run (rc ${rc} - 2 gate blocked / 3 SOC / 4 time) -> this and later cells to the next session"
    $stopAll = $true; SaveState; break
  }
  if ($rc -ne 0) {
    $STATE.cells[$keyName] = "stopped_rc$rc"; Log "CELL STOPPED $keyName (rc $rc) -> next cell"
    if ($it.Kind -eq "n4") { $STATE.notes += "N4 $keyName stopped rc$rc" }
    SaveState; continue
  }
  $sl = ReadSlot $outName
  Log "SLOT $outName :: $($sl.text) emerg=$($sl.emerg)"
  $wjson = if ($it.Kind -eq "supp") { "$OUTN\$($keyName)_watch.json" } else { "$OUTR\$($keyName)_watch.json" }
  $nev = WatchCheck $outName $wjson
  SlotReport $outName
  $cjson = if ($it.Kind -eq "supp") { "$OUTN\$($keyName)_check.json" } else { "$OUTR\$($keyName)_check.json" }
  $null = RunCheck $outName $it.Cell $cjson
  $tmpIt = [pscustomobject]@{ Cell = $it.Cell; Kind = $it.Kind; Block = $it.Block; Key = $keyName; OutName = $outName }
  $null = JudgeItem $tmpIt $gl
  $gact = GateAction $gl
  if ($gact -eq "run_marked_lower_fail") { $STATE.spare_next_session += "$keyName (N4) : lower fail marked run"; Log "SPARE-NEXT $keyName lower-fail marked run" }
  if ($sl.valid) {
    if ($STATE.watch -eq "on" -and $nev -gt 0) {
      if ($it.Kind -eq "n4" -and -not $it.IsRe) {
        $reIt = NewItem $it.Cell $it.Kind $it.Block $it.Key $it.OutName; $reIt.IsRe = $true; $reIt.Swapped = $it.Swapped
        $QUEUE.Insert(0, $reIt); $STATE.cells[$keyName] = "watch_event_invalid"; Log "WATCH EVENT $keyName ($nev) -> same cell again next (_re)"; SaveState; continue
      }
      $STATE.cells[$keyName] = "watch_event_invalid"
      if ($it.Kind -eq "n4") { $STATE.spare_next_session += "$($it.Key) (N4) : watch event twice" } else { $STATE.not_supplemented += "$keyName : watch event (one attempt)" }
      Log "WATCH EVENT $keyName ($nev) -> invalid, no further rerun"; SaveState; continue
    }
    $STATE.cells[$keyName] = "valid"
    if ($it.Kind -eq "supp") { SuppPairResource $tmpIt }
    SaveState; continue
  }
  if ($sl.emerg) {
    $emergCount++; $STATE.emergencies = $emergCount; $STATE.cells[$keyName] = "FAILED_emergency"
    if ($it.Kind -eq "n4") { $STATE.spare_next_session += "$($it.Key) (N4) : emergency" } else { $STATE.not_supplemented += "$keyName : emergency" }
    Log "EMERGENCY $keyName -> FAILED, no retry (emergencies=$emergCount)"; SaveState
    if ($emergCount -ge 2) { Log "SESSION END: 2nd emergency"; $STATE.stop_reason = "2nd emergency"; $stopAll = $true; break }
    continue
  }
  if ($it.Kind -eq "n4" -and -not $it.IsRe) {
    $reIt = NewItem $it.Cell $it.Kind $it.Block $it.Key $it.OutName; $reIt.IsRe = $true; $reIt.Swapped = $it.Swapped
    $QUEUE.Insert(0, $reIt); $STATE.cells[$keyName] = "slot_invalid"; Log "SLOT INVALID $keyName -> retry once after gate (_re)"; SaveState; continue
  }
  $STATE.cells[$keyName] = "slot_invalid"
  if ($it.Kind -eq "n4") { $STATE.spare_next_session += "$($it.Key) (N4) : slot invalid twice" } else { $STATE.not_supplemented += "$keyName : slot invalid (one attempt)" }
  Log "CELL FAILED $keyName (slot invalid)"; SaveState
}
if ($QUEUE.Count -gt 0) { $STATE.notes += "left for next session: $(($QUEUE | ForEach-Object { $_.Key }) -join ',')" }
$STATE.emergencies = $emergCount
SaveState
& $adb -s $DEVSER shell "settings put system screen_off_timeout 600000" 2>&1 | Out-Null
Add-Content -Encoding UTF8 "$H\phone_settings_log_1006r.txt" ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] restore (driver end): screen_off_timeout -> 600000 now=" + "$(& $adb -s $DEVSER shell 'settings get system screen_off_timeout')")
Log "DRIVER END emerg=$emergCount stop='$($STATE.stop_reason)' left=$(($QUEUE | ForEach-Object { $_.Key }) -join ',') cells=$(($STATE.cells.Keys | ForEach-Object { "$_=$($STATE.cells[$_])" }) -join ' ')"
