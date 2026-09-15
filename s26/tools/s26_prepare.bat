@echo off
REM ============================================================
REM  S26 - prepare the phone for an unattended measurement run
REM
REM  Android 12+ refuses startForegroundService() from a
REM  background app. The orchestrator foregrounds D1Check first
REM  to earn that exemption, which only works while the screen
REM  is ON and UNLOCKED. This wakes the screen, exempts both
REM  apps from Doze, foregrounds D1Check, and then actually
REM  tests the call that failed.
REM
REM  Usage: s26_prepare.bat
REM ============================================================
setlocal enabledelayedexpansion

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

set "D1=com.example.d1check"
set "RUNNER=com.example.d1check.benchmarkrunner"

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
  "%ADB%" devices
  pause
  exit /b 1
)
set "A=%ADB% -s %SER%"
echo Serial : %SER%
echo.

echo [1/5] Waking the screen
%A% shell input keyevent KEYCODE_WAKEUP >nul 2>&1
%A% shell wm dismiss-keyguard >nul 2>&1

echo [2/5] Exempting both apps from Doze
%A% shell cmd deviceidle whitelist +%D1% >nul 2>&1
%A% shell cmd deviceidle whitelist +%RUNNER% >nul 2>&1
%A% shell dumpsys deviceidle whitelist 2>nul | findstr /C:"d1check" 

echo [3/5] Screen state
%A% shell dumpsys deviceidle 2>nul | findstr /C:"mScreenOn" /C:"mCharging"
%A% shell dumpsys window 2>nul | findstr /C:"mDreamingLockscreen"

echo [4/5] Bringing D1Check to the foreground
%A% shell am start -W -n %D1%/.MainActivity 2>&1 | findstr /C:"Status" /C:"Error" /C:"Warning"

echo.
echo [5/5] Testing the call that failed before
%A% shell run-as %D1% am start-foreground-service --user 0 -a %D1%.action.STOP -n %D1%/.TelemetryForegroundService
if errorlevel 1 goto :bad
echo.
echo   [OK] the foreground-service call was accepted.
echo.
echo ============================================================
echo  Leave the phone UNLOCKED with D1Check on screen.
echo  D1Check holds FLAG_KEEP_SCREEN_ON, so it stays awake on
echo  its own once it is in front. Do not press the power button.
echo  Now run:  s26_formal.bat
echo ============================================================
pause
exit /b 0

:bad
echo.
echo   [X] Still refused.
echo.
echo   Most likely the phone is locked. Unlock it by hand - PIN,
echo   pattern or biometrics - so D1Check can come to the front,
echo   then run this script again.
echo.
echo   If it is already unlocked and this still fails, tell Claude
echo   and paste everything above.
pause
exit /b 1
