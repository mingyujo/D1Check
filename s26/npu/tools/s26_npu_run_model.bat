@echo off
REM ============================================================
REM  S26 - G3: first NPU inference with LiteRT run_model (adb shell, no app)
REM  Needs (from Colab build + AOT compile):
REM    ..\artifacts\litert_samsung_arm64\run_model, libLiteRtDispatch_Samsung.so (+ libLiteRt*.so)
REM    ..\artifacts\compiled_e9965\mobilenet_v1_1.0_224_Samsung_E9965.tflite
REM    ..\artifacts\compiled_e9965\mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite
REM    ..\artifacts\mobilenet_v1_1.0_224.tflite            (original FP32, for the CPU control run; optional)
REM  Usage: s26_npu_run_model.bat [iterations]      default 100
REM  Output: ..\results\G3_run_model_<timestamp>.txt
REM  USB or wireless adb both fine (no safety gate; this is a smoke test, not a formal run).
REM ============================================================
setlocal enabledelayedexpansion

set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if not exist "%ADB%" set "ADB=adb"
set "ITER=%~1"
if "%ITER%"=="" set "ITER=100"

REM resolve ..\ away: Windows adb mangles the remote name when the local path contains "..\"
for %%i in ("%~dp0..") do set "NPU=%%~fi"
set "ART=%NPU%\artifacts"
set "BIN=%ART%\litert_samsung_arm64"
set "MOD=%ART%\compiled_e9965"
set "RES=%NPU%\results"
if not exist "%RES%" mkdir "%RES%"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
set "F=%RES%\G3_run_model_%TS%.txt"
set "DEV=/data/local/tmp/npu"

if not exist "%BIN%\run_model" ( echo [X] missing %BIN%\run_model  ^(run build_litert_samsung.sh first^) & pause & exit /b 1 )
if not exist "%BIN%\libLiteRtDispatch_Samsung.so" ( echo [X] missing libLiteRtDispatch_Samsung.so & pause & exit /b 1 )
if not exist "%MOD%\mobilenet_v1_1.0_224_Samsung_E9965.tflite" ( echo [X] missing compiled FP32 model in %MOD% & pause & exit /b 1 )

echo ===== G3 run_model %TS%  iterations=%ITER% =====> "%F%"
"%ADB%" devices >> "%F%" 2>&1
"%ADB%" shell "getprop ro.build.fingerprint; getprop ro.build.version.oneui" >> "%F%" 2>&1

echo.
echo [1/4] Pushing binaries and models to %DEV% ...
"%ADB%" shell "rm -rf %DEV%; mkdir -p %DEV%" >> "%F%" 2>&1
REM explicit remote file names (never "dir/"): see header note
for %%f in ("%BIN%\*") do "%ADB%" push "%%~ff" "%DEV%/%%~nxf" >> "%F%" 2>&1
"%ADB%" push "%MOD%\mobilenet_v1_1.0_224_Samsung_E9965.tflite" "%DEV%/mobilenet_v1_1.0_224_Samsung_E9965.tflite" >> "%F%" 2>&1
if exist "%MOD%\mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite" "%ADB%" push "%MOD%\mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite" "%DEV%/mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite" >> "%F%" 2>&1
if exist "%ART%\mobilenet_v1_1.0_224.tflite" "%ADB%" push "%ART%\mobilenet_v1_1.0_224.tflite" "%DEV%/mobilenet_v1_1.0_224.tflite" >> "%F%" 2>&1
"%ADB%" shell "chmod 755 %DEV%/run_model; ls -l %DEV%; md5sum %DEV%/*" >> "%F%" 2>&1
"%ADB%" shell "test -x %DEV%/run_model" >nul 2>&1
if errorlevel 1 (
  echo [X] run_model did not arrive on the phone. See %F%
  type "%F%"
  pause
  exit /b 1
)
"%ADB%" logcat -c >nul 2>&1

REM Vendor ENN libs: a shell binary cannot see /vendor/lib64 by bare name, and putting the whole
REM /vendor/lib64 on LD_LIBRARY_PATH shadows system libs (libbase etc. -> "CANNOT LINK EXECUTABLE",
REM G3 run 05:40). So copy only the ENN chain next to run_model. Apps get this via public.libraries.txt.
"%ADB%" shell "for f in libenn_public_api_cpp.so libenn_user.samsung_slsi.so libenn_common_utils.so vendor.samsung_slsi.hardware.enn_aidl-V1-ndk.so vendor.samsung_slsi.hardware.enn_aux@1.0.so; do cp /vendor/lib64/$f %DEV%/ 2>&1 || echo COPY FAILED $f; done; ls -l %DEV%/*enn*" >> "%F%" 2>&1
REM binder thread pool shim (see binderpool_shim.c): only if it was built and placed in the artifacts folder
set "PRELOAD="
if exist "%BIN%\libbinderpool_shim.so" set "PRELOAD=LD_PRELOAD=%DEV%/libbinderpool_shim.so "
set "RUN=cd %DEV% && %PRELOAD%LD_LIBRARY_PATH=%DEV% ./run_model --dispatch_library_dir=%DEV% --iterations=%ITER% --print_tensors --sample_size=5"

echo [2/4] NPU  FP32-compiled model ...
echo. >> "%F%"
echo ===== NPU fp32 (mobilenet_v1_1.0_224_Samsung_E9965.tflite) =====>> "%F%"
"%ADB%" shell "%RUN% --graph=%DEV%/mobilenet_v1_1.0_224_Samsung_E9965.tflite --accelerator=npu" >> "%F%" 2>&1

echo [3/4] NPU  INT8-compiled model ...
echo. >> "%F%"
echo ===== NPU int8 (mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite) =====>> "%F%"
"%ADB%" shell "%RUN% --graph=%DEV%/mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite --accelerator=npu" >> "%F%" 2>&1

echo [4/4] CPU  control (original FP32 model, same binary) ...
echo. >> "%F%"
echo ===== CPU control (mobilenet_v1_1.0_224.tflite) =====>> "%F%"
"%ADB%" shell "if [ -f %DEV%/mobilenet_v1_1.0_224.tflite ]; then %RUN% --graph=%DEV%/mobilenet_v1_1.0_224.tflite --accelerator=cpu; else echo SKIPPED - original model not pushed; fi" >> "%F%" 2>&1

echo. >> "%F%"
echo ===== logcat (LiteRt / ENN / npu lines since start) =====>> "%F%"
"%ADB%" logcat -d 2>nul | findstr /I "LiteRt ENN_ enn npu Dispatch avc denied linker" >> "%F%"

echo.
echo ============================================
type "%F%"
echo ============================================
echo Written to: %F%
echo Tell Claude it is finished (send the file).
pause
