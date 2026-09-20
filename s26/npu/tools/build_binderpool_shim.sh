#!/usr/bin/env bash
# Build libbinderpool_shim.so (arm64) with the Android NDK. ~1 minute.
# Colab:  upload binderpool_shim.c + this file, then  !bash build_binderpool_shim.sh
#         (re-downloads the NDK if the Colab VM was recycled; ~600 MB, 2 min)
# Output: $WORK/libbinderpool_shim.so  -> download into ...\npu\artifacts\litert_samsung_arm64\
set -euo pipefail
WORK="${WORK:-/content}"
NDK_VER="${NDK_VER:-r27c}"
cd "$WORK"
if [ ! -d "$WORK/android-ndk-$NDK_VER" ]; then
  echo "downloading NDK $NDK_VER ..."
  curl -fsSL -o ndk.zip "https://dl.google.com/android/repository/android-ndk-$NDK_VER-linux.zip"
  unzip -q ndk.zip -d "$WORK" && rm -f ndk.zip
fi
CLANG="$WORK/android-ndk-$NDK_VER/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
SRC="$(dirname "$0")/binderpool_shim.c"
[ -f "$SRC" ] || SRC="$WORK/binderpool_shim.c"
"$CLANG" -shared -fPIC -O2 -o "$WORK/libbinderpool_shim.so" "$SRC" -lbinder_ndk -llog
ls -la "$WORK/libbinderpool_shim.so"
sha256sum "$WORK/libbinderpool_shim.so"
echo "== done. download $WORK/libbinderpool_shim.so into artifacts/litert_samsung_arm64/"
