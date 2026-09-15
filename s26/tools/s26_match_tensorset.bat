@echo off
REM ============================================================
REM  S26 - diagnose the container-hash difference
REM  Usage: s26_match_tensorset.bat          search
REM         s26_match_tensorset.bat --show   just print our header block
REM ============================================================
setlocal

set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\python.exe" set "PY=%USERPROFILE%\miniconda3\python.exe"
if not defined PY ( where py >nul 2>&1 && set "PY=py -3" )
if not defined PY (
  echo [X] Python not found.
  pause
  exit /b 1
)

%PY% "%~dp0s26_match_tensorset.py" %*
echo.
pause
