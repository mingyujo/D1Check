@echo off
setlocal enabledelayedexpansion
title S26 commit and push

REM ===================================================================
REM  s26_push.bat   (ASCII only, CRLF only -- do not add non-ASCII text)
REM    1) copy formal exports into s26\results\formal_strict\
REM    2) verify sha256 against dataset_manifest.json
REM    3) stage patch 1 / patch 2 sources + the whole s26 folder
REM    4) commit (message from s26_commit_msg.txt) and push
REM
REM  s26_push.bat dry   -> show what would be pushed, then stop
REM ===================================================================

set "DRY="
if /I "%~1"=="dry" set "DRY=1"

set "TOOLS=%~dp0"
cd /d "%~dp0..\.."
set "ROOT=%CD%"

echo.
echo ================== S26 COMMIT AND PUSH ==================
echo  repo : %ROOT%
if defined DRY echo  mode : DRY RUN
echo =========================================================
echo.

if not exist "%ROOT%\benchmark-runner" goto :notrepo

REM ---- [1] locate git ----------------------------------------------
set "GIT="
where git >nul 2>&1 && set "GIT=git"
if not defined GIT if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
if not defined GIT if exist "%ProgramFiles(x86)%\Git\cmd\git.exe" set "GIT=%ProgramFiles(x86)%\Git\cmd\git.exe"
if not defined GIT if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" set "GIT=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
if not defined GIT goto :nogit
echo [1/7] git    : %GIT%

REM ---- [2] locate python -------------------------------------------
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (
  where py >nul 2>&1 && set "PY=py"
)
if defined PY (echo [2/7] python : !PY!) else (echo [2/7] python : not found, sha256 check skipped)

REM ---- [3] check source results ------------------------------------
set "SRC=%ROOT%\results\S26_formal_strict\exports-v2"
if not exist "%SRC%\dataset_manifest.json" goto :noresults
echo [3/7] source : results\S26_formal_strict\exports-v2

REM ---- [4] copy ----------------------------------------------------
set "DST=%ROOT%\s26\results\formal_strict"
if not exist "%DST%" mkdir "%DST%"
copy /Y /B "%SRC%\run_summary.csv"               "%DST%\run_summary.csv"               >nul
if errorlevel 1 goto :copyfail
copy /Y /B "%SRC%\phase_temperature_summary.csv" "%DST%\phase_temperature_summary.csv" >nul
if errorlevel 1 goto :copyfail
copy /Y /B "%SRC%\thermal_timeseries.csv"        "%DST%\thermal_timeseries.csv"        >nul
if errorlevel 1 goto :copyfail
copy /Y /B "%SRC%\dataset_manifest.json"         "%DST%\dataset_manifest.json"         >nul
if errorlevel 1 goto :copyfail
echo [4/7] copied : -^> s26\results\formal_strict\

REM ---- [5] .gitattributes ------------------------------------------
REM CSV files use CRLF and dataset_manifest.json pins their sha256.
REM core.autocrlf must not rewrite them, so store the bytes verbatim.
> "%DST%\.gitattributes" echo # measurement outputs - bytes must match dataset_manifest.json sha256
>>"%DST%\.gitattributes" echo * -text
echo [5/7] wrote  : .gitattributes ^(* -text^)

if not defined PY goto :skipverify
echo.
"!PY!" "%TOOLS%s26_verify_exports.py" "%DST%"
if errorlevel 1 goto :hashfail
echo.
:skipverify

REM ---- [6] stage ---------------------------------------------------
"%GIT%" add "tools/d1_logger_v4.py"
"%GIT%" add "benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner/GpuBenchmarkEngine.kt"
"%GIT%" add "benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner/AccuracyPreflightEngine.kt"
"%GIT%" add "benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner/s26/GpuCompatibilityPolicy.kt"
REM .gitignore line 22 "results/" also matches s26/results/, so force-add
"%GIT%" add -f "s26"
echo [6/7] staged
echo.
echo ------------------ files to be pushed ------------------
"%GIT%" status --short
echo --------------------------------------------------------
set "BR="
for /f "delims=" %%b in ('"%GIT%" rev-parse --abbrev-ref HEAD') do set "BR=%%b"
echo  branch : !BR!
echo.

if defined DRY goto :dryend

REM ---- [7] commit and push -----------------------------------------
if not exist "%TOOLS%s26_commit_msg.txt" goto :nomsg
"%GIT%" commit -F "%TOOLS%s26_commit_msg.txt"
if errorlevel 1 echo [!] nothing to commit, or commit failed.

echo.
echo [7/7] push -^> origin !BR!
"%GIT%" push origin HEAD
if errorlevel 1 goto :pushfail
echo.
echo [OK] pushed.
goto :done

:dryend
echo [DRY] stopping here. Run without arguments to commit and push.
echo       To unstage:  git reset
goto :done

:notrepo
echo [X] Not the repository root. Keep this file in s26\tools\ and run it there.
goto :fail
:nogit
echo [X] git not found. Git for Windows is required.
goto :fail
:noresults
echo [X] No results at: %SRC%
echo     The formal run must finish before exports-v2 exists.
goto :fail
:copyfail
echo [X] Copy failed.
goto :fail
:hashfail
echo [X] sha256 mismatch. Stopping.
goto :fail
:nomsg
echo [X] s26_commit_msg.txt not found next to this script.
goto :fail
:pushfail
echo.
echo [X] Push failed.
echo     If the remote is ahead:  git pull --rebase   then run this again.
goto :fail

:done
echo.
pause
exit /b 0

:fail
echo.
echo *** ABORTED ***
pause
exit /b 1
