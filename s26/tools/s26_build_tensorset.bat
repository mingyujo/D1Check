@echo off
REM ============================================================
REM  S26 - download Imagenette + build the representative
REM        tensor set that --mode formal requires
REM
REM  Downloads about 325 MB the first time. Everything lands in
REM  C:\datasets, matching the paths in V4_INTEGRATION.md.
REM
REM  Usage: s26_build_tensorset.bat           build
REM         s26_build_tensorset.bat --check   what is present
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

%PY% "%~dp0s26_build_tensorset.py" %*
echo.
pause
