param([Parameter(Mandatory=$true)][string]$OneDrive, [string]$SourceCommit = "", [switch]$SkipSupp, [string]$Block1Only = "", [string]$TrefKey1 = "2026-10-15_day_b1", [string]$TrefKey2 = "2026-10-15_b2")
# M8 D-3 chain (2026-10-15 · 영훈 08:xx): P0 supplement (PERFETTO_ON_C32_r2) -> DEV block 1 -> bundle B1 -> DEV block 2 -> bundle B2. Sequential, one process, output to files only.
# Each driver run = m8_driver.ps1 (lock · console file). Bundles = m8_bundle.py --kind block (stage dir + zip under $OneDrive\sim\out_m8). No fixed idle waits (--no-fixed-idle · 영훈) · Tref keys per segment.
#   Start-Process powershell -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",<this>,"-OneDrive",<D1_ondevice>,"-SourceCommit",<sha>
# Log: results\chain_m8_1015_<MMdd_HHmmss>.txt. Stop: kill this process AND the driver (lock pid). ASCII only.
$ErrorActionPreference = "Continue"
$REPO = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_m6"
$DRV = "$REPO\s26\tools\mixreq\m8_driver.ps1"
$OUT = "$OneDrive\sim\out_m8"
$log = "$REPO\results\chain_m8_1015_" + (Get-Date -Format "MMdd_HHmmss") + ".txt"
function L($m) { "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss K") + "] $m" | Out-File -FilePath $log -Encoding UTF8 -Append }
if (-not $env:ANDROID_SERIAL) { L "ANDROID_SERIAL not set"; exit 2 }
Set-Location $REPO
L "chain start source=$SourceCommit"
# 1) P0 supplement (same Tref key as block 1 = day segment)
if (-not $SkipSupp) {
L "step 1: P0 supplement PERFETTO_ON_C32_r2"
& powershell -NoProfile -ExecutionPolicy Bypass -File $DRV -Stage p0 -PlanFile "$REPO\s26\results\m8_prep\plan_m8\p0_supp.json" -TrefKey "2026-10-15_day_b1" -NoFixedIdle
L "step 1 end rc=$LASTEXITCODE"
} else { L "step 1 skipped (done 08:34)" }
# 2) DEV block 1
L "step 2: DEV block 1 only=[$Block1Only] trefKey=$TrefKey1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $DRV -Stage dev -Block 1 -TrefKey $TrefKey1 -NoFixedIdle -GateForceAfterS 1800 -Only $Block1Only
$rc1 = $LASTEXITCODE
L "step 2 end rc=$rc1"
# 3) bundle B1 (results snapshot before block 2 starts)
L "step 3: bundle B1"
& py -X utf8 "$REPO\s26\tools\mixreq\m8_bundle.py" --kind block --block 1 --onedrive $OneDrive --stage "$OUT\m8_dev_block1_stage" --zip "$OUT\m8_dev_block1_bundle.zip" --apk-sha256 37960e25c5948f661f2f5b47a90a4356be1b3712706d34679e71a14842ced6ea --signer-sha256 6394e51f94c71bd6e9cc5d76ff66e503583c1dca7d50f7ed175dd2e444cfcd32 --source-commit $SourceCommit --fingerprint "samsung/m1sksx/m1s:17/CP2A.260605.016/S942NKSS4BZIG_OKR4BZIG:user/release-keys" 2>&1 | Out-File -FilePath "$OUT\m8_dev_block1_bundle_stdout.txt" -Encoding UTF8
L "step 3 end rc=$LASTEXITCODE"
# 4) DEV block 2 (영훈: no 20:00 wait · temperature gate only · new Tref key)
L "step 4: DEV block 2"
& powershell -NoProfile -ExecutionPolicy Bypass -File $DRV -Stage dev -Block 2 -TrefKey $TrefKey2 -NoFixedIdle -GateForceAfterS 1800
$rc2 = $LASTEXITCODE
L "step 4 end rc=$rc2"
# 5) bundle B2
L "step 5: bundle B2"
& py -X utf8 "$REPO\s26\tools\mixreq\m8_bundle.py" --kind block --block 2 --onedrive $OneDrive --stage "$OUT\m8_dev_block2_stage" --zip "$OUT\m8_dev_block2_bundle.zip" --apk-sha256 37960e25c5948f661f2f5b47a90a4356be1b3712706d34679e71a14842ced6ea --signer-sha256 6394e51f94c71bd6e9cc5d76ff66e503583c1dca7d50f7ed175dd2e444cfcd32 --source-commit $SourceCommit --fingerprint "samsung/m1sksx/m1s:17/CP2A.260605.016/S942NKSS4BZIG_OKR4BZIG:user/release-keys" 2>&1 | Out-File -FilePath "$OUT\m8_dev_block2_bundle_stdout.txt" -Encoding UTF8
L "step 5 end rc=$LASTEXITCODE"
L "chain end rc1=$rc1 rc2=$rc2"
exit 0
