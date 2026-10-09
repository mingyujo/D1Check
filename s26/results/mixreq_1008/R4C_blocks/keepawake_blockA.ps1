Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll", SetLastError=true)] public static extern uint SetThreadExecutionState(uint esFlags);'
$ES_CONTINUOUS = [uint32]"0x80000000"; $ES_SYSTEM_REQUIRED = [uint32]"0x00000001"; $ES_AWAYMODE_REQUIRED = [uint32]"0x00000040"
Add-Content -Path 'C:\Users\rhoyo\AndroidStudioProjects\D1Check_mixreq\results\S26_MIXREQ_R4C\keepawake_log.txt' -Value ("start " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + " pid=" + $PID)
while (-not (Test-Path 'C:\Users\rhoyo\AndroidStudioProjects\D1Check_mixreq\results\S26_MIXREQ_R4C\keepawake.stop')) { [Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_AWAYMODE_REQUIRED) | Out-Null; Start-Sleep -Seconds 50 }
[Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
Add-Content -Path 'C:\Users\rhoyo\AndroidStudioProjects\D1Check_mixreq\results\S26_MIXREQ_R4C\keepawake_log.txt' -Value ("stop " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + " pid=" + $PID)
