param([Parameter(Mandatory=$true)][ValidateSet("A","N")][string]$Block, [int]$StartIndex = -1, [switch]$DryRun,
      [string]$PlanDir = "", [string]$ResultsRoot = "", [int]$RetryRestS = 600, [switch]$SkipGate, [switch]$AllowSettingsMismatch,
      [switch]$StrictSettings, [int]$ReconnectWaitS = 600, [int]$ConnectionStopAfter = 3)
# S26 mixed-request block driver (R2 -> v2 R3, 2026-10-09). ASCII + CRLF only. One block per invocation (A = sessions 0..7, N = 8..15).
# v1 rules kept (prereg s3-3, s4): sessions in registered order; an invalid session is retried ONCE in the same slot after >= RetryRestS
# (600 s) rest + the gate (attempt 2, same sid/request ids); gate SOC/plugged block (exit 6) stops the block with "CHARGE NEEDED".
# v2 rules (prereg v2 #6 #7, R3 ledger 1-2 (3)):
#   * a second invalid attempt no longer stops the block: the slot is recorded as invalid_twice and the driver moves to the next index
#   * connection-class results (rc 2 gate script failed, rc 3 device/adb, rc 4 stall/lost): if the app never started on the phone
#     (host session_log has no start_time) the attempt is NOT consumed -> the host folder is moved aside (<folder>_pre<attempt>_<time>),
#     the driver waits for adb (disconnect/connect once a minute, up to ReconnectWaitS) and re-runs the same attempt;
#     ConnectionStopAfter (3) consecutive connection failures -> STOP "CONNECTION x3" (reconnect, then resume with -StartIndex <index>)
#   * settings mismatch (brightness 1 instead of 0) is allowed by default (-StrictSettings turns the check back on; -AllowSettingsMismatch kept as a no-op)
#   * rc 5 (attempt folder already exists, e.g. after a driver crash) counts as a consumed attempt -> next attempt number
# Keep-awake: SetThreadExecutionState loop (copy of v3_1006/keepawake_v3b.ps1) with a stop file.
# Serial only from $env:ANDROID_SERIAL (logged as <SERIAL>). Every variable name is unique ignoring case ($d/$D collisions).
$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_mixreq"
if (-not $PlanDir) { $PlanDir = "$REPO\s26\results\mixreq_1008\plan_v2" }
if (-not $ResultsRoot) { $ResultsRoot = "$REPO\results\S26_MIXREQ_1009v2" }
$TOOLDIR = "$REPO\s26\tools\mixreq"
$ADBEXE = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
$allowMismatch = -not $StrictSettings
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
Log "DRIVER START block=$Block startIndex=$StartIndex plan=$PlanDir results=$ResultsRoot dry=$DryRun allowSettingsMismatch=$allowMismatch (v2 driver: invalid_twice -> next index; connection x$ConnectionStopAfter -> stop)"
Log "NOTE: laptop lid must stay OPEN (Modern Standby stops the PC; SetThreadExecutionState cannot prevent it)"
$indices = if ($Block -eq "A") { 0..7 } else { 8..15 }
if ($StartIndex -ge 0) { $indices = $indices | Where-Object { $_ -ge $StartIndex } }
$STATE = [ordered]@{ block = $Block; driver = "v2"; sessions = [ordered]@{}; stop_reason = ""; retries = 0; invalid_twice = @(); connection_events = 0; pre_start_moves = @() }
function SaveState() { if (-not $DryRun) { ($STATE | ConvertTo-Json -Depth 6) | Set-Content -Encoding UTF8 $stateFile } }
function PolicyOf([int]$idx) {
  $planJson = Get-Content -Raw -Encoding UTF8 "$PlanDir\plan.json" | ConvertFrom-Json
  foreach ($sess in $planJson.sessions) { if ($sess.index -eq $idx) { return $sess.policy } }
  return "UNKNOWN"
}
function HostFolder([int]$idx, [int]$attempt) { return "$ResultsRoot\S26_MIXREQ_" + ("{0:00}" -f $idx) + "_" + (PolicyOf $idx) + "_a$attempt" }
function AppStarted([string]$folder) {
  $logPath = "$folder\host\session_log.json"
  if (-not (Test-Path $logPath)) { return $false }
  try { $sl = Get-Content -Raw -Encoding UTF8 $logPath | ConvertFrom-Json; return [bool]($sl.PSObject.Properties.Name -contains "start_time") } catch { return $true }
}
function RunSession([int]$idx, [int]$attempt) {
  $argList = @("-X","utf8","$TOOLDIR\mixreq_session.py","--plan",$PlanDir,"--index",$idx,"--attempt",$attempt,"--results",$ResultsRoot)
  if ($DryRun) { $argList += "--dry-run" }
  if ($SkipGate) { $argList += "--skip-gate" }
  if ($allowMismatch) { $argList += "--allow-settings-mismatch" }  # v2 #7: S26 rewrites brightness 0 -> 1 while awake (display float 0.0 = minimum); value is recorded per session
  Log "RUN index=$idx attempt=$attempt"
  & py @argList 2>&1 | ForEach-Object { Log ("  py: " + "$_") }
  $rcode = $LASTEXITCODE
  Log "RESULT index=$idx attempt=$attempt rc=$rcode (0 valid, 1 invalid, 2 gate fail, 3 device/settings, 4 stall, 5 folder exists, 6 charge needed)"
  return $rcode
}
function WaitForAdb() {
  # disconnect/connect once a minute until get-state == device or ReconnectWaitS elapsed. Returns $true when connected.
  if ($DryRun) { return $true }
  $t0 = Get-Date
  while ($true) {
    $st = (& $ADBEXE -s $DEVSER get-state 2>&1 | Out-String).Trim()
    if ($st -eq "device") { Log "adb reconnected (get-state device)"; return $true }
    $elapsed = ((Get-Date) - $t0).TotalSeconds
    if ($elapsed -ge $ReconnectWaitS) { Log "adb still not connected after $([int]$elapsed) s (state '$st')"; return $false }
    Log "adb state '$st' -> disconnect/connect, waiting 60 s (elapsed $([int]$elapsed) s of $ReconnectWaitS)"
    & $ADBEXE disconnect $DEVSER 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    & $ADBEXE connect $DEVSER 2>&1 | Out-Null
    Start-Sleep -Seconds 57
  }
}
# Runs one attempt; a connection-class failure that never reached the phone is retried (same attempt) after moving the host folder aside.
# Returns the final rc for that attempt (0..6) or -1 when the connection budget is exhausted (caller stops the block).
function RunAttempt([int]$idx, [int]$attempt) {
  while ($true) {
    $rcA = RunSession $idx $attempt
    $isConn = ($rcA -eq 2 -or $rcA -eq 3 -or $rcA -eq 4)
    if (-not $isConn) { $STATE.connection_events = 0; return $rcA }
    $fold = HostFolder $idx $attempt
    if (AppStarted $fold) { Log "connection-class rc=$rcA but the app had started (start_time present) -> attempt $attempt is consumed"; return $rcA }
    $STATE.connection_events++
    $moved = $fold + "_pre" + $attempt + "_" + (Get-Date -Format "HHmmss")
    if (Test-Path $fold) { Move-Item -Path $fold -Destination $moved -Force; $STATE.pre_start_moves += $moved; Log "pre-start failure rc=$rcA -> host folder moved aside: $(Split-Path -Leaf $moved) (attempt not consumed)" }
    SaveState
    if ($STATE.connection_events -ge $ConnectionStopAfter) { Log "CONNECTION x$($STATE.connection_events): consecutive pre-start connection failures -> stop block (reconnect, then resume with -StartIndex $idx)"; return -1 }
    $ok = WaitForAdb
    if (-not $ok) { Log "WAIT: adb not back after $ReconnectWaitS s -> one more attempt anyway (operator: check the wireless debugging address)" }
    if (-not $DryRun) { Start-Sleep -Seconds 5 }
  }
}
foreach ($idx in $indices) {
  $rc1 = RunAttempt $idx 1
  $STATE.sessions["$idx"] = [ordered]@{ attempt1 = $rc1 }
  SaveState
  if ($rc1 -eq -1) { $STATE.stop_reason = "CONNECTION x$ConnectionStopAfter at index $idx"; break }
  if ($rc1 -eq 6) { $STATE.stop_reason = "CHARGE NEEDED at index $idx (gate SOC/plugged)"; Log "STOP: charge needed -> block paused at index $idx (resume with -StartIndex $idx after charging + gate)"; break }
  if ($rc1 -eq 0) { continue }
  # invalid (1) / stall after start (4) / folder exists (5) / connection-class after start (2,3): one retry in the same slot after >= RetryRestS rest + gate
  Log "RETRY: resting $RetryRestS s before attempt 2 of index $idx (rc1=$rc1)"
  if (-not $DryRun) { Start-Sleep -Seconds $RetryRestS }
  $STATE.retries++
  $rc2 = RunAttempt $idx 2
  $STATE.sessions["$idx"].attempt2 = $rc2
  SaveState
  if ($rc2 -eq -1) { $STATE.stop_reason = "CONNECTION x$ConnectionStopAfter at index $idx (retry)"; break }
  if ($rc2 -eq 0) { continue }
  if ($rc2 -eq 6) { $STATE.stop_reason = "CHARGE NEEDED at index $idx retry"; Log "STOP: charge needed on retry (resume with -StartIndex $idx after charging + gate; attempt 2 folder may exist -> rc 5 -> slot invalid_twice)"; break }
  $STATE.invalid_twice += $idx
  $STATE.sessions["$idx"].slot = "invalid_twice"
  SaveState
  Log "INVALID_TWICE: index $idx (rc1=$rc1 rc2=$rc2) -> recorded, moving to the next index (prereg v2 #6)"
}
if (-not $STATE.stop_reason) { $STATE.stop_reason = "completed" }
SaveState
if ($kaProc) { Set-Content -Path $kaStop -Value "stop"; Log "keepawake stop requested" }
Log "DRIVER END block=$Block reason=$($STATE.stop_reason) retries=$($STATE.retries) invalid_twice=[$($STATE.invalid_twice -join ',')] pre_start_moves=$($STATE.pre_start_moves.Count)"
