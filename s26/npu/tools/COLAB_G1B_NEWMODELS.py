# =============================================================================
# G1-B : 조민규 개정 4.4 의 새 모델 2종을 Samsung E9965(Exynos 2600) 로 AOT 컴파일
#        → NPU 파티션 수를 확인한다.  Colab 새 노트북에 통째로 붙여넣고 실행(약 5~10분).
#
# 목적 : "CPU / GPU / NPU 3대 기계 스케줄링" 서사가 성립하는지의 전제조건 판정.
#        MobileNet V1 은 31/31 ops 1 partition 으로 이미 PASS(G1, 9/19).
#        EfficientDet 은 후처리 연산 때문에 부분 파티션일 가능성이 있다 — 그것도 결과다.
#
# 판정   PASS = DISPATCH_OP 있고 비-dispatch 연산자 0개      → npu_full  cell 가능
#        PART = DISPATCH_OP 있으나 CPU 잔여 연산자 있음      → npu_partial cell (gpu_assisted 와 같은 취급)
#        FAIL = DISPATCH_OP 없음 / Samsung backend 실패      → 해당 모델은 NPU 범위 밖
#
# ⚠ 라이선스 : efficientdet_lite0 는 exact binary 의 license 귀속이 미확인이다.
#   - 원본·컴파일 산출물 모두 저장소 / PR / APK / 팀 공유 ZIP 에 넣지 말 것
#   - 이 셀은 "각 실행자가 원 URL 에서 직접 확보" 규칙을 따른다 (MODEL_02B_PROBE §2)
#   - 레포에 올릴 것은 아래가 출력하는 aot_manifest.json / 판정표뿐이다
# =============================================================================

# ---------- 0. 설치 ----------------------------------------------------------
!pip install -q ai-edge-litert-nightly ai-edge-litert-sdk-samsung-nightly
# 두 번째 패키지가 setup.py 에서 아래를 자동으로 내려받는다:
#   https://soc-developer.semiconductor.samsung.com/api/v1/resource/download-file/ai-litecore-ubuntu2404-v1.2.0.tar.gz
# 실패하면 수동 다운로드 후 site-packages/ai_edge_litert_sdk_samsung/data/ 에 풀 것.

import hashlib, json, os, platform, shutil, subprocess, time, urllib.request
from pathlib import Path

WORK = Path("/content/g1b"); WORK.mkdir(parents=True, exist_ok=True)
MODELS = WORK / "models"; MODELS.mkdir(exist_ok=True)
OUT = WORK / "compiled_e9965_newmodels"

# ---------- 1. 모델 확보 + 해시 검증 (MODEL_02_INVENTORY.md 고정값) ----------
PINNED = [
    # (이름, version-pinned URL, bytes, sha256)
    ("efficientnet_lite0",
     "https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/float32/1/efficientnet_lite0.tflite",
     18_582_189, "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0"),
    ("efficientdet_lite0",
     "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float32/1/efficientdet_lite0.tflite",
     13_836_895, "40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58"),
    # 예비 후보 — EfficientDet 이 FAIL 일 때만 참고 (조민규는 아직 대안 승인 안 함)
    # ("ssd_mobilenet_v2",
    #  "https://storage.googleapis.com/mediapipe-models/object_detector/ssd_mobilenet_v2/float32/1/ssd_mobilenet_v2.tflite",
    #  11_316_189, "b8ccb1a25d45455ba52e85f26531948e1cb75efeb94c7c3d456d54fd4d6fbdd2"),
]

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

inputs = []
for name, url, want_bytes, want_sha in PINNED:
    dst = MODELS / f"{name}.tflite"
    if not dst.exists():
        print(f"downloading {name} ...")
        urllib.request.urlretrieve(url, dst)
    got_bytes, got_sha = dst.stat().st_size, sha256(dst)
    ok = (got_bytes == want_bytes) and (got_sha == want_sha)
    print(f"{name:22s} {got_bytes:>12,} B  sha={got_sha[:16]}…  {'OK' if ok else '*** MISMATCH ***'}")
    if not ok:
        raise SystemExit(f"{name}: 고정 해시와 불일치 — 중단. 원본이 바뀌었는지 확인할 것")
    inputs.append(dst)

# ---------- 2. AOT 컴파일 ----------------------------------------------------
import ai_edge_litert
from ai_edge_litert.aot import aot_compile
from ai_edge_litert.aot.vendors.samsung import target as samsung_target
import ai_edge_litert_sdk_samsung as sdk

sdk_libs = sdk.path_to_sdk_libs()
assert sdk_libs and Path(sdk_libs).is_dir(), f"Samsung SDK libs 없음: {sdk_libs} — LiteCore 다운로드 실패"
print(f"\nai_edge_litert {getattr(ai_edge_litert,'__version__','?')} / samsung sdk {getattr(sdk,'__version__','?')}")
print(f"SDK libs: {len(list(Path(sdk_libs).glob('*.so')))} .so")

# nightly 패키징 버그 우회 (G1 9/19 에서 확인된 것과 동일):
# libLiteRtCompilerPlugin_Samsung.so 가 flatbuffers::ClassicLocale::instance_ 를 참조하나 정의가 없음
FB_SHIM = r"""
#include <locale.h>
namespace flatbuffers {
class ClassicLocale {
  typedef locale_t locale_type;
  locale_type locale_;
  static ClassicLocale instance_;
  ClassicLocale();
  ~ClassicLocale();
 public:
  static const locale_type &Get() { return instance_.locale_; }
};
ClassicLocale::ClassicLocale() { locale_ = newlocale(LC_ALL, "C", nullptr); }
ClassicLocale::~ClassicLocale() { freelocale(locale_); }
ClassicLocale ClassicLocale::instance_;
}
"""
OUT.mkdir(parents=True, exist_ok=True)
src, so = OUT / "fb_classic_locale_shim.cpp", OUT / "libfb_classic_locale_shim.so"
src.write_text(FB_SHIM)
r = subprocess.run(["g++", "-O2", "-shared", "-fPIC", "-o", str(so), str(src)], capture_output=True, text=True)
if r.returncode == 0:
    os.environ["LD_PRELOAD"] = str(so) + (":" + os.environ["LD_PRELOAD"] if os.environ.get("LD_PRELOAD") else "")
    print(f"flatbuffers shim preloaded: {so.name}")
else:
    print("[!] shim 빌드 실패 (플러그인이 이미 고쳐졌으면 무해):", r.stderr.strip()[:300])

DISPATCH_OP = "DISPATCH_OP"

def inspect(path: Path) -> dict:
    info = {"file": path.name, "size": path.stat().st_size, "sha256": sha256(path)}
    try:
        from ai_edge_litert.tools import flatbuffer_utils as fu
        m = fu.read_model(path)
        counts = {}
        for sg in m.subgraphs:
            for op in sg.operators:
                n = fu.opcode_to_name(m, op.opcodeIndex) or "?"
                if n == "CUSTOM":
                    cc = m.operatorCodes[op.opcodeIndex].customCode
                    n = cc.decode() if isinstance(cc, (bytes, bytearray)) else str(cc)
                counts[n] = counts.get(n, 0) + 1
        info["operators"] = counts
        info["dispatch_ops"] = counts.get(DISPATCH_OP, 0)
        info["non_dispatch_ops"] = sum(v for k, v in counts.items() if k != DISPATCH_OP)
    except Exception as e:
        info["dispatch_ops"] = path.read_bytes().count(DISPATCH_OP.encode())
        info["non_dispatch_ops"] = None
        info["note"] = f"raw-search ({type(e).__name__})"
    if info["dispatch_ops"] == 0:
        info["verdict"] = "FAIL"
    elif info["non_dispatch_ops"] == 0:
        info["verdict"] = "PASS"
    else:
        info["verdict"] = "PART"
    return info

target = samsung_target.Target(samsung_target.SocModel.E9965)
manifest = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "purpose": "G1-B: 개정 4.4 새 모델 2종의 E9965 NPU 파티션 판정",
    "host": platform.platform(),
    "ai_edge_litert": getattr(ai_edge_litert, "__version__", "?"),
    "ai_edge_litert_sdk_samsung": getattr(sdk, "__version__", "?"),
    "target": repr(target),
    "models": [],
}
rows, reports = [], []

for mp in inputs:
    entry = {"input": mp.name, "input_sha256": sha256(mp), "input_size": mp.stat().st_size}
    print(f"\n=== compiling {mp.name} for {target!r} ===")
    t0 = time.time()
    try:
        result = aot_compile.aot_compile(str(mp), output_dir=str(OUT), target=[target], keep_going=True)
    except Exception as e:
        entry["error"] = f"{type(e).__name__}: {e}"
        print("[X]", entry["error"])
        rows.append((mp.stem, "-", "-", "EXCEPTION"))
        manifest["models"].append(entry); continue
    entry["compile_seconds"] = round(time.time() - t0, 1)
    rep = result.compilation_report(); print(rep); reports.append(f"### {mp.name}\n{rep}\n")
    entry["failed_backends"] = [f"{b.target_id}: {err}" for b, err in result.failed_backends]
    outs = []
    for backend, model in result.models_with_backend:
        dst = OUT / (mp.stem + backend.target_id_suffix + ".tflite")
        model.save(dst, export_only=True)
        ins = inspect(dst); outs.append(ins)
        ratio = ins["size"] / entry["input_size"]
        print(f"→ {dst.name}: {ins['size']:,} B ({ratio:.2f}× 원본), "
              f"dispatch={ins['dispatch_ops']}, non_dispatch={ins['non_dispatch_ops']}, {ins['verdict']}")
        rows.append((mp.stem, f"{ins['dispatch_ops']}", f"{ins['non_dispatch_ops']}", ins["verdict"]))
    entry["outputs"] = outs
    manifest["models"].append(entry)

(OUT / "aot_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT / "aot_report.txt").write_text("\n".join(reports), encoding="utf-8")

# ---------- 3. 판정표 --------------------------------------------------------
print("\n" + "=" * 68)
print(f"{'model':24s} {'dispatch':>9s} {'non-dispatch':>13s}  verdict")
print("-" * 68)
for name, d, nd, v in rows:
    print(f"{name:24s} {d:>9s} {nd:>13s}  {v}")
print("=" * 68)
print("""
읽는 법
  PASS  → 전 그래프 NPU. 그 task 는 npu_full cell 로 CPU/GPU 와 같은 3번째 기계가 된다
  PART  → 부분 위임. npu_partial cell 로 별도 표기하고 "순수 NPU 속도"라 부르지 않는다
          (조민규 계약의 gpu_assisted 와 같은 취급 — MULTITASK_EXPERIMENT_PROTOCOL §2)
  FAIL  → 그 task 는 NPU 미지원. 기계 적격성 제약 M_j 의 실증 근거가 되므로 이것도 결과다

산출물 크기가 원본의 약 0.5배면 가중치가 FP16 으로 저장된 것 = NPU 는 fp16 실행.
  → CPU/GPU(FP32) 와 수치 동등성(atol=1e-4, rtol=1e-3)은 통과하지 못한다.
  → NPU cell 판정은 품질 동등성(top-1/top-5 일치율, box IoU)으로 따로 설계할 것.

레포에 올릴 것: aot_manifest.json + 위 판정표.
올리지 말 것: *.tflite 원본과 컴파일 산출물 전부 (efficientdet 라이선스 경계).
""")
print(f"manifest: {OUT/'aot_manifest.json'}")
