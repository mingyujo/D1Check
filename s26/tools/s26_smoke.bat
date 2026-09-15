@echo off
REM ============================================================
REM  S26 - Pilot smoke run driver
REM  Finds the wireless serial, checks the pilot safety gate,
REM  clears logcat, then starts the v4 capture logger.
REM  Usage: s26_smoke.bat          -> CPU4 run (default)
REM         s26_smoke.bat GPU      -> GPU run
REM ============================================================
setlocal enabledelayedexpansion

set "RES=%~1"
if not defined RES set "RES=CPU4"

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

set "ROOT=%~dp0..\.."
pushd "%ROOT%"

REM ---------- python ----------
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY ( where py >nul 2>&1 && set "PY=py -3" )
if not defined PY (
  echo [X] Python not found. Install Python 3.11+ or open an Anaconda prompt.
  popd
  pause
  exit /b 1
)
echo Using python : %PY%

REM ---------- wireless serial ----------
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
  echo.
  echo [X] No wireless device found. Run s26_wifi.bat first, then unplug USB.
  "%ADB%" devices
  popd
  pause
  exit /b 1
)
echo Using serial : !SER!
echo Resource     : !RES!

REM ---------- safety gate preflight ----------
echo.
echo ===== Pilot safety gate =====
set "TMPB=%~dp0_gate_batt.tmp"
set "TMPT=%~dp0_gate_therm.tmp"
"%ADB%" -s !SER! shell dumpsys battery > "%TMPB%" 2>&1
"%ADB%" -s !SER! shell dumpsys thermalservice > "%TMPT%" 2>&1

set "PLUG=0"
set "LVL="
set "BST="
set "T10="
set "THS="

REM  Samsung prints an ACTION_BATTERY_CHANGED history below the state
REM  block. Those lines start with a date, so token-1 matching skips them.
for /f "usebackq tokens=1,2,3" %%a in ("%TMPB%") do (
  if "%%b"=="powered:" if "%%c"=="true" set "PLUG=1"
  if "%%a"=="level:" set "LVL=%%b"
  if "%%a"=="status:" set "BST=%%b"
  if "%%a"=="temperature:" set "T10=%%b"
)
for /f "usebackq tokens=1,2,3" %%a in ("%TMPT%") do (
  if "%%a"=="Thermal" if "%%b"=="Status:" set "THS=%%c"
)

if not defined LVL goto :parsefail
if not defined BST goto :parsefail
if not defined T10 goto :parsefail
if not defined THS goto :parsefail

del "%TMPB%" >nul 2>&1
del "%TMPT%" >nul 2>&1

set /a TC=!T10!/10
set /a TD=!T10!%%10

set "FAIL=0"
set "WHY="
if "!PLUG!"=="1" ( set "FAIL=1" & set "WHY=!WHY! plugged" )
if !LVL! LSS 30 ( set "FAIL=1" & set "WHY=!WHY! battery_level" )
if !LVL! GTR 100 ( set "FAIL=1" & set "WHY=!WHY! battery_level" )
if !T10! GTR 350 ( set "FAIL=1" & set "WHY=!WHY! battery_temperature" )
if not "!BST!"=="3" ( set "FAIL=1" & set "WHY=!WHY! not_discharging" )
if !THS! LSS 0 ( set "FAIL=1" & set "WHY=!WHY! android_thermal_status" )
if !THS! GTR 1 ( set "FAIL=1" & set "WHY=!WHY! android_thermal_status" )

echo   plugged             : !PLUG!            need 0
echo   battery level       : !LVL! %%          need 30-100
echo   battery temperature : !TC!.!TD! C       need 35.0 or less
echo   battery status      : !BST!             need 3 = DISCHARGING
echo   thermal status      : !THS!             need 0 or 1

if "!FAIL!"=="1" (
  echo.
  echo [X] The run would be REJECTED. Reasons:!WHY!
  echo     plugged / not_discharging  -^> unplug the USB cable
  echo     battery_temperature        -^> let the phone cool 10-15 min
  echo     battery_level              -^> charge to 30%% or more, then unplug
  echo.
  popd
  pause
  exit /b 1
)
echo   [OK] the gate would accept this run.

REM ---------- run ----------
echo.
echo ===== Clearing logcat =====
%PY% tools\d1_logger_v4.py --serial !SER! clear
if errorlevel 1 (
  echo [X] clear failed.
  popd
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  The logger starts now and KEEPS RUNNING. Leave this window.
echo  On the PHONE, in this order:
echo.
echo   1. D1Check          -^> tap the FIRST button  (new run)
echo   2. Benchmark Runner -^> Resource         : !RES!
echo                          Limit mode       : Duration (seconds)
echo                          Duration seconds : 60
echo                          Warmup count     : 20
echo                          Diagnostic       : UNCHECKED
echo                       -^> tap "Start: baseline 60s, then load"
echo   3. Wait ~2.5 min. 60s baseline, warmup 20, 60s load, flush.
echo   4. Keep D1Check in the FOREGROUND for the cooldown you want.
echo   5. D1Check          -^> tap the SECOND button (stop)
echo.
echo  The logger exits by itself once it sees run_stop.
echo ============================================================
echo.
%PY% tools\d1_logger_v4.py --serial !SER! capture results

echo.
echo Logger exited. Next: s26\tools\s26_analyze.bat
popd
pause
exit /b 0

:parsefail
echo.
echo [X] Could not parse the safety gate values.
echo     level=[!LVL!] status=[!BST!] temperature=[!T10!] thermal=[!THS!]
echo.
echo     First 30 lines of dumpsys battery:
echo     ----------------------------------
more /e +0 "%TMPB%" | findstr /n "^" | findstr /r "^[1-9]: ^[12][0-9]: ^30:"
echo     ----------------------------------
echo     Raw dumps kept for inspection:
echo       %TMPB%
echo       %TMPT%
echo     Send these two lines to Claude.
popd
pause
exit /b 1
