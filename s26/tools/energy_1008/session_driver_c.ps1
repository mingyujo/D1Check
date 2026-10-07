param([switch]$DryRun, [string]$WatchMode = "on", [int]$SeqStart = 1, [Parameter(Mandatory=$true)][ValidateSet("C1","C2")][string]$Session,
      [string]$SessionEnd = "2026-10-10 06:00", [string]$Blocks = "", [switch]$NoSmoke, [int]$RetryRestS = 600)
# Energy C (P1i 1008) session driver = copy of s26\tools\v3_1006\session_driver_v3b.ps1. Changed only (energy prereg v1 §6 · P1i prompt 1-5):
#   (1) -Session C1|C2 -> blocks C1 = 1..4 · C2 = 5..8 (or -Blocks "2,5,6" for blocks left from an earlier session — whole block, both cells).
#       Order in a block (§6-3, same frame each session): odd k = A -> B · even k = B -> A. Cells NAc (A, npu_eff_work100_v1) · NBc (B, npu_eff_work50eq_v1).
#       Folders results\S26_<cell>_b<k>_1008c (C1) / _1009c (C2) · host dir S26_host_energy_1008 · csv / logs *_c.
#   (2) cell 0 = smoke N (smoke_npu_eff_v1, outside judgment) once per session before the first block (-NoSmoke skips) · folder S26_smokeN_1008c / _1009c ·
#       gate upper only · after it: watchcheck · run check · slot report (no judge). A failed smoke is logged and the session continues.
#   (3) gate = night_1005e\start_gate_1005e.py (SOC 30..100 · SKIN <= 32 · AP <= 32 · BAT <= 30 · plugged 0). Lower (SKIN >= 29.1 · BAT >= 27.5) fail
#       -> the cell is NOT swapped, it runs marked "하한 미달" (LowerPolicy mark — §6-5) · no supplementary run.
#   (4) block condition (§6-7): at the start of every block SOC >= 45 and now + 2 cells x 35 min + 15 min <= -SessionEnd, else stop FROM that block
#       (never inside a block). The first measured cell of the session needs SOC >= 85 (run_cell MinSoc 85). The second cell of a block uses
#       MinSoc 30 (= orchestrator / runner start floor) so a block is not cut in the middle by the cell SOC check.
#   (5) brightness (§6-6): at session start the original screen_brightness_mode / screen_brightness are kept in brightness_orig_c.json
#       (written once — a later session reuses the first record) -> mode 0 · brightness 0 -> restored at driver end (and by restore_c.ps1).
#   (6) stall / reconnect / retry = v3b unchanged (trace idle 600 s or Σ + 150 min -> FAILED 8 · reconnect 3x · retry = same cell once after
#       >= 600 s rest + gate · failed retry -> measurement stops). Emergency = FAILED, no retry. Watch event -> same cell again right after (_re).
#   (7) per measured cell: night1005e_judge_c.py run (thermal description only) · watchcheck · model SHA (inside run) · energy_judge_v1.py qc
#       (run QC only — no E / ΔE numbers). No pair / cond (energy C pairs are judged once in judgeC after 8 pairs — prereg §4).
# Every variable name is unique ignoring case. Serial only from $env:ANDROID_SERIAL, logged as <SERIAL>.
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_host_energy_1008"
$TOOLSC = "$wd\s26\tools\energy_1008"
$TOOLSV = "$wd\s26\tools\v3_1006"
$SIM = "C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
$DSFX = if ($Session -eq "C1") { "1008c" } else { "1009c" }
$OUTC = "$SIM\out_$DSFX"
$JUDGECPY = "$SIM\night1005e_judge_c.py"
$ENERGYPY = "$SIM\energy_judge_v1.py"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
New-Item -ItemType Directory -Force $OUTC | Out-Null
New-Item -ItemType Directory -Force $H | Out-Null
$logFile = "$H\driver_c_log.txt"
$stateFile = "$H\driver_state_c_$Session.json"
$skinCsv = "$H\skin_watch_c.csv"
$phoneCsv = "$H\phone_watch_c.csv"
$gateCsvPath = "$H\gate_log_c.csv"
$BRIGHTFILE = "$H\brightness_orig_c.json"
$SETLOG = "$H\phone_settings_log_c.txt"
function Log([string]$msg) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $msg
  if ($DEVSER) { $line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>" }
  if ($DryRun) { $line; return }
  for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $logFile -Encoding UTF8 -Value $line -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 } }
}
$COMMONARGS = "--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
$MODELSHA = "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31"
$CELLSPEC = @{
  NAc    = @{ Chain="npu_eff_work100_v1";  Dur=900; Spans=1000000; Sha="4433e25923aa7aacfaa5f123466135e145b10100e27c7d416874abab8337f09c"; Tmo="--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600" }
  NBc    = @{ Chain="npu_eff_work50eq_v1"; Dur=900; Spans=1000000; Sha="ba74ed03e26ec5d7132c430504af544f6c9a7a0336c8a382ba715ecd2c12b4fa"; Tmo="--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600" }
  smokeN = @{ Chain="smoke_npu_eff_v1";    Dur=60;  Spans=100000;  Sha="82ce7744d47c8fa783d46f86fa105a4ed62883d84e8cc44d2a451bca2a906eeb"; Tmo="--runner-timeout-seconds 900 --logger-exit-timeout-seconds 600 --analyze-timeout-seconds 300 --cooling-min-seconds 60" }
}
$BLOCK_SOC = 45; $FIRST_SOC = 85; $CELL_FLOOR_SOC = 30; $BLOCK_MIN = 2 * 35 + 15
function NewItem([string]$cellName, [int]$blk, [bool]$firstInBlock) {
  if ($cellName -eq "smokeN") { $kk = "smokeN"; $on = "S26_smokeN_$DSFX" } else { $kk = "${cellName}_b$blk"; $on = "S26_${cellName}_b${blk}_$DSFX" }
  return [pscustomobject]@{ Cell = $cellName; Block = $blk; Key = $kk; OutName = $on; FirstInBlock = $firstInBlock; IsRe = $false; RetryOf = "" }
}
$BLOCKLIST = @()
if ($Blocks) { $BLOCKLIST = @($Blocks -split "," | ForEach-Object { [int]$_.Trim() }) } elseif ($Session -eq "C1") { $BLOCKLIST = @(1, 2, 3, 4) } else { $BLOCKLIST = @(5, 6, 7, 8) }
foreach ($bk in $BLOCKLIST) { if ($bk -lt 1 -or $bk -gt 8) { throw "block $bk not in 1..8" } }
$QUEUE = New-Object System.Collections.ArrayList
if (-not $NoSmoke) { [void]$QUEUE.Add((NewItem "smokeN" 0 $false)) }
foreach ($bk in $BLOCKLIST) {
  if ($bk % 2 -eq 1) { $c1st = "NAc"; $c2nd = "NBc" } else { $c1st = "NBc"; $c2nd = "NAc" }
  [void]$QUEUE.Add((NewItem $c1st $bk $true)); [void]$QUEUE.Add((NewItem $c2nd $bk $false))
}
$STATE = [ordered]@{ session = $Session; watch = $WatchMode; session_end = $SessionEnd; blocks = $BLOCKLIST; cells = [ordered]@{}; lower_marked = @(); qc = [ordered]@{};
                     brightness_orig = $null; emergencies = 0; stop_reason = ""; left_blocks = @(); notes = @() }
$script:seqNo = $SeqStart
$script:lastCellEnd = $null
$script:firstMeasuredDone = $false
function SaveState() { if (-not $DryRun) { ($STATE | ConvertTo-Json -Depth 8) | Set-Content -Encoding UTF8 $stateFile } }
function CellArgsOf([string]$cellName) { $cspec = $CELLSPEC[$cellName]; return "--npu-chain tools\chains\$($cspec.Chain).json --duration $($cspec.Dur) --npu-max-inference-spans $($cspec.Spans) $($cspec.Tmo) $COMMONARGS" }
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
  & py -X utf8 $JUDGECPY watchcheck $rd --phone-watch $phoneCsv --out $outJson > "$H\watch_$outName.stdout.txt" 2> "$H\watch_$outName.stderr.txt"
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
  $jout = "$OUTC\$keyName.json"
  & py -X utf8 $JUDGECPY run $rd --cell $it.Cell --block $it.Block --gate-label $gateLabel --watch $skinCsv --gate-log $gateCsvPath --phone-watch $phoneCsv --out $jout > "$H\judge_$outName.stdout.txt" 2> "$H\judge_$outName.stderr.txt"
  $jrc = $LASTEXITCODE
  $msl = ""
  if ($jrc -eq 0 -and (Test-Path $jout)) { try { $jj = Get-Content -Raw -Encoding UTF8 $jout | ConvertFrom-Json; $msl = "$($jj.model_sha_check.label)" } catch { $msl = "parse error" } }
  Log "JUDGE $outName rc=$jrc out=$jout model_sha='$msl' stderr=$((Get-Content -Encoding UTF8 "$H\judge_$outName.stderr.txt" -ErrorAction SilentlyContinue | Select-Object -Last 1) -join ' ')"
  return $jrc
}
function EnergyQc($it, [string]$keyName, [string]$outName) {
  $rd = RunDirOf $outName
  if (-not $rd) { Log "ENERGY QC $outName : no single run dir"; return 9 }
  $qout = "$OUTC\$($keyName)_qc.json"
  & py -X utf8 $ENERGYPY qc $rd --cell $it.Cell --block $it.Block --session $Session --out $qout > "$H\qc_$outName.stdout.txt" 2> "$H\qc_$outName.stderr.txt"
  $qrc = $LASTEXITCODE
  $qline = (Get-Content -Encoding UTF8 "$H\qc_$outName.stdout.txt" -ErrorAction SilentlyContinue | Select-Object -Last 1) -join ' '
  if ($qrc -ne 0) { $qline = "rc=$qrc " + ((Get-Content -Encoding UTF8 "$H\qc_$outName.stderr.txt" -ErrorAction SilentlyContinue | Select-Object -Last 1) -join ' ') }
  $STATE.qc[$keyName] = $qline
  Log "ENERGY QC $outName :: $qline"
  return $qrc
}
function QueueRetry($it, [string]$why) {
  $reIt = NewItem $it.Cell $it.Block $false; $reIt.IsRe = $true; $reIt.RetryOf = $why
  $QUEUE.Insert(0, $reIt)
}
function LeftBlocks() { return @($QUEUE | Where-Object { $_.Cell -ne "smokeN" } | ForEach-Object { $_.Block } | Select-Object -Unique) }
function SetBright([string]$why) {
  if (-not (Test-Path $BRIGHTFILE)) {
    $om = "$(& $adb -s $DEVSER shell 'settings get system screen_brightness_mode')".Trim()
    $ob = "$(& $adb -s $DEVSER shell 'settings get system screen_brightness')".Trim()
    ([ordered]@{ screen_brightness_mode = $om; screen_brightness = $ob; recorded = (Get-Date -Format "yyyy-MM-dd HH:mm:ss K"); by = "session_driver_c $Session" } | ConvertTo-Json) | Set-Content -Encoding UTF8 $BRIGHTFILE
  }
  $orig = Get-Content -Raw -Encoding UTF8 $BRIGHTFILE | ConvertFrom-Json
  $STATE.brightness_orig = "mode=$($orig.screen_brightness_mode) brightness=$($orig.screen_brightness) (recorded $($orig.recorded))"
  & $adb -s $DEVSER shell "settings put system screen_brightness_mode 0" 2>&1 | Out-Null
  & $adb -s $DEVSER shell "settings put system screen_brightness 0" 2>&1 | Out-Null
  $nm = "$(& $adb -s $DEVSER shell 'settings get system screen_brightness_mode')".Trim(); $nb = "$(& $adb -s $DEVSER shell 'settings get system screen_brightness')".Trim()
  Add-Content -Encoding UTF8 $SETLOG ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] brightness -> mode 0 · 0 ($why) now mode=$nm brightness=$nb · original $($STATE.brightness_orig)")
}
function RestoreBright([string]$why) {
  if (-not (Test-Path $BRIGHTFILE)) { return }
  $orig = Get-Content -Raw -Encoding UTF8 $BRIGHTFILE | ConvertFrom-Json
  & $adb -s $DEVSER shell "settings put system screen_brightness_mode $($orig.screen_brightness_mode)" 2>&1 | Out-Null
  & $adb -s $DEVSER shell "settings put system screen_brightness $($orig.screen_brightness)" 2>&1 | Out-Null
  $nm = "$(& $adb -s $DEVSER shell 'settings get system screen_brightness_mode')".Trim(); $nb = "$(& $adb -s $DEVSER shell 'settings get system screen_brightness')".Trim()
  Add-Content -Encoding UTF8 $SETLOG ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] brightness restore ($why) -> now mode=$nm brightness=$nb")
}

Log "DRIVER START pid=$PID session=$Session watch=$WatchMode dry=$DryRun sessionEnd=$SessionEnd blocks=$($BLOCKLIST -join ',') smoke=$(-not $NoSmoke) retryRest=${RetryRestS}s queue=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
if ($DryRun) {
  $fm = $false
  foreach ($it in $QUEUE) {
    $pol = if ($it.Cell -eq "smokeN") { "upper_only" } else { "mark" }
    $ms = if ($it.Cell -eq "smokeN") { $CELL_FLOOR_SOC } elseif (-not $fm) { $FIRST_SOC } else { $CELL_FLOOR_SOC }
    if ($it.Cell -ne "smokeN") { $fm = $true }
    $bc = if ($it.FirstInBlock) { " blockcheck(soc>=$BLOCK_SOC, now+${BLOCK_MIN}min<=end)" } else { "" }
    Log "PLAN $($it.Key) -> results\$($it.OutName) label=$('{0:D2}' -f $script:seqNo)_$($it.Key) chain=$($CELLSPEC[$it.Cell].Chain) sha=$($CELLSPEC[$it.Cell].Sha.Substring(0,8)) lower=$pol minsoc=$ms$bc hours=$(HoursOf $it.Cell) out=$OUTC args=$(CellArgsOf $it.Cell)"
    $script:seqNo++
  }
  exit 0
}
$sessEndAt = Get-Date $SessionEnd
& $adb -s $DEVSER shell "settings put system screen_off_timeout 86400000" 2>&1 | Out-Null
Add-Content -Encoding UTF8 $SETLOG ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] screen_off_timeout -> 86400000 (driver $Session start, before first cell) now=" + "$(& $adb -s $DEVSER shell 'settings get system screen_off_timeout')")
SetBright "driver $Session start"
SaveState
$emergCount = 0
$stopAll = $false
while ($QUEUE.Count -gt 0 -and -not $stopAll) {
  $it = $QUEUE[0]; $QUEUE.RemoveAt(0)
  $cspec = $CELLSPEC[$it.Cell]
  if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x"; $STATE.stop_reason = "adb"; $QUEUE.Insert(0, $it); $stopAll = $true; break }
  $socv = SocNow
  if ($socv -ge 0 -and $socv -lt 30) { Log "SESSION END: SOC $socv < 30"; $STATE.stop_reason = "soc<30"; $QUEUE.Insert(0, $it); $stopAll = $true; break }
  if ($it.FirstInBlock -and -not $it.IsRe) {
    $needEnd = (Get-Date).AddMinutes($BLOCK_MIN)
    if ($socv -lt $BLOCK_SOC -or $needEnd -gt $sessEndAt) {
      Log "BLOCK $($it.Block) NOT STARTED: soc=$socv (>= $BLOCK_SOC) now+${BLOCK_MIN}min=$($needEnd.ToString('MM-dd HH:mm')) (<= $($sessEndAt.ToString('MM-dd HH:mm'))) -> stop from this block (prereg §6-7)"
      $STATE.stop_reason = "block condition at b$($it.Block) (soc=$socv)"; $QUEUE.Insert(0, $it); $stopAll = $true; break
    }
    Log "BLOCK $($it.Block) START soc=$socv now+${BLOCK_MIN}min=$($needEnd.ToString('MM-dd HH:mm'))"
  }
  if ($it.IsRe -and $it.RetryOf -and $script:lastCellEnd) {
    $restDone = ((Get-Date) - $script:lastCellEnd).TotalSeconds
    if ($restDone -lt $RetryRestS) { $wait = [int][math]::Ceiling($RetryRestS - $restDone); Log "REST before retry $($it.Key)_re ($($it.RetryOf)): ${wait}s more (rest so far $([int]$restDone)s, min ${RetryRestS}s)"; Start-Sleep -Seconds $wait }
    Log "REST done $([int](((Get-Date) - $script:lastCellEnd).TotalSeconds))s since the failed cell ended -> gate"
  }
  $isSmoke = ($it.Cell -eq "smokeN")
  $policy = if ($isSmoke) { "upper_only" } else { "mark" }
  $minSocCell = if ($isSmoke) { $CELL_FLOOR_SOC } elseif (-not $script:firstMeasuredDone) { $FIRST_SOC } else { $CELL_FLOOR_SOC }
  $sfx = if ($it.IsRe) { "_re" } else { "" }
  $outName = "$($it.OutName)$sfx"
  $keyName = "$($it.Key)$sfx"
  $gl = NextLabel $keyName
  Log "CELL $keyName -> $outName label=$gl policy=$policy minsoc=$minSocCell remaining=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
  $null = & "$TOOLSC\run_cell_c.ps1" -Tag $keyName -Label $gl -OutName $outName -CellArgs (CellArgsOf $it.Cell) -ChainSha $cspec.Sha -Duration $cspec.Dur -MinSoc $minSocCell -Hours (HoursOf $it.Cell) -LowerPolicy $policy -Deadline $SessionEnd
  $rc = $LASTEXITCODE
  Log "CELL $keyName rc=$rc"
  if ($rc -eq 2 -or $rc -eq 3 -or $rc -eq 4 -or $rc -eq 7) {
    $STATE.cells[$keyName] = "not_run_rc$rc"; $STATE.stop_reason = "rc$rc at $keyName"
    Log "STOP: $keyName not run (rc ${rc} - 2 gate blocked / 3 SOC / 4 time / 7 unexpected lower) -> this and later cells to the next session"
    $QUEUE.Insert(0, $it)
    $stopAll = $true; SaveState; break
  }
  if ($rc -eq 8) {
    $script:lastCellEnd = Get-Date
    $STATE.cells[$keyName] = "FAILED_stall_connection"
    Log "CELL FAILED $keyName (멈춤 — 연결, stall detection)"
    if ($isSmoke) {
      if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed 3x after smoke stall"; $STATE.stop_reason = "adb after smoke stall"; $stopAll = $true; SaveState; break }
      $STATE.notes += "smoke stalled (outside judgment) - continue"; Log "SMOKE stalled -> continue with the blocks"; SaveState; continue
    }
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
  $nev = WatchCheck $outName "$OUTC\$($keyName)_watch.json"
  SlotReport $outName
  $null = RunCheck $outName "$OUTC\$($keyName)_check.json"
  if ($isSmoke) {
    $STATE.cells[$keyName] = if ($sl.valid) { "smoke_valid" } else { "smoke_invalid" }
    Log "SMOKE $keyName valid=$($sl.valid) watch_events=$nev (outside judgment) -> blocks"
    if ($sl.emerg) { $emergCount++; $STATE.emergencies = $emergCount; Log "EMERGENCY in smoke (emergencies=$emergCount)" }
    SaveState; continue
  }
  $script:firstMeasuredDone = $true
  $null = JudgeRun $it $keyName $outName $gl
  $null = EnergyQc $it $keyName $outName
  $gact = GateAction $gl
  if ($gact -eq "run_marked_lower_fail") { $STATE.lower_marked += "$keyName"; Log "LOWER MARK $keyName (하한 미달 표시 실행 — §6-5)" }
  if ($sl.valid) {
    if ($STATE.watch -eq "on" -and $nev -gt 0) {
      if (-not $it.IsRe) {
        QueueRetry $it ""; $STATE.cells[$keyName] = "watch_event_invalid"; Log "WATCH EVENT $keyName ($nev) -> same cell again next (_re)"; SaveState; continue
      }
      $STATE.cells[$keyName] = "watch_event_invalid"; $STATE.notes += "$($it.Key) : watch event twice -> block $($it.Block) short"
      Log "WATCH EVENT $keyName ($nev) -> invalid, no further rerun (block $($it.Block) short)"; SaveState; continue
    }
    $STATE.cells[$keyName] = "valid"
    SaveState; continue
  }
  if ($sl.emerg) {
    $emergCount++; $STATE.emergencies = $emergCount; $STATE.cells[$keyName] = "FAILED_emergency"
    $STATE.notes += "$($it.Key) : emergency -> block $($it.Block) short"
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
$STATE.left_blocks = @(LeftBlocks)
if ($QUEUE.Count -gt 0) { $STATE.notes += "left: $(($QUEUE | ForEach-Object { $_.Key }) -join ',')" }
$STATE.emergencies = $emergCount
SaveState
& $adb -s $DEVSER shell "settings put system screen_off_timeout 600000" 2>&1 | Out-Null
Add-Content -Encoding UTF8 $SETLOG ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] restore (driver $Session end): screen_off_timeout -> 600000 now=" + "$(& $adb -s $DEVSER shell 'settings get system screen_off_timeout')")
RestoreBright "driver $Session end"
Log "DRIVER END emerg=$emergCount stop='$($STATE.stop_reason)' left_blocks=$($STATE.left_blocks -join ',') lower_marked=$($STATE.lower_marked -join ',') cells=$(($STATE.cells.Keys | ForEach-Object { "$_=$($STATE.cells[$_])" }) -join ' ')"
