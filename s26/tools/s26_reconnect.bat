@echo off
REM ============================================================
REM  S26 - re-establish wireless adb after a Wi-Fi drop
REM
REM  Toggling airplane mode, or any Wi-Fi blip, kills the adb
REM  TCP session and usually changes the wireless debugging port.
REM  Pairing survives - only the connection has to be remade.
REM
REM  Usage: s26_reconnect.bat            auto-discover
REM         s26_reconnect.bat 172.30.1.46:41253   explicit
REM ============================================================
setlocal enabledelayedexpansion

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

echo [1/4] Dropping stale sessions
"%ADB%" disconnect >nul 2>&1
"%ADB%" reconnect offline >nul 2>&1

set "CON=%~1"

if not defined CON (
  echo [2/4] Discovering via mDNS
  for /f "usebackq tokens=3" %%a in (`"%ADB%" mdns services 2^>nul ^| findstr /C:"_adb-tls-connect"`) do set "CON=%%a"
)

if not defined CON (
  echo     mDNS found nothing. On the phone open
  echo       Settings -^> Developer options -^> Wireless debugging
  echo     and read "IP address and Port" from the MAIN screen.
  set /p CON=    Type it here as ip:port  ^> 
)

if not defined CON (
  echo [X] No address. Aborting.
  pause
  exit /b 1
)

echo [3/4] Connecting to !CON!
"%ADB%" connect !CON!

echo.
echo [4/4] Devices:
"%ADB%" devices

echo.
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
if defined SER (
  echo [OK] wireless device !SER! is back.
  echo.
  echo      If a run was interrupted, continue with:
  echo        s26_prepare.bat
  echo        s26_formal.bat
) else (
  echo [X] Still no wireless device.
  echo     Check that the phone is on the same Wi-Fi and that
  echo     Wireless debugging is still ON. If the phone was
  echo     rebooted, pairing is gone - use s26_wifi.bat instead.
)
pause
