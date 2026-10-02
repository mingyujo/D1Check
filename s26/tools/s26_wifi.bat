@echo off
REM ============================================================
REM  S26 - Wireless ADB pair + connect
REM  Usage: s26_wifi.bat <pair-ip:port> <6-digit-code>
REM  Get both from the phone: Developer options -> Wireless
REM  debugging -> "Pair device with pairing code".
REM  KEEP that dialog open until this script finishes.
REM ============================================================
setlocal enabledelayedexpansion

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

if "%~2"=="" (
  echo.
  echo   Usage: s26_wifi.bat ^<pair-ip:port^> ^<6-digit-code^>
  echo   Example: s26_wifi.bat <IP:PORT> 123456
  echo.
  echo   Open on the phone:
  echo     Settings -^> Developer options -^> Wireless debugging
  echo     -^> Pair device with pairing code
  echo.
  pause
  exit /b 1
)

echo [1/4] Pairing with %~1 ...
"%ADB%" pair %~1 %~2
if errorlevel 1 (
  echo.
  echo [X] Pairing failed. The port and code expire when the dialog closes.
  echo     Reopen "Pair device with pairing code" and run again with the NEW numbers.
  pause
  exit /b 1
)

echo.
echo [2/4] Discovering the connect port via mDNS ...
set "CON="
for /f "usebackq tokens=3" %%a in (`"%ADB%" mdns services 2^>nul ^| findstr /C:"_adb-tls-connect"`) do set "CON=%%a"

if not defined CON (
  echo     mDNS gave nothing. Look at the phone's Wireless debugging MAIN screen.
  echo     It shows "IP address and Port" - a DIFFERENT port from the pairing one.
  set /p CON=    Type it here as ip:port  ^> 
)

if not defined CON (
  echo [X] No connect address. Aborting.
  pause
  exit /b 1
)

echo.
echo [3/4] Connecting to !CON! ...
"%ADB%" connect !CON!

echo.
echo [4/4] Devices:
"%ADB%" devices

echo.
echo ============================================
echo  Now UNPLUG the USB cable, then run:
echo      s26_smoke.bat
echo ============================================
pause
