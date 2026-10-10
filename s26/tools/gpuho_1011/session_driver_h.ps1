param([switch]$DryRun, [string]$WatchMode = "on", [int]$SeqStart = 1, [string]$SessionEnd = "2026-10-13 06:00", [string]$Blocks = "",
      [switch]$NoSmoke, [int]$RetryRestS = 600, [string]$RetryFirst = "", [switch]$Resume, [string]$PhoneSha = "")
# GPU holdout (GH 1011) session driver = copy of s26\tools\energy_1008\session_driver_c.ps1 (energy C). Changed only (prereg GPU홀드아웃_사전등록_v1.md §2 · GH prompt 4단계 · 규칙 표):
#   (1) one session "H": blocks 1..8 (or -Blocks "3,4" for the blocks left — whole block, both cells). Mirror order (§2-3): odd k = A -> B · even k = B -> A.
#       Cells GAh (A, gpu_eff_work100_v1 · GPU d100 300 s + d1 600 s) · GBh (B, gpu_eff_work50eq_v1 · GPU d50 T s + d1 900 - T s). Folders results\S26_<cell>_b<k>_1011h ·
#       host dir S26_host_gpuho_1011 · csv / logs *_h. Judge = sim\night1005e_judge_h.py (wrapper over the frozen night1005e_judge.py 2db1cda5) run + pair; no energy QC.
#   (2) cell 0 = smoke G (smoke_gpu_eff_v1, outside judgment, §2-4): pass = run_check_1005e.py GPU (slot valid · duration_complete · model SHA 6c7ab0a6 (or the phone file SHA) · input_spec · n > 0 · no emergency).
#       FAIL -> wait 120 s -> once more (_re) -> FAIL again -> §0-2: no cells, driver ends with stop_reason "smoke G failed twice".
#   (3) gate = night_1005e\start_gate_1005e.py (SOC 30..100 · SKIN <= 32 · AP <= 32 · BAT <= 30 · plugged 0). Lower (SKIN >= 29.1 · BAT >= 27.5) fail -> NOT swapped, runs marked "하한 미달" (§2-5).
#   (4) block condition (§2-7): at the start of every block SOC >= 45 (and now + 85 min <= -SessionEnd, default far), else the driver stops FROM that block (the session
#       then charges the phone and relaunches with -Blocks "<k>,..." -Resume -NoSmoke = "블록 사이 충전"). First measured cell of the session SOC >= 85 (-Resume = already met).
#   (5) brightness (§2-6): original mode / brightness kept in brightness_orig_h.json (written once) -> mode 0 · 0 -> restored at driver end. screen_off_timeout 86400000 is KEPT at the end (prompt 5단계-1).
#   (6) invalid cell (slot invalid · stall · watch event · emergency) -> same cell once more (_re) after >= 600 s rest + gate; invalid again -> "invalid_twice": that block = 계산 불가
#       (kept in the 8-block denominator), the block's other cell (if still queued) is dropped, the driver goes on with the next block. 3rd emergency of the session -> stop (safety).
#   (7) operational abort (adb lost during the cell: stall with adb not 'device', adb not 'device' right after the cell, or the slot error text says closed / not found / offline / timed out):
#       the result folder is renamed <OutName>_abort_<HHmmss>, the attempt is NOT consumed, the same item is re-queued at the front; reconnect loop (connect every 60 s · mdns lookup
#       every 5 min · up to 60 min) -> gate -> the same cell. Reconnect failure -> driver ends (the session reconnects by hand and relaunches with -Resume [-RetryFirst]).
# Every variable name is unique ignoring case. Serial only from $env:ANDROID_SERIAL (may be updated in memory after an mdns lookup), logged as <SERIAL>.
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_host_gpuho_1011"
$TOOLSH = "$wd\s26\tools\gpuho_1011"
$TOOLSE = "$wd\s26\tools\night_1005e"
$SIM = "C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
$DSFX = "1011h"
$OUTC = "$SIM\out_gpuho"
$JUDGEHPY = "$SIM\night1005e_judge_h.py"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$script:DEVSER = $env:ANDROID_SERIAL
if (-not $script:DEVSER -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
New-Item -ItemType Directory -Force $OUTC | Out-Null
New-Item -ItemType Directory -Force $H | Out-Null
$logFile = "$H\driver_h_log.txt"
$stateFile = "$H\driver_state_h.json"
$skinCsv = "$H\skin_watch_h.csv"
$phoneCsv = "$H\phone_watch_h.csv"
$gateCsvPath = "$H\gate_log_h.csv"
$BRIGHTFILE = "$H\brightness_orig_h.json"
$SETLOG = "$H\phone_settings_log_h.txt"
function Log([string]$msg) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $msg
  if ($script:DEVSER) { $line = $line -replace [regex]::Escape($script:DEVSER), "<SERIAL>" }
  if ($DryRun) { $line; return }
  for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $logFile -Encoding UTF8 -Value $line -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 } }
}
$COMMONARGS = "--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
$GPUSHA = "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0"
$CELLSPEC = @{
  GAh    = @{ Chain="gpu_eff_work100_v1";  Dur=900; Spans=400000; Sha="df0ffa2f15ddc9c1c0cab60cd09daeff48e34165296af64aaf77e58bc85eb513"; Tmo="--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600" }
  GBh    = @{ Chain="gpu_eff_work50eq_v1"; Dur=900; Spans=400000; Sha="28d84c5c4c286dd94cfca13c9ef5dd2f46c7e34224c3a378ed0be50ae6838205"; Tmo="--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600" }
  smokeG = @{ Chain="smoke_gpu_eff_v1";    Dur=60;  Spans=50000;  Sha="16c951ba993423b82b2921b2e000957afeb7ea8e5b192121590a381ae29aea29"; Tmo="--runner-timeout-seconds 900 --logger-exit-timeout-seconds 600 --analyze-timeout-seconds 300 --cooling-min-seconds 60" }
}
$BLOCK_SOC = 45; $FIRST_SOC = 85; $CELL_FLOOR_SOC = 30; $BLOCK_MIN = 2 * 35 + 15; $SMOKE_RETRY_WAIT_S = 120; $EMERG_STOP = 3
$ABORT_PATTERN = "closed|not found|offline|timed out|timeout|device '.*' not|no devices|connection reset|broken pipe"
function NewItem([string]$cellName, [int]$blk, [bool]$firstInBlock) {
  if ($cellName -eq "smokeG") { $kk = "smokeG"; $on = "S26_smokeG_$DSFX" } else { $kk = "${cellName}_b$blk"; $on = "S26_${cellName}_b${blk}_$DSFX" }
  return [pscustomobject]@{ Cell = $cellName; Block = $blk; Key = $kk; OutName = $on; FirstInBlock = $firstInBlock; IsRe = $false; RetryOf = ""; Aborts = 0 }
}
$BLOCKLIST = @()
if ($Blocks -eq "none") { $BLOCKLIST = @() } elseif ($Blocks) { $BLOCKLIST = @($Blocks -split "," | ForEach-Object { [int]$_.Trim() }) } else { $BLOCKLIST = @(1, 2, 3, 4, 5, 6, 7, 8) }
foreach ($bk in $BLOCKLIST) { if ($bk -lt 1 -or $bk -gt 8) { throw "block $bk not in 1..8" } }
$QUEUE = New-Object System.Collections.ArrayList
if (-not $NoSmoke) { [void]$QUEUE.Add((NewItem "smokeG" 0 $false)) }
foreach ($bk in $BLOCKLIST) {
  if ($bk % 2 -eq 1) { $c1st = "GAh"; $c2nd = "GBh" } else { $c1st = "GBh"; $c2nd = "GAh" }
  [void]$QUEUE.Add((NewItem $c1st $bk $true)); [void]$QUEUE.Add((NewItem $c2nd $bk $false))
}
if ($RetryFirst) {
  $rp = $RetryFirst -split ":"
  if (-not $CELLSPEC.ContainsKey($rp[0]) -or $rp[0] -eq "smokeG") { throw "RetryFirst cell $($rp[0])" }
  $rItem = NewItem $rp[0] ([int]$rp[1]) $false; $rItem.IsRe = $true; $rItem.RetryOf = "slot_invalid (previous driver run)"
  $QUEUE.Insert(0, $rItem)
}
$STATE = [ordered]@{ session = "H"; watch = $WatchMode; session_end = $SessionEnd; blocks = $BLOCKLIST; cells = [ordered]@{}; lower_marked = @(); not_computable = [ordered]@{}; aborts = @();
                     brightness_orig = $null; emergencies = 0; stop_reason = ""; left_blocks = @(); notes = @(); phone_model_sha = $PhoneSha; smoke = [ordered]@{} }
$script:seqNo = $SeqStart
$script:lastCellEnd = $null
$script:firstMeasuredDone = [bool]$Resume
function SaveState() { if (-not $DryRun) { ($STATE | ConvertTo-Json -Depth 8) | Set-Content -Encoding UTF8 $stateFile } }
function CellArgsOf([string]$cellName) { $cspec = $CELLSPEC[$cellName]; return "--npu-chain tools\chains\$($cspec.Chain).json --duration $($cspec.Dur) --npu-max-inference-spans $($cspec.Spans) $($cspec.Tmo) $COMMONARGS" }
function HoursOf([string]$cellName) { return [math]::Round(($CELLSPEC[$cellName].Dur + 900) / 3600.0, 3) }
function NextLabel([string]$core) { $lab = ("{0:D2}_{1}" -f $script:seqNo, $core); $script:seqNo++; return $lab }
function AdbState() { return "$(& $adb -s $script:DEVSER get-state 2>$null)".Trim() }
function MdnsAddr() {
  # the phone's _adb-tls-connect line: "adb-<serial>-<x>  _adb-tls-connect._tcp  <ip>:<port>" -> ip:port (empty when none)
  $lines = @(& $adb mdns services 2>$null | ForEach-Object { "$_" } | Where-Object { $_ -match "_adb-tls-connect" })
  foreach ($ln in $lines) { if ($ln -match "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})\s*$") { return $matches[1] } }
  return ""
}
function AdbOk() {
  if ((AdbState) -eq "device") { return $true }
  for ($k = 1; $k -le 60; $k++) {
    Log "ADB state not device -> connect try $k (every 60 s · mdns every 5)"
    & $adb connect $script:DEVSER 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    if ((AdbState) -eq "device") { Log "ADB reconnected (try $k)"; return $true }
    if ($k % 5 -eq 0) {
      $ma = MdnsAddr
      if ($ma -and $ma -ne $script:DEVSER) {
        & $adb connect $ma 2>&1 | Out-Null
        Start-Sleep -Seconds 5
        if ("$(& $adb -s $ma get-state 2>$null)".Trim() -eq "device") { $script:DEVSER = $ma; $env:ANDROID_SERIAL = $ma; Log "ADB reconnected via mdns address (try $k) -> serial updated (<SERIAL>)"; return $true }
      }
    }
    Start-Sleep -Seconds 55
  }
  return $false
}
function SocNow() { $l = (& $adb -s $script:DEVSER shell "dumpsys battery | grep -E '^  level:'") -replace "\s+", " "; try { return [int](("$l" -split ":")[1].Trim()) } catch { return -1 } }
function PhoneModelSha() { $o = "$(& $adb -s $script:DEVSER shell 'sha256sum /data/local/tmp/efficientnet_lite0.tflite' 2>$null)".Trim(); return (($o -split "\s+")[0]) }
function ReadSlot([string]$outName) {
  $mp = "$wd\results\$outName\experiment_manifest.json"
  $res = @{ valid = $false; emerg = $false; text = "no manifest"; error = "" }
  if (Test-Path $mp) {
    try {
      $man = Get-Content -Raw -Encoding UTF8 $mp | ConvertFrom-Json
      $slot = $man.runs[0]
      $res.valid = [bool]$slot.validation.valid
      $res.emerg = ("$($slot.status)" -eq "emergency_aborted") -or ("$($man.halt_reason)" -match "emergency")
      $res.error = "$($slot.error) $($man.halt_reason)"
      $etxt = $res.error; if ($script:DEVSER) { $etxt = $etxt -replace [regex]::Escape($script:DEVSER), "<SERIAL>" }
      $res.text = "manifest=$($man.status) slot=$($slot.status) valid=$($res.valid) failed=$(($slot.validation.failed_checks) -join ',') halt=$($man.halt_reason) error=$($etxt.Substring(0, [Math]::Min(160, $etxt.Length)))"
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
  & py -X utf8 $JUDGEHPY watchcheck $rd --phone-watch $phoneCsv --out $outJson > "$H\watch_$outName.stdout.txt" 2> "$H\watch_$outName.stderr.txt"
  $wrc = $LASTEXITCODE
  if ($wrc -ne 0 -or -not (Test-Path $outJson)) { Log "WATCHCHECK $outName rc=$wrc (failed)"; return -1 }
  $wj = Get-Content -Raw -Encoding UTF8 $outJson | ConvertFrom-Json
  $nev = [int]$wj.phone_watch.n_events
  Log "WATCHCHECK $outName events=$nev samples=$($wj.phone_watch.n_samples) max_gap_s=$($wj.phone_watch.max_gap_s) ref_focus='$($wj.phone_watch.reference_focus)'"
  return $nev
}
function SlotReport([string]$outName) {
  $rep = & py -X utf8 "$wd\s26\tools\night_1002\chain_slot_report.py" "$wd\results\$outName" 2>&1 | ForEach-Object { "$_" }
  if ($script:DEVSER) { $rep = $rep | ForEach-Object { $_ -replace [regex]::Escape($script:DEVSER), "<SERIAL>" } }
  $rep | Set-Content -Encoding utf8 "$H\slot_$outName.txt"
}
function RunCheck([string]$outName, [string]$outJson) {
  $psha = $STATE.phone_model_sha
  $rcOut = & py -X utf8 "$TOOLSE\run_check_1005e.py" "$wd\results\$outName" GPU --phone-sha $psha 2>&1 | ForEach-Object { "$_" }
  $rcCode = $LASTEXITCODE
  $lastLine = ($rcOut | Select-Object -Last 1)
  if ($script:DEVSER) { $lastLine = "$lastLine" -replace [regex]::Escape($script:DEVSER), "<SERIAL>" }
  $lastLine | Set-Content -Encoding utf8 $outJson
  Log "RUNCHECK $outName rc=$rcCode :: $lastLine"
  return $rcCode
}
function JudgeRun($it, [string]$keyName, [string]$outName, [string]$gateLabel) {
  $rd = RunDirOf $outName
  if (-not $rd) { Log "JUDGE $outName : no single run dir"; return 9 }
  $jout = "$OUTC\$keyName.json"
  & py -X utf8 $JUDGEHPY run $rd --cell $it.Cell --block $it.Block --gate-label $gateLabel --watch $skinCsv --gate-log $gateCsvPath --phone-watch $phoneCsv --out $jout > "$H\judge_$outName.stdout.txt" 2> "$H\judge_$outName.stderr.txt"
  $jrc = $LASTEXITCODE
  $msl = ""
  if ($jrc -eq 0 -and (Test-Path $jout)) { try { $jj = Get-Content -Raw -Encoding UTF8 $jout | ConvertFrom-Json; $msl = "$($jj.model_sha_check.label)" } catch { $msl = "parse error" } }
  Log "JUDGE $outName rc=$jrc out=$jout model_sha='$msl' stderr=$((Get-Content -Encoding UTF8 "$H\judge_$outName.stderr.txt" -ErrorAction SilentlyContinue | Select-Object -Last 1) -join ' ')"
  return $jrc
}
function TryPair([int]$blk) {
  $ja = $STATE.cells.Keys | Where-Object { $_ -like "GAh_b$blk*" -and $STATE.cells[$_] -eq "valid" } | Select-Object -First 1
  $jb = $STATE.cells.Keys | Where-Object { $_ -like "GBh_b$blk*" -and $STATE.cells[$_] -eq "valid" } | Select-Object -First 1
  $pa = "$OUTC\pair_b$blk.json"
  if ($ja -and $jb -and -not (Test-Path $pa)) {
    & py -X utf8 $JUDGEHPY pair --a "$OUTC\$ja.json" --b "$OUTC\$jb.json" --out $pa > "$H\pair_b$blk.stdout.txt" 2> "$H\pair_b$blk.stderr.txt"
    Log "PAIR b$blk exit=$LASTEXITCODE out=$pa a=$ja b=$jb (열 지표 기술 — 판정은 judge_gpuho 한 번)"
  }
}
function QueueRetry($it, [string]$why) {
  $reIt = NewItem $it.Cell $it.Block $false; $reIt.IsRe = $true; $reIt.RetryOf = $why
  $QUEUE.Insert(0, $reIt)
}
function MarkNotComputable($it, [string]$why) {
  $STATE.not_computable["b$($it.Block)"] = "invalid_twice ($($it.Cell): $why)"
  # drop the block's other cell if it is still queued (the block is not computable either way — 등록 §2-8 · 규칙 표)
  $dropped = @()
  for ($qi = $QUEUE.Count - 1; $qi -ge 0; $qi--) { if ($QUEUE[$qi].Block -eq $it.Block -and $QUEUE[$qi].Cell -ne "smokeG") { $dropped += $QUEUE[$qi].Key; $QUEUE.RemoveAt($qi) } }
  Log "INVALID TWICE $($it.Key) ($why) -> block $($it.Block) = 계산 불가 (분모 8 유지) · dropped queued: $($dropped -join ',') -> next block"
}
function AbortRename([string]$outName) {
  $stamp = Get-Date -Format "HHmmss"
  $newName = "${outName}_abort_$stamp"
  try { if (Test-Path "$wd\results\$outName") { Rename-Item -Path "$wd\results\$outName" -NewName $newName -ErrorAction Stop } } catch { Log "ABORT rename failed: $_"; return "" }
  foreach ($sfx2 in @(".console.txt", ".stderr.txt")) { if (Test-Path "$wd\results\$outName$sfx2") { try { Rename-Item -Path "$wd\results\$outName$sfx2" -NewName "$newName$sfx2" -ErrorAction SilentlyContinue } catch { } } }
  return $newName
}
function IsAbort([string]$outName, [string]$wres, $sl) {
  if ((AdbState) -ne "device") { return "adb not device after cell" }
  if ($wres -eq "stall" -or $wres -eq "cap") {
    $csv = "$H\adb_state_h.csv"
    if (Test-Path $csv) { $last = @(Import-Csv $csv -Encoding UTF8 | Where-Object { $_.cell -eq $outName -or $_.cell -like "$outName*" }) | Select-Object -Last 1; if ($last -and "$($last.adb_state_ok)" -eq "0") { return "stall with adb state 0" } }
  }
  if ($sl -and ($sl.error -match $ABORT_PATTERN)) { return "slot error matches adb-loss pattern" }
  return ""
}
function LeftBlocks() { return @($QUEUE | Where-Object { $_.Cell -ne "smokeG" } | ForEach-Object { $_.Block } | Select-Object -Unique) }
function SetBright([string]$why) {
  if (-not (Test-Path $BRIGHTFILE)) {
    $om = "$(& $adb -s $script:DEVSER shell 'settings get system screen_brightness_mode')".Trim()
    $ob = "$(& $adb -s $script:DEVSER shell 'settings get system screen_brightness')".Trim()
    ([ordered]@{ screen_brightness_mode = $om; screen_brightness = $ob; recorded = (Get-Date -Format "yyyy-MM-dd HH:mm:ss K"); by = "session_driver_h" } | ConvertTo-Json) | Set-Content -Encoding UTF8 $BRIGHTFILE
  }
  $orig = Get-Content -Raw -Encoding UTF8 $BRIGHTFILE | ConvertFrom-Json
  $STATE.brightness_orig = "mode=$($orig.screen_brightness_mode) brightness=$($orig.screen_brightness) (recorded $($orig.recorded))"
  & $adb -s $script:DEVSER shell "settings put system screen_brightness_mode 0" 2>&1 | Out-Null
  & $adb -s $script:DEVSER shell "settings put system screen_brightness 0" 2>&1 | Out-Null
  $nm = "$(& $adb -s $script:DEVSER shell 'settings get system screen_brightness_mode')".Trim(); $nb = "$(& $adb -s $script:DEVSER shell 'settings get system screen_brightness')".Trim()
  Add-Content -Encoding UTF8 $SETLOG ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] brightness -> mode 0 · 0 ($why) now mode=$nm brightness=$nb · original $($STATE.brightness_orig)")
}
function RestoreBright([string]$why) {
  if (-not (Test-Path $BRIGHTFILE)) { return }
  $orig = Get-Content -Raw -Encoding UTF8 $BRIGHTFILE | ConvertFrom-Json
  & $adb -s $script:DEVSER shell "settings put system screen_brightness_mode $($orig.screen_brightness_mode)" 2>&1 | Out-Null
  & $adb -s $script:DEVSER shell "settings put system screen_brightness $($orig.screen_brightness)" 2>&1 | Out-Null
  $nm = "$(& $adb -s $script:DEVSER shell 'settings get system screen_brightness_mode')".Trim(); $nb = "$(& $adb -s $script:DEVSER shell 'settings get system screen_brightness')".Trim()
  Add-Content -Encoding UTF8 $SETLOG ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] brightness restore ($why) -> now mode=$nm brightness=$nb")
}

Log "DRIVER START pid=$PID session=H watch=$WatchMode dry=$DryRun sessionEnd=$SessionEnd blocks=$($BLOCKLIST -join ',') smoke=$(-not $NoSmoke) retryRest=${RetryRestS}s resume=$Resume retryFirst=$RetryFirst queue=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
if ($DryRun) {
  $fm = [bool]$Resume
  foreach ($it in $QUEUE) {
    $pol = if ($it.Cell -eq "smokeG") { "upper_only" } else { "mark" }
    $ms = if ($it.Cell -eq "smokeG") { $CELL_FLOOR_SOC } elseif (-not $fm) { $FIRST_SOC } else { $CELL_FLOOR_SOC }
    if ($it.Cell -ne "smokeG") { $fm = $true }
    $bc = if ($it.FirstInBlock) { " blockcheck(soc>=$BLOCK_SOC, now+${BLOCK_MIN}min<=end)" } else { "" }
    $psx = if ($it.IsRe) { "_re" } else { "" }
    Log "PLAN $($it.Key)$psx -> results\$($it.OutName)$psx label=$('{0:D2}' -f $script:seqNo)_$($it.Key)$psx chain=$($CELLSPEC[$it.Cell].Chain) sha=$($CELLSPEC[$it.Cell].Sha.Substring(0,8)) lower=$pol minsoc=$ms$bc hours=$(HoursOf $it.Cell) out=$OUTC args=$(CellArgsOf $it.Cell)"
    $script:seqNo++
  }
  exit 0
}
$sessEndAt = Get-Date $SessionEnd
if (-not (AdbOk)) { Log "DRIVER END: adb not device at start (reconnect failed)"; exit 3 }
if (-not $STATE.phone_model_sha) { $STATE.phone_model_sha = PhoneModelSha }
Log "PHONE model file sha256 = $($STATE.phone_model_sha) (expected $GPUSHA · equal=$($STATE.phone_model_sha -eq $GPUSHA))"
& $adb -s $script:DEVSER shell "settings put system screen_off_timeout 86400000" 2>&1 | Out-Null
Add-Content -Encoding UTF8 $SETLOG ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] screen_off_timeout -> 86400000 (driver H start, before first cell) now=" + "$(& $adb -s $script:DEVSER shell 'settings get system screen_off_timeout')")
SetBright "driver H start"
SaveState
$emergCount = 0
$stopAll = $false
$smokeFails = 0
while ($QUEUE.Count -gt 0 -and -not $stopAll) {
  $it = $QUEUE[0]; $QUEUE.RemoveAt(0)
  $cspec = $CELLSPEC[$it.Cell]
  if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed (60 min)"; $STATE.stop_reason = "adb"; $QUEUE.Insert(0, $it); $stopAll = $true; break }
  $socv = SocNow
  if ($socv -ge 0 -and $socv -lt 30) { Log "SESSION END: SOC $socv < 30"; $STATE.stop_reason = "soc<30 at $($it.Key)"; $QUEUE.Insert(0, $it); $stopAll = $true; break }
  if ($it.FirstInBlock -and -not $it.IsRe) {
    $needEnd = (Get-Date).AddMinutes($BLOCK_MIN)
    if ($socv -lt $BLOCK_SOC -or $needEnd -gt $sessEndAt) {
      Log "BLOCK $($it.Block) NOT STARTED: soc=$socv (>= $BLOCK_SOC) now+${BLOCK_MIN}min=$($needEnd.ToString('MM-dd HH:mm')) (<= $($sessEndAt.ToString('MM-dd HH:mm'))) -> stop from this block (충전 필요 — 블록 사이 충전 · 등록 §2-7)"
      $STATE.stop_reason = "block condition at b$($it.Block) (soc=$socv)"; $QUEUE.Insert(0, $it); $stopAll = $true; break
    }
    Log "BLOCK $($it.Block) START soc=$socv now+${BLOCK_MIN}min=$($needEnd.ToString('MM-dd HH:mm'))"
  }
  if ($it.IsRe -and $it.RetryOf -and $script:lastCellEnd) {
    $restDone = ((Get-Date) - $script:lastCellEnd).TotalSeconds
    if ($restDone -lt $RetryRestS) { $wait = [int][math]::Ceiling($RetryRestS - $restDone); Log "REST before retry $($it.Key)_re ($($it.RetryOf)): ${wait}s more (rest so far $([int]$restDone)s, min ${RetryRestS}s)"; Start-Sleep -Seconds $wait }
    Log "REST done $([int](((Get-Date) - $script:lastCellEnd).TotalSeconds))s since the failed cell ended -> gate"
  }
  $isSmoke = ($it.Cell -eq "smokeG")
  $policy = if ($isSmoke) { "upper_only" } else { "mark" }
  $minSocCell = if ($isSmoke) { $CELL_FLOOR_SOC } elseif (-not $script:firstMeasuredDone) { $FIRST_SOC } else { $CELL_FLOOR_SOC }
  $sfx = if ($it.IsRe) { "_re" } else { "" }
  $outName = "$($it.OutName)$sfx"
  $keyName = "$($it.Key)$sfx"
  if (Test-Path "$wd\results\$outName") { $prev = AbortRename $outName; Log "OUT DIR already exists (earlier abandoned attempt) -> renamed $prev" }
  $gl = NextLabel $keyName
  Log "CELL $keyName -> $outName label=$gl policy=$policy minsoc=$minSocCell aborts=$($it.Aborts) remaining=$(($QUEUE | ForEach-Object { $_.Key }) -join ',')"
  $null = & "$TOOLSH\run_cell_h.ps1" -Tag $keyName -Label $gl -OutName $outName -CellArgs (CellArgsOf $it.Cell) -ChainSha $cspec.Sha -Duration $cspec.Dur -MinSoc $minSocCell -Hours (HoursOf $it.Cell) -LowerPolicy $policy -Deadline $SessionEnd
  $rc = $LASTEXITCODE
  Log "CELL $keyName rc=$rc"
  if ($rc -eq 2 -or $rc -eq 3 -or $rc -eq 4 -or $rc -eq 7) {
    $STATE.cells[$keyName] = "not_run_rc$rc"; $STATE.stop_reason = "rc$rc at $keyName"
    Log "STOP: $keyName not run (rc ${rc} - 2 gate blocked / 3 SOC / 4 time / 7 unexpected lower) -> this and later cells wait for the session (charge / gate)"
    $QUEUE.Insert(0, $it)
    $stopAll = $true; SaveState; break
  }
  if ($rc -ne 0 -and $rc -ne 8) {
    $STATE.cells[$keyName] = "stopped_rc$rc"; $STATE.stop_reason = "rc$rc at $keyName"
    Log "MEASUREMENT STOP: $keyName stopped before launch (rc $rc)"
    $QUEUE.Insert(0, $it); $stopAll = $true; SaveState; break
  }
  $script:lastCellEnd = Get-Date
  $wres = if ($rc -eq 8) { "stall" } else { "exited" }
  $sl = ReadSlot $outName
  Log "SLOT $outName :: $($sl.text) emerg=$($sl.emerg) wait=$wres"
  # ---- operational abort? (adb lost — attempt not consumed)
  $abortWhy = ""
  if (-not $sl.valid) { $abortWhy = IsAbort $outName $wres $sl }
  if ($abortWhy) {
    $newName = AbortRename $outName
    $STATE.aborts += "$keyName -> $newName ($abortWhy)"
    $STATE.cells["$keyName" + "_abort_" + ($newName -replace '.*_abort_', '')] = "abort ($abortWhy)"
    $it.Aborts = $it.Aborts + 1
    Log "ABORT $keyName ($abortWhy) -> renamed $newName · attempt NOT consumed · same cell again after reconnect + gate (aborts=$($it.Aborts))"
    $QUEUE.Insert(0, $it)
    if ($it.Aborts -ge 4) { Log "SESSION END: 4 aborts on $($it.Key) -> stop (the session looks at the connection)"; $STATE.stop_reason = "4 aborts at $($it.Key)"; $stopAll = $true; SaveState; break }
    SaveState
    if (-not (AdbOk)) { Log "SESSION END: adb reconnect failed after abort"; $STATE.stop_reason = "adb after abort at $keyName"; $stopAll = $true; SaveState; break }
    continue
  }
  $nev = WatchCheck $outName "$OUTC\$($keyName)_watch.json"
  SlotReport $outName
  $chk = RunCheck $outName "$OUTC\$($keyName)_check.json"
  if ($isSmoke) {
    $STATE.smoke[$keyName] = if ($chk -eq 0) { "pass" } else { "FAIL (rc $chk)" }
    Log "SMOKE G $keyName runcheck rc=$chk valid=$($sl.valid) watch_events=$nev (outside judgment)"
    if ($chk -eq 0) { SaveState; continue }
    $smokeFails++
    if ($smokeFails -ge 2) { Log "SMOKE G FAILED TWICE -> 등록 §0-2: 측정 안 함 — no cells"; $STATE.stop_reason = "smoke G failed twice (등록 §0-2)"; $stopAll = $true; SaveState; break }
    Log "SMOKE G FAIL #1 -> wait ${SMOKE_RETRY_WAIT_S}s -> once more (_re)"
    Start-Sleep -Seconds $SMOKE_RETRY_WAIT_S
    $reS = NewItem "smokeG" 0 $false; $reS.IsRe = $true; $reS.RetryOf = "smoke fail"
    $QUEUE.Insert(0, $reS); SaveState; continue
  }
  $script:firstMeasuredDone = $true
  $null = JudgeRun $it $keyName $outName $gl
  $gact = GateAction $gl
  if ($gact -eq "run_marked_lower_fail") { $STATE.lower_marked += "$keyName"; Log "LOWER MARK $keyName (하한 미달 표시 실행 — 등록 §2-5)" }
  $invalidWhy = ""
  if ($sl.emerg) { $emergCount++; $STATE.emergencies = $emergCount; $invalidWhy = "emergency"; Log "EMERGENCY $keyName (emergencies=$emergCount)" }
  elseif (-not $sl.valid) { $invalidWhy = if ($wres -ne "exited") { "stall" } else { "slot_invalid" } }
  elseif ($STATE.watch -eq "on" -and $nev -gt 0) { $invalidWhy = "watch_event ($nev)" }
  elseif ($chk -ne 0) { $invalidWhy = "runcheck (GPU evidence) rc $chk" }
  if (-not $invalidWhy) {
    $STATE.cells[$keyName] = "valid"
    SaveState
    TryPair $it.Block
    continue
  }
  $STATE.cells[$keyName] = "invalid ($invalidWhy)"
  if ($emergCount -ge $EMERG_STOP) { Log "SESSION END: ${EMERG_STOP}rd emergency (safety)"; $STATE.stop_reason = "${EMERG_STOP}rd emergency"; $stopAll = $true; SaveState; break }
  if (-not $it.IsRe) {
    QueueRetry $it $invalidWhy
    Log "INVALID $keyName ($invalidWhy) -> same cell once more after >= ${RetryRestS}s rest + gate (_re)"; SaveState; continue
  }
  MarkNotComputable $it $invalidWhy
  SaveState
}
$STATE.left_blocks = @(LeftBlocks)
if ($QUEUE.Count -gt 0) { $STATE.notes += "left: $(($QUEUE | ForEach-Object { $_.Key }) -join ',')" }
$STATE.emergencies = $emergCount
SaveState
Add-Content -Encoding UTF8 $SETLOG ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] driver H end: screen_off_timeout kept (prompt 5단계-1) now=" + "$(& $adb -s $script:DEVSER shell 'settings get system screen_off_timeout')")
RestoreBright "driver H end"
Log "DRIVER END emerg=$emergCount stop='$($STATE.stop_reason)' left_blocks=$($STATE.left_blocks -join ',') lower_marked=$($STATE.lower_marked -join ',') not_computable=$(($STATE.not_computable.Keys | ForEach-Object { "$_=$($STATE.not_computable[$_])" }) -join ' ') cells=$(($STATE.cells.Keys | ForEach-Object { "$_=$($STATE.cells[$_])" }) -join ' ')"
