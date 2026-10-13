$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
Set-Location $REPO
$log = "$REPO\results\m7_s7_and_repro_console.txt"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] M6 repro smoke retry (same attempt 2 · app had not started · band wait 0)" | Out-File $log -Encoding UTF8 -Append
& py -X utf8 "$REPO\s26\tools\mixreq\m6_session.py" --plan "$REPO\s26\results\m6_1012\plan_m6p" --index 0 --attempt 2 --results "$REPO\results\S26_M7_M6REPRO" --runlog "$REPO\results\S26_M7_runs.jsonl" --label M6REPRO_P0 --allow-settings-mismatch --band-wait-s 0 2>&1 | Out-File -FilePath "$REPO\results\S26_M7_M6REPRO_console2.txt" -Encoding UTF8 -Append
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] M6 repro retry rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
