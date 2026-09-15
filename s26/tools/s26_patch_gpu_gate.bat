@echo off
REM ============================================================
REM  S26 - apply / revert the GPU compatibility-gate patch
REM  Usage: s26_patch_gpu_gate.bat           apply
REM         s26_patch_gpu_gate.bat --check   status only
REM         s26_patch_gpu_gate.bat --revert  undo
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

%PY% "%~dp0s26_patch_gpu_gate.py" %*
echo.
pause
