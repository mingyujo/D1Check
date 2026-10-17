$ErrorActionPreference='Stop'
$out=Join-Path $PSScriptRoot '../../results/RL_COST_20261017_01'
$rows=@(Get-CimInstance Win32_Process)
$python=@($rows|Where-Object Name -match '^python(w)?\.exe$'|Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine)
$known=@($rows|Where-Object {$_.ProcessId -ne $PID -and $_.Name -match '^(pwsh|powershell)\.exe$' -and $_.CommandLine -match '(A24-|S26-|calibration|m8_calibrate|cost_decomposition)'}|Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine)
if($python.Count -or $known.Count){throw 'Producer alive; do not claim final free-slot snapshot'}
$volumes=@(Get-PSDrive C,D|ForEach-Object {[ordered]@{volume=$_.Name;free_bytes=$_.Free}})
if(@($volumes|Where-Object free_bytes -lt 8589934592).Count){throw '8GiB reserve'}
$reg=Get-Content (Join-Path $PSScriptRoot '../../models/registration.json') -Raw|ConvertFrom-Json
$reservationFiles=Get-ChildItem 'C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs' -Filter '*RESERVATION*.json' -Recurse -File
$reservations=@(foreach($f in $reservationFiles){$v=Get-Content -LiteralPath $f.FullName -Raw|ConvertFrom-Json;if($null -ne $v.global_reserved){[ordered]@{path=$f.FullName;sha256=(Get-FileHash -LiteralPath $f.FullName).Hash.ToLowerInvariant();global_reserved=[long]$v.global_reserved}}})
$lock=[IO.File]::Open($reg.worker_lock_path,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::ReadWrite)
$acquired=$false
try{$lock.Lock(0,1);$acquired=$true}finally{if($acquired){$lock.Unlock(0,1)};$lock.Dispose()}
$value=[ordered]@{schema='A24-final-producer-snapshot-v1';checked_utc=[DateTime]::UtcNow.ToString('o');active_python=$python;active_known_producers=$known;volumes=$volumes;reservation_registry=$reservations;shared_lock_acquire_release_pass=$true;new_environment=0;new_NN=0}
$target=Join-Path $out 'FINAL_PRODUCER_SNAPSHOT.json'
$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($value|ConvertTo-Json -Depth 12)+[Environment]::NewLine)
$stream=[IO.File]::Open($target,[IO.FileMode]::CreateNew)
try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
Write-Output 'Fresh producer-free/8GiB/shared-lock snapshot saved'
