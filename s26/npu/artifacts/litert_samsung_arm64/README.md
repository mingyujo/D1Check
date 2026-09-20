# litert_samsung_arm64 — provenance
built_at: 2026-09-18T20:32:47Z
host: Linux 6.6.122+ x86_64 / Ubuntu 24.04.5 LTS
litert_ref: main
litert_commit: 9380426b202dddc9f3dbd421cd5472c4c081f6bd
bazel: bazel 7.7.0
ndk: r27c (27.2.12479018)
targets: //litert/vendors/samsung/dispatch:dispatch_api_so //litert/tools:run_model
config: -c opt --config=android_arm64 --copt=-DABSL_FLAGS_STRIP_NAMES=0 --copt=-DABSL_FLAGS_STRIP_HELP=0

sha256:
b9a1042338868672a6b8ccd4271369c5efd947368738ac91681521d20d6bee41  libLiteRtClGlAccelerator.so
f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f  libLiteRtDispatch_Samsung.so
7842bd2e38da3b05309cdce22c82ca5a4b0163fa95ebd1ac4526aab087985036  run_model
