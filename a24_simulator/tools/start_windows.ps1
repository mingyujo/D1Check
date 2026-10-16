param([string]$Python='', [string]$Node='node.exe', [int]$Port=8766)
$ErrorActionPreference='Stop'
$a24Root=Split-Path -Parent $PSScriptRoot
if (!$Python) { $Python=Join-Path $a24Root '.venv/Scripts/python.exe' }
$a24Existing=Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($a24Existing) {
 $a24Owner=Join-Path $a24Root ('runtime/SERVER_OWNER_'+$a24Existing.OwningProcess+'.json')
 if (!(Test-Path -LiteralPath $a24Owner)) { throw 'Port occupied by a different service. No process was stopped.' }
 Write-Output ('Already running: http://127.0.0.1:'+$Port+'/'); exit 0
}
$a24GuardText=& $Python -B (Join-Path $PSScriptRoot 'guard.py')
if ($LASTEXITCODE -ne 0 -or !($a24GuardText | ConvertFrom-Json).ok) { throw 'Preflight guard failed; no worker was started' }
& $Python -B (Join-Path $PSScriptRoot 'bootstrap.py')
if ($LASTEXITCODE -ne 0) { throw 'Data SHA verification failed' }
& $Python -B (Join-Path $PSScriptRoot 'configure_v2.py')
if ($LASTEXITCODE -ne 0) { throw 'Local registration differs' }
$env:A24_PYTHON=$Python; $env:PORT=[string]$Port
Start-Process -FilePath $Node -ArgumentList @((Join-Path $a24Root 'src/server_v2.cjs')) -WorkingDirectory $a24Root -WindowStyle Hidden
Write-Output ('http://127.0.0.1:'+$Port+'/')
