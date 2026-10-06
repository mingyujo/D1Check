param(
    [ValidateSet('Check','Smoke','Run','Status')][string]$Action = 'Check',
    [string]$Output,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$repoPath = Split-Path $PSScriptRoot -Parent
$previousMkl = $env:MKL_THREADING_LAYER
$previousEncoding = $env:PYTHONIOENCODING
Push-Location -LiteralPath $repoPath
try {
    $env:MKL_THREADING_LAYER = 'SEQUENTIAL'
    $env:PYTHONIOENCODING = 'utf-8'
    $arguments = @('-u','-B','-m','tools.d1_queue_ppo','--action',$Action.ToLowerInvariant())
    if ($Output) { $arguments += @('--output',$Output) }
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Queue PPO $Action exited with code $LASTEXITCODE" }
} finally {
    $env:MKL_THREADING_LAYER = $previousMkl
    $env:PYTHONIOENCODING = $previousEncoding
    Pop-Location
}
