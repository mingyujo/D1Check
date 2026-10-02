@echo off
setlocal enabledelayedexpansion
REM =====================================================================
REM  s26_npu_go.bat - G4 one-shot: connect -> build -> install -> run -> logs
REM
REM  ASCII only, CRLF line endings. Do not add non-ASCII text to this file:
REM  cmd.exe parses it under the console codepage (cp949 here) and breaks.
REM
REM  Usage:
REM    s26_npu_go.bat <IP:PORT>             NPU / float / 50 iters
REM    s26_npu_go.bat                               use existing connection or mDNS
REM    s26_npu_go.bat <IP:PORT> CPU float   CPU control (original model)
REM    s26_npu_go.bat <IP:PORT> NPU uint8   INT8 compiled model
REM    s26_npu_go.bat <IP:PORT> NPU float 50 skipbuild
REM
REM  ip:port = phone Settings - Developer options - Wireless debugging MAIN screen.
REM  Not the pairing dialog port. The port changes after any Wi-Fi drop.
REM =====================================================================

set "CLONE=C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
set "PKG=com.example.d1check.npurunner"
set "ACT=%PKG%/.NpuRunnerActivity"

REM ---- args: if arg1 looks like ip:port treat it as connect address
set "ADDR="
set "P1=%~1"
echo(%P1%| findstr /R "[0-9]\.[0-9].*:[0-9]" >nul
if not errorlevel 1 (
  set "ADDR=%~1"
  set "ACC=%~2"
  set "DTYPE=%~3"
  set "ITER=%~4"
  set "SKIPBUILD=%~5"
) else (
  set "ACC=%~1"
  set "DTYPE=%~2"
  set "ITER=%~3"
  set "SKIPBUILD=%~4"
)
if "%ACC%"=="" set "ACC=NPU"
if "%DTYPE%"=="" set "DTYPE=float"
if "%ITER%"=="" set "ITER=50"

set "SCRIPT_DIR=%~dp0"
set "OUTDIR=%SCRIPT_DIR%..\results"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
for /f "tokens=1-6 delims=/:. " %%a in ("%date% %time%") do set "TS=%%a%%b%%c_%%d%%e%%f"
set "TS=%TS: =0%"
set "LOG=%OUTDIR%\G4_GO_%TS%.txt"
set "RUNID=g4go_%ACC%_%DTYPE%_%TS%"

call :log "================= D1 NPU G4 one-shot ================="
call :log "when        : %date% %time%"
call :log "accelerator : %ACC%  dtype: %DTYPE%  iterations: %ITER%"
call :log "connect     : %ADDR%"
call :log "run_id      : %RUNID%"
call :log ""

if not exist "%ADB%" (
  call :log "[X] adb not found at %ADB%"
  goto :fail
)

REM ---------------------------------------------------------------- 0. JDK
call :log "----- [0] JDK -----"
set "JBR=C:\Program Files\Android\Android Studio\jbr"
if defined JAVA_HOME (
  call :log "JAVA_HOME=%JAVA_HOME%"
) else (
  if exist "%JBR%\bin\java.exe" (
    set "JAVA_HOME=%JBR%"
    call :log "JAVA_HOME unset - using Android Studio JBR"
  ) else (
    call :log "[!] no JAVA_HOME and no Android Studio JBR - gradle may fail"
  )
)
if defined JAVA_HOME "%JAVA_HOME%\bin\java.exe" -version >>"%LOG%" 2>&1

REM ------------------------------------------ 1. published LiteRT versions
call :log ""
call :log "----- [1] com.google.ai.edge.litert:litert published versions -----"
set "MAVEN_XML=%OUTDIR%\litert_maven_metadata_%TS%.xml"
curl.exe -sS --max-time 30 -o "%MAVEN_XML%" "https://dl.google.com/dl/android/maven2/com/google/ai/edge/litert/litert/maven-metadata.xml" 2>>"%LOG%"
if exist "%MAVEN_XML%" (
  call :log "saved: %MAVEN_XML%"
  findstr /C:"<version>" "%MAVEN_XML%" >>"%LOG%"
  findstr /C:"<release>" "%MAVEN_XML%" >>"%LOG%"
) else (
  call :log "[!] maven-metadata fetch failed - ignore if offline"
)

REM ------------------------------------------------- 2. connect and select
call :log ""
call :log "----- [2] device -----"
"%ADB%" start-server >nul 2>&1
"%ADB%" reconnect offline >nul 2>&1

if defined ADDR (
  call :log "adb connect %ADDR%"
  "%ADB%" connect %ADDR% >>"%LOG%" 2>&1
)

call :count_devices
if "%NDEV%"=="0" (
  call :log "no device - trying mDNS"
  set "AUTOCON="
  for /f "usebackq tokens=3" %%a in (`"%ADB%" mdns services 2^>nul ^| findstr /C:"_adb-tls-connect"`) do set "AUTOCON=%%a"
  if defined AUTOCON (
    call :log "mDNS found !AUTOCON! - connecting"
    "%ADB%" connect !AUTOCON! >>"%LOG%" 2>&1
  ) else (
    call :log "mDNS found nothing"
  )
  call :count_devices
)

"%ADB%" devices -l >>"%LOG%" 2>&1

if "%NDEV%"=="0" (
  call :log ""
  call :log "[X] no device connected."
  call :log "    1. phone: Developer options - Wireless debugging must be ON"
  call :log "    2. phone and PC on the same Wi-Fi"
  call :log "    3. pass the ip:port from the Wireless debugging MAIN screen:"
  call :log "         s26_npu_go.bat IP:PORT"
  call :log "    4. after a phone reboot, pair again with s26\tools\s26_wifi.bat"
  goto :fail
)

set "SER="
if defined ADDR set "SER=%ADDR%"
if not defined SER (
  for /f "usebackq skip=1 tokens=1,2" %%a in (`"%ADB%" devices`) do (
    if "%%b"=="device" (
      echo %%a | findstr ":" >nul && set "SER=%%a"
    )
  )
)
if not defined SER (
  for /f "usebackq skip=1 tokens=1,2" %%a in (`"%ADB%" devices`) do (
    if "%%b"=="device" set "SER=%%a"
  )
)
if not defined SER (
  call :log "[X] could not pick a serial - check adb devices"
  goto :fail
)

set "A=%ADB% -s %SER%"
REM make gradle installDebug target the same device
set "ANDROID_SERIAL=%SER%"
call :log "serial      : %SER%"
call :log "device count: %NDEV%"

%A% shell getprop ro.product.model >>"%LOG%" 2>&1
%A% shell getprop ro.build.version.oneui >>"%LOG%" 2>&1
%A% shell getprop ro.board.platform >>"%LOG%" 2>&1
%A% shell input keyevent KEYCODE_WAKEUP >nul 2>&1

REM -------------------------------------------------------------- 3. build
if /I "%SKIPBUILD%"=="skipbuild" (
  call :log ""
  call :log "----- [3] build skipped -----"
  goto :run
)
call :log ""
call :log "----- [3] gradlew :npu-runner:installDebug -----"
pushd "%CLONE%"
REM absolute path: cmd skips the current dir when NoDefaultCurrentDirectoryInExePath is set
call "%CLONE%\gradlew.bat" :npu-runner:installDebug --stacktrace >>"%LOG%" 2>&1
set "GRADLE_RC=!ERRORLEVEL!"
popd
call :log "gradle exit code = !GRADLE_RC!"
if not "!GRADLE_RC!"=="0" (
  call :log ""
  call :log "[X] build failed. key lines:"
  findstr /N /C:"error:" /C:"e: " /C:"Could not find" /C:"Could not resolve" /C:"FAILURE:" /C:"What went wrong" "%LOG%"
  goto :fail
)

REM ---------------------------------------------------------------- 4. run
:run
call :log ""
call :log "----- [4] launch -----"
%A% shell pm path %PKG% >>"%LOG%" 2>&1
%A% logcat -c
%A% shell am force-stop %PKG%

set "MODEL_EXTRA=--es model_asset models/mobilenet_v1_1.0_224_Samsung_E9965.tflite"
if /I "%DTYPE%"=="uint8" set "MODEL_EXTRA=--es model_asset models/mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite"
if /I "%ACC%"=="CPU" set "MODEL_EXTRA=--es model_asset models/mobilenet_v1_1.0_224.tflite"
REM quality gate (NPU float only): 32 inputs vs CPU reference, runs after the timing loop
set "QEXTRA="
if /I "%ACC%"=="NPU" if /I "%DTYPE%"=="float" set "QEXTRA=--ei quality_n 32"
call :log "model extra : %MODEL_EXTRA% %QEXTRA%"

%A% shell am start -n %ACT% --es accelerator %ACC% --es dtype %DTYPE% --ei iterations %ITER% --ei warmup 5 --es run_id %RUNID% --ez autofinish true %MODEL_EXTRA% %QEXTRA% >>"%LOG%" 2>&1

call :log "waiting for result, up to 150 s"
set /a WAITED=0
:waitloop
REM ping instead of timeout: timeout aborts when stdin is redirected (non-interactive runs)
ping -n 6 127.0.0.1 >nul
set /a WAITED+=5
%A% logcat -d -s D1NPU:I >"%TEMP%\d1_npu_tail.txt" 2>&1
findstr /C:"SUMMARY_END" "%TEMP%\d1_npu_tail.txt" >nul
if not errorlevel 1 goto :collect
if !WAITED! GEQ 150 (
  call :log "[!] no SUMMARY_END within 150 s - saving partial logs"
  goto :collect
)
echo     ... !WAITED!s
goto :waitloop

REM ------------------------------------------------------------ 5. collect
:collect
call :log ""
call :log "----- [5] logcat D1NPU -----"
%A% logcat -d -s D1NPU:I >>"%LOG%" 2>&1
call :log ""
call :log "----- [5b] logcat litert / tflite / ENN / linker -----"
REM native LiteRT tag is lowercase "litert". "LiteRt:V" alone matches nothing.
%A% logcat -d litert:V tflite:V LiteRt:V LiteRtDispatch:V LiteRtRuntime:V ENN:V enn:V litert_jni:V linker:V DEBUG:V AndroidRuntime:E *:S >>"%LOG%" 2>&1
call :log ""
call :log "----- [5c] crash buffer -----"
%A% logcat -d -b crash *:V >>"%LOG%" 2>&1

%A% exec-out run-as %PKG% cat files/npu-runner-v1/summary-latest.json >"%OUTDIR%\G4_summary_%TS%.json" 2>nul

echo.
echo ==========================================================
echo  log: %LOG%
echo ==========================================================
echo.
echo --- verdict hints ---
findstr /C:"available_accelerators" "%LOG%"
findstr /C:"first inference" "%LOG%"
findstr /C:"=== OK ===" "%LOG%"
findstr /C:"=== FAILED ===" "%LOG%"
findstr /C:"quality gate:" "%LOG%"
findstr /C:"MediumInterface" "%LOG%"
findstr /C:"CANNOT LINK" "%LOG%"
findstr /C:"UnsatisfiedLink" "%LOG%"
echo ---------------------
echo.
echo Done. Tell Claude "done" - it reads the results folder directly.
goto :end

REM ------------------------------------------------------------- helpers
:count_devices
set /a NDEV=0
for /f "usebackq skip=1 tokens=1,2" %%a in (`"%ADB%" devices`) do (
  if "%%b"=="device" set /a NDEV+=1
)
exit /b 0

:fail
echo.
echo [X] aborted. log: %LOG%
echo     Tell Claude "failed" - it will read the log and fix it.
goto :end

:log
echo(%~1
>>"%LOG%" echo(%~1
exit /b 0

:end
endlocal
