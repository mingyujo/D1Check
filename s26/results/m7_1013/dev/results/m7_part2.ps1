$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
Set-Location $REPO
$log = "$REPO\results\m7_part2_console.txt"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 2: P D2 (index 18..23) start" | Out-File $log -Encoding UTF8 -Append
& powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\s26\tools\mixreq\m7_driver.ps1" -Kind p -Items "18,19,20,21,22,23" 2>&1 | Out-File -FilePath $log -Encoding UTF8 -Append
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] P D2 end rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
$state = Get-ChildItem "$REPO\results\S26_M7_P\driver_state_p_*.json" | Sort-Object LastWriteTime | Select-Object -Last 1
$reason = ""
if ($state) { try { $reason = (Get-Content -Raw $state.FullName | ConvertFrom-Json).stop_reason } catch { $reason = "unreadable" } }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] P D2 stop_reason=$reason" | Out-File $log -Encoding UTF8 -Append
if ($reason -ne "completed") { "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] P driver did not complete -> K set 2 not started (operator)" | Out-File $log -Encoding UTF8 -Append; exit 2 }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 2: K set 2 (B C A = index 7,8,9) start" | Out-File $log -Encoding UTF8 -Append
& powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\s26\tools\mixreq\m7_driver.ps1" -Kind k -Items "7,8,9" 2>&1 | Out-File -FilePath $log -Encoding UTF8 -Append
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] K set 2 end rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
