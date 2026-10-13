$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
Set-Location $REPO
$log = "$REPO\results\m7_s7_and_repro_console.txt"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] S7 regression start (plan_v3c index 6 attempt 2 · legacy validate · band wait 0)" | Out-File $log -Encoding UTF8 -Append
& py -X utf8 "$REPO\s26\tools\mixreq\m6_session.py" --plan "$REPO\s26\results\mixreq_1008\plan_v3c" --index 6 --attempt 2 --legacy-validate --results "$REPO\results\S26_M7_S7" --runlog "$REPO\results\S26_M7_runs.jsonl" --label S7_m7 --allow-settings-mismatch --band-wait-s 0 *>> "$REPO\results\S26_M7_S7_console.txt"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] S7 rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] M6 repro smoke start (plan_m6p index 0 L-C attempt 2 · m6_validate)" | Out-File $log -Encoding UTF8 -Append
& py -X utf8 "$REPO\s26\tools\mixreq\m6_session.py" --plan "$REPO\s26\results\m6_1012\plan_m6p" --index 0 --attempt 2 --results "$REPO\results\S26_M7_M6REPRO" --runlog "$REPO\results\S26_M7_runs.jsonl" --label M6REPRO_P0 --allow-settings-mismatch *>> "$REPO\results\S26_M7_M6REPRO_console.txt"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] M6 repro rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
