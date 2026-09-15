@echo off
REM ============================================================
REM  S26 - formal measurement, matched to the A24 design
REM
REM  The A24 run was reverse-engineered from its own numbers:
REM    60,287 latency samples, 18,818 thermal rows, 80 slots,
REM    CPU median 41.190 ms, GPU 3.19577x slower.
REM  Only --duration 60 reproduces all three. V4_INTEGRATION.md
REM  shows --duration 600 but that is an illustrative example.
REM
REM  Design (identical to A24 so the two devices can be paired):
REM    CPU 1/2/4 threads x duty 25/50/75/100   = 12 conditions
REM    GPU              x duty 25/50/75/100   =  4 conditions
REM    16 conditions x 5 repeats              = 80 runs
REM    60 s baseline, 60 s load, stable conditioning and cooling
REM    ~270 s per run  ->  about 6 hours
REM
REM  GPU profile: gpu-fp32-strict-v1 (precision_loss_allowed=false).
REM  The A24 headline numbers are "GPU strict", and its representative
REM  max absolute error was 3.58e-6, i.e. fp32 level. A first attempt
REM  with gpu-compat-default-v1 (fp16) reached 2.62e-2 and failed the
REM  pre-registered representative gate on 1 of 40 top-1 labels. The
REM  thresholds were NOT touched; the configuration was.
REM
REM  --seed matches the A24 run so the randomised block order is
REM  the same on both devices.
REM
REM  Usage: s26_formal.bat dry     print the plan only
REM         s26_formal.bat         start, or resume if interrupted
REM ============================================================
setlocal enabledelayedexpansion

set "DRY="
if /I "%~1"=="dry" set "DRY=--dry-run"

set "TENSORSET=C:\datasets\d1-imagenette-val40.d1tset"
set "OUT=results\S26_formal_strict"

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

if not exist "%TENSORSET%" (
  echo [X] Representative tensor set not found:
  echo     %TENSORSET%
  echo.
  echo     formal mode cannot start without it. Build it first:
  echo         s26_build_tensorset.bat
  popd & pause & exit /b 1
)

findstr /C:"FORMAL_GPU_VALIDATED_DEVICE_PREFIXES" tools\d1_logger_v4.py >nul 2>&1
if errorlevel 1 (
  echo [X] Patch 2 is not applied. Every GPU run would fail
  echo     validation with formal_gpu_valid. Apply it first:
  echo         s26_patch_formal_gate.bat
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

set "RESUME="
if exist "%OUT%\experiment_manifest.json" set "RESUME=--resume"

echo Serial    : !SER!
echo Output    : %OUT%
echo TensorSet : %TENSORSET%
if defined DRY   echo Mode      : DRY RUN - nothing runs on the phone
if defined RESUME (echo State     : RESUME) else (echo State     : NEW)
echo Profile   : gpu-fp32-strict-v1  (fp32 forced, matches A24)
echo Design    : CPU 1/2/4 x duty 25/50/75/100, GPU x duty 25/50/75/100
echo             60 s load, repeat 5 = 80 runs, about 6 hours
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
echo   formal mode requires SOC 30-90. Start at 90, not 100.
echo   80 runs draw roughly 3,200 mAh of a 4,315 mAh battery, so
echo   expect one charge break near run 60-65. Charge, unplug,
echo   cool below 35 C, s26_prepare.bat, then run this again.
echo.
echo ===== Before you walk away =====
echo   Phone UNLOCKED with D1Check in front. Do NOT press power.
echo   PC sleep and hibernate set to Never.
echo   Leave the phone in ONE place - the A24 run had a location
echo   change mid-experiment that became a confounder.
echo.

%PY% tools\d1_experiment_orchestrator.py ^
  --serial !SER! ^
  --mode formal ^
  --resources CPU GPU ^
  --cpu-thread-levels 1 2 4 ^
  --duty-cycles 25 50 75 100 ^
  --duration 60 ^
  --warmup 20 ^
  --repeat 5 ^
  --seed 20260910 ^
  --accuracy-preflight required ^
  --accuracy-validation-scope backend-performance-formal ^
  --representative-tensor-set "%TENSORSET%" ^
  --gpu-profile gpu-fp32-strict-v1 ^
  --accuracy-input-count 32 ^
  --accuracy-seed 305419896 ^
  --accuracy-atol 0.0001 ^
  --accuracy-rtol 0.001 ^
  --start-policy stable ^
  --cooling-policy stable ^
  --output-dir %OUT% %RESUME% %DRY%

set "RC=%errorlevel%"
echo.
echo Orchestrator exit code: %RC%
echo Runs completed:
dir /b /ad "%OUT%\runs" 2>nul | find /c /v ""
echo.
if not "%RC%"=="0" (
  echo Stopped. If the reason was battery: charge, unplug, let it
  echo cool, unlock, s26_prepare.bat, then run this again. Completed
  echo slots are immutable and will not be repeated.
)
popd
pause
