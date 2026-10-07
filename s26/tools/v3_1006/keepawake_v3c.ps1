# V3 v2 (P1h 1007, 15:5x) copy of keepawake_v3b.ps1 — changed only: + ES_DISPLAY_REQUIRED (the PC entered Modern Standby on 'Idle Timeout' 3x during A2 with the system-only request), stop file keepawake_c.stop, log keepawake_c_log.txt.
# was: V3 v2 (P1h 1007) copy of s26\tools\v3_1006\keepawake_v3.ps1 — changed only: host dir S26_host_v3_1007.
Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll", SetLastError=true)] public static extern uint SetThreadExecutionState(uint esFlags);'
$ES_CONTINUOUS = [uint32]"0x80000000"; $ES_SYSTEM_REQUIRED = [uint32]"0x00000001"; $ES_AWAYMODE_REQUIRED = [uint32]"0x00000040"; $ES_DISPLAY_REQUIRED = [uint32]"0x00000002"
$stop = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_v3_1007\keepawake_c.stop"
$log = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_v3_1007\keepawake_c_log.txt"
Add-Content -Path $log -Value ("start " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + " pid=" + $PID)
while (-not (Test-Path $stop)) {
  [Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_AWAYMODE_REQUIRED -bor $ES_DISPLAY_REQUIRED) | Out-Null
  Start-Sleep -Seconds 50
}
[Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
Add-Content -Path $log -Value ("stop " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + " pid=" + $PID)




