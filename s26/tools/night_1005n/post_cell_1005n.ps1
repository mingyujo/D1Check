param(
  [Parameter(Mandatory=$true)][string]$OutName,
  [Parameter(Mandatory=$true)][string]$Cell,
  [Parameter(Mandatory=$true)][int]$Block,
  [Parameter(Mandatory=$true)][string]$GateLabel
)
# NIGHT 1005n (after post_chain_1005.ps1): after a chain orchestrator exits (never while it runs)
# -> slot report (1004 chain_slot_report.py, unchanged) -> night1005_judge.py run (frozen ca8680c2...) -> out_1005n\<cell>_b<block>.json
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_night_1005n_host"
$SIM = "C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
$S = $env:ANDROID_SERIAL
$res = "$wd\results\$OutName"
$tag = "${Cell}_b${Block}"
$rep = & py -X utf8 "$wd\results\S26_night_1004_host\chain_slot_report.py" $res 2>&1 | ForEach-Object { "$_" }
if ($S) { $rep = $rep | ForEach-Object { $_ -replace [regex]::Escape($S), "<SERIAL>" } }
$rep | Set-Content -Encoding utf8 "$H\slot_$OutName.txt"
$runDirs = @(Get-ChildItem "$res\runs" -Directory)
"run dirs: " + $runDirs.Count
if ($runDirs.Count -ne 1) { "NOT EXACTLY ONE RUN DIR"; exit 2 }
$rd = $runDirs[0].FullName
$out = "$SIM\out_1005n\$tag.json"
& py -X utf8 "$SIM\night1005_judge.py" run $rd --cell $Cell --block $Block --watch "$H\skin_watch_1005n.csv" --gate-log "$H\gate_log_1005n.csv" --gate-label $GateLabel --out $out > "$H\judge_$OutName.stdout.txt" 2> "$H\judge_$OutName.stderr.txt"
"judge exit=$LASTEXITCODE out=$out"
Get-Content -Encoding UTF8 "$H\judge_$OutName.stderr.txt" | Select-Object -First 5
