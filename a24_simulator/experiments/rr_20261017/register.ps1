param([ValidateSet('Register','Test','Run')][string]$Mode='Register')
$ErrorActionPreference='Stop'
$pkg=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$base='C:/Users/chomg/Documents/Codex/2026-10-11/dkfo'
$utf8=[Text.UTF8Encoding]::new($false)
function SaveNew($path,$value) {
 $bytes=$utf8.GetBytes(($value|ConvertTo-Json -Depth 90)+[Environment]::NewLine)
 $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
 try {$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function Pin($path) {$f=Get-Item -LiteralPath $path;[ordered]@{path=$f.FullName;sha256=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant();bytes=$f.Length}}
function FreeSlot {
 $python=@(Get-CimInstance Win32_Process|Where-Object Name -match '^python(w)?\.exe$')
 $otherPS=@(Get-CimInstance Win32_Process|Where-Object {$_.ProcessId -ne $PID -and $_.Name -match '^(pwsh|powershell)\.exe$' -and $_.CommandLine -match '(A24-|S26-|execute_calibration|m8_calibrate|cost_decomposition)'})
 if($python.Count -or $otherPS.Count){throw 'Own producer busy; no Python helper/test/environment started'}
 if(@(Get-PSDrive C,D|Where-Object Free -lt 8GB).Count){throw '8GiB reserve'}
}
if($Mode -eq 'Register') {
 $parent=Join-Path $base 'outputs/S26-MULTIRESOURCE-20261017-G004/BUDGET_RESERVATION.json'
 $p=Get-Content -LiteralPath $parent -Raw|ConvertFrom-Json
 if($p.global_reserved -ne 124574){throw 'Global reservation changed; review first'}
 $ledgers=@($p.global_ledgers|ForEach-Object {[ordered]@{path=$_.path;START=$_.START}})
 $active=$p.new_ledger;$count=0
 foreach($line in [IO.File]::ReadLines($active)){if(($line|ConvertFrom-Json).event -eq 'START'){$count++}}
 $ledgers+=@([ordered]@{path=$active;START=$count;active_at_registration=$true})
 $outdir=Join-Path $base 'outputs/A24-RR-20261017';[IO.Directory]::CreateDirectory($outdir)|Out-Null
 $budget=[ordered]@{schema='A24-RR-budget-v1';created_utc=[DateTime]::UtcNow.ToString('o');parent=(Pin $parent);previous_global_reserved=124574;new_reservation=8;global_reserved=124582;global_cap=137712;unreserved=13130;global_ledgers=$ledgers;new_ledger=(Join-Path $pkg 'results/RR_20261017_01/receipts.jsonl');planned_START=7;maximum_requests=3072;NN=0;fit=0;old_consumption_preserved=$true}
 SaveNew (Join-Path $outdir 'BUDGET_RESERVATION.json') $budget
 SaveNew (Join-Path $PSScriptRoot 'BUDGET_RESERVATION.json') $budget
 $old=Get-Content -LiteralPath (Join-Path $pkg 'experiments/rules_no_rl_20261017/OPERATION.json') -Raw|ConvertFrom-Json
 $all=@($old.pins)
 foreach($file in @('rr_policy.py','run_rr.py','test_rr.py','register.ps1','BUDGET_RESERVATION.json')) {$all+=@(Pin (Join-Path $PSScriptRoot $file))}
 $all+=@(Pin (Join-Path $pkg 'results/RULES_NO_RL_20261017_01/RESULT.json'))
 $op=[ordered]@{schema='A24-RR-operation-v1';created_utc=[DateTime]::UtcNow.ToString('o');pins=$all;inputs=$old.inputs;cost_model=$old.cost_model;budget=(Pin (Join-Path $PSScriptRoot 'BUDGET_RESERVATION.json'));saved_rules_report=(Pin (Join-Path $pkg 'results/RULES_NO_RL_20261017_01/RESULT.json'));output_dir='results/RR_20261017_01';environment_cap=8;planned_STARTs=7;maximum_requests=3072;NN_execution=0;NN_training=0;model_fit=0;periodic_GitHub_check=$false;automatic_retry=$false}
 SaveNew (Join-Path $PSScriptRoot 'OPERATION.json') $op
 SaveNew (Join-Path $PSScriptRoot 'TEST_OPERATION.json') ([ordered]@{schema='A24-RR-tests-v1';created_utc=[DateTime]::UtcNow.ToString('o');pins=@($all|Where-Object {$_.path -match '(rr_policy|run_rr|test_rr|register)\.(py|ps1)$'});output=(Join-Path $PSScriptRoot 'PURE_TEST_RESULT.json');environment_START=0;NN=0})
 Write-Output 'REGISTERED RR7; global reserved124582; runtime/test NOT_RUN'
 exit
}
FreeSlot
$op=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'OPERATION.json') -Raw|ConvertFrom-Json
foreach($pin in $op.pins){if((Get-FileHash -LiteralPath $pin.path).Hash.ToLowerInvariant() -ne $pin.sha256){throw "Source/input drift: $($pin.path)"}}
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1'
$pythonExe='C:/Users/chomg/AppData/Local/Programs/Python/Python311/python.exe'
if($Mode -eq 'Test') {
 if(Test-Path -LiteralPath (Join-Path $PSScriptRoot 'PURE_TEST_RESULT.json')){throw 'Test namespace consumed'}
 & $pythonExe -B -X utf8 (Join-Path $PSScriptRoot 'test_rr.py') (Join-Path $PSScriptRoot 'PURE_TEST_RESULT.json')
 if($LASTEXITCODE -ne 0){throw 'RR tests failed; no automatic retry'}
} else {
 $test=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'PURE_TEST_RESULT.json') -Raw|ConvertFrom-Json
 if($test.status -ne 'PASS'){throw 'Pure test PASS required'}
 if(Test-Path -LiteralPath (Join-Path $pkg $op.output_dir)){throw 'RR runtime namespace consumed'}
 & $pythonExe -B -X utf8 (Join-Path $PSScriptRoot 'run_rr.py') (Join-Path $PSScriptRoot 'OPERATION.json')
 if($LASTEXITCODE -ne 0){throw 'RR runtime failed; inspect saved frontier; no retry'}
}
