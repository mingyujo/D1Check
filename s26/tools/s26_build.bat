@echo off
REM ============================================================
REM  S26 - build and install the benchmark-runner from the CLI
REM  Does not need Android Studio to be open or to see the device.
REM  Usage: s26_build.bat            -> benchmark-runner only
REM         s26_build.bat all        -> app + benchmark-runner
REM ============================================================
setlocal enabledelayedexpansion

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"

set "ROOT=%~dp0..\.."
pushd "%ROOT%"

REM ---------- JDK ----------
if not defined JAVA_HOME (
  if exist "%ProgramFiles%\Android\Android Studio\jbr\bin\java.exe" (
    set "JAVA_HOME=%ProgramFiles%\Android\Android Studio\jbr"
  )
)
if not defined JAVA_HOME (
  if exist "%LOCALAPPDATA%\Programs\Android Studio\jbr\bin\java.exe" (
    set "JAVA_HOME=%LOCALAPPDATA%\Programs\Android Studio\jbr"
  )
)
if not defined JAVA_HOME (
  echo [X] No JDK found. Android Studio normally ships one at
  echo     "%ProgramFiles%\Android\Android Studio\jbr".
  echo     Set JAVA_HOME yourself and run again.
  popd
  pause
  exit /b 1
)
echo JAVA_HOME : %JAVA_HOME%

REM ---------- target device ----------
set "SER="
for /f "usebackq skip=1 tokens=1,2" %%a in (`"%ADB%" devices`) do (
  if "%%b"=="device" (
    echo %%a | findstr ":" >nul && set "SER=%%a"
  )
)
if not defined SER (
  for /f "usebackq skip=1 tokens=1,2" %%a in (`"%ADB%" devices`) do (
    if "%%b"=="device" set "SER=%%a"
  )
)
if not defined SER (
  echo [X] No device. Run s26_wifi.bat first.
  "%ADB%" devices
  popd
  pause
  exit /b 1
)
set "ANDROID_SERIAL=%SER%"
echo Device    : %SER%

set "TASKS=:benchmark-runner:installDebug"
if /I "%~1"=="all" set "TASKS=:app:installDebug :benchmark-runner:installDebug"
echo Tasks     : %TASKS%
echo.
echo Close any build running inside Android Studio first, or Gradle will
echo wait on the same lock.
echo.

call gradlew.bat %TASKS%
set "RC=%errorlevel%"

echo.
if not "%RC%"=="0" (
  echo [X] Gradle failed with exit code %RC%.
  echo     Read the first "e: " line above - that is the real error.
  popd
  pause
  exit /b %RC%
)

echo ===== Verifying what is now on the phone =====
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY ( where py >nul 2>&1 && set "PY=py -3" )
if defined PY %PY% "%~dp0s26_build_check.py" "%ADB%" "%SER%"

echo.
echo Done. Next: s26_pilot.bat
popd
pause
