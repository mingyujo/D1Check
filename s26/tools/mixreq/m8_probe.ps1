param([Parameter(Mandatory=$true)][string]$OutDir, [string]$Tag = "probe")
# M8 (2026-10-14) instrumentation probe — READ-ONLY adb shell reads for the P0 계측 확인 (session_m8.json optional_probes · 프롬프트 B-3 3 · D-1 3). ASCII only.
# Each item is recorded as supported / unsupported / unknown with the raw output; nothing is changed on the phone. Serial from $env:ANDROID_SERIAL only (masked in files).
$ErrorActionPreference = "Continue"
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$DEVSER = $env:ANDROID_SERIAL
if (-not $DEVSER) { Write-Output "ANDROID_SERIAL empty"; exit 2 }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$log = Join-Path $OutDir ("probe_" + $Tag + "_" + $ts + ".txt")
function Rec([string]$name, [string]$cmd) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $out = @(& $adb -s $DEVSER shell $cmd 2>&1 | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] })
  $rc = $LASTEXITCODE
  $sw.Stop()
  $text = ($out -join "`n")
  if ($DEVSER) { $text = $text -replace [regex]::Escape($DEVSER), "<SERIAL>" }
  Add-Content -Path $log -Encoding UTF8 -Value ("=== " + $name + " | cmd: " + $cmd + " | rc=" + $rc + " | ms=" + $sw.ElapsedMilliseconds)
  Add-Content -Path $log -Encoding UTF8 -Value $text
}
Rec "cpu_scaling_cur_freq" 'for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq; do echo $c $(cat $c 2>&1); done'
Rec "cpu_policy_cur_freq" 'for c in /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq; do echo $c $(cat $c 2>&1); done'
Rec "cpu_online" 'cat /sys/devices/system/cpu/online 2>&1'
Rec "gpu_freq_candidates" 'for p in /sys/class/kgsl/kgsl-3d0/gpuclk /sys/kernel/gpu/gpu_clock /sys/devices/platform/*.mali/clock /sys/devices/platform/*mali*/cur_freq /sys/class/misc/mali0/device/clock /sys/kernel/debug/mali/clock /sys/devices/platform/*.g3d/clock; do echo $p $(cat $p 2>&1 | head -c 200); done'
Rec "gpu_devfreq" 'for d in /sys/class/devfreq/*; do echo $d $(cat $d/cur_freq 2>&1); done'
Rec "npu_candidates" 'for p in /sys/class/npu/npu0/* /sys/devices/platform/*npu*/clock /sys/devices/platform/*.npu/* /sys/class/dsp/*; do echo $p $(cat $p 2>&1 | head -c 120); done 2>&1 | head -60'
Rec "thermal_zones" 'for z in /sys/class/thermal/thermal_zone*; do echo $z $(cat $z/type 2>&1) $(cat $z/temp 2>&1); done 2>&1 | head -40'
Rec "thermalservice_hal" 'dumpsys thermalservice | sed -n ''/Current temperatures from HAL/,/Current cooling devices/p'''
Rec "thermal_headroom_dumpsys" 'dumpsys thermalservice | grep -i -A3 headroom'
Rec "perfetto_version" 'perfetto --version 2>&1'
Rec "perfetto_traced" 'ps -A 2>&1 | grep -E ''traced|perfetto'' '
Rec "perfetto_power_ds" 'perfetto --query 2>&1 | grep -i -A2 ''android.power'' | head -20'
Rec "battery_dumpsys" 'dumpsys battery'
Rec "power_supply_sysfs" 'ls /sys/class/power_supply/ 2>&1; cat /sys/class/power_supply/battery/current_now 2>&1; cat /sys/class/power_supply/battery/voltage_now 2>&1'
Rec "top_threads_runner" 'top -H -n 1 -b 2>&1 | grep -i requestrunner | head -20'
Rec "fingerprint" 'getprop ro.build.fingerprint'
Write-Output ("probe written: " + $log)
