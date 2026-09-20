// binderpool_shim.c — LD_PRELOAD helper for running LiteRT's run_model from `adb shell`.
//
// Why: the Samsung ENN runtime talks to the vendor HAL over binder
// (vendor.samsung_slsi.hardware.enn_aidl.IEnnInterfaceAidl). An Android *app* process always has
// a binder thread pool, a plain shell binary does not. Without it the HAL cannot call back into
// our process and ENN's init fails ("Waited one second ... Number of threads started in the
// threadpool: 0" -> "MediumInterface initialization failed", G3 run 2026-09-19 05:42).
// This library starts the thread pool before main() runs. Not needed inside an app.
//
// Build (Colab/WSL with the NDK from build_litert_samsung.sh):
//   $NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang \
//       -shared -fPIC -O2 -o libbinderpool_shim.so binderpool_shim.c -lbinder_ndk -llog
// Use:  LD_PRELOAD=/data/local/tmp/npu/libbinderpool_shim.so ./run_model ...
#include <android/binder_process.h>
#include <android/log.h>

__attribute__((constructor)) static void d1_start_binder_pool(void) {
  ABinderProcess_setThreadPoolMaxThreadCount(4);
  ABinderProcess_startThreadPool();
  __android_log_print(ANDROID_LOG_INFO, "D1NPU", "binderpool_shim: binder thread pool started (max 4)");
}
