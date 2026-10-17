$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$target='D:/A24_RL_COST_20261017_223_COMPLETE_PREAUDIT.zip'
$receipt='D:/A24_RL_COST_20261017_223_COMPLETE_PREAUDIT.json'
if((Test-Path $target)-or(Test-Path $receipt)){throw 'Backup already exists; preserve without overwrite'}
if(@(Get-CimInstance Win32_Process|Where-Object Name -match '^python(w)?\.exe$').Count){throw 'Wait for numerical slot before bulk backup'}
if(@(Get-PSDrive C,D|Where-Object Free -lt 8GB).Count){throw '8GiB reserve'}
$terminal=Get-Content (Join-Path $root 'results/RL_COST_20261017_01/COMPLETE.json') -Raw|ConvertFrom-Json
if($terminal.new_COMPLETE -ne 223){throw 'Closed223 required'}
$paths=@(Get-ChildItem (Join-Path $root 'results/RL_COST_20261017_01'),$PSScriptRoot -File -Recurse|ForEach-Object FullName)
$paths+=@('CONTINUE.json','README.md','COMPLETED_AND_FILES.md','docs/RR_AND_COST_RL_DEVELOPMENT.md','docs/COST_RL_LIMITATIONS.md')|ForEach-Object {Join-Path $root $_}
$files=@(foreach($p in $paths|Sort-Object -Unique){$f=Get-Item -LiteralPath $p;[ordered]@{path='a24_simulator/'+[IO.Path]::GetRelativePath($root,$f.FullName).Replace('\','/');source=$f.FullName;bytes=$f.Length;sha256=(Get-FileHash -LiteralPath $p).Hash.ToLowerInvariant()}})
$manifest=[ordered]@{schema='A24223-closed-execution-overlay-backup-v1';created_utc=[DateTime]::UtcNow.ToString('o');base_commit='8ea30e4e884bbab1b7fcb791f2e49f740d4eae52';scope='223 environments COMPLETE; independent saved/NN/UI final audits pending at snapshot';runtime_directory_created=$false;runtime_data_location='a24_simulator/results/RL_COST_20261017_01';new_environment=0;new_NN=0;files=$files}
$opPath=Join-Path $PSScriptRoot 'BACKUP_OPERATION.json'
$utf8=[Text.UTF8Encoding]::new($false)
$opbytes=$utf8.GetBytes(($manifest|ConvertTo-Json -Depth 12)+[Environment]::NewLine)
$s=[IO.File]::Open($opPath,[IO.FileMode]::CreateNew);try{$s.Write($opbytes,0,$opbytes.Length);$s.Flush($true)}finally{$s.Dispose()}
Add-Type -AssemblyName System.IO.Compression
$stream=[IO.File]::Open($target,[IO.FileMode]::CreateNew)
$zip=[IO.Compression.ZipArchive]::new($stream,[IO.Compression.ZipArchiveMode]::Create,$false)
try{
 foreach($f in $files){$entry=$zip.CreateEntry($f.path,[IO.Compression.CompressionLevel]::NoCompression);$dest=$entry.Open();$src=[IO.File]::Open($f.source,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete);try{$src.CopyTo($dest)}finally{$src.Dispose();$dest.Dispose()}}
 $entry=$zip.CreateEntry('BACKUP_MANIFEST.json',[IO.Compression.CompressionLevel]::NoCompression);$dest=$entry.Open();try{$dest.Write($opbytes,0,$opbytes.Length)}finally{$dest.Dispose()}
}finally{$zip.Dispose();$stream.Dispose()}
$stream=[IO.File]::OpenRead($target);$zip=[IO.Compression.ZipArchive]::new($stream,[IO.Compression.ZipArchiveMode]::Read,$false)
try{foreach($f in $files){$e=$zip.GetEntry($f.path);if($null -eq $e -or $e.Length -ne $f.bytes){throw 'Backup member absent/size'};$r=$e.Open();$hash=[Security.Cryptography.SHA256]::Create();try{$actual=[Convert]::ToHexString($hash.ComputeHash($r)).ToLowerInvariant()}finally{$r.Dispose();$hash.Dispose()};if($actual -ne $f.sha256){throw "Backup member SHA $($f.path)"}}}finally{$zip.Dispose();$stream.Dispose()}
$proof=[ordered]@{status='PASS_EXACT_CLOSED_OVERLAY_BACKUP';path=$target;bytes=(Get-Item $target).Length;sha256=(Get-FileHash $target).Hash.ToLowerInvariant();members_verified=$files.Count;operation_path=$opPath;operation_sha256=(Get-FileHash $opPath).Hash.ToLowerInvariant();scope=$manifest.scope;created_utc=[DateTime]::UtcNow.ToString('o');new_environment=0;new_NN=0}
[IO.File]::WriteAllText($receipt,($proof|ConvertTo-Json -Depth 12)+[Environment]::NewLine,$utf8)
[IO.File]::WriteAllText((Join-Path $root 'results/RL_COST_20261017_01/BACKUP_REFERENCE.json'),($proof|ConvertTo-Json -Depth 12)+[Environment]::NewLine,$utf8)
$proof|ConvertTo-Json -Depth 12
