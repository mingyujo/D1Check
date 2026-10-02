@echo off
REM ============================================================
REM  D1Check - S26 device profile collector  (READ ONLY)
REM  Nothing is installed or changed on the phone.
REM
REM  Usage:  s26_collect.bat            (one device connected)
REM          s26_collect.bat <serial>   (if several are listed)
REM  Output: ..\device\*.txt
REM ============================================================
setlocal

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

set "OUT=%~dp0..\device"
if not exist "%OUT%" mkdir "%OUT%"

set "SER="
if not "%~1"=="" set "SER=-s %~1"

echo.
echo ============================================
echo   S26 device profile collector
echo   adb    : %ADB%
echo   output : %OUT%
echo ============================================
echo.

echo [0/8] adb devices
"%ADB%" devices -l > "%OUT%\00_devices.txt" 2>&1
type "%OUT%\00_devices.txt"
echo.

"%ADB%" %SER% shell echo ok > "%OUT%\_probe.txt" 2>&1
find "ok" "%OUT%\_probe.txt" >nul 2>&1
if errorlevel 1 goto :cannot_reach
del "%OUT%\_probe.txt" >nul 2>&1

echo [1/8] getprop full dump
"%ADB%" %SER% shell getprop > "%OUT%\01_getprop_full.txt" 2>&1

echo [2/8] key identifiers
echo === key identifiers ===> "%OUT%\02_getprop_key.txt"
call :prop ro.product.model
call :prop ro.product.device
call :prop ro.product.name
call :prop ro.product.manufacturer
call :prop ro.build.version.release
call :prop ro.build.version.sdk
call :prop ro.build.fingerprint
call :prop ro.board.platform
call :prop ro.hardware
call :prop ro.soc.manufacturer
call :prop ro.soc.model
call :prop ro.product.cpu.abi
type "%OUT%\02_getprop_key.txt"
echo.

echo [3/8] dumpsys thermalservice - sample 1 of 3
"%ADB%" %SER% shell dumpsys thermalservice > "%OUT%\03_thermalservice_1.txt" 2>&1
ping -n 6 127.0.0.1 >nul
echo [3/8] dumpsys thermalservice - sample 2 of 3
"%ADB%" %SER% shell dumpsys thermalservice > "%OUT%\03_thermalservice_2.txt" 2>&1
ping -n 6 127.0.0.1 >nul
echo [3/8] dumpsys thermalservice - sample 3 of 3
"%ADB%" %SER% shell dumpsys thermalservice > "%OUT%\03_thermalservice_3.txt" 2>&1

echo [4/8] thermal zones
"%ADB%" %SER% shell "for f in /sys/class/thermal/thermal_zone*; do echo $f $(cat $f/type 2>/dev/null) $(cat $f/temp 2>/dev/null); done" > "%OUT%\04_thermal_zones.txt" 2>&1

echo [5/8] dumpsys battery
"%ADB%" %SER% shell dumpsys battery > "%OUT%\05_battery.txt" 2>&1

echo [6/8] battery sysfs - 10 samples, 1s apart
echo === power_supply dirs ===> "%OUT%\06_battery_sysfs.txt"
"%ADB%" %SER% shell "ls -1 /sys/class/power_supply/ 2>/dev/null" >> "%OUT%\06_battery_sysfs.txt" 2>&1
echo. >> "%OUT%\06_battery_sysfs.txt"
echo === n current_now voltage_now charge_counter capacity ===>> "%OUT%\06_battery_sysfs.txt"
for /l %%I in (1,1,10) do call :sample %%I

echo [7/8] packages and NNAPI library
echo === packages matching d1check ===> "%OUT%\07_packages_nnapi.txt"
"%ADB%" %SER% shell "pm list packages 2>/dev/null | grep -i d1check" >> "%OUT%\07_packages_nnapi.txt" 2>&1
echo. >> "%OUT%\07_packages_nnapi.txt"
echo === libneuralnetworks.so ===>> "%OUT%\07_packages_nnapi.txt"
"%ADB%" %SER% shell "ls -l /system/lib64/libneuralnetworks.so /vendor/lib64/libneuralnetworks.so 2>&1" >> "%OUT%\07_packages_nnapi.txt" 2>&1
type "%OUT%\07_packages_nnapi.txt"
echo.

echo [8/8] cpu / memory / power
echo === dumpsys power thermal lines ===> "%OUT%\08_misc.txt"
"%ADB%" %SER% shell "dumpsys power 2>/dev/null | grep -i -E 'thermal|headroom'" >> "%OUT%\08_misc.txt" 2>&1
echo. >> "%OUT%\08_misc.txt"
echo === cpu max freq per core ===>> "%OUT%\08_misc.txt"
"%ADB%" %SER% shell "for c in /sys/devices/system/cpu/cpu[0-9]*; do echo $c $(cat $c/cpufreq/cpuinfo_max_freq 2>/dev/null); done" >> "%OUT%\08_misc.txt" 2>&1
echo. >> "%OUT%\08_misc.txt"
echo === cpuinfo ===>> "%OUT%\08_misc.txt"
"%ADB%" %SER% shell cat /proc/cpuinfo >> "%OUT%\08_misc.txt" 2>&1
echo. >> "%OUT%\08_misc.txt"
echo === meminfo head ===>> "%OUT%\08_misc.txt"
"%ADB%" %SER% shell "head -5 /proc/meminfo" >> "%OUT%\08_misc.txt" 2>&1
echo. >> "%OUT%\08_misc.txt"
echo === uptime ===>> "%OUT%\08_misc.txt"
"%ADB%" %SER% shell cat /proc/uptime >> "%OUT%\08_misc.txt" 2>&1

echo.
echo ============================================
echo   DONE.  Files written to:
echo   %OUT%
echo ============================================
dir /b "%OUT%"
echo.
echo Tell Claude it is finished.
pause
exit /b 0

:prop
"%ADB%" %SER% shell getprop %1 > "%OUT%\_p.txt" 2>&1
set "PV="
set /p PV=< "%OUT%\_p.txt"
echo %1=%PV%>> "%OUT%\02_getprop_key.txt"
del "%OUT%\_p.txt" >nul 2>&1
exit /b 0

:sample
"%ADB%" %SER% shell "echo %1 $(cat /sys/class/power_supply/battery/current_now 2>/dev/null) $(cat /sys/class/power_supply/battery/voltage_now 2>/dev/null) $(cat /sys/class/power_supply/battery/charge_counter 2>/dev/null) $(cat /sys/class/power_supply/battery/capacity 2>/dev/null)" >> "%OUT%\06_battery_sysfs.txt" 2>&1
ping -n 2 127.0.0.1 >nul
exit /b 0

:cannot_reach
echo.
echo *** ERROR: cannot reach the device. ***
echo.
echo   1. Phone: Settings - Developer options - USB debugging must be ON
echo   2. When the "Allow USB debugging?" popup appears on the phone,
echo      tick "Always allow" and press Allow.
echo   3. If more than one device is listed above, re-run with the serial:
echo         s26_collect.bat SERIAL
echo   4. For wireless adb: run "adb connect IP:PORT" first.
echo.
pause
exit /b 1
