@echo off
REM ============================================================
REM  S26 - Analyze the newest captured run
REM  Usage: s26_analyze.bat  [run_id]
REM  With no argument it picks the newest folder under results\.
REM  Output also saved to ..\device\11_smoke_summary.txt
REM ============================================================
setlocal enabledelayedexpansion

set "ROOT=%~dp0..\.."
pushd "%ROOT%"

set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY ( where py >nul 2>&1 && set "PY=py -3" )
if not defined PY (
  echo [X] Python not found.
  popd
  pause
  exit /b 1
)

set "RUN=%~1"
if not defined RUN (
  if not exist "results" (
    echo [X] No results folder. Run s26_smoke.bat first.
    popd
    pause
    exit /b 1
  )
  for /f "delims=" %%d in ('dir /b /ad /o-d results 2^>nul') do (
    if not defined RUN set "RUN=%%d"
  )
)
if not defined RUN (
  echo [X] No run folder under results\.
  popd
  pause
  exit /b 1
)

echo Analyzing run: !RUN!
echo.

set "OUT=%~dp0..\device\11_smoke_summary.txt"
%PY% tools\d1_logger_v4.py analyze results\!RUN! > "%OUT%" 2>&1
type "%OUT%"

echo.
echo ============================================
echo  Pass criteria - check these three:
echo    inference_latency.count                       ^> 0
echo    thermal_coverage.passes_formal_requirement    true
echo    run_envelope_validation                       pass
echo.
echo  formal_gpu_valid is null on CPU and false on GPU
echo  for this phone. That is EXPECTED - the check is
echo  hardcoded to SM-A245. It does not mean failure.
echo ============================================
echo.
echo Saved to: %OUT%
echo Per-inference rows: results\!RUN!\merged\latency_timeline.csv
popd
pause
