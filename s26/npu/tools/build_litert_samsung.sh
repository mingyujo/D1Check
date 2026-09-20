#!/usr/bin/env bash
# ============================================================================
# G2 — build the LiteRT Samsung NPU runtime pieces for Android arm64 from source
#   * libLiteRtDispatch_Samsung.so   (dispatch: LiteRT -> ENN on the phone)   ← G2 deliverable
#   * run_model                      (LiteRT CLI: runs a .tflite on npu/gpu/cpu, prints timings) ← G3 tool
#   * libLiteRtCompilerPlugin_Samsung.so (arm64, JIT only; built if BUILD_JIT=1)
#
# Where:  Google Colab (Ubuntu 24.04, x86_64) or WSL2 Ubuntu 22.04/24.04.  NOT Windows native.
# Usage:  bash build_litert_samsung.sh [git-ref]        default ref = main
#         Colab:  !bash build_litert_samsung.sh 2>&1 | tail -40
#         WSL2 :  WORK=$HOME bash build_litert_samsung.sh
# Time:   first run 30-90 min (downloads TensorFlow sources, NDK ~600 MB, compiles LiteRT runtime).
#         Keep the Colab tab open; the VM is discarded on disconnect.
# Output: $WORK/litert_samsung_arm64/  -> zip it and save to  ...\measure\s26\npu\artifacts\
#
# Why 'main' and not the v2.2.0 tag: the AOT-compiled models were produced by the nightly
# (2.3.0.dev20260917) compiler; the dispatch must understand the same Samsung bytecode header,
# so build the dispatch from the same code line. Pass 'v2.2.0' as ref to build the tagged version
# if the main build refuses the models (see NPU_RUNNER_SPEC.md §1.2).
# ============================================================================
set -euo pipefail

REF="${1:-main}"
WORK="${WORK:-/content}"
NDK_VER="${NDK_VER:-r27c}"
BUILD_JIT="${BUILD_JIT:-0}"
mkdir -p "$WORK" && cd "$WORK"
LOG="$WORK/build_litert_samsung.log"
echo "== $(date -u +%FT%TZ) start ref=$REF work=$WORK" | tee "$LOG"

# ---- 1. bazelisk (downloads the bazel version LiteRT pins in .bazelversion) ----
mkdir -p "$WORK/bin"
if [ ! -x "$WORK/bin/bazel" ]; then
  curl -fsSL -o "$WORK/bin/bazel" https://github.com/bazelbuild/bazelisk/releases/latest/download/bazelisk-linux-amd64
  chmod +x "$WORK/bin/bazel"
fi
export PATH="$WORK/bin:$PATH"
echo "bazelisk: $(bazel --version 2>&1 | tail -1)" | tee -a "$LOG"

# ---- 2. Android NDK ----
if [ ! -d "$WORK/android-ndk-$NDK_VER" ]; then
  echo "downloading NDK $NDK_VER ..." | tee -a "$LOG"
  curl -fsSL -o "$WORK/ndk.zip" "https://dl.google.com/android/repository/android-ndk-$NDK_VER-linux.zip"
  unzip -q "$WORK/ndk.zip" -d "$WORK" && rm -f "$WORK/ndk.zip"
fi
export ANDROID_NDK_HOME="$WORK/android-ndk-$NDK_VER"
echo "NDK: $ANDROID_NDK_HOME ($(grep Pkg.Revision "$ANDROID_NDK_HOME/source.properties"))" | tee -a "$LOG"

# ---- 3. LiteRT source ----
if [ ! -d "$WORK/LiteRT" ]; then
  git clone --depth 1 --branch "$REF" https://github.com/google-ai-edge/LiteRT.git "$WORK/LiteRT" 2>&1 | tail -2 | tee -a "$LOG"
fi
cd "$WORK/LiteRT"
COMMIT="$(git rev-parse HEAD)"
echo "LiteRT ref=$REF commit=$COMMIT bazelversion=$(cat .bazelversion 2>/dev/null || echo ?)" | tee -a "$LOG"

# ---- 4. build ----
TARGETS=( //litert/vendors/samsung/dispatch:dispatch_api_so //litert/tools:run_model )
if [ "$BUILD_JIT" = "1" ]; then TARGETS+=( //litert/vendors/samsung/compiler:compiler_plugin_so ); fi
echo "bazel build ${TARGETS[*]}" | tee -a "$LOG"
set +e
# ABSL_FLAGS_STRIP_NAMES defaults to 1 on Android -> every --flag becomes "Unknown command line flag"
# (seen 2026-09-19 on the phone). Keep flag names so run_model is usable from adb shell.
bazel build -c opt --config=android_arm64 --verbose_failures \
  --copt=-DABSL_FLAGS_STRIP_NAMES=0 --copt=-DABSL_FLAGS_STRIP_HELP=0 \
  "${TARGETS[@]}" 2>&1 | tee -a "$LOG" | grep -E "^(INFO: (Analyzed|Found|Build completed|Elapsed)|ERROR|FAILED|Target //)"
RC=${PIPESTATUS[0]}
set -e
if [ "$RC" != "0" ]; then
  echo "[X] bazel failed (rc=$RC). Send the last 60 lines of $LOG:" | tee -a "$LOG"
  tail -60 "$LOG"
  exit "$RC"
fi

# ---- 5. collect outputs ----
OUT="$WORK/litert_samsung_arm64"
rm -rf "$OUT" && mkdir -p "$OUT"
find -L bazel-bin/litert/vendors/samsung -name 'libLiteRtDispatch_Samsung.so' -exec cp -L {} "$OUT/" \;
find -L bazel-bin/litert/tools -maxdepth 1 -type f -name 'run_model' -exec cp -L {} "$OUT/" \;
# any runtime .so run_model may need next to it (libLiteRt*, GPU accelerator prebuilts)
find -L bazel-bin/litert -name 'libLiteRt*.so' -not -name 'libLiteRtDispatch_*' -not -name 'libLiteRtCompilerPlugin_*' -exec cp -L -n {} "$OUT/" \; 2>/dev/null || true
if [ "$BUILD_JIT" = "1" ]; then
  find -L bazel-bin/litert/vendors/samsung -name 'libLiteRtCompilerPlugin_Samsung.so' -exec cp -L {} "$OUT/" \;
  # LiteCore on-device compiler libs for JIT (the pip SDK package has the same tarball, arm64 subdir)
  SDK_ARM64="$(python3 -c 'import ai_edge_litert_sdk_samsung as s,pathlib;print(pathlib.Path(s.get_sdk_path())/"lib/arm64-v8a")' 2>/dev/null || true)"
  [ -d "$SDK_ARM64" ] && cp -L "$SDK_ARM64"/*.so "$OUT/" && echo "copied LiteCore arm64 libs from $SDK_ARM64" | tee -a "$LOG"
fi
ls -la "$OUT" | tee -a "$LOG"
[ -f "$OUT/libLiteRtDispatch_Samsung.so" ] || { echo "[X] dispatch .so not found in bazel-bin"; exit 2; }
[ -f "$OUT/run_model" ] || echo "[!] run_model not found - G3 CLI missing, dispatch still usable for the app path"

# ---- 6. provenance ----
{
  echo "# litert_samsung_arm64 — provenance"
  echo "built_at: $(date -u +%FT%TZ)"
  echo "host: $(uname -srm) / $(lsb_release -ds 2>/dev/null || echo unknown)"
  echo "litert_ref: $REF"
  echo "litert_commit: $COMMIT"
  echo "bazel: $(bazel --version 2>&1 | tail -1)"
  echo "ndk: $NDK_VER ($(grep Pkg.Revision "$ANDROID_NDK_HOME/source.properties" | cut -d= -f2 | tr -d ' '))"
  echo "targets: ${TARGETS[*]}"
  echo "config: -c opt --config=android_arm64 --copt=-DABSL_FLAGS_STRIP_NAMES=0 --copt=-DABSL_FLAGS_STRIP_HELP=0"
  echo
  echo "sha256:"
  (cd "$OUT" && sha256sum * | grep -v README)
} > "$OUT/README.md"
cat "$OUT/README.md" | tee -a "$LOG"
echo "== done. zip and download: $OUT" | tee -a "$LOG"
