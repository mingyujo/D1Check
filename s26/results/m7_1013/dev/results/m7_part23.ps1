$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
Set-Location $REPO
$log = "$REPO\results\m7_part23_console.txt"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 2 start" | Out-File $log -Encoding UTF8 -Append
& powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\results\m7_part2.ps1"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 2 end rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
if ($LASTEXITCODE -eq 2) { "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 2 stopped early -> part 3 not started (operator)" | Out-File $log -Encoding UTF8 -Append; exit 2 }
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 3 start" | Out-File $log -Encoding UTF8 -Append
& powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\results\m7_part3.ps1"
"[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] part 3 end rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
