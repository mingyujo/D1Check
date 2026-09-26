@echo off
setlocal enabledelayedexpansion
title S26 energy unit audit

REM ===================================================================
REM  s26_energy.bat   (ASCII only, CRLF only)
REM    Walks every run of the formal experiment, integrates the 1 Hz
REM    current samples, and compares them against the charge counter.
REM    This is the step 2 unit verification -- no new measurement needed.
REM
REM    s26_energy.bat                 -> results\S26_formal_strict
REM    s26_energy.bat <experiment>    -> that directory instead
REM ===================================================================

set "TOOLS=%~dp0"
cd /d "%~dp0..\.."
set "ROOT=%CD%"

set "EXP=%~1"
if "%EXP%"=="" set "EXP=results\S26_formal_strict"

echo.
echo ================== S26 ENERGY UNIT AUDIT ==================
echo  repo       : %ROOT%
echo  experiment : %EXP%
echo ===========================================================
echo.

if not exist "%ROOT%\%EXP%\runs" goto :noruns

set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY (
  where py >nul 2>&1 && set "PY=py"
)
if not defined PY goto :nopy

"!PY!" "%TOOLS%s26_energy.py" "%ROOT%\%EXP%"
if errorlevel 1 goto :fail

echo.
echo [OK] done. See %EXP%\energy_audit.csv
goto :done

:noruns
echo [X] Not found: %ROOT%\%EXP%\runs
goto :fail
:nopy
echo [X] python not found.
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
