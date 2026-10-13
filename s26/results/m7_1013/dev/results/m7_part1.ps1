$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
Set-Location $REPO
$log = "$REPO\results\m7_part1_console.txt"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 1: K set 1 (A B C = index 4,5,6) start" | Out-File $log -Encoding UTF8 -Append
& powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\s26\tools\mixreq\m7_driver.ps1" -Kind k -Items "4,5,6" 2>&1 | Out-File -FilePath $log -Encoding UTF8 -Append
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] K set 1 end rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
$state = Get-ChildItem "$REPO\results\S26_M7_K\driver_state_k_*.json" | Sort-Object LastWriteTime | Select-Object -Last 1
$reason = ""
if ($state) { try { $reason = (Get-Content -Raw $state.FullName | ConvertFrom-Json).stop_reason } catch { $reason = "unreadable" } }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] K set 1 stop_reason=$reason" | Out-File $log -Encoding UTF8 -Append
if ($reason -ne "completed") { "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] K driver did not complete -> P D1 not started (operator)" | Out-File $log -Encoding UTF8 -Append; exit 2 }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 1: P D1 (index 12..17) start" | Out-File $log -Encoding UTF8 -Append
& powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\s26\tools\mixreq\m7_driver.ps1" -Kind p -Items "12,13,14,15,16,17" 2>&1 | Out-File -FilePath $log -Encoding UTF8 -Append
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] P D1 end rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
