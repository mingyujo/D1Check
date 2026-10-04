# Night 1004: wait for the EffB2 block driver (pid given) to exit, then run stage 4 G50P via run_cell_1004.ps1 (same detached process).
param([Parameter(Mandatory=$true)][int]$DriverPid)
$H = "C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_night_1004_host"
while (Get-Process -Id $DriverPid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 10 }
$common = "--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --logger-keep-files-open --analyze-timeout-seconds 600 --cooling-min-seconds 600 --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261004 --accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3"
$cell = "--npu-chain tools\chains\g50_probe_gpu_v1.json --duration 840 --npu-max-inference-spans 400000 $common"
& "$H\run_cell_1004.ps1" -Tag G50P -Label 04_G50P -OutName S26_G50P_1004 -CellArgs $cell -ChainSha 63a0872c8f77005a8985363b427f2d2c5b4a2cdf71f07f272bc32a536c6c3527 -MinSoc 41 -Hours 0.5
