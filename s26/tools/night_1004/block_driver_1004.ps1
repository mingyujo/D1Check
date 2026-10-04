# Night 1004 EffB2 block driver (detached). For each run: gate -> dry-run -> launch -> wait -> validate; retry once on failure
# (no retry after a safety emergency). Reads $env:ANDROID_SERIAL only; the address is never written to any file (<SERIAL>).
$ErrorActionPreference = "Continue"
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_night_1004_host"
$S = $env:ANDROID_SERIAL
if (-not $S) { throw "ANDROID_SERIAL not set" }
$log = "$H\block_driver_1004_log.txt"
function Log([string]$m) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $m
  Add-Content -Path $log -Encoding UTF8 -Value ($line -replace [regex]::Escape($S), "<SERIAL>")
}
$MODEL = "--npu-model-path /data/local/tmp/efficientnet_lite0.tflite --npu-model-sha256 6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0 --npu-model-size 18582189 --npu-timed-input-spec lcg-rgb-127-128"
$TAIL = "--duration 60 --warmup 20 --repeat 1 --seed 20261003 --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 1800 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
function ArgsFor([string]$acc, [int]$duty) {
  if ($acc -eq "CPU") {
    return "--mode pilot --resources NPU --npu-accelerator CPU $MODEL --npu-run-only-span --accuracy-preflight off --duty-cycles $duty $TAIL"
  }
  return "--mode pilot --resources NPU --npu-accelerator GPU --npu-gpu-precision FP32 $MODEL --npu-input-spec lcg-rgb-127-128 --npu-reference-path /data/local/tmp/efficientnet_lite0.tflite --npu-run-only-span --accuracy-preflight off --gpu-profile gpu-fp32-strict-v1 --duty-cycles $duty $TAIL"
}
function Validate([string]$outName) {
  $mp = "$wd\results\$outName\experiment_manifest.json"
  if (-not (Test-Path $mp)) { return @{ ok = $false; emergency = $false; text = "missing manifest" } }
  try {
    $m = Get-Content -Raw -Encoding UTF8 $mp | ConvertFrom-Json
    $r = $m.runs[0]
    $v = $r.validation
    $ok = ($r.status -eq "completed") -and ($v -ne $null) -and ($v.valid -eq $true)
    $txt = "manifest_status=$($m.status) halt=$($m.halt_reason) slot_status=$($r.status) valid=$($v.valid) failed=$(($v.failed_checks) -join ',') error=$($r.error)"
    $em = ($txt -match "emergency")
    return @{ ok = $ok; emergency = $em; text = $txt }
  } catch { return @{ ok = $false; emergency = $false; text = "manifest parse error: $_" } }
}
$specs = @(
  "03_01_gpu50|S26_EffB2_01_gpu50_1004|GPU|50",
  "03_02_gpu100|S26_EffB2_02_gpu100_1004|GPU|100",
  "03_03_cpu50|S26_EffB2_03_cpu50_1004|CPU|50",
  "03_04_cpu100|S26_EffB2_04_cpu100_1004|CPU|100",
  "03_05_cpu100|S26_EffB2_05_cpu100_1004|CPU|100",
  "03_06_cpu50|S26_EffB2_06_cpu50_1004|CPU|50",
  "03_07_gpu100|S26_EffB2_07_gpu100_1004|GPU|100",
  "03_08_gpu50|S26_EffB2_08_gpu50_1004|GPU|50"
)
Log "DRIVER START pid=$PID specs=$($specs.Count)"
$emergencies = 0
foreach ($spec in $specs) {
  $p = $spec.Split("|"); $label = $p[0]; $outName = $p[1]; $acc = $p[2]; $duty = [int]$p[3]
  $cellArgs = ArgsFor $acc $duty
  $done = $false
  for ($attempt = 1; $attempt -le 2 -and -not $done; $attempt++) {
    $tgt = $outName; $glabel = $label
    if ($attempt -eq 2) { $tgt = "${outName}_retry"; $glabel = "${label}_retry" }
    Log "GATE $glabel (attempt $attempt)"
    $gout = & py -X utf8 "$wd\s26\tools\s26_start_gate.py" $S $glabel "$H\gate_log_1004.csv" 2>&1
    $grc = $LASTEXITCODE
    Log ("GATE rc=$grc last=" + ($gout | Select-Object -Last 1))
    if ($grc -ne 0) { Log "GATE BLOCKED (rc=$grc) -> stop driver"; Log "DRIVER END (blocked)"; exit 2 }
    $dr = & "$H\dryrun_1004.ps1" -Label $glabel -OutName $tgt -CellArgs $cellArgs
    Log "DRYRUN $dr"
    if (-not ("$dr" -match "exit=0")) { Log "DRYRUN FAILED -> attempt counts as failed"; continue }
    $lr = & "$H\launch_cell_1004.ps1" -Label $glabel -OutName $tgt -Args $cellArgs
    $pidLine = ($lr | Where-Object { "$_" -match "^pid=\d+" } | Select-Object -Last 1)
    $opid = [int](("$pidLine" -replace "pid=", ""))
    Log "LAUNCHED $glabel -> $tgt pid=$opid"
    Start-Sleep -Seconds 5
    while (Get-Process -Id $opid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 15 }
    $v = Validate $tgt
    Log "DONE $tgt -> ok=$($v.ok) $($v.text)"
    if ($v.ok) { $done = $true; break }
    if ($v.emergency) { $emergencies++; Log "SAFETY EMERGENCY ($emergencies) -> no retry, run FAILED (missing)"; break }
    Log "RUN FAILED $glabel attempt $attempt"
  }
  if (-not $done) { Log "MISSING $label -> continue block order" }
  if ($emergencies -ge 2) { Log "TWO SAFETY EMERGENCIES IN DRIVER -> stop"; break }
}
Log "DRIVER END emergencies=$emergencies"
