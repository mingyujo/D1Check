$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
Set-Location $REPO
$log = "$REPO\results\m7_part3_console.txt"
function Reason($pattern) { $st = Get-ChildItem $pattern | Sort-Object LastWriteTime | Select-Object -Last 1; if ($st) { try { return (Get-Content -Raw $st.FullName | ConvertFrom-Json).stop_reason } catch { return "unreadable" } }; return "" }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 3: K set 3 (C A B = index 10,11,12) start" | Out-File $log -Encoding UTF8 -Append
& powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\s26\tools\mixreq\m7_driver.ps1" -Kind k -Items "10,11,12" 2>&1 | Out-File -FilePath $log -Encoding UTF8 -Append
$r = Reason "$REPO\results\S26_M7_K\driver_state_k_*.json"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] K set 3 end rc=$LASTEXITCODE stop_reason=$r" | Out-File $log -Encoding UTF8 -Append
if ($r -ne "completed") { "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] K driver did not complete -> stop part 3 (operator)" | Out-File $log -Encoding UTF8 -Append; exit 2 }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 3: P D3 (index 24..29) start" | Out-File $log -Encoding UTF8 -Append
& powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\s26\tools\mixreq\m7_driver.ps1" -Kind p -Items "24,25,26,27,28,29" 2>&1 | Out-File -FilePath $log -Encoding UTF8 -Append
$r = Reason "$REPO\results\S26_M7_P\driver_state_p_*.json"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] P D3 end rc=$LASTEXITCODE stop_reason=$r" | Out-File $log -Encoding UTF8 -Append
if ($r -ne "completed") { "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] P driver did not complete -> S not started (operator)" | Out-File $log -Encoding UTF8 -Append; exit 2 }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 3: S dev 1..6 (index 16..21) start" | Out-File $log -Encoding UTF8 -Append
& powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\s26\tools\mixreq\m7_driver.ps1" -Kind s -Items "16,17,18,19,20,21" 2>&1 | Out-File -FilePath $log -Encoding UTF8 -Append
$r = Reason "$REPO\results\S26_M7_S\driver_state_s_*.json"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] S dev end rc=$LASTEXITCODE stop_reason=$r" | Out-File $log -Encoding UTF8 -Append
