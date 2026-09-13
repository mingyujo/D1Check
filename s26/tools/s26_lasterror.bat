@echo off
REM ============================================================
REM  S26 - Pull the exact failure message of the last run
REM  Usage: s26_lasterror.bat
REM  Output: ..\device\12_gpu_failure.txt
REM ============================================================
setlocal enabledelayedexpansion

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

set "ROOT=%~dp0..\.."
pushd "%ROOT%"

set "SER="
for /f "usebackq skip=1 tokens=1,2" %%a in (`"%ADB%" devices`) do (
  if "%%b"=="device" (
    echo %%a | findstr ":" >nul && set "SER=%%a"
  )
)

set "F=%~dp0..\device\12_gpu_failure.txt"

echo ===== 1. what the orchestrator produced =====> "%F%"
dir /s /b results\S26_pilot_60s >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 2. run_error lines in captured logs =====>> "%F%"
findstr /s /i /c:"run_error" /c:"delegate_init" /c:"interpreter_init" results\S26_pilot_60s\*.jsonl >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 3. orchestrator result json =====>> "%F%"
findstr /s /i /c:"error" /c:"invalid" /c:"reason" results\S26_pilot_60s\*.json >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 4. live logcat D1GPU (buffer may still hold it) =====>> "%F%"
if defined SER (
  "%ADB%" -s !SER! logcat -d -s D1GPU:I >> "%F%" 2>&1
) else (
  echo   no device connected >> "%F%"
)

echo. >> "%F%"
echo ===== 5. GPU / OpenCL libraries on the device =====>> "%F%"
if defined SER (
  "%ADB%" -s !SER! shell "ls /vendor/lib64/ 2>/dev/null | grep -i -E 'OpenCL|GLES|mali|xclipse|vulkan'" >> "%F%" 2>&1
  "%ADB%" -s !SER! shell "cat /vendor/etc/public.libraries*.txt 2>/dev/null | grep -i -E 'OpenCL|GLES'" >> "%F%" 2>&1
  "%ADB%" -s !SER! shell "dumpsys SurfaceFlinger 2>/dev/null | grep -i -E 'GLES|Vendor|Renderer' | head -5" >> "%F%" 2>&1
)

echo.
echo ============================================
type "%F%"
echo ============================================
echo.
echo Written to: %F%
popd
pause
