@echo off
REM ============================================================
REM  S26 - CPU-only pilot, 60 s DURATION
REM  GPU is skipped entirely, and so is the CPU/GPU output
REM  equivalence preflight, because the GPU delegate is blocked
REM  by LiteRT's built-in device compatibility list on this SoC.
REM  Usage: s26_pilot_cpu.bat dry   -> print the plan only
REM         s26_pilot_cpu.bat       -> run it
REM ============================================================
setlocal enabledelayedexpansion

set "DRY="
if /I "%~1"=="dry" set "DRY=--dry-run"

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

set "ROOT=%~dp0..\.."
pushd "%ROOT%"

set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY ( where py >nul 2>&1 && set "PY=py -3" )
if not defined PY (
  echo [X] Python not found.
  popd
  pause
  exit /b 1
)

set "SER="
set "SER_ANY="
REM  A wireless serial is either ip:port or an mDNS transport name that
REM  starts with "adb-". Prefer wireless; fall back to whatever single
REM  device is attached.
for /f "usebackq skip=1 tokens=1,2" %%a in (`"%ADB%" devices`) do (
  if "%%b"=="device" (
    set "SER_ANY=%%a"
    echo %%a | findstr ":" >nul && set "SER=%%a"
    echo %%a | findstr /B "adb-" >nul && set "SER=%%a"
  )
)
if not defined SER set "SER=%SER_ANY%"
if not defined SER (
  echo [X] No wireless device. Run s26_wifi.bat first, then unplug USB.
  "%ADB%" devices
  popd
  pause
  exit /b 1
)

echo Serial    : !SER!
echo Resources : CPU only, 4 threads, 60 s DURATION
echo Preflight : off
if defined DRY echo Mode      : DRY RUN
echo.

%PY% tools\d1_experiment_orchestrator.py ^
  --serial !SER! ^
  --mode pilot ^
  --resources CPU ^
  --cpu-threads 4 ^
  --duration 60 ^
  --warmup 20 ^
  --repeat 1 ^
  --seed 20260913 ^
  --accuracy-preflight off ^
  --output-dir results\S26_cpu_60s %DRY%

echo.
echo Orchestrator exit code: %errorlevel%
echo Result: results\S26_cpu_60s\runs\^<run_id^>\merged\summary.json
popd
pause
