param([Parameter(Mandatory=$true)][string]$StopFile, [Parameter(Mandatory=$true)][string]$LogFile)
# M6-A PC keep-awake for the whole phone part (same SetThreadExecutionState loop as statesplit_driver.ps1 / mixreq_driver.ps1).
# Runs until $StopFile exists. Start hidden:  Start-Process powershell -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",<this>,"-StopFile",<f>,"-LogFile",<g> -PassThru
# NOTE: laptop lid must stay OPEN (Modern Standby stops the PC; SetThreadExecutionState cannot prevent it). ASCII only.
Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll", SetLastError=true)] public static extern uint SetThreadExecutionState(uint esFlags);'
$ES_CONTINUOUS = [uint32]"0x80000000"; $ES_SYSTEM_REQUIRED = [uint32]"0x00000001"; $ES_AWAYMODE_REQUIRED = [uint32]"0x00000040"
Add-Content -Path $LogFile -Value ("start " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + " pid=" + $PID)
while (-not (Test-Path $StopFile)) { [Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_AWAYMODE_REQUIRED) | Out-Null; Start-Sleep -Seconds 50 }
[Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
Add-Content -Path $LogFile -Value ("stop " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + " pid=" + $PID)
