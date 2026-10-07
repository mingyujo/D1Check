param(
  [Parameter(Mandatory=$true)][string]$Label,
  [Parameter(Mandatory=$true)][string]$OutName,
  [Parameter(Mandatory=$true)][string]$CellArgs
)
# V3 v2 (P1h 1007) copy of s26\tools\v3_1006\dryrun_v3.ps1 — changed only: host dir S26_host_v3_1007.
# V3 1006 copy of s26\tools\n4_1006\dryrun_1006r.ps1 — changed only: host dir S26_host_v3_1006.
# N4 1006r (copy of dryrun_1005e.ps1, host dir only). NIGHT 1005e (copy of the 1005n file, host dir only; 1005n was a copy of dryrun_1005.ps1, host dir only): orchestrator --dry-run for one cell. Serial comes only from $env:ANDROID_SERIAL and is scrubbed to <SERIAL> before saving.
$wd = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
$hostDir = "$wd\results\S26_host_v3_1007"
$S = $env:ANDROID_SERIAL
if (-not $S) { throw "ANDROID_SERIAL not set" }
$argList = @("-X", "utf8", "tools\d1_experiment_orchestrator.py", "--serial", $S) + ($CellArgs -split '\s+' | Where-Object { $_ -ne "" }) + @("--output-dir", "$wd\results\$OutName", "--dry-run")
Push-Location $wd
$out = & py @argList 2>&1 | ForEach-Object { "$_" }
$code = $LASTEXITCODE
Pop-Location
$scrubbed = $out | ForEach-Object { $_ -replace [regex]::Escape($S), "<SERIAL>" }
$file = "$hostDir\dryrun_${Label}_" + (Get-Date -Format "HHmmss") + ".txt"
$scrubbed | Set-Content -Encoding utf8 $file
"exit=$code file=$file lines=" + $scrubbed.Count
