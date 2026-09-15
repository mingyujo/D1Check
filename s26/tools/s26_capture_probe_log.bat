@echo off
REM ============================================================
REM  S26 - Capture NNAPI probe log from logcat  (READ ONLY)
REM  Run this AFTER pressing "Probe NNAPI devices" in the
REM  Benchmark Runner app on the phone.
REM  Usage: s26_capture_probe_log.bat   [serial]
REM  Output: ..\device\09_nnapi_probe.txt
REM ============================================================
setlocal enabledelayedexpansion

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

set "OUT=%~dp0..\device"
if not exist "%OUT%" mkdir "%OUT%"
set "F=%OUT%\09_nnapi_probe.txt"

set "SER="
if not "%~1"=="" set "SER=-s %~1"

echo Capturing D1NPU log lines...

echo ===== 1. device =====> "%F%"
"%ADB%" %SER% shell getprop ro.product.model >> "%F%" 2>&1
"%ADB%" %SER% shell getprop ro.build.version.sdk >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 2. D1NPU probe output =====>> "%F%"
"%ADB%" %SER% logcat -d -s D1NPU:V >> "%F%" 2>&1

echo. >> "%F%"
echo ===== 3. NNAPI related runtime lines (context) =====>> "%F%"
"%ADB%" %SER% logcat -d -b main -t 2000 >> "%F%".tmp 2>&1
findstr /I /C:"neuralnetworks" /C:"NNAPI" /C:"nnapi-reference" "%F%".tmp >> "%F%" 2>&1
del "%F%".tmp >nul 2>&1

echo.
echo ============================================
type "%F%"
echo ============================================
echo.

findstr /C:"nnapi_device" "%F%" >nul 2>&1
if errorlevel 1 (
  echo [!] No "nnapi_device" line found.
  echo [!] Press "Probe NNAPI devices" in the Benchmark Runner app,
  echo [!] then run this script again WITHOUT rebooting the phone.
) else (
  echo [OK] nnapi_device lines captured.
)

echo.
echo Written to: %F%
echo Tell Claude it is finished.
pause
