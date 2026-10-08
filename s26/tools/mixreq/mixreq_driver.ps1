param([Parameter(Mandatory=$true)][ValidateSet("A","N")][string]$Block, [int]$StartIndex = -1, [switch]$DryRun,
      [string]$PlanDir = "", [string]$ResultsRoot = "", [int]$RetryRestS = 600, [switch]$SkipGate, [switch]$AllowSettingsMismatch)
# S26 mixed-request block driver (R2). ASCII + CRLF only. One block per invocation (A = sessions 0..7, N = 8..15).
# Rules (prereg §3-3, §4): sessions in registered order; an invalid session is retried ONCE in the same slot after >= RetryRestS (600 s)
# rest + the gate (attempt 2, same sid/request ids); a second invalid stops the block; gate SOC/plugged block (exit 6) stops the block
# with "CHARGE NEEDED"; a thermal gate block (exit 2) waits inside start_gate (120 s polling), so exit 2 here means the gate script
# itself failed -> stop. Keep-awake: SetThreadExecutionState loop (copy of v3_1006/keepawake_v3b.ps1) with a stop file.
# Serial only from $env:ANDROID_SERIAL (logged as <SERIAL>). Every variable name is unique ignoring case ($d/$D collisions).
$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_mixreq"
if (-not $PlanDir) { $PlanDir = "$REPO\s26\results\mixreq_1008\plan_v1" }
if (-not $ResultsRoot) { $ResultsRoot = "$REPO\results\S26_MIXREQ_1009" }
$TOOLDIR = "$REPO\s26\tools\mixreq"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
New-Item -ItemType Directory -Force $ResultsRoot | Out-Null
$driverLog = "$ResultsRoot\driver_log_block$Block.txt"
$stateFile = "$ResultsRoot\driver_state_block$Block.json"
function Log([string]$msg) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $msg
  if ($DEVSER) { $line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>" }
  Write-Host $line
  if (-not $DryRun) { for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $driverLog -Encoding UTF8 -Value $line -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 } } }
}
# --- keep-awake (copy of v3_1006/keepawake_v3b.ps1 logic, new paths)
$kaStop = "$ResultsRoot\keepawake.stop"
$kaLog = "$ResultsRoot\keepawake_log.txt"
if (Test-Path $kaStop) { Remove-Item $kaStop -Force }
$kaScript = @"
Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll", SetLastError=true)] public static extern uint SetThreadExecutionState(uint esFlags);'
`$ES_CONTINUOUS = [uint32]"0x80000000"; `$ES_SYSTEM_REQUIRED = [uint32]"0x00000001"; `$ES_AWAYMODE_REQUIRED = [uint32]"0x00000040"
Add-Content -Path '$kaLog' -Value ("start " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + " pid=" + `$PID)
while (-not (Test-Path '$kaStop')) { [Win32.Power]::SetThreadExecutionState(`$ES_CONTINUOUS -bor `$ES_SYSTEM_REQUIRED -bor `$ES_AWAYMODE_REQUIRED) | Out-Null; Start-Sleep -Seconds 50 }
[Win32.Power]::SetThreadExecutionState(`$ES_CONTINUOUS) | Out-Null
Add-Content -Path '$kaLog' -Value ("stop " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + " pid=" + `$PID)
"@
$kaFile = "$ResultsRoot\keepawake_block$Block.ps1"
Set-Content -Path $kaFile -Value $kaScript -Encoding ASCII
$kaProc = $null
if (-not $DryRun) { $kaProc = Start-Process powershell -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",$kaFile -PassThru; Log "keepawake pid=$($kaProc.Id)" }
Log "DRIVER START block=$Block startIndex=$StartIndex plan=$PlanDir results=$ResultsRoot dry=$DryRun"
Log "NOTE: laptop lid must stay OPEN (Modern Standby stops the PC; SetThreadExecutionState cannot prevent it)"
$indices = if ($Block -eq "A") { 0..7 } else { 8..15 }
if ($StartIndex -ge 0) { $indices = $indices | Where-Object { $_ -ge $StartIndex } }
$STATE = [ordered]@{ block = $Block; sessions = [ordered]@{}; stop_reason = ""; retries = 0 }
function SaveState() { if (-not $DryRun) { ($STATE | ConvertTo-Json -Depth 6) | Set-Content -Encoding UTF8 $stateFile } }
function RunSession([int]$idx, [int]$attempt) {
  $argList = @("-X","utf8","$TOOLDIR\mixreq_session.py","--plan",$PlanDir,"--index",$idx,"--attempt",$attempt,"--results",$ResultsRoot)
  if ($DryRun) { $argList += "--dry-run" }
  if ($SkipGate) { $argList += "--skip-gate" }
  if ($AllowSettingsMismatch) { $argList += "--allow-settings-mismatch" }  # R2 10/9 decision: S26 rewrites brightness 0 -> 1 while awake (display float 0.0 = minimum); value is recorded per session
  Log "RUN index=$idx attempt=$attempt"
  & py @argList 2>&1 | ForEach-Object { Log ("  py: " + "$_") }
  $rcode = $LASTEXITCODE
  Log "RESULT index=$idx attempt=$attempt rc=$rcode (0 valid, 1 invalid, 2 gate fail, 3 device/settings, 4 stall, 5 folder exists, 6 charge needed)"
  return $rcode
}
foreach ($idx in $indices) {
  $rc1 = RunSession $idx 1
  $STATE.sessions["$idx"] = [ordered]@{ attempt1 = $rc1 }
  SaveState
  if ($rc1 -eq 6) { $STATE.stop_reason = "CHARGE NEEDED at index $idx (gate SOC/plugged)"; Log "STOP: charge needed -> block paused at index $idx (resume with -StartIndex $idx after charging + gate)"; break }
  if ($rc1 -eq 3 -or $rc1 -eq 5 -or $rc1 -eq 2) { $STATE.stop_reason = "rc=$rc1 at index $idx"; Log "STOP: rc=$rc1 (device/settings/folder/gate script) -> block stopped"; break }
  if ($rc1 -eq 0) { continue }
  # invalid (1) or stall (4): one retry in the same slot after >= RetryRestS rest + gate
  Log "RETRY: resting $RetryRestS s before attempt 2 of index $idx"
  if (-not $DryRun) { Start-Sleep -Seconds $RetryRestS }
  $STATE.retries++
  $rc2 = RunSession $idx 2
  $STATE.sessions["$idx"].attempt2 = $rc2
  SaveState
  if ($rc2 -eq 0) { continue }
  if ($rc2 -eq 6) { $STATE.stop_reason = "CHARGE NEEDED at index $idx retry"; Log "STOP: charge needed on retry"; break }
  $STATE.stop_reason = "second invalid at index $idx (rc=$rc2)"
  Log "STOP: second invalid at index $idx -> block stopped (report; the other block runs as registered)"
  break
}
if (-not $STATE.stop_reason) { $STATE.stop_reason = "completed" }
SaveState
if ($kaProc) { Set-Content -Path $kaStop -Value "stop"; Log "keepawake stop requested" }
Log "DRIVER END block=$Block reason=$($STATE.stop_reason)"
