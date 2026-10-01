#requires -Version 5.1
param(
    [ValidateSet('Check','Run')][string]$Action = 'Check',
    [Parameter(Mandatory=$true)][string]$Manifest
)
$ErrorActionPreference = 'Stop'
$utf8 = [System.Text.UTF8Encoding]::new($false)
$manifestFile = [System.IO.Path]::GetFullPath($Manifest)
$auditRoot = [System.IO.Path]::GetDirectoryName($manifestFile)
$cleanupRoot = [System.IO.Path]::GetFullPath((Join-Path $env:USERPROFILE 'Documents\D1Check_Arrival_Extension'))
if ($auditRoot -ne (Join-Path $cleanupRoot 'storage_cleanup_pc_20261001_v1')) { throw 'Unexpected audit directory' }
$manifestData = Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $manifestData.inventory_complete -or $manifestData.root -ne $cleanupRoot) { throw 'Incomplete inventory or root mismatch' }
$receiptPath = Join-Path $auditRoot 'cleanup_receipt.json'
if (Test-Path -LiteralPath $receiptPath) { throw 'Cleanup receipt already exists; inspect it, do not repeat automatically' }
$activeBuilds = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq 'java.exe' -and $_.CommandLine -match 'Gradle|D1Check_Arrival_Extension|D1Check-model02b'
})
if ($activeBuilds.Count -gt 0) { throw 'Build process active; no deletion' }
foreach ($keep in $manifestData.protected) {
    if (-not (Test-Path -LiteralPath $keep.path -PathType Leaf)) { throw 'Protected artifact missing' }
    if ((Get-FileHash -LiteralPath $keep.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $keep.sha256) { throw 'Protected artifact changed' }
}
foreach ($target in $manifestData.targets) {
    $resolved = [System.IO.Path]::GetFullPath($target.path)
    if (-not $resolved.StartsWith($cleanupRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Target escapes cleanup root' }
    $parts = $resolved.Substring($cleanupRoot.Length + 1).Split('\')
    if ($parts[0] -notmatch '_build_v\d+$' -or $parts[1] -ne 'build' -or $parts[2] -notin @('_benchmark-runner','_telemetry-contract')) { throw 'Not a dedicated build intermediate' }
    $direct = $parts.Count -eq 4 -and $parts[3] -in @('generated','kotlin','tmp')
    $task = $parts.Count -eq 5 -and $parts[3] -eq 'intermediates'
    if (-not ($direct -or $task)) { throw 'Unexpected target depth/category' }
    $ancestor = $resolved
    while ($ancestor.Length -gt $cleanupRoot.Length) {
        $item = Get-Item -LiteralPath $ancestor -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse point in target ancestors' }
        $ancestor = [System.IO.Path]::GetDirectoryName($ancestor)
    }
    # Check current contents too: an old inventory must not delete a newly added APK/key/model/journal.
    $content = @(Get-ChildItem -LiteralPath ('\\?\' + $resolved) -Recurse -Force -ErrorAction Stop)
    if (@($content | Where-Object { ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 }).Count -gt 0) { throw 'Reparse point inside target' }
    $files = @($content | Where-Object { -not $_.PSIsContainer })
    if (@($files | Where-Object { $_.Extension.ToLowerInvariant() -in @('.apk','.jks','.keystore','.tflite','.onnx','.jsonl') }).Count -gt 0) { throw 'Protected extension inside target' }
    $size = ($files | Measure-Object -Property Length -Sum).Sum
    if ($files.Count -ne $target.files -or $size -ne $target.bytes) { throw 'Inventory changed; no deletion' }
}
if ($Action -eq 'Check') {
    Write-Output ('CHECK_OK: targets=' + $manifestData.targets.Count + '; protected=' + $manifestData.protected.Count + '; deleted=0; device_commands=0')
    exit 0
}
$results = [System.Collections.Generic.List[object]]::new()
$started = [DateTime]::UtcNow.ToString('o')
$before = (Get-PSDrive C).Free
function Save-Checkpoint([string]$State) {
    $data = [ordered]@{ started_utc=$started; updated_utc=[DateTime]::UtcNow.ToString('o'); state=$State; free_before_bytes=$before; free_now_bytes=(Get-PSDrive C).Free; results=@($results.ToArray()); device_commands=0 }
    [System.IO.File]::WriteAllText($receiptPath, ($data | ConvertTo-Json -Depth 8), $utf8)
}
Save-Checkpoint 'in_progress'
foreach ($target in $manifestData.targets) {
    $result = [ordered]@{ path=$target.path; planned_bytes=$target.bytes; planned_files=$target.files; status='unknown' }
    try {
        Remove-Item -LiteralPath ('\\?\' + [System.IO.Path]::GetFullPath($target.path)) -Recurse -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $target.path) { throw 'Target remains' }
        $result.status = 'deleted'
    } catch {
        $result.status = 'failed_or_partial'
        $result.error = $_.Exception.Message
    }
    $results.Add([pscustomobject]$result)
    if ($results.Count % 25 -eq 0) { Save-Checkpoint 'in_progress' }
}
Save-Checkpoint 'deletion_finished_pending_preservation_check'
foreach ($keep in $manifestData.protected) {
    if ((Get-FileHash -LiteralPath $keep.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $keep.sha256) { throw 'Post-cleanup preservation check failed; inspect receipt' }
}
Save-Checkpoint 'finished_preservation_verified'
Write-Output ('Deleted=' + @($results | Where-Object status -eq 'deleted').Count + '; failed_or_partial=' + @($results | Where-Object status -ne 'deleted').Count)
