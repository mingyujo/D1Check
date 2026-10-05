param([string]$Start = "N50P2,NI300r2,G50P2", [string]$FirstGate = "yes")
# AM 1005 session driver: runs the cells in prereg 1005 s2 order with the s1 item-3 lower-bound rule, one after another.
# Order N50P2 -> NI300r2 -> G50P2. If the FIRST gate fails the lower bound (N50P2, required) -> G50P2 -> N50P2 -> NI300r2.
# Later N50P2 lower fail -> moved to the end; if already last -> skipped (recorded). NI300r2 / G50P2 run marked.
# 07:41 fix: $c and $C are the same variable in PowerShell (case-insensitive) -> table renamed $CELLS, row $cell. Restart args -Start/-FirstGate.
# After a cell ran: post_chain_1005.ps1 (judges). If the slot is not valid -> driver stops (retry decision by the session).
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_am_1005_host"
$log = "$H\driver_1005_log.txt"
function Log([string]$m) { Add-Content -Path $log -Encoding UTF8 -Value ("[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $m) }
$common = "--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --logger-keep-files-open --analyze-timeout-seconds 600 --cooling-min-seconds 600 --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261004 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
$CELLS = @{
  N50P2   = @{ Label="01_N50P2";   Args="--npu-chain tools\chains\n50_probe_npu_v1.json --duration 960 --npu-max-inference-spans 1500000 $common"; Sha="a0ae4d7d0188de403752ca929316d69331812f3fe5a795194d05219ef66a4d49"; MinSoc=43; Hours=0.55; Policy="required"; Judge="n50p";  Judge2="n50p2";  Prev="N50P" }
  NI300r2 = @{ Label="02_NI300r2"; Args="--npu-chain tools\chains\npu_idle300_v1.json --duration 840 --npu-max-inference-spans 1200000 $common"; Sha="f721513b07d0af9ea03499f7babeff197fa644425f00b2fa1fd87159ec4e13bf"; MinSoc=41; Hours=0.65; Policy="mark"; Judge="ni300"; Judge2="ni300r2"; Prev="NI300" }
  G50P2   = @{ Label="03_G50P2";   Args="--npu-chain tools\chains\g50_probe_gpu_v1.json --duration 840 --npu-max-inference-spans 400000 $common"; Sha="63a0872c8f77005a8985363b427f2d2c5b4a2cdf71f07f272bc32a536c6c3527"; MinSoc=42; Hours=0.5; Policy="mark"; Judge="g50p";  Judge2="g50p2";  Prev="G50P" }
}
$queue = New-Object System.Collections.ArrayList
[void]$queue.AddRange(@($Start -split ","))
$firstGate = ($FirstGate -eq "yes")
Log "DRIVER START pid=$PID queue=$($queue -join ',')"
while ($queue.Count -gt 0) {
  $t = $queue[0]; $queue.RemoveAt(0); $cell = $CELLS[$t]
  $out = "S26_${t}_1005"
  if (Test-Path "$wd\results\$out") { $out = "S26_${t}_1005_b" }
  Log "CELL $t -> $out (policy $($cell.Policy)) remaining=$($queue -join ',')"
  & "$H\run_cell_1005.ps1" -Tag $t -Label $cell.Label -OutName $out -CellArgs $cell.Args -ChainSha $cell.Sha -MinSoc $cell.MinSoc -Hours $cell.Hours -LowerPolicy $cell.Policy
  $rc = $LASTEXITCODE
  Log "CELL $t rc=$rc"
  if ($rc -eq 7) {
    if ($firstGate) {
      $queue.Clear(); [void]$queue.AddRange(@("G50P2","N50P2","NI300r2"))
      Log "FIRST GATE LOWER FAIL -> order G50P2 -> N50P2 -> NI300r2 (G50P2 marked 'lower-fail start')"
    } elseif ($queue.Count -gt 0) {
      [void]$queue.Add("N50P2"); Log "N50P2 lower fail -> moved to end: $($queue -join ',')"
    } else { Log "N50P2 lower fail at last position -> SKIPPED (next session)" }
  }
  if ($rc -ne 3 -and $rc -ne 4) { $firstGate = $false }
  if ($rc -eq 0) {
    $pc = & "$H\post_chain_1005.ps1" -OutName $out -Judge $cell.Judge -Tag $t -Judge2 $cell.Judge2 -PrevTag $cell.Prev 2>&1 | ForEach-Object { "$_" }
    Log ("POST $t :: " + ($pc -join " | "))
    $mp = "$wd\results\$out\experiment_manifest.json"
    $valid = $false
    try { $m = Get-Content -Raw -Encoding UTF8 $mp | ConvertFrom-Json; $valid = [bool]$m.runs[0].validation.valid } catch {}
    if (-not $valid) { Log "SLOT NOT VALID for $t -> driver stops (session decides retry per 1004 rules)"; break }
  }
}
Log "DRIVER END queue=$($queue -join ',')"
