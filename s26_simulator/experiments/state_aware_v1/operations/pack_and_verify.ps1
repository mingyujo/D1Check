$ErrorActionPreference='Stop'
$studyOutput=$PSScriptRoot
$packPlan=Get-Content -LiteralPath (Join-Path $studyOutput 'PACK_PLAN.json') -Raw | ConvertFrom-Json
$packResults=@()
foreach($pack in $packPlan){
  $destination=[IO.Path]::GetFullPath($pack.zip)
  if(Test-Path -LiteralPath $destination){throw "Archive already exists: $destination"}
  Compress-Archive -Path (Join-Path $pack.staging '*') -DestinationPath $destination -CompressionLevel Optimal
  $zipInfo=Get-Item -LiteralPath $destination
  if($zipInfo.Length -gt 95MB){throw 'Archive exceeds conservative GitHub file limit; retain evidence and use a new packaging registration'}
  $readback=Join-Path $studyOutput ('ZIP_READBACK_part'+$pack.part)
  if(Test-Path -LiteralPath $readback){throw 'Readback directory already exists'}
  Expand-Archive -LiteralPath $destination -DestinationPath $readback
  $manifest=Get-Content -LiteralPath (Join-Path $readback 'MANIFEST.json') -Raw | ConvertFrom-Json
  $verified=0
  foreach($file in $manifest.files){
    $target=Join-Path $readback $file.path
    $actual=Get-Item -LiteralPath $target
    if($actual.Length -ne $file.bytes){throw "Readback length mismatch: $target"}
    if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256){throw "Readback SHA mismatch: $target"}
    $verified++
  }
  if($verified -ne 300){throw 'Expected 100 raw/config/proof triples'}
  $packResults += [ordered]@{part=$pack.part;file=$zipInfo.Name;bytes=$zipInfo.Length;sha256=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant();files_verified=$verified;raw_cases=100;status='PASS'}
  Write-Output ('Readback PASS part '+$pack.part+': '+$verified+' files')
}
$publicDir=Split-Path -Parent $packPlan[0].zip
$result=[ordered]@{status='PASS';created_utc=[DateTime]::UtcNow.ToString('o');method='Compress-Archive then fresh Expand-Archive; every uncompressed byte length/SHA checked';raw_cases=300;uncompressed_files_verified=900;new_policy_environments=0;packs=$packResults}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $publicDir 'RAW_PACK_VERIFICATION.json') -Encoding utf8
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $studyOutput 'RAW_PACK_VERIFICATION.json') -Encoding utf8
