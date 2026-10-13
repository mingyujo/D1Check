$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
Set-Location $REPO
$log = "$REPO\results\m7_smokes_console.txt"
foreach ($w in @("p", "k", "s")) {
  "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] smoke $w start" | Out-File $log -Encoding UTF8 -Append
  & powershell -NoProfile -ExecutionPolicy Bypass -File "$REPO\s26\tools\mixreq\m7_driver.ps1" -Kind smoke -Smoke $w 2>&1 | Out-File -FilePath $log -Encoding UTF8 -Append
  "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] smoke $w end rc=$LASTEXITCODE" | Out-File $log -Encoding UTF8 -Append
}
