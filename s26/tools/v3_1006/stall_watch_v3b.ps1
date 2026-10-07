# V3 v2 (P1h 1007) — cell stall detection (sim\V3_사전등록_v2.md s3 운영 보강 · prompt 1-5 (2) and (5)). Operation only: no measurement code,
# no judge rule. Dot-sourced by run_cell_v3b.ps1 (and by the stall self-test).
# Progress trace of the cell output folder = (file count | size sum | latest write time), from file METADATA only:
#   experiment_manifest.json (and *.tmp*) = directory-enumeration metadata only (never opened, CLAUDE.md s3 - the orchestrator os.replace()s it);
#   other files = a fresh IO.FileInfo(path).Refresh() (path attribute query) because files the logger keeps open
#   (--logger-keep-files-open) may show stale sizes in a directory enumeration.
# Every PollS: trace; every AdbEveryS: `adb get-state` -> adb_state csv (ok 1/0, never the stderr text).
# Stall = trace unchanged > StallSec, or elapsed > CapSec  -> taskkill /T /F the orchestrator tree -> return "stall" / "cap".
# Normal exit -> "exited".
function Get-CellTrace([string]$dir) {
  if (-not (Test-Path -LiteralPath $dir)) { return "nodir" }
  $files = @(Get-ChildItem -LiteralPath $dir -Recurse -File -Force -ErrorAction SilentlyContinue)
  [int64]$sum = 0; [int64]$latest = 0; $cnt = 0
  foreach ($f in $files) {
    $len = $null; $lw = $null
    if ($f.Name -eq "experiment_manifest.json" -or $f.Name -like "*.tmp*") {
      $len = $f.Length; $lw = $f.LastWriteTimeUtc.Ticks
    } else {
      try {
        $fi = New-Object System.IO.FileInfo -ArgumentList $f.FullName
        $fi.Refresh()
        if ($fi.Exists) { $len = $fi.Length; $lw = $fi.LastWriteTimeUtc.Ticks }
      } catch { }
    }
    if ($len -ne $null) { $cnt++; $sum += $len; if ($lw -gt $latest) { $latest = $lw } }
  }
  return "$cnt|$sum|$latest"
}

function Wait-CellWithStall {
  param([int]$OrchPid, [string]$Dir, [int]$StallSec, [int]$CapSec, [scriptblock]$LogFn, [string]$AdbCsv = "", [string]$CellTag = "",
        [int]$PollS = 15, [int]$TraceEveryS = 60, [int]$AdbEveryS = 60, [string]$AdbExe = "", [string]$Serial = "")
  $t0 = Get-Date
  $lastTrace = Get-CellTrace $Dir
  $lastChange = Get-Date
  $nextTrace = (Get-Date).AddSeconds($TraceEveryS)
  $nextAdb = (Get-Date).AddSeconds($AdbEveryS)
  if ($AdbCsv -and -not (Test-Path $AdbCsv)) { Add-Content -Path $AdbCsv -Encoding UTF8 -Value "local_time,cell,adb_state_ok,trace_idle_s,elapsed_s" }
  & $LogFn "STALLWATCH start pid=$OrchPid stall>${StallSec}s cap>${CapSec}s trace0=$lastTrace"
  while (Get-Process -Id $OrchPid -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds $PollS
    $now = Get-Date
    if ($now -ge $nextTrace) {
      $nextTrace = $now.AddSeconds($TraceEveryS)
      $tr = Get-CellTrace $Dir
      if ($tr -ne $lastTrace) { $lastTrace = $tr; $lastChange = $now }
    }
    $idle = [int]($now - $lastChange).TotalSeconds
    $el = [int]($now - $t0).TotalSeconds
    if ($AdbCsv -and $AdbExe -and $now -ge $nextAdb) {
      $nextAdb = $now.AddSeconds($AdbEveryS)
      $st = "$(& $AdbExe -s $Serial get-state 2>$null)".Trim()
      $ok = if ($st -eq "device") { 1 } else { 0 }
      for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $AdbCsv -Encoding UTF8 -Value ("{0},{1},{2},{3},{4}" -f $now.ToString("yyyy-MM-dd HH:mm:ss"), $CellTag, $ok, $idle, $el) -ErrorAction Stop; break } catch { Start-Sleep -Milliseconds 200 } }
      if ($ok -eq 0) { & $LogFn "ADB get-state not device (elapsed ${el}s, trace idle ${idle}s)" }
    }
    $why = $null
    if ($idle -gt $StallSec) { $why = "stall" } elseif ($el -gt $CapSec) { $why = "cap" }
    if ($why) {
      & $LogFn "STALL DETECTED ($why): trace idle ${idle}s (limit $StallSec) elapsed ${el}s (cap $CapSec) last trace=$lastTrace -> kill orchestrator tree pid=$OrchPid"
      $null = & taskkill.exe /PID $OrchPid /T /F 2>$null
      & $LogFn "taskkill rc=$LASTEXITCODE"
      Start-Sleep -Seconds 3
      $alive = [bool](Get-Process -Id $OrchPid -ErrorAction SilentlyContinue)
      & $LogFn "orchestrator alive after kill=$alive"
      return $why
    }
  }
  return "exited"
}
