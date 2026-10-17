param([ValidateSet('Prepare','Test','Register','Run')][string]$Mode='Prepare')
$ErrorActionPreference='Stop'
$pkg=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$base='C:/Users/chomg/Documents/Codex/2026-10-11/dkfo';$utf8=[Text.UTF8Encoding]::new($false)
function SaveNew($path,$value) {
 $b=$utf8.GetBytes(($value|ConvertTo-Json -Depth 90)+[Environment]::NewLine)
 $f=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
 try{$f.Write($b,0,$b.Length);$f.Flush($true)}finally{$f.Dispose()}
}
function Pin($path){$f=Get-Item -LiteralPath $path;[ordered]@{path=$f.FullName;sha256=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant();bytes=$f.Length}}
function FreeSlot {
 $py=@(Get-CimInstance Win32_Process|Where-Object Name -match '^python(w)?\.exe$')
 $ps=@(Get-CimInstance Win32_Process|Where-Object {$_.ProcessId -ne $PID -and $_.Name -match '^(pwsh|powershell)\.exe$' -and $_.CommandLine -match '(A24-|S26-|execute_calibration|m8_calibrate|cost_decomposition)'})
 if($py.Count -or $ps.Count){throw 'Own producer busy; A24 Python0'}
 if(@(Get-PSDrive C,D|Where-Object Free -lt 8GB).Count){throw '8GiB reserve'}
}
if($Mode -eq 'Prepare') {
 $old=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'SOURCE_PREPARATION.json') -Raw|ConvertFrom-Json
 foreach($pin in $old.pins){if((Get-FileHash -LiteralPath $pin.path).Hash.ToLowerInvariant() -ne $pin.sha256){throw 'Predecessor source drift'}}
 $pins=@($old.pins)+@((Pin (Join-Path $PSScriptRoot 'prepare_inputs_v2.cjs')),(Pin (Join-Path $PSScriptRoot 'register_v2.ps1')))
 SaveNew (Join-Path $PSScriptRoot 'SOURCE_PREPARATION_V2.json') ([ordered]@{schema='A24-cost-RL-source-preparation-v2';created_utc=[DateTime]::UtcNow.ToString('o');pins=$pins;allow_runtime=$false;tests='NOT_RUN';environment_START=0;NN=0;model_fit=0;expected_START=223;shared_existing_reservation=256;new_reservation=0;correction='Historical input keys inherited from exact original root default; explicit384 override preserved. V1 has no runtime/tests/input generation.'})
 Write-Output 'V2 source preparation frozen; SAME256 reservation; no Python/NN/environment'
 exit
}
$prep=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'SOURCE_PREPARATION_V2.json') -Raw|ConvertFrom-Json
foreach($pin in $prep.pins){if((Get-FileHash -LiteralPath $pin.path).Hash.ToLowerInvariant() -ne $pin.sha256){throw "Frozen source/input drift: $($pin.path)"}}
if($Mode -eq 'Test') {
 FreeSlot
 if(Test-Path -LiteralPath (Join-Path $PSScriptRoot 'INPUTS.json')){throw 'Test/inputs namespace consumed; inspect frontier'}
 SaveNew (Join-Path $PSScriptRoot 'TEST_OPERATION.json') ([ordered]@{schema='A24-cost-RL-pure-tests-v1';created_utc=[DateTime]::UtcNow.ToString('o');pins=$prep.pins;output=(Join-Path $PSScriptRoot 'PURE_TEST_RESULT.json');environment_START=0;NN=0;automatic_retry=$false})
 node (Join-Path $PSScriptRoot 'prepare_inputs_v2.cjs')
 if($LASTEXITCODE -ne 0){throw 'Input generation failed'}
 $env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1'
 & 'C:/Users/chomg/AppData/Local/Programs/Python/Python311/python.exe' -B -X utf8 (Join-Path $PSScriptRoot 'test_cost_rl.py') (Join-Path $PSScriptRoot 'PURE_TEST_RESULT.json')
 if($LASTEXITCODE -ne 0){throw 'Pure tests failed; preserve output/source; no retry'}
 exit
}
if($Mode -eq 'Register') {
 $test=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'PURE_TEST_RESULT.json') -Raw|ConvertFrom-Json
 if($test.status -ne 'PASS'){throw 'Pure tests PASS required'}
 $rr=Join-Path $pkg 'results/RR_20261017_01'
 $complete=Get-Content -LiteralPath (Join-Path $rr 'COMPLETE.json') -Raw|ConvertFrom-Json
 if($complete.new_COMPLETE -ne 7 -or (Get-FileHash -LiteralPath (Join-Path $rr 'RESULT.json')).Hash.ToLowerInvariant() -ne $complete.result_sha256){throw 'RR complete SHA/count required'}
 $op=[ordered]@{schema='A24-cost-RL-operation-v1';created_utc=[DateTime]::UtcNow.ToString('o');pins=@($prep.pins)+@((Pin (Join-Path $PSScriptRoot 'INPUTS.json')),(Pin (Join-Path $PSScriptRoot 'PURE_TEST_RESULT.json')),(Pin (Join-Path $rr 'RESULT.json')),(Pin (Join-Path $rr 'COMPLETE.json')));policy_config=$test.policy_config;reward_spec=$test.reward_spec;inputs=(Pin (Join-Path $PSScriptRoot 'INPUTS.json'));budget=(Pin (Join-Path $PSScriptRoot 'BUDGET_RESERVATION.json'));cost_model=(Pin (Join-Path $pkg 'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'));warm_start=(Pin (Join-Path $pkg 'results/PROTECTED48_V2_20261016_01/PPO_PROTECTED48_EP024.pt'));saved_RR_comparison=(Pin (Join-Path $rr 'RESULT.json'));output_dir='results/RL_COST_20261017_01';environment_cap=256;planned_STARTs=223;maximum_requests=3072;learner_seed=20268501;learner_settings=@{episodes_per_update=8;epochs=3;minibatch_frames=256;learning_rate=.0003;clip=.2;value_coef=.5;entropy_coef=.01;gradient_clip=.5;kl_stop=.03;gae_time_s=20.;dual_lr=5.};checkpoint_episodes=@(32,64,96);automatic_retry=$false;new_fit=0;periodic_GitHub_check=$false;fresh_device_confirmation=$false}
 SaveNew (Join-Path $PSScriptRoot 'OPERATION.json') $op
 Write-Output 'RL OPERATION REGISTERED 223/256; train96 DEV48 fresh60 historical7 control12'
 exit
}
FreeSlot
$opPath=Join-Path $PSScriptRoot 'OPERATION.json'
$op=Get-Content -LiteralPath $opPath -Raw|ConvertFrom-Json
if(Test-Path -LiteralPath (Join-Path $pkg $op.output_dir)){throw 'Runtime namespace already consumed'}
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1'
& 'C:/Users/chomg/AppData/Local/Programs/Python/Python311/python.exe' -B -X utf8 (Join-Path $PSScriptRoot 'run_training.py') $opPath
if($LASTEXITCODE -ne 0){throw 'RL runtime failed; exact frontier review only; no retry'}
