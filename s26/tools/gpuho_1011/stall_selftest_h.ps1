# GPU holdout (GH 1011) copy of s26\tools\energy_1008\stall_selftest_c.ps1 - changed only: host dir S26_host_gpuho_1011 . csv / stop / log names *_h . helper names *_h (logic unchanged).
# Energy C (P1i 1008) copy of v3_1006\stall_selftest_v3b.ps1 - changed only: dot-sources energy_1008\stall_watch_h.ps1 . output S26_host_gpuho_1011\stall_selftest_h.txt . temp dir prefix c_stall_.
# V3 v2 (P1h 1007) stall-detection self-test (prompt 1-5: fake process + 60 s threshold). No adb, no phone.
#  T1 fake orchestrator = powershell Start-Sleep 300, writes no file           -> expect "stall" after ~60-80 s, process killed
#  T2 fake orchestrator = writes to ONE kept-open file every 5 s for 100 s (like --logger-keep-files-open), StallSec 60
#                                                                               -> expect "exited" (no false stall)
#  T3 same writer for 300 s, StallSec 600, CapSec 90                           -> expect "cap", process killed
#  T0 enumeration-vs-refresh: size seen by Get-ChildItem vs FileInfo.Refresh() while the writer holds the file open (recorded)
param([string]$Out = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_gpuho_1011\stall_selftest_h.txt")
$ErrorActionPreference = "Continue"
. "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\s26\tools\gpuho_1011\stall_watch_h.ps1"
$base = Join-Path $env:TEMP ("h_stall_" + (Get-Date -Format "HHmmss"))
New-Item -ItemType Directory -Force $base | Out-Null
$lines = New-Object System.Collections.ArrayList
function Rec([string]$m) { $l = "[" + (Get-Date -Format "HH:mm:ss") + "] " + $m; [void]$lines.Add($l); $l }
$logFn = { param($x) Rec "  watch: $x" }
function Writer([string]$dir, [int]$secs) {
  New-Item -ItemType Directory -Force $dir | Out-Null
  $code = "`$fs = [IO.File]::Open('$dir\raw.log','Create','Write','ReadWrite'); `$w = New-Object IO.StreamWriter(`$fs); `$t0 = Get-Date; while (((Get-Date) - `$t0).TotalSeconds -lt $secs) { `$w.WriteLine(('x' * 200)); `$w.Flush(); Start-Sleep -Seconds 5 }; `$w.Close()"
  return Start-Process powershell -ArgumentList "-NoProfile", "-Command", $code -WindowStyle Hidden -PassThru
}
$res = [ordered]@{}
# T1
$d1 = "$base\t1"; New-Item -ItemType Directory -Force $d1 | Out-Null
$p1 = Start-Process powershell -ArgumentList "-NoProfile", "-Command", "Start-Sleep 300" -WindowStyle Hidden -PassThru
$t = Get-Date; $r1 = Wait-CellWithStall -OrchPid $p1.Id -Dir $d1 -StallSec 60 -CapSec 3600 -LogFn $logFn -PollS 5 -TraceEveryS 60
$e1 = [int]((Get-Date) - $t).TotalSeconds; $alive1 = [bool](Get-Process -Id $p1.Id -ErrorAction SilentlyContinue)
$res.T1 = ($r1 -eq "stall") -and (-not $alive1) -and ($e1 -ge 60) -and ($e1 -le 140)
Rec "T1 result=$r1 elapsed=${e1}s alive_after=$alive1 -> $(if ($res.T1) {'PASS'} else {'FAIL'})"
# T0 + T2
$d2 = "$base\t2"; $p2 = Writer $d2 100
Start-Sleep -Seconds 12
$enum = (Get-ChildItem -LiteralPath $d2 -File | Where-Object Name -eq "raw.log").Length
$fi = New-Object System.IO.FileInfo -ArgumentList "$d2\raw.log"; $fi.Refresh(); $fresh = $fi.Length
Rec "T0 kept-open file after 12 s: enumeration Length=$enum  FileInfo.Refresh Length=$fresh"
$t = Get-Date; $r2 = Wait-CellWithStall -OrchPid $p2.Id -Dir $d2 -StallSec 60 -CapSec 3600 -LogFn $logFn -PollS 5 -TraceEveryS 60
$e2 = [int]((Get-Date) - $t).TotalSeconds
$res.T2 = ($r2 -eq "exited")
Rec "T2 result=$r2 elapsed=${e2}s -> $(if ($res.T2) {'PASS'} else {'FAIL'})"
# T3
$d3 = "$base\t3"; $p3 = Writer $d3 300
$t = Get-Date; $r3 = Wait-CellWithStall -OrchPid $p3.Id -Dir $d3 -StallSec 600 -CapSec 90 -LogFn $logFn -PollS 5 -TraceEveryS 60
$e3 = [int]((Get-Date) - $t).TotalSeconds; $alive3 = [bool](Get-Process -Id $p3.Id -ErrorAction SilentlyContinue)
$res.T3 = ($r3 -eq "cap") -and (-not $alive3)
Rec "T3 result=$r3 elapsed=${e3}s alive_after=$alive3 -> $(if ($res.T3) {'PASS'} else {'FAIL'})"
$np = @($res.Values | Where-Object { $_ }).Count
Rec "stall selftest $(if ($np -eq $res.Count) {'PASS'} else {'FAIL'}) ($np/$($res.Count))"
$lines | Set-Content -Encoding UTF8 $Out
Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue
