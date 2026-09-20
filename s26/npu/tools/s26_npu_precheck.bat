@echo off
REM ============================================================
REM  S26 - NPU access pre-check   (READ ONLY on device, ~40 seconds)
REM  Gate G0 of NPU_ACCESS_PLAN_0916.md
REM  Usage: s26_npu_precheck.bat   [serial]
REM  Output: ..\device\11_npu_precheck.txt
REM          ..\device\12_enn_symbols.txt   (+ .json)
REM          ..\device\13_nnapi_probe_logcat.txt
REM          ..\device\libenn_public_api_cpp.so   (pulled copy, do NOT commit)
REM  USB or wireless adb both fine (no safety gate involved).
REM ============================================================
setlocal

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

set "OUT=%~dp0..\device"
if not exist "%OUT%" mkdir "%OUT%"
set "F=%OUT%\11_npu_precheck.txt"

set "SER="
if not "%~1"=="" set "SER=-s %~1"

echo Pre-checking NPU access paths on S26...
echo (Before running: open benchmark-runner and press "Probe NNAPI devices" once,
echo  so that section 11 can capture the D1NPU logcat lines.)
echo.

echo ===== 0. adb devices =====> "%F%"
"%ADB%" devices >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 1. build / OS identity =====>> "%F%"
"%ADB%" %SER% shell "getprop ro.product.model; getprop ro.soc.model; getprop ro.hardware; getprop ro.build.version.release; getprop ro.build.version.sdk; getprop ro.build.version.oneui; getprop ro.build.display.id; getprop ro.build.fingerprint" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 2. android.hardware.npu feature (API 37 / Android 17 only) =====>> "%F%"
"%ADB%" %SER% shell "pm list features 2>/dev/null | grep -i -E 'npu|neural'" >> "%F%" 2>&1
"%ADB%" %SER% shell "echo '(empty above = feature not declared on this build)'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 3. AIDL services (service list) matching enn / neural / npu =====>> "%F%"
"%ADB%" %SER% shell "service list 2>/dev/null | grep -i -E 'enn|neural|npumanager|\.npu'" >> "%F%" 2>&1
echo --- HIDL (lshal) --->> "%F%"
"%ADB%" %SER% shell "lshal 2>/dev/null | grep -i -E 'enn|neural'" >> "%F%" 2>&1
echo --- init services --->> "%F%"
"%ADB%" %SER% shell "getprop | grep -i -E 'init.svc.*(enn|npu|neural)'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 4. ENN public libraries (app-loadable) =====>> "%F%"
"%ADB%" %SER% shell "ls -l /vendor/lib64/libenn_public_api_cpp.so /vendor/lib64/libenn_public_api_cpp_lib.so /vendor/lib64/libenn_user.samsung_slsi.so /vendor/lib64/libenn_user_lib.so 2>&1" >> "%F%" 2>&1
echo --- which public.libraries file lists them --->> "%F%"
"%ADB%" %SER% shell "grep -H -i enn /system/etc/public.libraries.txt /vendor/etc/public.libraries*.txt /system_ext/etc/public.libraries*.txt /product/etc/public.libraries*.txt 2>/dev/null" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 5. all enn / npu libs in vendor + system (reference) =====>> "%F%"
"%ADB%" %SER% shell "ls -l /vendor/lib64 2>/dev/null | grep -i -E 'enn|npu|litecore|graphgen' | grep -v -i input" >> "%F%" 2>&1
"%ADB%" %SER% shell "ls -l /system/lib64 2>/dev/null | grep -i -E 'enn|npu|litecore|graphgen|neural' | grep -v -i input" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 6. any LiteRT NPU libs shipped by the platform? (expect none) =====>> "%F%"
"%ADB%" %SER% shell "find /system /vendor /product /system_ext /apex -name 'libLiteRt*' 2>/dev/null" >> "%F%" 2>&1
"%ADB%" %SER% shell "echo '(empty above = app must bundle libLiteRtDispatch_Samsung.so itself)'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 7. ENN / NPU related packages and versions =====>> "%F%"
"%ADB%" %SER% shell "pm list packages 2>/dev/null | grep -i -E 'litert|ai\.edge|aicore|npu|enn|ondevice'" >> "%F%" 2>&1
"%ADB%" %SER% shell "dumpsys package com.google.android.aicore 2>/dev/null | grep -m2 -E 'versionName|versionCode'" >> "%F%" 2>&1
"%ADB%" %SER% shell "dumpsys package com.samsung.android.aicore 2>/dev/null | grep -m2 -E 'versionName|versionCode'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 8. ENN / NPU related props =====>> "%F%"
"%ADB%" %SER% shell "getprop | grep -i -E 'enn|npu|litert|nnapi|litecore' | grep -v -i -E 'input|hnpu'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 9. vendor test binaries (EnnTest etc.) =====>> "%F%"
"%ADB%" %SER% shell "ls /vendor/bin 2>/dev/null | grep -i -E 'enn|npu'" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 10. thermal sensors mentioning NPU (expect none) =====>> "%F%"
"%ADB%" %SER% shell "dumpsys thermalservice 2>/dev/null | grep -i npu" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 11. NNAPI probe result from benchmark-runner (D1NPU logcat) =====>> "%F%"
"%ADB%" %SER% logcat -d 2>nul | findstr /I "D1NPU" > "%OUT%\13_nnapi_probe_logcat.txt"
for %%A in ("%OUT%\13_nnapi_probe_logcat.txt") do echo D1NPU logcat bytes captured: %%~zA  - see 13_nnapi_probe_logcat.txt. 0 bytes = press the Probe button first, then rerun >> "%F%"

echo. >> "%F%"
echo ===== 12. pull ENN public libs and check exported ENN symbols (dependency tree) =====>> "%F%"
"%ADB%" %SER% pull /vendor/lib64/libenn_public_api_cpp.so "%OUT%\libenn_public_api_cpp.so" >> "%F%" 2>&1
"%ADB%" %SER% pull /vendor/lib64/libenn_user.samsung_slsi.so "%OUT%\libenn_user.samsung_slsi.so" >> "%F%" 2>&1

set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY ( where py >nul 2>&1 && set "PY=py -3" )
if defined PY (
  if exist "%OUT%\libenn_public_api_cpp.so" (
    %PY% "%~dp0s26_npu_symbols.py" "%OUT%\libenn_public_api_cpp.so" "%OUT%\libenn_user.samsung_slsi.so" --json "%OUT%\12_enn_symbols.json" > "%OUT%\12_enn_symbols.txt" 2>&1
    type "%OUT%\12_enn_symbols.txt" >> "%F%"
  ) else (
    echo [X] pull failed - symbol check skipped >> "%F%"
  )
) else (
  echo [X] python not found - run s26_npu_symbols.py manually >> "%F%"
)

echo.
echo ============================================
type "%F%"
echo ============================================
echo.
echo Written to: %F%
echo NOTE: libenn_public_api_cpp.so in ..\device is a pulled vendor binary.
echo       Keep it local; do not commit it to GitHub.
echo Tell Claude it is finished.
pause
