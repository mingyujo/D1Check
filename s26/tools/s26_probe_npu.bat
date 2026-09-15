@echo off
REM ============================================================
REM  S26 - NPU / NNAPI runtime probe   (READ ONLY, ~15 seconds)
REM  Usage: s26_probe_npu.bat   [serial]
REM  Output: ..\device\10_npu_runtime.txt
REM ============================================================
setlocal

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

set "OUT=%~dp0..\device"
if not exist "%OUT%" mkdir "%OUT%"
set "F=%OUT%\10_npu_runtime.txt"

set "SER="
if not "%~1"=="" set "SER=-s %~1"

echo Probing NPU / NNAPI runtime...

echo ===== 1. APEX modules containing "neural" =====> "%F%"
"%ADB%" %SER% shell "ls /apex 2>/dev/null | grep -i -E 'neural|nnapi'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 2. libneuralnetworks.so search =====>> "%F%"
"%ADB%" %SER% shell "ls -l /apex/com.android.neuralnetworks/lib64/libneuralnetworks.so 2>&1" >> "%F%" 2>&1
"%ADB%" %SER% shell "find /apex /system /vendor /system_ext /product -name 'libneuralnetworks*.so' 2>/dev/null" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 3. public.libraries.txt entries =====>> "%F%"
"%ADB%" %SER% shell "cat /system/etc/public.libraries.txt /vendor/etc/public.libraries*.txt /system_ext/etc/public.libraries*.txt /product/etc/public.libraries*.txt 2>/dev/null | sort -u" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 4. vendor libs matching enn / npu / neural / litert =====>> "%F%"
"%ADB%" %SER% shell "ls /vendor/lib64 2>/dev/null | grep -i -E 'enn|npu|neural|litert|gpu_delegate'" >> "%F%" 2>&1
"%ADB%" %SER% shell "ls /system/lib64 2>/dev/null | grep -i -E 'enn|npu|neural|litert'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 5. NPU device nodes =====>> "%F%"
"%ADB%" %SER% shell "ls -l /dev/ 2>/dev/null | grep -i -E 'npu|enn|dsp'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 6. NPU related props =====>> "%F%"
"%ADB%" %SER% shell "getprop | grep -i -E 'npu|neural|enn|nnapi'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 7. HAL services matching neural / nn =====>> "%F%"
"%ADB%" %SER% shell "lshal 2>/dev/null | grep -i -E 'neural|nnapi'" >> "%F%" 2>&1
"%ADB%" %SER% shell "service list 2>/dev/null | grep -i -E 'neural|npu'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 8. Play / on-device AI packages =====>> "%F%"
"%ADB%" %SER% shell "pm list packages 2>/dev/null | grep -i -E 'ondevice|aicore|edge|npu|gms'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 9. battery current sanity (still plugged) =====>> "%F%"
"%ADB%" %SER% shell "dumpsys battery | grep -i -E 'current|charge counter|status|USB powered|voltage|level'" >> "%F%" 2>&1

echo.
echo ============================================
type "%F%"
echo ============================================
echo.
echo Written to: %F%
echo Tell Claude it is finished.
pause
