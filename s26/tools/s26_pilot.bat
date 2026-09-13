@echo off
REM ============================================================
REM  S26 - Automated pilot via the experiment orchestrator
REM  No phone UI taps: it drives D1Check and the runner itself.
REM  Picks an unused output folder, and refuses to run against a
REM  stale APK (source patched but app not reinstalled).
REM  Usage: s26_pilot.bat dry     -> print the plan, touch nothing
REM         s26_pilot.bat         -> run CPU(4 threads) + GPU, 60 s each
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
for /f "usebackq skip=1 tokens=1,2" %%a in (`"%ADB%" devices`) do (
  if "%%b"=="device" (
    echo %%a | findstr ":" >nul && set "SER=%%a"
  )
)
if not defined SER (
  echo [X] No wireless device. Run s26_wifi.bat first, then unplug USB.
  "%ADB%" devices
  popd
  pause
  exit /b 1
)

echo Serial : !SER!

REM ---------- is the app on the phone actually built from these sources ----------
echo.
echo ===== Build freshness =====
%PY% "%~dp0s26_build_check.py" "%ADB%" "!SER!"
set "FRESH=%errorlevel%"
if "%FRESH%"=="2" (
  echo.
  echo Aborting so you do not spend 8 minutes measuring the old app.
  popd
  pause
  exit /b 1
)

REM ---------- pick an unused output folder ----------
set /a N=1
:slot
set "OUT=results\S26_pilot_60s_%N%"
if exist "%OUT%" (
  set /a N+=1
  goto :slot
)
echo.
echo Output : %OUT%
if defined DRY echo Mode   : DRY RUN - nothing is executed on the phone
echo.

%PY% tools\d1_experiment_orchestrator.py ^
  --serial !SER! ^
  --mode pilot ^
  --resources CPU GPU ^
  --cpu-threads 4 ^
  --duration 60 ^
  --warmup 20 ^
  --repeat 1 ^
  --seed 20260913 ^
  --output-dir %OUT% %DRY%

echo.
echo Orchestrator exit code: %errorlevel%
echo Result: %OUT%\runs\^<run_id^>\merged\summary.json
popd
pause
