@echo off
REM ============================================================
REM  S26 - record the display state as an experiment condition
REM
REM  READ ONLY. Nothing on the phone is changed. Set brightness
REM  and adaptive mode by hand, then run this to capture what
REM  they were, so the value lands in the evidence folder.
REM
REM  Why it matters: the screen stays on for the whole run
REM  (FLAG_KEEP_SCREEN_ON). Its power is charged to the same
REM  battery being measured, and its heat reaches the chassis
REM  where the SKIN sensor sits. Adaptive brightness drifting
REM  mid-run injects noise straight into SKIN.
REM
REM  Usage: s26_display.bat
REM  Output: ..\device\13_display_state.txt
REM ============================================================
setlocal enabledelayedexpansion

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

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
  pause
  exit /b 1
)
set "A=%ADB% -s %SER%"
set "F=%~dp0..\device\13_display_state.txt"
if not exist "%~dp0..\device" mkdir "%~dp0..\device"

echo ===== display state at %DATE% %TIME% =====> "%F%"

echo. >> "%F%"
echo --- brightness --->> "%F%"
echo screen_brightness_mode (0=manual 1=adaptive):>> "%F%"
%A% shell settings get system screen_brightness_mode >> "%F%" 2>&1
echo screen_brightness (raw):>> "%F%"
%A% shell settings get system screen_brightness >> "%F%" 2>&1
echo screen_brightness_float:>> "%F%"
%A% shell settings get system screen_brightness_float >> "%F%" 2>&1

echo. >> "%F%"
echo --- night mode / theme --->> "%F%"
%A% shell "cmd uimode night" >> "%F%" 2>&1
%A% shell settings get secure ui_night_mode >> "%F%" 2>&1

echo. >> "%F%"
echo --- refresh rate --->> "%F%"
%A% shell "dumpsys display | grep -i -E 'mRefreshRate|refreshRate=|fps' | head -8" >> "%F%" 2>&1
%A% shell settings get secure refresh_rate_mode >> "%F%" 2>&1

echo. >> "%F%"
echo --- timeout / always-on --->> "%F%"
echo screen_off_timeout (ms):>> "%F%"
%A% shell settings get system screen_off_timeout >> "%F%" 2>&1
echo aod_mode:>> "%F%"
%A% shell settings get system aod_mode >> "%F%" 2>&1

echo. >> "%F%"
echo --- power saving --->> "%F%"
echo low_power:>> "%F%"
%A% shell settings get global low_power >> "%F%" 2>&1
%A% shell "dumpsys power | grep -i -E 'mScreenBrightness|mIsPowered|Display Power' | head -6" >> "%F%" 2>&1

echo.
echo ============================================
type "%F%"
echo ============================================
echo.

set "MODE="
for /f "usebackq delims=" %%a in (`%A% shell settings get system screen_brightness_mode`) do set "MODE=%%a"
set "MODE=!MODE: =!"
if "!MODE!"=="1" (
  echo [X] ADAPTIVE BRIGHTNESS IS ON.
  echo     It will drift over six hours and move the SKIN sensor
  echo     with it. Turn it off on the phone:
  echo       Settings -^> Display -^> Adaptive brightness  OFF
  echo     then drag the brightness slider near the minimum and
  echo     run this script again.
) else (
  echo [OK] brightness is manual. Keep the slider where it is for
  echo      the whole run and for every later session you want to
  echo      compare against.
)

set "LP="
for /f "usebackq delims=" %%a in (`%A% shell settings get global low_power`) do set "LP=%%a"
set "LP=!LP: =!"
if "!LP!"=="1" (
  echo.
  echo [X] POWER SAVING MODE IS ON. It throttles CPU and GPU.
  echo     Turn it off before measuring.
)

echo.
echo Written to: %F%
pause
