$ErrorActionPreference='Stop'
$taskRoot=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$taskOut=Join-Path $taskRoot 'results/LONG_SCALE_20261017_V4_01'
$taskProcess=Get-CimInstance Win32_Process -Filter 'ProcessId=30400'
if(-not $taskProcess -or $taskProcess.CommandLine -notlike '*long_scale_20261017*run_scale_v4.py*OPERATION_V4.json*'){throw 'Worker owner mismatch'}
$taskCreated=(Get-Process -Id 30400).StartTime.ToUniversalTime().Ticks
$taskRegistered=[ordered]@{schema='A24-explicit-user-scope-limit-v1';utc=[DateTime]::UtcNow.ToString('o');user_instruction='3072까지만해';maximum_requests=3072;stop_condition='durable COMPLETE N03072_RL; all selected outputs persisted; prevent next length';actual_owner=$taskProcess|Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine;worker_source_sha256=(Get-FileHash (Join-Path $PSScriptRoot 'run_scale_v4.py')).Hash.ToLower();worker_source_modified=$false;higher_requested_lengths_cancelled=@(6144,12288);scheduled_automation=$false}
$taskPinFile=Join-Path $PSScriptRoot 'USER_SCOPE_LIMIT_3072.json'
if(Test-Path $taskPinFile){throw 'scope operator consumed'}
[IO.File]::WriteAllText($taskPinFile,($taskRegistered|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
$taskClock=[Diagnostics.Stopwatch]::StartNew()
while($taskClock.Elapsed.TotalSeconds -lt 3600){
    $taskLedger=Join-Path $taskOut 'receipts.jsonl'
    $taskText=[IO.File]::ReadAllText($taskLedger)
    if($taskText -match '"event":"COMPLETE"[^\r\n]*"label":"N03072_RL"'){
        $taskCurrent=Get-Process -Id 30400 -ErrorAction SilentlyContinue
        if($taskCurrent -and $taskCurrent.StartTime.ToUniversalTime().Ticks -ne $taskCreated){throw 'PID reused'}
        if($taskCurrent){Stop-Process -Id 30400 -ErrorAction Stop}
        $taskFinal=[IO.File]::ReadAllText($taskLedger)
        $taskReceipt=[ordered]@{schema='A24-user-stop-after-selected-saved-completion-v1';utc=[DateTime]::UtcNow.ToString('o');maximum_requests=3072;stop_after_selected_COMPLETE=$true;worker_source_modified=$false;automatic_retry=$false;elapsed_watch_s=$taskClock.Elapsed.TotalSeconds;ledger_sha256=(Get-FileHash $taskLedger).Hash.ToLower();larger_START_present=($taskFinal -match '"event":"START"[^\r\n]*"n":(6144|12288)');explicit_user_instruction='3072까지만해';owner_pid=30400;scope_sha256=(Get-FileHash $taskPinFile).Hash.ToLower()}
        $taskReceiptPath=Join-Path $PSScriptRoot 'USER_STOP_AFTER_3072_RECEIPT.json'
        [IO.File]::WriteAllText($taskReceiptPath,($taskReceipt|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
        Write-Output ($taskReceipt|ConvertTo-Json -Compress);exit 0
    }
    if(-not (Get-Process -Id 30400 -ErrorAction SilentlyContinue)){throw 'Worker exited before selected completion; inspect failures, no retry'}
    Start-Sleep -Milliseconds 20
}
throw 'Scope stopper timed out without changing worker'