param([Parameter(Mandatory=$true)][string]$OutCsv, [Parameter(Mandatory=$true)][string]$StopFile, [double]$PeriodS = 2.3, [string]$Tag = "")
# M7 (2026-10-13, 등록 M7 v2 §1-4 · §2-6 · §4-3) continuous host HAL + battery log. READ-ONLY adb: one `adb shell` per sample runs
#   cat /proc/uptime; dumpsys thermalservice | sed -n '/Current temperatures from HAL/,/Current cooling devices/p'; dumpsys battery
# One CSV row per sample (target period PeriodS = 2.3 s, actual interval recorded): host time (ms epoch + ISO) · device uptime ·
# AP / SKIN / BAT / PA (HAL block only — the "Cached temperatures" block is NOT read) · thermal status of SKIN row · battery level ·
# status · plugged (AC|USB|Wireless|Dock powered true -> 1) · current_now (uA, if printed) · voltage · battery temperature · cmd_ms · err.
# A failed read is recorded as a row with empty fields and err = adb rc / parse (never dropped). Output = this file only (no console).
# Runs until $StopFile exists. Serial only from $env:ANDROID_SERIAL (never written). ASCII only in this file.
$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
$evlog = [System.IO.Path]::ChangeExtension($OutCsv, ".events.txt")
function Ev([string]$m) { $l = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff K") + "] " + $m; if ($DEVSER) { $l = $l -replace [regex]::Escape($DEVSER), "<SERIAL>" }; Add-Content -Path $evlog -Encoding UTF8 -Value $l }
if (-not $DEVSER) { Ev "ANDROID_SERIAL empty -> exit"; exit 2 }
$header = "host_ms,host_iso,device_uptime_s,AP,SKIN,BAT,PA,skin_status,level,status,plugged,current_now_uA,voltage_mV,bat_temp_deci_c,cmd_ms,interval_ms,err,tag"
if (-not (Test-Path $OutCsv)) { Add-Content -Path $OutCsv -Encoding UTF8 -Value $header }
$cmd = "cat /proc/uptime; echo __THERMAL__; dumpsys thermalservice | sed -n '/Current temperatures from HAL/,/Current cooling devices/p'; echo __BATTERY__; dumpsys battery"
Ev "START pid=$PID period=$PeriodS out=$OutCsv tag=$Tag"
$t0 = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
$k = 0
$prev = $null
while (-not (Test-Path $StopFile)) {
  $due = $t0 + [int64]($k * $PeriodS * 1000)
  $now = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
  if ($due -gt $now) { Start-Sleep -Milliseconds ([int]($due - $now)) }
  $hostMs = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
  $iso = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss.fffK")
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $out = @(& $adb -s $DEVSER shell $cmd 2>&1 | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] })
  $rc = $LASTEXITCODE
  $sw.Stop()
  $text = ($out -join "`n")
  $up = ""; $ap = ""; $skin = ""; $bat = ""; $pa = ""; $sst = ""; $level = ""; $status = ""; $plugged = ""; $cur = ""; $volt = ""; $btemp = ""; $err = ""
  if ($rc -ne 0) { $err = "adb_rc_$rc" }
  try {
    $parts = $text -split "__THERMAL__", 2
    if ($parts[0] -match '^\s*([0-9]+\.[0-9]+)\s') { $up = $matches[1] }
    if ($parts.Count -gt 1) {
      $tb = ($parts[1] -split "__BATTERY__", 2)
      $thermal = $tb[0]
      foreach ($m in [regex]::Matches($thermal, 'Temperature\{mValue=([-0-9.]+), mType=\d+, mName=([A-Za-z0-9_]+), mStatus=(\d+)\}')) {
        $name = $m.Groups[2].Value.ToUpper(); $val = $m.Groups[1].Value
        if ($name -eq "AP") { $ap = $val } elseif ($name -eq "SKIN") { $skin = $val; $sst = $m.Groups[3].Value } elseif ($name -eq "BAT") { $bat = $val } elseif ($name -eq "PA") { $pa = $val }
      }
      if ($tb.Count -gt 1) {
        $b = $tb[1]
        if ($b -match '(?m)^\s*level:\s*(\d+)') { $level = $matches[1] }
        if ($b -match '(?m)^\s*status:\s*(\d+)') { $status = $matches[1] }
        $plugged = if ($b -match '(?m)^\s*(AC|USB|Wireless|Dock) powered:\s*true') { "1" } else { "0" }
        if ($b -match '(?m)^\s*current now:\s*(-?\d+)') { $cur = $matches[1] }
        if ($b -match '(?m)^\s*voltage:\s*(\d+)') { $volt = $matches[1] }
        if ($b -match '(?m)^\s*temperature:\s*(-?\d+)') { $btemp = $matches[1] }
      } elseif (-not $err) { $err = "no_battery_block" }
    } elseif (-not $err) { $err = "no_thermal_block" }
    if (-not $err -and (-not $skin -or -not $ap)) { $err = "hal_missing" }
  } catch { if (-not $err) { $err = "parse" } }
  $interval = if ($prev -ne $null) { $hostMs - $prev } else { "" }
  $prev = $hostMs
  $row = @($hostMs, $iso, $up, $ap, $skin, $bat, $pa, $sst, $level, $status, $plugged, $cur, $volt, $btemp, $sw.ElapsedMilliseconds, $interval, $err, $Tag) -join ","
  for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $OutCsv -Encoding UTF8 -Value $row -ErrorAction Stop; break } catch { Start-Sleep -Milliseconds 200 } }
  $k++
  $nowAfter = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
  while (($t0 + [int64]($k * $PeriodS * 1000)) -lt $nowAfter) { $k++ }
}
Ev "STOP pid=$PID rows=$k"
