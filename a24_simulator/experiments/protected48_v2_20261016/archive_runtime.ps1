param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$taskOut=Join-Path $taskRoot 'results/PROTECTED48_V2_20261016_01'
$taskComplete=Get-Content -Raw -LiteralPath (Join-Path $taskOut 'COMPLETE.json') | ConvertFrom-Json
$taskResult=Join-Path $taskOut 'RESULT.json'
if ((Get-FileHash -LiteralPath $taskResult -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskComplete.result_sha256) { throw 'Terminal SHA mismatch' }
foreach($taskName in @('NN_AUDIT.json','INDEPENDENT_AUDIT.json')) { if (!(Test-Path -LiteralPath (Join-Path $taskOut $taskName))) {throw "Audit missing: $taskName"} }
$taskDestination=[IO.Path]::GetFullPath($Destination)
if(Test-Path -LiteralPath $taskDestination){throw 'Existing archive; no overwrite'}
$taskDrive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($taskDestination))
if($taskDrive.AvailableFreeSpace -lt 8GB){throw '8GiB reserve'}
$taskRows=@()
foreach($taskGeneration in @('protected48_20261016_01','protected48_v2_20261016_01')) {
 $taskFolder=Join-Path $taskRoot "runtime/$taskGeneration"
 foreach($taskFile in Get-ChildItem -LiteralPath $taskFolder -File -Recurse){
  if(($taskFile.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Reparse runtime member'}
  $taskRelative=$taskGeneration+'/'+[IO.Path]::GetRelativePath($taskFolder,$taskFile.FullName).Replace('\','/')
  $taskRows+=@{name=$taskRelative;source=$taskFile.FullName;bytes=$taskFile.Length;sha256=(Get-FileHash -LiteralPath $taskFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
 }
}
$taskManifest=@{schema='A24-protected48-exact-runtime-archive-v1';result_sha256=$taskComplete.result_sha256;files=$taskRows;files_count=$taskRows.Count;simulation=0;NN_training=0;utc=[DateTime]::UtcNow.ToString('o')}
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($taskDestination)) | Out-Null
$taskStream=[IO.File]::Open($taskDestination,[IO.FileMode]::CreateNew)
$taskZip=[IO.Compression.ZipArchive]::new($taskStream,[IO.Compression.ZipArchiveMode]::Create,$false)
try{
 foreach($taskRow in $taskRows){[IO.Compression.ZipFileExtensions]::CreateEntryFromFile($taskZip,$taskRow.source,$taskRow.name,[IO.Compression.CompressionLevel]::Optimal) | Out-Null}
 $taskEntry=$taskZip.CreateEntry('RUNTIME_MANIFEST.json');$taskWriter=[IO.StreamWriter]::new($taskEntry.Open(),[Text.UTF8Encoding]::new($false))
 try{$taskWriter.Write(($taskManifest | ConvertTo-Json -Depth 8))}finally{$taskWriter.Dispose()}
}finally{$taskZip.Dispose();$taskStream.Dispose()}
$taskCheck=[IO.Compression.ZipFile]::OpenRead($taskDestination)
try{
 foreach($taskRow in $taskRows){$taskEntry=$taskCheck.GetEntry($taskRow.name);if($null -eq $taskEntry -or $taskEntry.Length -ne $taskRow.bytes){throw 'Archive member size mismatch'};$taskInput=$taskEntry.Open();try{$taskH=[Security.Cryptography.SHA256]::Create();$taskActual=[Convert]::ToHexString($taskH.ComputeHash($taskInput)).ToLowerInvariant()}finally{$taskInput.Dispose();$taskH.Dispose()};if($taskActual -ne $taskRow.sha256){throw 'Archive readback SHA mismatch'}}
}finally{$taskCheck.Dispose()}
$taskReceipt=@{status='PASS_EXACT_RUNTIME_ARCHIVE_READBACK';path=$taskDestination;bytes=(Get-Item -LiteralPath $taskDestination).Length;sha256=(Get-FileHash -LiteralPath $taskDestination -Algorithm SHA256).Hash.ToLowerInvariant();files=$taskRows.Count;source_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();result_sha256=$taskComplete.result_sha256;utc=[DateTime]::UtcNow.ToString('o')}
$taskReceipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ($taskDestination+'.receipt.json') -Encoding utf8NoBOM
$taskReceipt | ConvertTo-Json -Depth 5
