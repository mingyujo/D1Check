param([string]$OutCsv = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_1005e\phone_watch_1005e.csv",
      [string]$StopFile = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_1005e\phone_watch.stop",
      [int]$PeriodS = 10)
# NIGHT 1005e call/screen watch (prereg night1005e s3). READ-ONLY adb: dumpsys + date only, no setting is changed.
# Fixed cadence: sample k starts at t0 + k*period (not "sleep after the command").
# One `adb shell` call per sample runs these 5 phone commands (chosen from this phone's real output, 2026-10-05 23:1x):
#   (1) dumpsys telephony.registry | grep mCallState=        -> "    mCallState=0" (one line per phone slot; all kept, joined by '|')
#   (2) dumpsys audio | grep -m1 'Actual mode'                -> "- Actual mode = MODE_NORMAL"   (Wi-Fi calls such as KakaoTalk change this)
#   (3) dumpsys window | grep -m1 mCurrentFocus=              -> "  mCurrentFocus=Window{13012bd u0 com.sec.android.app.launcher/...LauncherActivity}"
#                                                                (the hex window id and 'u0' are dropped; the component is kept)
#   (4) dumpsys power | grep -m1 mWakefulness=                -> "  mWakefulness=Awake"
#   (5) date +%s%3N                                           -> phone epoch ms
# CSV: pc_ms, phone_ms, call_state, audio_mode, focus, wakefulness, cmd_ms, ok, basic_normal, period_s, err
#   cmd_ms = wall time of the one adb call; ok = 1 when the adb call returned 0 and all 5 values parsed;
#   basic_normal = (1) all 0 and (2) MODE_NORMAL and (4) Awake (focus (3) is judged per run by night1005e_judge.py);
#   err = adb exit code only (stderr is discarded: adb error text contains the device address).
# cmd_ms > 1000 three samples in a row -> period 30 s from then on (time written to phone_watch_events.txt).
# Serial only from $env:ANDROID_SERIAL (set from `adb devices` when empty); never written.
$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
if (-not $env:ANDROID_SERIAL) { . "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\s26\tools\night_1005e\serial_1005e.ps1" }
$S = $env:ANDROID_SERIAL
$evlog = Join-Path (Split-Path $OutCsv) "phone_watch_events.txt"
function Ev([string]$m) { $l = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff K") + "] " + $m; if ($S) { $l = $l -replace [regex]::Escape($S), "<SERIAL>" }; Add-Content -Path $evlog -Encoding UTF8 -Value $l }
if (-not $S) { Ev "no single serial -> exit"; exit 2 }
if (-not (Test-Path $OutCsv)) { Add-Content -Path $OutCsv -Encoding UTF8 -Value "pc_ms,phone_ms,call_state,audio_mode,focus,wakefulness,cmd_ms,ok,basic_normal,period_s,err" }
# (no double quotes inside: PowerShell 5.1 strips them when passing native arguments -> first version failed with adb rc 1)
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
  # 2>&1 (not 2>$null: the v1 background process got adb rc 1 every sample after the first with 2>$null);
  # stderr lines (ErrorRecord, may contain the address) are dropped below — only ^[CAWPT]= lines are parsed, nothing else is written.
  $out = @(& $adb -s $S shell $cmd 2>&1 | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] })
  $rc = $LASTEXITCODE
  $sw.Stop()
  $ms = $sw.ElapsedMilliseconds
  $v = @{ C = ""; A = ""; W = ""; P = ""; T = "" }
  # (v1/v2 bug: a loop variable named $s overwrote the serial $S — PowerShell names ignore case)
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
