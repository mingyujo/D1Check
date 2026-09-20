#!/usr/bin/env python3
"""S26 (Exynos 2600 = E9965) 용 LiteRT NPU AOT 컴파일 — Gate G1.

호스트 요구: Linux x86_64 (Google Colab 또는 WSL2 Ubuntu 24.04). Windows 네이티브에서는 컴파일 불가
(Samsung SDK 가 linux x86_64 전용). `--inspect` 만은 어디서나 됨.

준비 (한 번):
    python -m venv litert_env && source litert_env/bin/activate      # Colab 은 생략
    pip install --upgrade pip
    pip install ai-edge-litert-nightly ai-edge-litert-sdk-samsung-nightly
    # 두 번째 패키지 설치 중 Samsung 사이트에서 ai-litecore-ubuntu2404-v1.2.0.tar.gz 를
    # 자동으로 내려받는다 (setup.py). 실패하면 네트워크/프록시 문제 → 로그의 URL 로 수동 다운로드 후
    # site-packages/ai_edge_litert_sdk_samsung/data/ 에 풀어 넣는다.

실행:
    python s26_npu_aot_compile.py --model mobilenet_v1_1.0_224.tflite \
                                  --model mobilenet_v1_1.0_224_quant.tflite \
                                  --out compiled_e9965
    python s26_npu_aot_compile.py --inspect compiled_e9965/mobilenet_v1_1.0_224_Samsung_E9965.tflite

산출물:
    <out>/<모델명>_Samsung_E9965.tflite   NPU 바이트코드가 삽입된 LiteRT 모델 (runner 에 넣을 파일)
    <out>/aot_manifest.json               버전·SHA-256·파티션 통계 (provenance 용, runner 기록과 대조)
    <out>/aot_report.txt                  compilation_report() 원문

판정 기준 (계획서 G1):
    PASS  = 실패 0, DISPATCH_OP 존재, 비-dispatch 연산자 0개 (전 그래프 NPU)
    PART  = DISPATCH_OP 존재하나 CPU 잔여 연산자 있음 → 기록 후 진행 (partial delegation 명시)
    FAIL  = failed_backends 에 Samsung 포함 또는 DISPATCH_OP 없음
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

DISPATCH_OP = "DISPATCH_OP"

# ai-edge-litert-nightly 2.3.0.dev2026091x 패키징 버그 우회: libLiteRtCompilerPlugin_Samsung.so 가
# flatbuffers::ClassicLocale::instance_ (flatbuffers/util.cpp) 를 참조하는데 wheel 어디에도 없어
# "undefined symbol: _ZN11flatbuffers13ClassicLocale9instance_E" 로 플러그인 로드가 실패한다 (2026-09-19 Colab 실측).
# flatbuffers 원본과 같은 정의를 가진 .so 를 만들어 LD_PRELOAD 한다. 버그가 고쳐진 버전에서는 무해.
FB_SHIM_SRC = r"""
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
}  // namespace flatbuffers
"""


def build_fb_shim(out: Path) -> Path | None:
    """Compile the flatbuffers shim with g++ (Colab/WSL have it). Returns .so path or None."""
    import shutil
    import subprocess
    if not shutil.which("g++"):
        print("[!] g++ 없음 → flatbuffers shim 생략 (플러그인 로드 실패 시 'apt install g++')")
        return None
    src = out / "fb_classic_locale_shim.cpp"
    so = out / "libfb_classic_locale_shim.so"
    src.write_text(FB_SHIM_SRC, encoding="utf-8")
    r = subprocess.run(["g++", "-O2", "-shared", "-fPIC", "-o", str(so), str(src)], capture_output=True, text=True)
    if r.returncode != 0:
        print("[!] shim 빌드 실패:", r.stderr.strip()[:400])
        return None
    return so


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_model(path: Path) -> dict:
    """컴파일된 .tflite 에서 연산자 구성을 읽는다. ai_edge_litert 가 없으면 바이트 검색으로 대체."""
    info = {"file": str(path), "size": path.stat().st_size, "sha256": sha256(path)}
    try:
        from ai_edge_litert.tools import flatbuffer_utils as fu  # type: ignore
        m = fu.read_model(path)
        names = []
        for sg in m.subgraphs:
            for op in sg.operators:
                name = fu.opcode_to_name(m, op.opcodeIndex) or "?"
                if name == "CUSTOM":  # 커스텀 연산자는 customCode 가 실제 이름 (예: DISPATCH_OP)
                    cc = m.operatorCodes[op.opcodeIndex].customCode
                    name = cc.decode() if isinstance(cc, (bytes, bytearray)) else str(cc)
                names.append(name)
        counts = {}
        for n in names:
            counts[n] = counts.get(n, 0) + 1
        info["operators"] = counts
        info["dispatch_ops"] = counts.get(DISPATCH_OP, 0)
        info["non_dispatch_ops"] = sum(v for k, v in counts.items() if k != DISPATCH_OP)
        info["metadata"] = [md.name.decode() if isinstance(md.name, bytes) else str(md.name)
                            for md in (m.metadata or [])]
        info["method"] = "flatbuffer"
    except Exception as e:  # noqa: BLE001
        data = path.read_bytes()
        info["dispatch_ops"] = data.count(DISPATCH_OP.encode())
        info["non_dispatch_ops"] = None
        info["method"] = f"raw-search ({type(e).__name__}: {e})"
    if info["dispatch_ops"] == 0:
        info["verdict"] = "FAIL"
    elif info.get("non_dispatch_ops") == 0:
        info["verdict"] = "PASS"
    else:
        info["verdict"] = "PART" if info.get("non_dispatch_ops") else "PASS?"
    return info


def compile_models(models: list[Path], out: Path) -> int:
    if not (sys.platform == "linux" and platform.machine() in ("x86_64", "AMD64")):
        print("[X] Samsung AOT 는 Linux x86_64 에서만 동작한다. Colab 또는 WSL2 에서 실행할 것.")
        return 2
    try:
        import ai_edge_litert  # type: ignore
        from ai_edge_litert.aot import aot_compile  # type: ignore
        from ai_edge_litert.aot.vendors.samsung import target as samsung_target  # type: ignore
    except ImportError as e:
        print(f"[X] ai-edge-litert-nightly 가 없다: {e}\n    pip install ai-edge-litert-nightly")
        return 2
    sdk_ver, sdk_libs = None, None
    try:
        import ai_edge_litert_sdk_samsung as sdk  # type: ignore
        sdk_ver = getattr(sdk, "__version__", "?")
        sdk_libs = sdk.path_to_sdk_libs()
    except ImportError:
        print("[X] ai-edge-litert-sdk-samsung-nightly 가 없다.\n    pip install ai-edge-litert-sdk-samsung-nightly")
        return 2
    if not sdk_libs or not Path(sdk_libs).is_dir():
        print(f"[X] Samsung SDK 라이브러리 폴더가 비어 있다: {sdk_libs}\n"
              "    설치 중 LiteCore tar.gz 다운로드가 실패한 것. 스크립트 머리말의 수동 절차 참조.")
        return 2
    so_files = sorted(p.name for p in Path(sdk_libs).glob("*.so"))
    print(f"ai_edge_litert {getattr(ai_edge_litert, '__version__', '?')} / samsung sdk {sdk_ver}")
    print(f"SDK libs: {sdk_libs} ({len(so_files)} .so: {', '.join(so_files[:6])}{' ...' if len(so_files) > 6 else ''})")

    out.mkdir(parents=True, exist_ok=True)
    import os
    shim = build_fb_shim(out)
    if shim:
        prev = os.environ.get("LD_PRELOAD", "")
        os.environ["LD_PRELOAD"] = f"{shim}:{prev}" if prev else str(shim)  # apply_plugin_main 이 상속
        print(f"flatbuffers shim: LD_PRELOAD={shim}")
    target = samsung_target.Target(samsung_target.SocModel.E9965)
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": platform.platform(),
        "ai_edge_litert": getattr(ai_edge_litert, "__version__", "?"),
        "ai_edge_litert_sdk_samsung": sdk_ver,
        "sdk_libs": so_files,
        "flatbuffers_shim_preloaded": bool(shim),
        "target": repr(target),
        "models": [],
    }
    rc = 0
    report_lines = []
    for mp in models:
        if not mp.is_file():
            print(f"[X] 없음: {mp}")
            rc = 1
            continue
        entry = {"input": str(mp), "input_sha256": sha256(mp), "input_size": mp.stat().st_size}
        print(f"\n=== compiling {mp.name} for {target!r} ===")
        t0 = time.time()
        try:
            result = aot_compile.aot_compile(str(mp), output_dir=str(out), target=[target], keep_going=True)
        except Exception as e:  # noqa: BLE001
            entry["error"] = f"{type(e).__name__}: {e}"
            print(f"[X] 예외: {entry['error']}")
            manifest["models"].append(entry)
            rc = 1
            continue
        entry["compile_seconds"] = round(time.time() - t0, 1)
        rep = result.compilation_report()
        report_lines.append(f"### {mp.name}\n{rep}\n")
        print(rep)
        entry["failed_backends"] = [f"{b.target_id}: {err}" for b, err in result.failed_backends]
        outputs = []
        for backend, model in result.models_with_backend:
            name = mp.stem + backend.target_id_suffix + ".tflite"
            dst = out / name
            model.save(dst, export_only=True)
            ins = inspect_model(dst)
            outputs.append(ins)
            print(f"→ {dst.name}: {ins['size']:,} B, dispatch_ops={ins['dispatch_ops']}, "
                  f"non_dispatch_ops={ins['non_dispatch_ops']}, verdict={ins['verdict']}")
            if ins["verdict"] == "FAIL":
                rc = 1
        entry["outputs"] = outputs
        if entry["failed_backends"]:
            rc = 1
        manifest["models"].append(entry)

    (out / "aot_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "aot_report.txt").write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nmanifest: {out / 'aot_manifest.json'}\nreport:   {out / 'aot_report.txt'}")
    print("G1 판정:", "PASS/PART (위 verdict 참조)" if rc == 0 else "FAIL — 계획서 §4 G1 실패 분기 참조")
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", action="append", type=Path, default=[], help="입력 .tflite (반복 가능)")
    ap.add_argument("--out", type=Path, default=Path("compiled_e9965"))
    ap.add_argument("--inspect", type=Path, help="컴파일된 .tflite 만 검사")
    a = ap.parse_args()
    if a.inspect:
        info = inspect_model(a.inspect)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0 if info["verdict"] != "FAIL" else 1
    if not a.model:
        ap.error("--model 을 하나 이상 주거나 --inspect 를 쓸 것")
    return compile_models(a.model, a.out)


if __name__ == "__main__":
    sys.exit(main())
