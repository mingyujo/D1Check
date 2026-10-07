param([Parameter(Mandatory=$true)][string]$OutCsv, [Parameter(Mandatory=$true)][string]$StopFile, [int]$PeriodS = 10)
# [1008 mixreq copy] of s26\tools\night_1005e\phone_watch_1005e.ps1 - changed only: OutCsv/StopFile are mandatory parameters and the
# serial comes from $env:ANDROID_SERIAL only (no serial_1005e.ps1 dot-source). READ-ONLY adb: dumpsys + date, no setting is changed.
# Fixed cadence: sample k starts at t0 + k*period. One adb shell call per sample runs 5 phone commands:
#   (1) dumpsys telephony.registry | grep mCallState=   (2) dumpsys audio | grep -m1 'Actual mode'
#   (3) dumpsys window | grep -m1 mCurrentFocus=         (4) dumpsys power | grep -m1 mWakefulness=   (5) date +%s%3N
# CSV: pc_ms, phone_ms, call_state, audio_mode, focus, wakefulness, cmd_ms, ok, basic_normal, period_s, err
#   basic_normal = all call states 0 and MODE_NORMAL and Awake. err = adb exit code only (stderr dropped: it may contain the address).
# cmd_ms > 1000 three samples in a row -> period 30 s from then on.
$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
$evlog = Join-Path (Split-Path $OutCsv) "phone_watch_events.txt"
function Ev([string]$m) { $l = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff K") + "] " + $m; if ($DEVSER) { $l = $l -replace [regex]::Escape($DEVSER), "<SERIAL>" }; Add-Content -Path $evlog -Encoding UTF8 -Value $l }
if (-not $DEVSER) { Ev "ANDROID_SERIAL empty -> exit"; exit 2 }
if (-not (Test-Path $OutCsv)) { Add-Content -Path $OutCsv -Encoding UTF8 -Value "pc_ms,phone_ms,call_state,audio_mode,focus,wakefulness,cmd_ms,ok,basic_normal,period_s,err" }
$cmd = 'echo C=$(dumpsys telephony.registry | grep mCallState= | sed ''s/.*mCallState=//'' | tr ''\n'' ''|''); echo A=$(dumpsys audio | grep -m1 ''Actual mode'' | sed ''s/.*= //''); echo W=$(dumpsys window | grep -m1 mCurrentFocus= | sed ''s/.*mCurrentFocus=//''); echo P=$(dumpsys power | grep -m1 mWakefulness= | sed ''s/.*mWakefulness=//''); echo T=$(date +%s%3N)'
Ev "START pid=$PID period=$PeriodS out=$OutCsv"
$period = $PeriodS
$slow = 0
$t0 = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
$k = 0
while (-not (Test-Path $StopFile)) {
  $due = $t0 + [int64]$k * $period * 1000
  $now = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
  if ($due -gt $now) { Start-Sleep -Milliseconds ([int]($due - $now)) }
  $pc = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $out = @(& $adb -s $DEVSER shell $cmd 2>&1 | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] })
  $rc = $LASTEXITCODE
  $sw.Stop()
  $ms = $sw.ElapsedMilliseconds
  $v = @{ C = ""; A = ""; W = ""; P = ""; T = "" }
  foreach ($line in $out) { $lineText = "$line"; if ($lineText -match '^([CAWPT])=(.*)$') { $v[$matches[1]] = $matches[2].Trim() } }
  $call = $v.C.TrimEnd('|')
  $focus = $v.W -replace '^Window\{[0-9a-f]+ u\d+ ', '' -replace '\}$', ''
  $ok = ($rc -eq 0) -and $call -and $v.A -and $v.W -and $v.P -and ($v.T -match '^\d+$')
  $basic = $ok -and (($call -split '\|' | Where-Object { $_ -ne '0' }).Count -eq 0) -and ($v.A -eq 'MODE_NORMAL') -and ($v.P -eq 'Awake')
  $err = if ($rc -ne 0) { "adb_rc_$rc" } else { "" }
  $row = @($pc, $(if ($v.T -match '^\d+$') { $v.T } else { "" }), $call, $v.A, $focus, $v.P, $ms, [int][bool]$ok, [int][bool]$basic, $period, $err) | ForEach-Object { '"' + ("$_" -replace '"', "'") + '"' }
  for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $OutCsv -Encoding UTF8 -Value ($row -join ",") -ErrorAction Stop; break } catch { Start-Sleep -Milliseconds 200 } }
  if ($ms -gt 1000) { $slow++ } else { $slow = 0 }
  if ($slow -ge 3 -and $period -lt 30) {
    $period = 30; $t0 = [DateTimeOffset]::Now.ToUnixTimeMilliseconds() + 30000; $k = 0
    Ev "PERIOD -> 30 s (cmd_ms > 1000 three in a row)"
    continue
  }
  $k++
  $nowAfter = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
  while (($t0 + [int64]$k * $period * 1000) -lt $nowAfter) { $k++ }
}
Ev "STOP pid=$PID"
