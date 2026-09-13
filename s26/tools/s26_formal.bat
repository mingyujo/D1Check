@echo off
REM ============================================================
REM  S26 - formal measurement, thread-scaling sweep
REM
REM  Sized for ONE battery window (SOC 90 -> 30). If the gate
REM  stops it on low battery, charge, unplug, and run this again
REM  with no argument: it resumes from the same manifest.
REM
REM  Design: CPU 1/2/4 threads + GPU, duty 100, 300 s, 3 repeats
REM          = 4 conditions x 3 = 12 runs
REM
REM  Usage: s26_formal.bat dry     print the plan only
REM         s26_formal.bat         start, or resume if interrupted
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
  popd & pause & exit /b 1
)

set "SER="
for /f "usebackq skip=1 tokens=1,2" %%a in (`"%ADB%" devices`) do (
  if "%%b"=="device" (
    echo %%a | findstr ":" >nul && set "SER=%%a"
  )
)
if not defined SER (
  echo [X] No wireless device. Run s26_wifi.bat first.
  popd & pause & exit /b 1
)

set "OUT=results\S26_formal_threads"
set "RESUME="
if exist "%OUT%\experiment_manifest.json" set "RESUME=--resume"

echo Serial : !SER!
echo Output : %OUT%
if defined RESUME (echo Mode   : RESUME) else (echo Mode   : NEW)
echo.

%PY% "%~dp0s26_build_check.py" "%ADB%" "!SER!"
if "%errorlevel%"=="2" (
  echo.
  echo Aborting - rebuild first with s26_build.bat
  popd & pause & exit /b 1
)

echo.
echo ===== Battery =====
for /f "usebackq tokens=1,2,3" %%a in (`"%ADB%" -s !SER! shell dumpsys battery`) do (
  if "%%a"=="level:" echo   level  %%b %%
  if "%%a"=="status:" echo   status %%b   ^(3 = discharging^)
)
echo   Formal energy eligibility needs SOC 30-90.
echo   12 runs draw roughly 2,400 mAh of a 4,315 mAh battery.
echo.

%PY% tools\d1_experiment_orchestrator.py ^
  --serial !SER! ^
  --mode formal ^
  --resources CPU GPU ^
  --cpu-thread-levels 1 2 4 ^
  --duty-cycles 100 ^
  --duration 300 ^
  --warmup 20 ^
  --repeat 3 ^
  --seed 20260913 ^
  --start-policy stable ^
  --cooling-policy stable ^
  --output-dir %OUT% %RESUME%

set "RC=%errorlevel%"
echo.
echo Orchestrator exit code: %RC%
echo Runs completed:
dir /b /ad "%OUT%\runs" 2>nul | find /c /v ""
echo.
if not "%RC%"=="0" (
  echo If it stopped on battery level, charge the phone, unplug it,
  echo wait until it is cool, then run this script again - it resumes.
)
popd
pause
