@echo off
REM ============================================================
REM  S26 - rehearse --resume before betting a long night on it
REM
REM  Runs a deliberately small formal-shaped experiment. Stop it
REM  yourself with Ctrl+C partway through, then run this again:
REM  it detects the existing manifest and continues where it
REM  stopped instead of starting over.
REM
REM  Usage: s26_resume_test.bat          start (or continue)
REM         s26_resume_test.bat fresh    delete and start over
REM ============================================================
setlocal enabledelayedexpansion

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
  echo [X] No wireless device. Run s26_wifi.bat first.
  popd & pause & exit /b 1
)

set "OUT=results\S26_resume_test"

if /I "%~1"=="fresh" (
  if exist "%OUT%" (
    echo Deleting %OUT% ...
    rmdir /s /q "%OUT%"
  )
)

set "RESUME="
if exist "%OUT%\experiment_manifest.json" set "RESUME=--resume"

echo Serial : !SER!
echo Output : %OUT%
if defined RESUME (
  echo Mode   : RESUME - continuing an existing experiment
) else (
  echo Mode   : NEW
)
echo.

%PY% "%~dp0s26_build_check.py" "%ADB%" "!SER!"
if "%errorlevel%"=="2" (
  echo.
  echo Aborting - rebuild first with s26_build.bat
  popd & pause & exit /b 1
)

echo.
echo ============================================================
echo  4 short runs. Press Ctrl+C after the 2nd one finishes,
echo  answer Y to terminate, then run this script again with no
echo  argument. It must pick up at run 3, not run 1.
echo ============================================================
echo.

%PY% tools\d1_experiment_orchestrator.py ^
  --serial !SER! ^
  --mode pilot ^
  --resources CPU GPU ^
  --cpu-thread-levels 2 4 ^
  --duty-cycles 100 ^
  --duration 30 ^
  --warmup 20 ^
  --repeat 1 ^
  --seed 20260913 ^
  --accuracy-preflight off ^
  --output-dir %OUT% %RESUME%

echo.
echo Orchestrator exit code: %errorlevel%
echo.
echo Runs completed so far:
dir /b /ad "%OUT%\runs" 2>nul | find /c /v ""
popd
pause
