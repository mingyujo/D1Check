@echo off
setlocal enabledelayedexpansion
REM =====================================================================
REM  s26_npu_diag.bat - capture the FULL logcat around one NPU invoke
REM
REM  The tag filter in s26_npu_go.bat caught nothing, so this runs a single
REM  inference with no warmup and dumps every buffer unfiltered.
REM
REM  Usage: s26_npu_diag.bat <IP:PORT>
REM         s26_npu_diag.bat <IP:PORT> CPU     (CPU control, same engine)
REM  No rebuild. Uses the APK already installed.
REM =====================================================================

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
set "PKG=com.example.d1check.npurunner"
set "ACT=%PKG%/.NpuRunnerActivity"

set "ADDR=%~1"
set "ACC=%~2"
if "%ACC%"=="" set "ACC=NPU"

set "SCRIPT_DIR=%~dp0"
set "OUTDIR=%SCRIPT_DIR%..\results"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
for /f "tokens=1-6 delims=/:. " %%a in ("%date% %time%") do set "TS=%%a%%b%%c_%%d%%e%%f"
set "TS=%TS: =0%"
set "OUT=%OUTDIR%\G4_DIAG_%ACC%_%TS%.txt"

if defined ADDR "%ADB%" connect %ADDR% >nul 2>&1

set "SER=%ADDR%"
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
  echo [X] no device. pass ip:port as the first argument.
  exit /b 1
)
set "A=%ADB% -s %SER%"

echo ===== D1 NPU diag =====                >"%OUT%"
echo when : %date% %time%                  >>"%OUT%"
echo ser  : %SER%                          >>"%OUT%"
echo acc  : %ACC%                          >>"%OUT%"
echo.                                      >>"%OUT%"

echo [1/6] device + package
%A% shell getprop ro.product.model         >>"%OUT%" 2>&1
%A% shell getprop ro.build.version.oneui   >>"%OUT%" 2>&1
%A% shell pm path %PKG%                    >>"%OUT%" 2>&1

echo [2/6] native libs shipped in the APK
%A% shell run-as %PKG% ls -l lib/arm64     >>"%OUT%" 2>&1
%A% shell "ls -l /data/app/*/%PKG%*/lib/arm64 2>/dev/null" >>"%OUT%" 2>&1

echo [3/6] vendor ENN libs visible to apps
%A% shell "ls -l /vendor/lib64/libenn* 2>/dev/null"        >>"%OUT%" 2>&1
%A% shell "grep -i enn /vendor/etc/public.libraries.txt"   >>"%OUT%" 2>&1
%A% shell "getprop | grep -i enn"                          >>"%OUT%" 2>&1

echo [4/6] clearing logcat and running ONE inference
%A% logcat -c
%A% logcat -b all -c >nul 2>&1
%A% shell am force-stop %PKG%
set "MODEL_EXTRA=--es model_asset models/mobilenet_v1_1.0_224_Samsung_E9965.tflite"
if /I "%ACC%"=="CPU" set "MODEL_EXTRA=--es model_asset models/mobilenet_v1_1.0_224.tflite"
%A% shell am start -n %ACT% --es accelerator %ACC% --es dtype float --ei iterations 1 --ei warmup 0 --es run_id diag_%ACC%_%TS% --ez autofinish false %MODEL_EXTRA% >>"%OUT%" 2>&1

echo     waiting 25 s
REM ping instead of timeout: timeout aborts when stdin is redirected (non-interactive runs)
ping -n 26 127.0.0.1 >nul

echo [5/6] full logcat (unfiltered, threadtime)
echo.                                      >>"%OUT%"
echo ===== FULL LOGCAT =====               >>"%OUT%"
%A% logcat -d -v threadtime                >>"%OUT%" 2>&1

echo [6/6] other buffers
echo.                                      >>"%OUT%"
echo ===== CRASH BUFFER =====              >>"%OUT%"
%A% logcat -d -b crash -v threadtime       >>"%OUT%" 2>&1
echo.                                      >>"%OUT%"
echo ===== EVENTS BUFFER =====             >>"%OUT%"
%A% logcat -d -b events -v threadtime      >>"%OUT%" 2>&1

%A% exec-out run-as %PKG% cat files/npu-runner-v1/summary-latest.json >"%OUTDIR%\G4_DIAG_summary_%TS%.json" 2>nul

echo.
echo ==========================================================
echo  saved: %OUT%
echo ==========================================================
echo.
echo grep preview:
findstr /I /C:"litert" /C:"LiteRt" /C:"enn" /C:"dispatch" /C:"npu" "%OUT%" | findstr /V /C:"input" | more +0
echo.
echo Tell Claude "diag done".
endlocal
