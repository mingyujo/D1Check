@echo off
REM superseded by s26_npu_go.bat (connect + build + install + run + logs).
REM Kept only so old notes do not point at a missing file.
echo This script is superseded. Use:
echo    s26_npu_go.bat ^<ip:port^>
echo.
echo Forwarding now...
call "%~dp0s26_npu_go.bat" %*
