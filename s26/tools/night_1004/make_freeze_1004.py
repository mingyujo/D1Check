"""Night 1004: build the pre-measurement freeze ledger D1_ondevice\\sim\\out_1004\\freeze_1004.txt (1-A).
Reads files and git metadata only. Never touches the phone, never writes the adb serial."""
import datetime
import hashlib
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
WD = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
OD = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice"
OUT = os.path.join(OD, "sim", "out_1004", "freeze_1004.txt")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git(*a):
    return subprocess.run(["git", *a], cwd=WD, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def gitlog(rel):
    return git("log", "-1", "--format=%h %cI", "--", rel)


def mtime(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")


L = []
now = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
L.append(f"# 밤 1004 동결 원장 (측정 전 SHA · 시각, KST) — 생성 {now}")
L.append("## 사전 등록 · 체인기록 · P1c 문서 (OneDrive 사본 SHA · mtime / 레포 사본 SHA · git blob · 마지막 커밋)")
pairs = [
    ("밤1004_사전등록_v1.md", os.path.join(OD, "sim", "밤1004_사전등록_v1.md"), "d1sim/docs/밤1004_사전등록_v1.md"),
    ("밤1004_체인기록.md", os.path.join(OD, "sim", "밤1004_체인기록.md"), "d1sim/docs/밤1004_체인기록.md"),
    ("v2_예측_밤1004.md", os.path.join(OD, "sim", "v2_예측_밤1004.md"), "d1sim/docs/v2_예측_밤1004.md"),
    ("SIM_V2_결과_1004.md", os.path.join(OD, "sim", "SIM_V2_결과_1004.md"), "d1sim/docs/SIM_V2_결과_1004.md"),
    ("작업결과_1004_시뮬v2.md", os.path.join(OD, "작업결과_1004_시뮬v2.md"), "d1sim/docs/작업결과_1004_시뮬v2.md"),
]
for name, od_path, rel in pairs:
    od_sha = sha(od_path) if os.path.exists(od_path) else "없음"
    od_mt = mtime(od_path) if os.path.exists(od_path) else "-"
    rp = os.path.join(WD, rel.replace("/", os.sep))
    r_sha = sha(rp) if os.path.exists(rp) else "없음"
    blob = git("rev-parse", f"HEAD:{rel}") or "없음"
    same = "같음" if od_sha == r_sha else "다름"
    L.append(f"{name}")
    L.append(f"  OneDrive {od_sha}  mtime {od_mt}")
    L.append(f"  레포     {r_sha}  ({same})  blob {blob}  커밋 {gitlog(rel)}")
L.append("## 예측 JSON (P1c 동결)")
for rel in ["d1sim/out/night_1004_prediction_v2.json", "d1sim/out/night_1004_prediction_v1.json"]:
    p = os.path.join(WD, rel.replace("/", os.sep))
    L.append(f"{sha(p)} *{rel}  blob {git('rev-parse', 'HEAD:' + rel)}  커밋 {gitlog(rel)}")
L.append("## 체인 canonical SHA (py tools\\npu_chain.py validate) + 파일 SHA · 커밋")
for c in ["n50_probe_npu_v1", "g50_probe_gpu_v1", "gpu_idle300_v1", "npu_idle300_v1"]:
    rel = f"tools/chains/{c}.json"
    r = subprocess.run(["py", "-X", "utf8", r"tools\npu_chain.py", "validate", rel.replace("/", "\\")], cwd=WD,
                       capture_output=True, text=True, encoding="utf-8")
    try:
        j = json.loads(r.stdout)
        canon, tot, segs = j.get("sha256"), j.get("total_duration_s"), j.get("segment_count")
    except Exception:
        canon, tot, segs = f"PARSE_FAIL exit={r.returncode}", None, None
    L.append(f"{c} canonical {canon} total_s {tot} segments {segs} exit {r.returncode}  file {sha(os.path.join(WD, rel.replace('/', os.sep)))}  커밋 {gitlog(rel)}")
L.append("## import 대상 판정기 (무변경 — 프롬프트 접두와 대조)")
judges = [
    ("ea282d4a", os.path.join(OD, "sim", "m1m2_judge_1002.py")),
    ("379039dd", os.path.join(WD, "d1sim", "tools", "fit_throttle_v1.py")),
    ("a5ceab41", os.path.join(OD, "sim", "night1003_judge.py")),
    ("516116b4", os.path.join(OD, "sim", "night1003_judge_pacing.py")),
    ("bd4bbd87", os.path.join(OD, "sim", "night1003_judge_effblock.py")),
    ("cc7d1559", os.path.join(OD, "sim", "night1003_judge_npu600.py")),
    ("31822678", os.path.join(OD, "sim", "throttle_curve_0928.py")),
]
for pre, p in judges:
    s = sha(p)
    L.append(f"{s} *{p}  기대 접두 {pre}… → {'일치' if s.startswith(pre) else '불일치'}")
L.append("## 설치본 · 모델 (0단계 adb, 01:1x)")
L.append("npu-runner base.apk 5ac485e382ebc82e380e6161ca6301ff89e9ab3d8be49b5d5388ab28b42c1033 lastUpdateTime 2026-10-02 23:56:58 versionCode 1 (재설치 없음)")
L.append("EffNet 기기 모델 /data/local/tmp/efficientnet_lite0.tflite 6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0 (18,582,189 B)")
aot = os.path.join(WD, "npu-runner", "src", "main", "assets", "models", "efficientnet_lite0_Samsung_E9965.tflite")
L.append(f"EffNet AOT 체크아웃 {sha(aot) if os.path.exists(aot) else '없음'} (EffN420 dry-run model_expected 311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31)")
L.append(f"HEAD(측정 시작) {git('rev-parse', 'HEAD')} · origin/s26-measure {git('rev-parse', 'origin/s26-measure')}")
L.append("## d_min (체인기록 §0) = 1 (rest_idle duty 1 = 10 s 주기 100 ms 가동) — 대체 순서 0→1→5→10 의 다음 값은 5")
L.append("## dry-run (1-A, 실제 시리얼 · 출력은 results\\S26_night_1004_host\\dryrun_*.txt, 시리얼 <SERIAL> 치환)")
L.append("N50P exit 0 · config.duration_s 960 · npu.chain n50_probe_npu_v1 · 960 · a0ae4d7d… · max_inference_spans 1,500,000 (01:20:16)")
L.append("EffN420 exit 0 · duration 420 · model_asset models/efficientnet_lite0_Samsung_E9965.tflite · model_expected 311e4aac… · spans 1,000,000 (01:20:16)")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(L) + "\n")
print("\n".join(L))
