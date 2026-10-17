param([ValidateSet('Register','NN','Saved','QA','Documents')][string]$Mode='Register')
$ErrorActionPreference='Stop'
$pkg=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'));$out=Join-Path $pkg 'results/RL_COST_20261017_01'
$utf8=[Text.UTF8Encoding]::new($false)
function Pin($p){$f=Get-Item -LiteralPath $p;[ordered]@{path=$f.FullName;sha256=(Get-FileHash -LiteralPath $p).Hash.ToLowerInvariant();bytes=$f.Length}}
function SaveNew($p,$v){$bytes=$utf8.GetBytes(($v|ConvertTo-Json -Depth 80)+[Environment]::NewLine);$f=[IO.File]::Open($p,[IO.FileMode]::CreateNew);try{$f.Write($bytes,0,$bytes.Length);$f.Flush($true)}finally{$f.Dispose()}}
function FreeSlot {
 $py=@(Get-CimInstance Win32_Process|Where-Object Name -match '^python(w)?\.exe$')
 $ps=@(Get-CimInstance Win32_Process|Where-Object {$_.ProcessId -ne $PID -and $_.Name -match '^(pwsh|powershell)\.exe$' -and $_.CommandLine -match '(A24-|S26-|calibration|m8_calibrate|cost_decomposition)'})
 if($py.Count -or $ps.Count){throw 'Producer alive; defer postrun without starting helper'}
 if(@(Get-PSDrive C,D|Where-Object Free -lt 8GB).Count){throw '8GiB reserve'}
}
FreeSlot
if($Mode -eq 'Register') {
 $prepPath=Join-Path $PSScriptRoot 'POSTRUN_SOURCE_PREPARATION.json'
 $prep=Get-Content -LiteralPath $prepPath -Raw|ConvertFrom-Json
 foreach($pin in $prep.pins){if((Get-FileHash -LiteralPath $pin.path).Hash.ToLowerInvariant() -ne $pin.sha256){throw "Prepared postrun source drift $($pin.path)"}}
 $terminal=Get-Content -LiteralPath (Join-Path $out 'COMPLETE.json') -Raw|ConvertFrom-Json
 if($terminal.new_COMPLETE -ne 223 -or $terminal.result_sha256 -ne (Get-FileHash -LiteralPath (Join-Path $out 'RESULT.json')).Hash.ToLowerInvariant()){throw 'Exact complete223 required'}
 $op=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'OPERATION.json') -Raw|ConvertFrom-Json
 $pins=@($op.pins)+@((Pin $prepPath))
 foreach($p in @('audit_nn_v2.py','audit_saved.cjs','report_v2.cjs','qa_report.cjs','finalize_docs.cjs','final_handoff.cjs','final_snapshot.ps1','postrun.ps1')){$pins+=@(Pin (Join-Path $PSScriptRoot $p))}
 foreach($p in (Get-ChildItem -LiteralPath $out -File)){$pins+=@(Pin $p.FullName)}
 SaveNew (Join-Path $PSScriptRoot 'POSTRUN_OPERATION.json') ([ordered]@{schema='A24-cost-RL-postrun-operation-v1';created_utc=[DateTime]::UtcNow.ToString('o');pins=$pins;new_environment_START=0;new_NN_training=0;saved_optimizer_replay=$true;automatic_retry=$false})
 Write-Output 'Postrun source and all completed evidence pinned; no new environment'
 exit
}
$opPath=Join-Path $PSScriptRoot 'POSTRUN_OPERATION.json'
$op=Get-Content -LiteralPath $opPath -Raw|ConvertFrom-Json
foreach($pin in $op.pins){if((Get-FileHash -LiteralPath $pin.path).Hash.ToLowerInvariant() -ne $pin.sha256){throw "Postrun source/evidence drift $($pin.path)"}}
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1'
switch($Mode){
 'NN' {
  if(Test-Path -LiteralPath (Join-Path $out 'NN_AUDIT.json')){throw 'NN audit consumed'}
  $py='C:/Users/chomg/AppData/Local/Programs/Python/Python311/python.exe'
  & $py -B -X utf8 -c "import ast,pathlib;ast.parse(pathlib.Path(r'$PSScriptRoot/audit_nn_v2.py').read_text(encoding='utf-8'));print('NN audit AST PASS; environment0')"
  if($LASTEXITCODE -ne 0){throw 'NN audit AST'}
  & $py -B -X utf8 (Join-Path $PSScriptRoot 'audit_nn_v2.py')
  if($LASTEXITCODE -ne 0){throw 'NN saved replay failed; no retry'}
 }
 'Saved' {
  $nn=Get-Content -LiteralPath (Join-Path $out 'NN_AUDIT.json') -Raw|ConvertFrom-Json
  if($nn.status -notlike 'PASS_EXACT*'){throw 'Exact NN PASS required'}
  SaveNew (Join-Path $PSScriptRoot 'SAVED_AUDIT_OPERATION.json') ([ordered]@{schema='A24-cost-RL-saved-audit-v1';created_utc=[DateTime]::UtcNow.ToString('o');pins=@($op.pins)+@((Pin (Join-Path $out 'NN_AUDIT.json')));new_environment=0;NN=0})
  node (Join-Path $PSScriptRoot 'audit_saved.cjs') (Join-Path $PSScriptRoot 'SAVED_AUDIT_OPERATION.json')
  if($LASTEXITCODE -ne 0){throw 'Independent saved audit failed'}
 }
 'QA' {
  SaveNew (Join-Path $PSScriptRoot 'REPORT_OPERATION.json') ([ordered]@{schema='A24-cost-RL-report-v1';created_utc=[DateTime]::UtcNow.ToString('o');pins=@($op.pins)+@((Pin (Join-Path $out 'NN_AUDIT.json')),(Pin (Join-Path $out 'SAVED_AUDIT.json')));new_environment=0;NN=0})
  node (Join-Path $PSScriptRoot 'report_v2.cjs')
  if($LASTEXITCODE -ne 0){throw 'Renderer failed'}
  node (Join-Path $PSScriptRoot 'qa_report.cjs')
  if($LASTEXITCODE -ne 0){throw 'Actual UI QA failed'}
 }
 'Documents' {
  SaveNew (Join-Path $PSScriptRoot 'DOCUMENT_OPERATION.json') ([ordered]@{schema='A24-cost-RL-document-v1';created_utc=[DateTime]::UtcNow.ToString('o');pins=@($op.pins)+@((Pin (Join-Path $out 'SAVED_AUDIT.json')),(Pin (Join-Path $out 'UI_QA/RESULT.json')),(Pin (Join-Path $out 'REPORT_DATA.json')),(Pin (Join-Path $out 'REPORT.html')));new_environment=0;NN=0})
  node (Join-Path $PSScriptRoot 'finalize_docs.cjs')
  if($LASTEXITCODE -ne 0){throw 'Final documents failed'}
 }
}
