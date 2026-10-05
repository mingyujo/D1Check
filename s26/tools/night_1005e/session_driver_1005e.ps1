param([switch]$DryRun, [string]$WatchMode = "on_provisional", [string]$Phase = "all", [int]$SeqStart = 1)
# NIGHT 1005e session driver (after session_driver_1005n.ps1). Every variable name is unique ignoring case (10/5 07:40 and 1005e watch v1 bug).
# Phase "all": smoke N -> smoke G (prereg night1005e s4-0) -> N2 block 1 -> block 2 (s4-1) -> N4 block 1 (s6). "n2" skips smoke, "n4" = only N4 block 1.
# Smoke: upper gate only; pass = run_check_1005e.py; retry once after gate when the slot is invalid and the cause is not emergency/model/SHA/path/input.
#   Watch negative control: watchcheck on the smoke runs -> 0 events = watch "on" (confirmed), events > 0 = "record_only" (s3).
#   Smoke N fail -> no NPU cells; smoke G fail -> no GPU cells; both -> stop (s7).
# N2 order (s4-1): b1 = NAe GBe NBe GAe, b2 = GAe NBe GBe NAe (subset keeps order, s7). Block 2 only if every block-1 cell is valid.
# Lower rule (s1): upper pass + lower fail -> swap with the NEXT cell of the same block once (both marked); swapped / last cell -> run marked.
#   A marked run is judged as usual and goes to the spare list with reason "하한 미달" (s1 supplementary run - a later session).
# After each orchestrator exit, BEFORE the next gate: watchcheck. Watch "on" and events > 0 -> the same cell again right after (folder _re,
#   once per cell); _re also with events -> spare list. Slot invalid (not emergency) -> the same cell again right after (_re, once per cell).
#   Emergency -> FAILED, no retry; 2nd emergency of the night -> session end. SOC < 30 or adb reconnect 3x fail -> session end.
# Judge (frozen night1005e_judge.py 2db1cda5) per cell; pair when both A and B of a resource in a block are valid; resource + cmp after N2.
# N4 block 1 (s6): NIe (SOC >= 41, 0.55 h) -> GIe (SOC >= 40, 0.65 h), night1004_judge.py ni300 / gi300 (fd22d3ba) + watchcheck + run_check (model SHA).
# Serial only from $env:ANDROID_SERIAL, logged as <SERIAL>.
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_host_1005e"
$TOOLS = "$wd\s26\tools\night_1005e"
$SIM = "C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
$OUTE = "$SIM\out_1005e"
$OUTR = "$SIM\out_1005r"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
$logFile = "$H\driver_1005e_log.txt"
$stateFile = "$H\driver_state_1005e.json"
function Log([string]$msg) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $msg
  if ($DEVSER) { $line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>" }
  if ($DryRun) { $line; return }
  for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $logFile -Encoding UTF8 -Value $line -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 } }
}
$COMMONARGS = "--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
$LONGTMO = "--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600"
$SMOKETMO = "--cooling-min-seconds 60 --runner-timeout-seconds 900 --logger-exit-timeout-seconds 600 --analyze-timeout-seconds 300"
$NPUSHA = "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31"
$GPUSHA = "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0"
$SPEC = @{
  smokeN = @{ Chain="smoke_npu_eff_v1";   Dur=60;   Spans=100000;  Tmo=$SMOKETMO; Sha="82ce7744d47c8fa783d46f86fa105a4ed62883d84e8cc44d2a451bca2a906eeb"; Res="NPU"; Hrs=0.2;  Soc=30 }
  smokeG = @{ Chain="smoke_gpu_eff_v1";   Dur=60;   Spans=50000;   Tmo=$SMOKETMO; Sha="16c951ba993423b82b2921b2e000957afeb7ea8e5b192121590a381ae29aea29"; Res="GPU"; Hrs=0.2;  Soc=30 }
  NAe    = @{ Chain="npu_eff_work100_v1"; Dur=900;  Spans=1000000; Tmo=$LONGTMO;  Sha="4433e25923aa7aacfaa5f123466135e145b10100e27c7d416874abab8337f09c"; Res="NPU"; Hrs=0.5;  Soc=41 }
  NBe    = @{ Chain="npu_eff_work50_v1";  Dur=900;  Spans=1000000; Tmo=$LONGTMO;  Sha="168a5b53c1c73dee0d3e219832735de67642946b98d57c2899bb1db7b2eaa3f6"; Res="NPU"; Hrs=0.5;  Soc=41 }
  GAe    = @{ Chain="gpu_eff_work100_v1"; Dur=900;  Spans=400000;  Tmo=$LONGTMO;  Sha="df0ffa2f15ddc9c1c0cab60cd09daeff48e34165296af64aaf77e58bc85eb513"; Res="GPU"; Hrs=0.5;  Soc=41 }
  GBe    = @{ Chain="gpu_eff_work50_v1";  Dur=900;  Spans=400000;  Tmo=$LONGTMO;  Sha="4af89784ae20fce30f356ca30c69d4ec54aab65f9582901e846a0b4ac54cf53c"; Res="GPU"; Hrs=0.5;  Soc=41 }
  NIe    = @{ Chain="npu_eff_idle300_v1"; Dur=840;  Spans=1200000; Tmo=$LONGTMO;  Sha="db087cfabdc3503f0465c54a2bf589f1731c735625b5ae7a93aebf3cadea69fa"; Res="NPU"; Hrs=0.55; Soc=41 }
  GIe    = @{ Chain="gpu_eff_idle300_v1"; Dur=1260; Spans=400000;  Tmo=$LONGTMO;  Sha="25eea6a576694063ade211b633ef5965adf7a5b1be2fdf829119be6ac8fee454"; Res="GPU"; Hrs=0.65; Soc=40 }
}
$STATE = [ordered]@{ watch = $WatchMode; smoke = [ordered]@{}; n2 = [ordered]@{}; n4 = [ordered]@{}; spare = @(); emergencies = 0; resources = @("NPU","GPU"); notes = @() }
$script:seqNo = $SeqStart
function SaveState() { if (-not $DryRun) { ($STATE | ConvertTo-Json -Depth 8) | Set-Content -Encoding UTF8 $stateFile } }
function CellArgsOf([string]$cellName) { $cs = $SPEC[$cellName]; return "--npu-chain tools\chains\$($cs.Chain).json --duration $($cs.Dur) --npu-max-inference-spans $($cs.Spans) $($cs.Tmo) $COMMONARGS" }
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
function RunOnce([string]$cellName, [string]$tagName, [string]$outName, [string]$gateLabel, [string]$policy) {
  $cs = $SPEC[$cellName]
  $null = & "$TOOLS\run_cell_1005e.ps1" -Tag $tagName -Label $gateLabel -OutName $outName -CellArgs (CellArgsOf $cellName) -ChainSha $cs.Sha -Duration $cs.Dur -MinSoc $cs.Soc -Hours $cs.Hrs -LowerPolicy $policy
  return $LASTEXITCODE
}
function GateAction([string]$gateLabel) {
  $row = @(Import-Csv "$H\gate_log_1005e.csv" -Encoding UTF8 | Where-Object { $_.label -eq $gateLabel }) | Select-Object -Last 1
  if ($row) { return "$($row.action)" } else { return "" }
}
function WatchCheck([string]$outName, [string]$outJson) {
  $rd = RunDirOf $outName
  if (-not $rd) { Log "WATCHCHECK $outName : no single run dir"; return -1 }
  & py -X utf8 "$SIM\night1005e_judge.py" watchcheck $rd --phone-watch "$H\phone_watch_1005e.csv" --out $outJson > "$H\watch_$outName.stdout.txt" 2> "$H\watch_$outName.stderr.txt"
  $wrc = $LASTEXITCODE
  if ($wrc -ne 0 -or -not (Test-Path $outJson)) { Log "WATCHCHECK $outName rc=$wrc (failed)"; return -1 }
  $wj = Get-Content -Raw -Encoding UTF8 $outJson | ConvertFrom-Json
  $nev = [int]$wj.phone_watch.n_events
  Log "WATCHCHECK $outName events=$nev samples=$($wj.phone_watch.n_samples) max_gap_s=$($wj.phone_watch.max_gap_s) gap='$($wj.phone_watch.gap_label)' ref_focus='$($wj.phone_watch.reference_focus)'"
  return $nev
}
function SlotReport([string]$outName) {
  $rep = & py -X utf8 "$wd\results\S26_night_1004_host\chain_slot_report.py" "$wd\results\$outName" 2>&1 | ForEach-Object { "$_" }
  if ($DEVSER) { $rep = $rep | ForEach-Object { $_ -replace [regex]::Escape($DEVSER), "<SERIAL>" } }
  $rep | Set-Content -Encoding utf8 "$H\slot_$outName.txt"
}
function RunCheck([string]$outName, [string]$res, [string]$outJson) {
  $phoneSha = if ($res -eq "GPU") { $GPUSHA } else { $NPUSHA }
  $rcOut = & py -X utf8 "$TOOLS\run_check_1005e.py" "$wd\results\$outName" $res --phone-sha $phoneSha 2>&1 | ForEach-Object { "$_" }
  $rcCode = $LASTEXITCODE
  ($rcOut | Select-Object -Last 1) | Set-Content -Encoding utf8 $outJson
  Log "RUNCHECK $outName rc=$rcCode :: $(($rcOut | Select-Object -Last 1))"
  return $rcCode
}
function JudgeN2([string]$cellName, [int]$blk, [string]$outName, [string]$gateLabel, [string]$jsonPath) {
  $rd = RunDirOf $outName
  if (-not $rd) { Log "JUDGE $outName : no single run dir"; return 9 }
  $jargs = @("-X", "utf8", "$SIM\night1005e_judge.py", "run", $rd, "--cell", $cellName, "--block", "$blk", "--gate-label", $gateLabel,
             "--watch", "$H\skin_watch_1005e.csv", "--gate-log", "$H\gate_log_1005e.csv", "--out", $jsonPath)
  if ($STATE.watch -eq "on") { $jargs += @("--phone-watch", "$H\phone_watch_1005e.csv") }
  & py @jargs > "$H\judge_$outName.stdout.txt" 2> "$H\judge_$outName.stderr.txt"
  $jrc = $LASTEXITCODE
  Log "JUDGE $outName rc=$jrc out=$jsonPath phone_watch=$($STATE.watch -eq 'on') :: $((Get-Content -Encoding UTF8 "$H\judge_$outName.stderr.txt" | Select-Object -First 2) -join ' | ')"
  return $jrc
}

Log "DRIVER START pid=$PID watch=$WatchMode phase=$Phase dry=$DryRun"
$emergCount = 0
$sessionEnd = $false

# ------------------------------------------------------------------ smoke
if ($Phase -eq "all") {
  $okRes = @{}
  $watchSeen = @()
  foreach ($sm in @("smokeN", "smokeG")) {
    $res = $SPEC[$sm].Res
    if ($DryRun) { Log "PLAN smoke $sm -> results\S26_${sm}_1005e label=$('{0:D2}' -f $script:seqNo)_$sm upper_only args=$(CellArgsOf $sm)"; $script:seqNo++; continue }
    $okRes[$res] = $false
    foreach ($attempt in 1, 2) {
      if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x"; $sessionEnd = $true; break }
      $sfx = if ($attempt -eq 2) { "_re" } else { "" }
      $outName = "S26_${sm}_1005e$sfx"
      $gl = NextLabel "$sm$sfx"
      Log "SMOKE $sm attempt $attempt -> $outName label=$gl"
      $rc = RunOnce $sm "$sm$sfx" $outName $gl "upper_only"
      Log "SMOKE $sm rc=$rc"
      if ($rc -ne 0) { $STATE.smoke["$sm$sfx"] = "not_run_rc$rc"; break }
      $sl = ReadSlot $outName
      Log "SLOT $outName :: $($sl.text) emerg=$($sl.emerg)"
      SlotReport $outName
      $chk = RunCheck $outName $res "$OUTE\check_$outName.json"
      $nev = WatchCheck $outName "$OUTE\watch_$outName.json"
      if ($nev -ge 0) { $watchSeen += $nev }
      if ($chk -eq 0) { $okRes[$res] = $true; $STATE.smoke["$sm$sfx"] = "pass"; break }
      if ($sl.emerg) { $emergCount++; $STATE.smoke["$sm$sfx"] = "FAILED_emergency"; break }
      $ctext = Get-Content -Raw -Encoding UTF8 "$OUTE\check_$outName.json"
      $hard = $ctext -match "model sha differs|no sha in run|input_spec|runner jsonl count|emergency"
      $STATE.smoke["$sm$sfx"] = if ($hard) { "FAILED_hard" } else { "FAILED_slot" }
      if ($hard -or $sl.valid) { break }
      Log "SMOKE $sm slot invalid (not emergency/model/SHA/path/input) -> retry once after gate"
    }
    SaveState
    if ($sessionEnd) { break }
  }
  if (-not $DryRun) {
    if ($STATE.watch -eq "on_provisional") {
      if ($watchSeen.Count -ge 1 -and (@($watchSeen | Where-Object { $_ -ne 0 }).Count -eq 0)) { $STATE.watch = "on" }
      else { $STATE.watch = "record_only" }
      Log "WATCH negative control: smoke events=$($watchSeen -join ',') -> watch=$($STATE.watch)"
    }
    $resList = @(); if ($okRes["NPU"]) { $resList += "NPU" }; if ($okRes["GPU"]) { $resList += "GPU" }
    $STATE.resources = $resList
    Log "SMOKE RESULT NPU=$($okRes['NPU']) GPU=$($okRes['GPU']) -> resources=$($resList -join ',')"
    SaveState
    if ($resList.Count -eq 0) { Log "BOTH SMOKES FAILED -> no N2 / N4 (prereg s7)"; $sessionEnd = $true }
  }
}
if ($DryRun -and $Phase -ne "all") { }
if (-not $DryRun -and $Phase -ne "all") { $STATE.resources = @("NPU", "GPU"); if ($WatchMode) { $STATE.watch = $WatchMode } }

function OrderOf([string[]]$base, [string[]]$resAllowed) { return @($base | Where-Object { $resAllowed -contains $SPEC[$_].Res }) }
$resAllowedNow = if ($DryRun) { @("NPU", "GPU") } else { @($STATE.resources) }
$BLOCKPLAN = @{ 1 = (OrderOf @("NAe","GBe","NBe","GAe") $resAllowedNow); 2 = (OrderOf @("GAe","NBe","GBe","NAe") $resAllowedNow) }
$jsonOf = @{}

function TryPair([int]$blk, [hashtable]$statusMap) {
  foreach ($pr in @(@("NPU","NAe","NBe"), @("GPU","GAe","GBe"))) {
    $pa = "$OUTE\pair_$($pr[0])_b$blk.json"
    if ($statusMap[$pr[1]] -eq "valid" -and $statusMap[$pr[2]] -eq "valid" -and -not (Test-Path $pa)) {
      & py -X utf8 "$SIM\night1005e_judge.py" pair --a $jsonOf["$($pr[1])_b$blk"] --b $jsonOf["$($pr[2])_b$blk"] --out $pa > "$H\pair_$($pr[0])_b$blk.stdout.txt" 2> "$H\pair_$($pr[0])_b$blk.stderr.txt"
      Log "PAIR $($pr[0]) b$blk exit=$LASTEXITCODE out=$pa a=$($jsonOf["$($pr[1])_b$blk"]) b=$($jsonOf["$($pr[2])_b$blk"])"
    }
  }
}

# ------------------------------------------------------------------ N2
if ($Phase -in @("all", "n2") -and -not $sessionEnd) {
  for ($blk = 1; $blk -le 2 -and -not $sessionEnd; $blk++) {
    $queue = New-Object System.Collections.ArrayList
    foreach ($cn in $BLOCKPLAN[$blk]) { [void]$queue.Add($cn) }
    if ($queue.Count -eq 0) { break }
    if ($DryRun) {
      foreach ($cn in $queue) { Log "PLAN N2 b$blk $cn -> results\S26_${cn}_b${blk}_1005e label=$('{0:D2}' -f $script:seqNo)_${cn}_b$blk sha=$($SPEC[$cn].Sha.Substring(0,8)) args=$(CellArgsOf $cn)"; $script:seqNo++ }
      continue
    }
    $swapped = @{}; $statusMap = @{}; $reUsed = @{}
    Log "BLOCK $blk START queue=$($queue -join ',') watch=$($STATE.watch)"
    while ($queue.Count -gt 0) {
      $item = $queue[0]; $queue.RemoveAt(0)
      $isRe = $item.EndsWith("|re"); $cn = $item.Replace("|re", "")
      if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x"; $sessionEnd = $true; break }
      $socv = SocNow
      if ($socv -ge 0 -and $socv -lt 30) { Log "SESSION END: SOC $socv < 30"; $sessionEnd = $true; break }
      $policy = if ((-not $swapped[$item]) -and $queue.Count -gt 0) { "required" } else { "mark" }
      $sfx = if ($isRe) { "_re" } else { "" }
      $outName = "S26_${cn}_b${blk}_1005e$sfx"
      $gl = NextLabel "${cn}_b$blk$sfx"
      $jsonPath = "$OUTE\${cn}_b$blk$sfx.json"
      Log "CELL $item b$blk -> $outName label=$gl policy=$policy remaining=$($queue -join ',')"
      $rc = RunOnce $cn "${cn}_b$blk$sfx" $outName $gl $policy
      Log "CELL $item b$blk rc=$rc"
      if ($rc -eq 7) {
        if ($queue.Count -gt 0) { $nxt = $queue[0]; $queue.Insert(1, $item); $swapped[$item] = $true; $swapped[$nxt] = $true; Log "LOWER FAIL $item -> swapped with next $nxt (once): queue=$($queue -join ',')" }
        continue
      }
      if ($rc -eq 3 -or $rc -eq 4) { $statusMap[$cn] = "skipped_rc$rc"; $STATE.n2["${cn}_b$blk"] = "skipped_rc$rc"; Log "SKIPPED $cn (rc $rc)"; SaveState; continue }
      if ($rc -ne 0) { $statusMap[$cn] = "stopped_rc$rc"; $STATE.n2["${cn}_b$blk"] = "stopped_rc$rc"; Log "CELL STOPPED $cn (rc $rc) -> next cell"; SaveState; continue }
      $sl = ReadSlot $outName
      Log "SLOT $outName :: $($sl.text) emerg=$($sl.emerg)"
      $nev = WatchCheck $outName "$OUTE\watch_$outName.json"
      SlotReport $outName
      $null = JudgeN2 $cn $blk $outName $gl $jsonPath
      if ((GateAction $gl) -eq "run_marked_lower_fail") { $STATE.spare += "${cn}_b$blk$sfx : 하한 미달 (보충 런 — 나중 세션)"; Log "SPARE ${cn}_b$blk$sfx lower-fail marked run" }
      if ($sl.valid) {
        if ($STATE.watch -eq "on" -and $nev -gt 0) {
          if (-not $reUsed[$cn]) { $reUsed[$cn] = $true; $queue.Insert(0, "$cn|re"); $STATE.n2["${cn}_b$blk$sfx"] = "watch_event_invalid"; Log "WATCH EVENT $cn b$blk ($nev) -> same cell again next (_re)"; SaveState; continue }
          $statusMap[$cn] = "FAILED_watch_twice"; $STATE.n2["${cn}_b$blk$sfx"] = "watch_event_invalid"; $STATE.spare += "${cn}_b$blk : 감시 이벤트 2번"; Log "WATCH EVENT twice $cn b$blk -> spare"; SaveState; continue
        }
        $statusMap[$cn] = "valid"; $jsonOf["${cn}_b$blk"] = $jsonPath; $STATE.n2["${cn}_b$blk$sfx"] = "valid"; SaveState
        TryPair $blk $statusMap; continue
      }
      if ($sl.emerg) {
        $emergCount++; $STATE.emergencies = $emergCount; $statusMap[$cn] = "FAILED_emergency"; $STATE.n2["${cn}_b$blk$sfx"] = "FAILED_emergency"; $STATE.spare += "${cn}_b$blk : 안전 비상"
        Log "EMERGENCY $cn b$blk -> FAILED, no retry (emergencies tonight=$emergCount)"; SaveState
        if ($emergCount -ge 2) { Log "SESSION END: 2nd emergency"; $sessionEnd = $true; break }
        continue
      }
      if (Test-Path $jsonPath) { Move-Item -Force $jsonPath ($jsonPath -replace '\.json$', '_invalid.json') }
      if (-not $reUsed[$cn]) { $reUsed[$cn] = $true; $queue.Insert(0, "$cn|re"); $STATE.n2["${cn}_b$blk$sfx"] = "slot_invalid"; Log "SLOT INVALID $cn b$blk -> retry once after gate (_re)"; SaveState; continue }
      $statusMap[$cn] = "FAILED_invalid_twice"; $STATE.n2["${cn}_b$blk$sfx"] = "slot_invalid"; $STATE.spare += "${cn}_b$blk : 슬롯 invalid 2번"; Log "CELL FAILED $cn b$blk (second attempt invalid)"; SaveState
    }
    $summary = ($BLOCKPLAN[$blk] | ForEach-Object { "$_=$($statusMap[$_])" }) -join " "
    Log "BLOCK $blk END $summary"
    if ($blk -eq 1 -and -not $sessionEnd) {
      $allOk = $true; foreach ($cn in $BLOCKPLAN[1]) { if ($statusMap[$cn] -ne "valid") { $allOk = $false } }
      if (-not $allOk) { Log "BLOCK 1 NOT COMPLETE -> block 2 NOT started (prereg s4-1)"; $STATE.notes += "block 1 incomplete -> block 2 not started"; SaveState; break }
    }
  }
  if (-not $DryRun) {
    foreach ($rn in @("NPU", "GPU")) {
      $pl = @(@(1, 2) | ForEach-Object { "$OUTE\pair_${rn}_b$_.json" } | Where-Object { Test-Path $_ })
      if ($pl.Count -ge 1) {
        & py -X utf8 "$SIM\night1005e_judge.py" resource --pairs @pl --room-c 23 --out "$OUTE\res_$rn.json" > "$H\res_$rn.stdout.txt" 2> "$H\res_$rn.stderr.txt"
        Log "RESOURCE $rn pairs=$($pl.Count) exit=$LASTEXITCODE"
      }
    }
    SaveState
  }
}

# ------------------------------------------------------------------ N4 block 1
if ($Phase -in @("all", "n2", "n4") -and -not $sessionEnd) {
  $n4queue = New-Object System.Collections.ArrayList
  foreach ($cn in (OrderOf @("NIe", "GIe") $resAllowedNow)) { [void]$n4queue.Add($cn) }
  if ($DryRun) { foreach ($cn in $n4queue) { Log "PLAN N4 b1 $cn -> results\S26_${cn}_b1_1005r label=$('{0:D2}' -f $script:seqNo)_${cn}_b1 sha=$($SPEC[$cn].Sha.Substring(0,8)) soc>=$($SPEC[$cn].Soc) hours=$($SPEC[$cn].Hrs) args=$(CellArgsOf $cn)"; $script:seqNo++ } }
  else {
    $swapped4 = @{}; $reUsed4 = @{}
    Log "N4 BLOCK 1 START queue=$($n4queue -join ',')"
    while ($n4queue.Count -gt 0) {
      $item = $n4queue[0]; $n4queue.RemoveAt(0)
      $isRe = $item.EndsWith("|re"); $cn = $item.Replace("|re", "")
      if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x"; $sessionEnd = $true; break }
      $policy = if ((-not $swapped4[$item]) -and $n4queue.Count -gt 0) { "required" } else { "mark" }
      $sfx = if ($isRe) { "_re" } else { "" }
      $outName = "S26_${cn}_b1_1005r$sfx"
      $gl = NextLabel "${cn}_b1$sfx"
      Log "N4 CELL $item -> $outName label=$gl policy=$policy"
      $rc = RunOnce $cn "${cn}_b1$sfx" $outName $gl $policy
      Log "N4 CELL $item rc=$rc"
      if ($rc -eq 7) { if ($n4queue.Count -gt 0) { $nxt = $n4queue[0]; $n4queue.Insert(1, $item); $swapped4[$item] = $true; $swapped4[$nxt] = $true; Log "N4 LOWER FAIL $item -> swapped with $nxt" }; continue }
      if ($rc -ne 0) { $STATE.n4["${cn}_b1$sfx"] = "not_run_rc$rc"; Log "N4 $cn not run (rc $rc) -> N4 stops here (one order: NIe b1 -> GIe b1 -> GIe b2 -> NIe b2)"; SaveState; break }
      $sl = ReadSlot $outName
      Log "SLOT $outName :: $($sl.text) emerg=$($sl.emerg)"
      $nev = WatchCheck $outName "$OUTR\${cn}_b1${sfx}_watch.json"
      SlotReport $outName
      $null = RunCheck $outName $SPEC[$cn].Res "$OUTR\${cn}_b1${sfx}_check.json"
      $sub = if ($cn -eq "NIe") { "ni300" } else { "gi300" }
      $rd = RunDirOf $outName
      if ($rd) {
        & py -X utf8 "$SIM\night1004_judge.py" $sub $rd --watch "$H\skin_watch_1005e.csv" --out "$OUTR\${cn}_b1$sfx.json" > "$H\judge_$outName.stdout.txt" 2> "$H\judge_$outName.stderr.txt"
        Log "N4 JUDGE $sub $outName exit=$LASTEXITCODE"
      }
      if ((GateAction $gl) -eq "run_marked_lower_fail") { $STATE.spare += "${cn}_b1$sfx (N4) : 하한 미달 (보충 런 — 나중 세션)" }
      if ($sl.valid) {
        if ($STATE.watch -eq "on" -and $nev -gt 0) {
          if (-not $reUsed4[$cn]) { $reUsed4[$cn] = $true; $n4queue.Insert(0, "$cn|re"); $STATE.n4["${cn}_b1$sfx"] = "watch_event_invalid"; Log "N4 WATCH EVENT $cn -> again (_re)"; SaveState; continue }
          $STATE.n4["${cn}_b1$sfx"] = "watch_event_invalid"; $STATE.spare += "${cn}_b1 (N4) : 감시 이벤트 2번"; SaveState; continue
        }
        $STATE.n4["${cn}_b1$sfx"] = "valid"; SaveState; continue
      }
      if ($sl.emerg) {
        $emergCount++; $STATE.emergencies = $emergCount; $STATE.n4["${cn}_b1$sfx"] = "FAILED_emergency"; $STATE.spare += "${cn}_b1 (N4) : 안전 비상"; SaveState
        if ($emergCount -ge 2) { Log "SESSION END: 2nd emergency"; $sessionEnd = $true; break }
        continue
      }
      if (-not $reUsed4[$cn]) { $reUsed4[$cn] = $true; $n4queue.Insert(0, "$cn|re"); $STATE.n4["${cn}_b1$sfx"] = "slot_invalid"; Log "N4 SLOT INVALID $cn -> retry once (_re)"; SaveState; continue }
      $STATE.n4["${cn}_b1$sfx"] = "slot_invalid"; $STATE.spare += "${cn}_b1 (N4) : 슬롯 invalid 2번"; SaveState
    }
  }
}
$STATE.emergencies = $emergCount
SaveState
Log "DRIVER END emerg=$emergCount sessionEnd=$sessionEnd watch=$($STATE.watch) spare=$($STATE.spare -join ' ; ')"
