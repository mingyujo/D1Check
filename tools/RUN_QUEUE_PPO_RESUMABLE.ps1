param(
    [ValidateSet('Check','Run','Resume','Status','Smoke')][string]$Action = 'Check',
    [string]$Output,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$priorMkl = $env:MKL_THREADING_LAYER
$priorEncoding = $env:PYTHONIOENCODING
Push-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
try {
    $env:MKL_THREADING_LAYER = 'SEQUENTIAL'
    $env:PYTHONIOENCODING = 'utf-8'
    $arguments = @('-u','-B','-m','tools.d1_queue_ppo_resume','--action',$Action.ToLowerInvariant())
    if ($Output) { $arguments += @('--output',$Output) }
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Queue PPO $Action failed: exit $LASTEXITCODE" }
} finally {
    $env:MKL_THREADING_LAYER = $priorMkl
    $env:PYTHONIOENCODING = $priorEncoding
    Pop-Location
}
