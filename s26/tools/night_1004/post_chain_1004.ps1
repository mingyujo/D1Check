param(
  [Parameter(Mandatory=$true)][string]$OutName,
  [Parameter(Mandatory=$true)][string]$Judge,
  [Parameter(Mandatory=$true)][string]$Tag
)
# Night 1004: after a chain orchestrator exits (never while it runs) -> slot report + frozen judge (night1004_judge.py <judge>).
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$H = "$wd\results\S26_night_1004_host"
$SIM = "C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
$S = $env:ANDROID_SERIAL
$res = "$wd\results\$OutName"
$rep = & py -X utf8 "$H\chain_slot_report.py" $res 2>&1 | ForEach-Object { "$_" }
if ($S) { $rep = $rep | ForEach-Object { $_ -replace [regex]::Escape($S), "<SERIAL>" } }
$rep | Set-Content -Encoding utf8 "$H\slot_$Tag.txt"
$runDirs = @(Get-ChildItem "$res\runs" -Directory)
"run dirs: " + $runDirs.Count
if ($runDirs.Count -ne 1) { "NOT EXACTLY ONE RUN DIR"; exit 2 }
$rd = $runDirs[0].FullName
$out = "$SIM\out_1004\$Tag.json"
& py -X utf8 "$SIM\night1004_judge.py" $Judge $rd --watch "$H\skin_watch_1004.csv" --out $out > "$H\judge_$Tag.stdout.txt" 2> "$H\judge_$Tag.stderr.txt"
"judge exit=$LASTEXITCODE out=$out"
Get-Content -Encoding UTF8 "$H\judge_$Tag.stderr.txt" | Select-Object -First 5
