param([Parameter(Mandatory=$true)][ValidateSet("p","k","e")][string]$Kind, [string]$Items = "", [switch]$DryRun, [switch]$InBlockCharge,
      [string]$ResultsBase = "", [int]$RetryRestS = 600, [switch]$SkipGate, [switch]$StrictSettings, [int]$ReconnectWaitS = 600,
      [int]$ConnectionStopAfter = 3, [int]$LockWaitS = 3600)
# M6-A (2026-10-12) copy of statesplit_driver.ps1 (M5) - rules kept: runs in the registered order; an invalid run is retried ONCE in the same
# slot after >= RetryRestS (600 s) rest (attempt 2); a second invalid attempt -> slot invalid_twice, next item (order kept); connection-class
# results (rc 2/3/4) before the app started are not consumed (host folder moved aside, adb wait, same attempt); ConnectionStopAfter
# consecutive connection failures -> STOP; rc 5 = consumed attempt. Invalid attempt folders are never deleted.
# M6 changes: session script = m6_session.py (screen_off_timeout get/put 86400000 every run, never restored / awake/keyguard / SOC 30~90 /
# start SKIN band) / gauge script = m6_gauge.py; rc 6 = CHARGE NEEDED -> STOP (operator: "cable in" -> charge to 90 -> "cable out" -> 20 min
# + gate -> resume the same item with -InBlockCharge: every later run is marked in_block_charge); rc 7 = phone locked -> wait (60 s polls,
# up to LockWaitS) without consuming the attempt; rc 8 = SOC > 90 for 90 min -> STOP. No keep-awake here (m6_keepawake.ps1 runs once for
# the whole phone part). No screen_off_timeout restore line anywhere.
#   -Kind k : plan_m6k items "0,1" (K1 K2)       -> results\S26_M6_K
#   -Kind p : plan_m6p items "0,1,2,3,4,5" (dev) -> results\S26_M6_P
#   -Kind e : plan_m6e items "E1,E2,E3,ET"       -> results\S26_M6_GAUGE  (ET = with the device-side loop)
# Serial only from $env:ANDROID_SERIAL (logged as <SERIAL>). ASCII only.
$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
if (-not $ResultsBase) { $ResultsBase = "$REPO\results" }
$planByKind = @{ "p" = "plan_m6p"; "k" = "plan_m6k"; "e" = "plan_m6e" }
$rootByKind = @{ "p" = "S26_M6_P"; "k" = "S26_M6_K"; "e" = "S26_M6_GAUGE" }
$defItems = @{ "p" = "0,1,2,3,4,5"; "k" = "0,1"; "e" = "E1,E2,E3,ET" }
$PlanDir = "$REPO\s26\results\m6_1012\" + $planByKind[$Kind]
$ResultsRoot = "$ResultsBase\" + $rootByKind[$Kind]
$RunLog = "$ResultsBase\S26_M6_runs.jsonl"
$TOOLDIR = "$REPO\s26\tools\mixreq"
Set-Location $REPO   # plan device_inputs.json host paths are repo-relative
$ADBEXE = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER -and -not $DryRun) { throw "ANDROID_SERIAL not set" }
if (-not $Items) { $Items = $defItems[$Kind] }
$itemList = $Items.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
New-Item -ItemType Directory -Force $ResultsRoot | Out-Null
$runTag = (Get-Date -Format "MMdd_HHmmss")
$driverLog = "$ResultsRoot\driver_log_$Kind.txt"
$stateFile = "$ResultsRoot\driver_state_${Kind}_$runTag.json"
$script:charged = [bool]$InBlockCharge
function Log([string]$msg) {
  $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] " + $msg
  if ($DEVSER) { $line = $line -replace [regex]::Escape($DEVSER), "<SERIAL>" }
  Write-Host $line
  if (-not $DryRun) { for ($i = 0; $i -lt 5; $i++) { try { Add-Content -Path $driverLog -Encoding UTF8 -Value $line -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 300 } } }
}
Log "DRIVER START kind=$Kind items=[$($itemList -join ',')] plan=$PlanDir results=$ResultsRoot dry=$DryRun inBlockCharge=$($script:charged) (M6-A copy of M5 driver)"
Log "NOTE: laptop lid must stay OPEN (Modern Standby stops the PC; SetThreadExecutionState cannot prevent it)"
$STATE = [ordered]@{ kind = $Kind; driver = "m6a-v1"; items = [ordered]@{}; stop_reason = ""; retries = 0; invalid_twice = @(); connection_events = 0; pre_start_moves = @(); lock_waits = 0 }
function SaveState() { if (-not $DryRun) { ($STATE | ConvertTo-Json -Depth 6) | Set-Content -Encoding UTF8 $stateFile } }
function LabelOf([string]$item) {
  if ($Kind -eq "k") { return "K" + ([int]$item + 1) }
  if ($Kind -eq "p") { return "P" + $item }
  return $item
}
function HostFolder([string]$item, [int]$attempt) {
  if ($Kind -eq "e") { return "$ResultsRoot\${item}_a$attempt" }
  $planJson = Get-Content -Raw -Encoding UTF8 "$PlanDir\plan.json" | ConvertFrom-Json
  $pol = "UNKNOWN"
  foreach ($sess in $planJson.sessions) { if ($sess.index -eq [int]$item) { $pol = $sess.policy } }
  return "$ResultsRoot\S26_MIXREQ_" + ("{0:00}" -f [int]$item) + "_" + $pol + "_a$attempt"
}
function AppStarted([string]$folder) {
  foreach ($p in @("$folder\host\session_log.json", "$folder\host\gauge_log.json")) {
    if (Test-Path $p) { try { $sl = Get-Content -Raw -Encoding UTF8 $p | ConvertFrom-Json; if ($sl.PSObject.Properties.Name -contains "start_time") { return $true } } catch { return $true } }
  }
  return $false
}
function RunOnce([string]$item, [int]$attempt) {
  if ($Kind -eq "e") {
    $argList = @("-X","utf8","$TOOLDIR\m6_gauge.py","--plan",$PlanDir,"--run",$item,"--attempt",$attempt,"--results",$ResultsRoot,"--runlog",$RunLog)
    if ($item -eq "ET") { $argList += "--et-loop" }
  } else {
    $argList = @("-X","utf8","$TOOLDIR\m6_session.py","--plan",$PlanDir,"--index",$item,"--attempt",$attempt,"--results",$ResultsRoot,"--runlog",$RunLog,"--label",(LabelOf $item))
    if (-not $StrictSettings) { $argList += "--allow-settings-mismatch" }
    if ($SkipGate) { $argList += "--skip-gate" }
  }
  if ($script:charged) { $argList += "--in-block-charge" }
  if ($DryRun) { $argList += "--dry-run" }
  Log "RUN item=$item label=$(LabelOf $item) attempt=$attempt inBlockCharge=$($script:charged)"
  & py @argList 2>&1 | ForEach-Object { Log ("  py: " + "$_") }
  $rcode = $LASTEXITCODE
  Log "RESULT item=$item attempt=$attempt rc=$rcode (0 valid, 1 invalid, 2 gate, 3 device/settings, 4 stall, 5 folder exists, 6 charge needed, 7 locked, 8 SOC>90)"
  return $rcode
}
function WaitForAdb() {
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
function RunAttempt([string]$item, [int]$attempt) {
  $lockT0 = Get-Date
  while ($true) {
    $rcA = RunOnce $item $attempt
    if ($rcA -eq 7) {
      $STATE.lock_waits++
      SaveState
      if (((Get-Date) - $lockT0).TotalSeconds -ge $LockWaitS) { Log "LOCKED for $LockWaitS s -> stop"; return -7 }
      Log "PHONE LOCKED: operator please unlock the phone (waiting 60 s, attempt not consumed)"
      if (-not $DryRun) { Start-Sleep -Seconds 60 }
      continue
    }
    $isConn = ($rcA -eq 2 -or $rcA -eq 3 -or $rcA -eq 4)
    if (-not $isConn) { $STATE.connection_events = 0; return $rcA }
    $fold = HostFolder $item $attempt
    if (AppStarted $fold) { Log "connection-class rc=$rcA but the app had started (start_time present) -> attempt $attempt is consumed"; return $rcA }
    $STATE.connection_events++
    $moved = $fold + "_pre" + $attempt + "_" + (Get-Date -Format "HHmmss")
    if (Test-Path $fold) { Move-Item -Path $fold -Destination $moved -Force; $STATE.pre_start_moves += $moved; Log "pre-start failure rc=$rcA -> host folder moved aside: $(Split-Path -Leaf $moved) (attempt not consumed)" }
    SaveState
    if ($STATE.connection_events -ge $ConnectionStopAfter) { Log "CONNECTION x$($STATE.connection_events): consecutive pre-start connection failures -> stop (reconnect, then resume with -Items from $item)"; return -1 }
    $ok = WaitForAdb
    if (-not $ok) { Log "WAIT: adb not back after $ReconnectWaitS s -> one more attempt anyway (operator: check the wireless debugging address)" }
    if (-not $DryRun) { Start-Sleep -Seconds 5 }
  }
}
function StopFor([int]$rc, [string]$item, [string]$where) {
  if ($rc -eq -1) { $STATE.stop_reason = "CONNECTION x$ConnectionStopAfter at $item$where"; return $true }
  if ($rc -eq -7) { $STATE.stop_reason = "LOCKED at $item$where"; return $true }
  if ($rc -eq 6) { $STATE.stop_reason = "CHARGE NEEDED at $item$where"; Log "STOP: CHARGE NEEDED -> operator: cable in, charge to 90, cable out, 20 min + gate, then resume -Items from $item -InBlockCharge"; return $true }
  if ($rc -eq 8) { $STATE.stop_reason = "SOC above 90 at $item$where"; return $true }
  return $false
}
foreach ($item in $itemList) {
  $rc1 = RunAttempt $item 1
  $STATE.items[$item] = [ordered]@{ attempt1 = $rc1 }
  SaveState
  if (StopFor $rc1 $item "") { break }
  if ($rc1 -eq 0) { continue }
  Log "RETRY: resting $RetryRestS s before attempt 2 of item $item (rc1=$rc1)"
  if (-not $DryRun) { Start-Sleep -Seconds $RetryRestS }
  $STATE.retries++
  $rc2 = RunAttempt $item 2
  $STATE.items[$item].attempt2 = $rc2
  SaveState
  if (StopFor $rc2 $item " (retry)") { break }
  if ($rc2 -eq 0) { continue }
  $STATE.invalid_twice += $item
  $STATE.items[$item].slot = "invalid_twice"
  SaveState
  Log "INVALID_TWICE: item $item (rc1=$rc1 rc2=$rc2) -> recorded, moving to the next item"
}
if (-not $STATE.stop_reason) { $STATE.stop_reason = "completed" }
SaveState
Log "DRIVER END kind=$Kind reason=$($STATE.stop_reason) retries=$($STATE.retries) invalid_twice=[$($STATE.invalid_twice -join ',')] pre_start_moves=$($STATE.pre_start_moves.Count) lock_waits=$($STATE.lock_waits)"
