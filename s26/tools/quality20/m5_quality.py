"""M5 품질 연결 (등록 d1sim/docs/상태분리_사전등록_v2.md §3 Q1 · Q2 · Q3) — phone runs + judge. COMMITTED BEFORE THE PHONE RUN.

  set ANDROID_SERIAL=<ip:port>
  py -3 -X utf8 s26/tools/quality20/m5_quality.py run-q1 --run-id q1_1012a --apk-sha <installed request-runner sha> [--backends CPU,GPU,NPU]
  py -3 -X utf8 s26/tools/quality20/m5_quality.py run-q2 --run-id q2_1012_fp32 --precision FP32 --apk-sha <installed quality-runner sha>
  py -3 -X utf8 s26/tools/quality20/m5_quality.py judge --q1 results/S26_M5_Q1_q1_1012a --q2 NONE=results/S26_M5_Q2_q2_1012_none
      --q2 FP32=results/S26_M5_Q2_q2_1012_fp32 [--q2 FP16=...] --out <dir> [--request-runner-apk-sha ..] [--quality-runner-apk-sha ..]

run-q1 = q20_run.Runner (imported, unchanged) pointed at request-runner's InputListActivity (package com.example.d1check.requestrunner,
  output files/q1, intent d1_q1_manifest · d1_q1_backend · d1_q1_run_id). Same pushed inputs as Q20 (/data/local/tmp/quality20: 20 canonical
  tensors + 2 models, SHA-verified); the manifest = q20_common.build_app_manifest (mixreq settings: CPU numThreads 1 · GPU FP32 · NPU AOT) +
  png_check (00575b… canonical PNG + labels, /data/local/tmp/quality20/q1png/) → the one image also goes through the request path.
  Logcat marks use the tag D1Q1 with the Q20 mark grammar, so q20_evidence is reused with LOG_TAG = "D1Q1".
run-q2 = q20_run.Runner on quality-runner GPU only, with the extra d1_q2_gpu_precision (NONE = no gpuOptions = 기본 · FP32 · FP16).
judge:
  Q1 → q1_judge.json = q20_judge.judge_run (imported; Q20 허용식 · top-1 · top-5 · 판정 이름 = Q20 등록의 이름만) on the Q1 run + evidence
       (q20_evidence with D1Q1) + png_check rows + Q1-vs-Q20 run0 bit comparison per backend (기록).
  Q2 → q2_compare.json: GPU run0 outputs NONE vs FP32 (and FP16 if given): per image max |Δ| · top-1 equal · top-5 order equal · bit equal +
       counts. 기술만 (판정 이름 없음, 등록 §3). If the API had been missing the text would be "API 없음 — GPU 실제 정밀도 미확인 유지".
  Q3 → q3_npu_fp16.json: Q1 NPU run0 vs Q1 CPU run0 (same request-runner path): top-1 same n/20 · top-5 set same n/20 · cosine per image.
       Name (등록 §3 Q3, fixed before results): 20/20 top-1 AND top-5 set ≥ 19/20 AND cosine ≥ 0.999 for all 20 →
       "NPU FP16 합격 (request-runner · 20장)", otherwise "NPU FP16 불합격". Q20 NPU numbers are quoted as reference only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q20_common as QC  # noqa: E402
import q20_run as QR  # noqa: E402

Q3_PASS = "NPU FP16 합격 (request-runner · 20장)"
Q3_FAIL = "NPU FP16 불합격"
Q3_COSINE_MIN = 0.999
Q3_TOP5_SET_MIN = 19
RR_PACKAGE = "com.example.d1check.requestrunner"
QR_PACKAGE = "com.example.d1check.qualityrunner"
PNG_SAMPLE = "00575b9132bb3746"
PNG_SHA256 = "3e8b925feafbfe5fdd4efb9d7911f445a3212100fa73744f6fd855cf6160f1ab"
REPO = QC.REPO
DEFAULT_PNG = REPO / "local_inputs" / "canonical_v123" / f"{PNG_SAMPLE}.png"
DEFAULT_LABELS = REPO / "local_inputs" / "reference_pc" / "labels_without_background.txt"


def use_request_runner():
    """Point the imported q20 modules at request-runner's input-list mode (module constants only)."""
    QC.APP_PACKAGE = RR_PACKAGE
    QC.APP_ACTIVITY = f"{RR_PACKAGE}/.InputListActivity"
    QC.APP_OUTPUT_DIR = f"/storage/emulated/0/Android/data/{RR_PACKAGE}/files/q1"
    QC.MIXREQ_APP_PACKAGE = QR_PACKAGE        # "other app, untouched" record = quality-runner in this mode
    QC.LOG_TAG = "D1Q1"


def rewrite_am_start(argv: list[str], mode: str, q1_manifest: str | None, precision: str | None) -> list[str]:
    """q20_run.Runner.run_backend starts the app with the Q20 extras; translate them for Q1 / add the Q2 extra."""
    argv = list(argv)
    if not (len(argv) > 2 and argv[0] == "shell" and argv[1] == "am" and argv[2] == "start"):
        return argv
    if mode == "q1":
        names = {"d1_q20_manifest": "d1_q1_manifest", "d1_q20_backend": "d1_q1_backend", "d1_q20_run_id": "d1_q1_run_id"}
        out = []
        i = 0
        while i < len(argv):
            if argv[i] == "--es" and i + 2 < len(argv) and argv[i + 1] in names:
                value = q1_manifest if argv[i + 1] == "d1_q20_manifest" else argv[i + 2]
                out += ["--es", names[argv[i + 1]], value]
                i += 3
            else:
                out.append(argv[i])
                i += 1
        return out
    if mode == "q2":
        return argv + ["--es", "d1_q2_gpu_precision", precision]
    return argv


class M5Runner(QR.Runner):
    def __init__(self, args, mode: str):
        super().__init__(args)
        self.mode = mode
        self.q1_manifest = None
        self.record["m5_mode"] = mode
        if mode == "q2":
            self.record["q2_gpu_precision"] = args.precision

    def adb(self, *argv, timeout=60, check=False):
        return super().adb(*rewrite_am_start(list(argv), self.mode, self.q1_manifest, getattr(self.args, "precision", None)), timeout=timeout, check=check)

    def push_all(self):
        super().push_all()
        if self.mode != "q1":
            return
        dev = f"{QC.DEVICE_ROOT}/q1png"
        self.shell(f"mkdir -p {dev}")
        files = [("png", Path(self.args.png), f"{dev}/{PNG_SAMPLE}.png", PNG_SHA256),
                 ("labels", Path(self.args.labels), f"{dev}/labels_without_background.txt", QC.LABELS_SHA256)]
        for name, host, device, sha in files:
            if QC.sha256_file(host) != sha:
                raise SystemExit(f"{name} {host} sha != registered {sha}")
            present = self.shell(f"sha256sum {device} 2>/dev/null").split()
            if not (present and present[0] == sha):
                self.adb("push", str(host), device, timeout=120, check=True)
                after = self.shell(f"sha256sum {device}").split()
                if not self.dry and (not after or after[0] != sha):
                    raise RuntimeError(f"pushed {name} SHA mismatch")
        m = QC.build_app_manifest(self.manifest, self.run_id, QC.ORIGINAL_MODEL_SHA256, QC.AOT_MODEL_SHA256)
        m["png_check"] = dict(sample_id=PNG_SAMPLE, image_path=f"{dev}/{PNG_SAMPLE}.png", image_sha256=PNG_SHA256,
                              labels_path=f"{dev}/labels_without_background.txt", labels_sha256=QC.LABELS_SHA256)
        m["m5"] = dict(mode="q1", path="request-runner InputListActivity", registration="d1sim/docs/상태분리_사전등록_v2.md §3 Q1")
        local = self.host / "q1_manifest.json"
        QC.write_json(local, m)
        sha = QC.sha256_file(local)
        device_manifest = f"{QC.DEVICE_ROOT}/q1_manifest_{self.run_id}.json"
        self.adb("push", str(local), device_manifest, timeout=120, check=True)
        after = self.shell(f"sha256sum {device_manifest}").split()
        if not self.dry and (not after or after[0] != sha):
            raise RuntimeError("pushed q1 manifest SHA mismatch")
        self.q1_manifest = device_manifest
        self.record["q1_manifest_sha256"] = sha
        self.log(f"q1 manifest pushed sha256={sha} -> {device_manifest}")


# ----------------------------------------------------------------------------------------------- judge helpers
def run0(root: Path, backend: str, index: int, sample_id: str) -> list[float] | None:
    p = root / backend / "device" / f"{index:02d}_{sample_id}.run0.f32le"
    return QC.read_f32le(p, QC.OUTPUT_ELEMENTS) if p.is_file() else None


def run0_bytes(root: Path, backend: str, index: int, sample_id: str) -> bytes | None:
    p = root / backend / "device" / f"{index:02d}_{sample_id}.run0.f32le"
    return p.read_bytes() if p.is_file() else None


def q3(samples: list[tuple[int, str]], npu: dict, cpu: dict) -> dict:
    """samples = [(index, sample_id)]; npu/cpu = {sample_id: list[float] | None}."""
    rows = []
    for i, sid in samples:
        a, b = npu.get(sid), cpu.get(sid)
        if a is None or b is None:
            rows.append(dict(index=i, sample_id=sid, available=False, top1_same=False, top5_set_same=False, cosine=None))
            continue
        ta, tb = QC.topk(a), QC.topk(b)
        rows.append(dict(index=i, sample_id=sid, available=True, top1_npu=ta[0][0], top1_cpu=tb[0][0], top1_same=ta[0][0] == tb[0][0],
                         top5_npu=[k for k, _ in ta], top5_cpu=[k for k, _ in tb], top5_set_same=set(k for k, _ in ta) == set(k for k, _ in tb),
                         top5_order_same=[k for k, _ in ta] == [k for k, _ in tb], cosine=QC.cosine(a, b),
                         max_abs_diff=max(abs(x - y) for x, y in zip(a, b))))
    n = len(samples)
    top1 = sum(1 for r in rows if r["top1_same"])
    top5 = sum(1 for r in rows if r["top5_set_same"])
    cos_ok = sum(1 for r in rows if r["cosine"] is not None and r["cosine"] >= Q3_COSINE_MIN)
    passed = n == QC.SAMPLE_COUNT and top1 == n and top5 >= Q3_TOP5_SET_MIN and cos_ok == n
    cos = [r["cosine"] for r in rows if r["cosine"] is not None]
    return dict(rule=f"top-1 {QC.SAMPLE_COUNT}/{QC.SAMPLE_COUNT} AND top-5 set ≥ {Q3_TOP5_SET_MIN}/{QC.SAMPLE_COUNT} AND cosine ≥ {Q3_COSINE_MIN} (all 20)",
                verdict=Q3_PASS if passed else Q3_FAIL, images=n, top1_same=top1, top5_set_same=top5,
                top5_order_same=sum(1 for r in rows if r.get("top5_order_same")), cosine_ge_min=cos_ok,
                cosine_min=min(cos) if cos else None, cosine_median=sorted(cos)[len(cos) // 2] if cos else None,
                max_abs_diff_max=max((r["max_abs_diff"] for r in rows if r.get("max_abs_diff") is not None), default=None), rows=rows)


def q2_compare(samples: list[tuple[int, str]], runs: dict[str, Path], base: str = "NONE", forced: str = "FP32") -> dict:
    out = dict(description_only=True, base=base, forced=forced, pairs={})
    names = list(runs)
    for other in [n for n in names if n != base]:
        rows = []
        for i, sid in samples:
            a, b = run0(runs[base], "GPU", i, sid), run0(runs[other], "GPU", i, sid)
            ab, bb = run0_bytes(runs[base], "GPU", i, sid), run0_bytes(runs[other], "GPU", i, sid)
            if a is None or b is None:
                rows.append(dict(index=i, sample_id=sid, available=False))
                continue
            ta, tb = QC.topk(a), QC.topk(b)
            rows.append(dict(index=i, sample_id=sid, available=True, bit_equal=ab == bb, max_abs_diff=max(abs(x - y) for x, y in zip(a, b)),
                             top1_same=ta[0][0] == tb[0][0], top5_order_same=[k for k, _ in ta] == [k for k, _ in tb], cosine=QC.cosine(a, b)))
        ok = [r for r in rows if r["available"]]
        out["pairs"][f"{base}_vs_{other}"] = dict(images=len(rows), available=len(ok), bit_equal=sum(1 for r in ok if r["bit_equal"]),
                                                  max_abs_diff_max=max((r["max_abs_diff"] for r in ok), default=None),
                                                  top1_same=sum(1 for r in ok if r["top1_same"]), top5_order_same=sum(1 for r in ok if r["top5_order_same"]),
                                                  cosine_min=min((r["cosine"] for r in ok if r["cosine"] is not None), default=None), rows=rows)
    return out


def judge(args) -> int:
    import q20_evidence as QE
    import q20_judge as QJ
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ref = QJ.load_reference(Path(args.reference))
    samples = [(r["index"], r["sample_id"]) for r in ref["refs"]]
    result = dict(schema="s26-m5-quality-v1", registration="d1sim/docs/상태분리_사전등록_v2.md §3 (SHA-256 717bc4e5…)", judged_at=QC.now_iso())
    if args.q1:
        q1 = Path(args.q1)
        saved = QC.LOG_TAG
        QC.LOG_TAG = "D1Q1"
        try:
            run_id = QC.read_json(q1 / "host" / "run_record.json")["run_id"]
            evidence = QE.evaluate_run(q1, run_id)
        finally:
            QC.LOG_TAG = saved
        QC.write_json(out / "q1_evidence.json", evidence)
        j = QJ.judge_run(ref, q1, evidence, args.request_runner_apk_sha)
        j["path"] = "request-runner InputListActivity (M5 Q1) — 판정 이름 = Q20 등록 (품질20장_사전등록_v1.md §3) 이름만"
        png = {}
        for b in QC.BACKENDS:
            p = q1 / b / "device" / "png_check.json"
            png[b] = QC.read_json(p) if p.is_file() else None
            if png[b]:
                png[b] = {k: v for k, v in png[b].items() if k != "request_path_record"}
        j["png_check"] = png
        if args.q20:
            q20 = Path(args.q20)
            j["vs_q20_run0_bit_equal"] = {b: sum(1 for i, sid in samples if run0_bytes(q1, b, i, sid) is not None
                                                 and run0_bytes(q1, b, i, sid) == run0_bytes(q20, b, i, sid)) for b in QC.BACKENDS}
            j["vs_q20_root"] = str(q20)
        QC.write_json(out / "q1_judge.json", j)
        result["q1"] = {b: dict(verdict=r["verdict"], tags=r["tags"], top1=r["aggregate"]["top1_equal"], top5_order=r["aggregate"]["top5_order_equal"],
                                cosine_min=r["aggregate"]["cosine_min"], violations=r["aggregate"]["violations_total"],
                                evidence=r.get("evidence_verdict")) for b, r in j["backends"].items()}
        npu = {sid: run0(q1, "NPU", i, sid) for i, sid in samples}
        cpu = {sid: run0(q1, "CPU", i, sid) for i, sid in samples}
        r3 = q3(samples, npu, cpu)
        r3.update(registration="상태분리_사전등록_v2.md §3 Q3 (기준은 Q20 NPU 결과를 본 뒤 고정 — 판정은 새 자료 Q1 로만)",
                  q20_reference_only="Q20 NPU: top-1 20/20 · top-5 순서 19/20 · cosine 최소 0.99996 (참조 — 판정에 쓰지 않음)",
                  q1_root=str(q1), npu_evidence=j["backends"].get("NPU", {}).get("evidence_verdict"))
        QC.write_json(out / "q3_npu_fp16.json", r3)
        result["q3"] = {k: r3[k] for k in ("verdict", "top1_same", "top5_set_same", "cosine_ge_min", "cosine_min")}
    if args.q2:
        runs = {}
        for item in args.q2:
            name, _, path = item.partition("=")
            runs[name] = Path(path)
        if "NONE" in runs and "FP32" in runs:
            c = q2_compare(samples, runs)
            c.update(api="LiteRT 2.2.0 CompiledModel.GpuOptions.Precision {DEFAULT, FP16, FP32, FP16_WITH_FP32_ACCUM} — 있음",
                     runs={k: str(v) for k, v in runs.items()}, apk_sha256=args.quality_runner_apk_sha,
                     note="기본 = gpuOptions 를 넣지 않음 (NONE) · FP16 은 옵션이 먹는지 보는 보조 기술 (등록 밖)")
            for name, root in runs.items():
                s = root / "GPU" / "device" / "summary.json"
                c.setdefault("summaries", {})[name] = (lambda d: dict(status=d.get("status"), images_ok=d.get("images_ok"),
                                                                      gpu_options=(d.get("compiled_model_options") or {}).get("gpu_options")))(QC.read_json(s)) if s.is_file() else None
            QC.write_json(out / "q2_compare.json", c)
            result["q2"] = {k: {kk: v[kk] for kk in ("available", "bit_equal", "max_abs_diff_max", "top1_same", "top5_order_same")} for k, v in c["pairs"].items()}
    QC.write_json(out / "m5_quality_summary.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run-q1", "run-q2"):
        p = sub.add_parser(name)
        p.add_argument("--run-id", required=True)
        p.add_argument("--apk", help="local APK copy (expected SHA computed from it)")
        p.add_argument("--apk-sha")
        p.add_argument("--inputs", default=str(QC.DEFAULT_INPUTS_DIR))
        p.add_argument("--original-model", default=str(QC.DEFAULT_ORIGINAL_MODEL))
        p.add_argument("--aot-model", default=str(QC.DEFAULT_AOT_MODEL))
        p.add_argument("--backends", default="CPU,GPU,NPU" if name == "run-q1" else "GPU")
        p.add_argument("--results")
        p.add_argument("--rest-s", type=int, default=60)
        p.add_argument("--timeout-s", type=int, default=900)
        p.add_argument("--skin-max", type=float, default=34.0)
        p.add_argument("--bat-max", type=float, default=32.0)
        p.add_argument("--skip-thermal", action="store_true")
        p.add_argument("--dry-run", action="store_true")
        if name == "run-q1":
            p.add_argument("--png", default=str(DEFAULT_PNG))
            p.add_argument("--labels", default=str(DEFAULT_LABELS))
        else:
            p.add_argument("--precision", required=True, choices=("NONE", "FP32", "FP16"))
    j = sub.add_parser("judge")
    j.add_argument("--q1")
    j.add_argument("--q20", help="Q20 run root (e.g. results/S26_Q20_q20_1009a) for the run0 bit comparison (기록)")
    j.add_argument("--q2", action="append", help="NAME=root, NAME in NONE / FP32 / FP16")
    j.add_argument("--reference", default=str(QC.DEFAULT_INPUTS_DIR))
    j.add_argument("--out", required=True)
    j.add_argument("--request-runner-apk-sha")
    j.add_argument("--quality-runner-apk-sha")
    args = ap.parse_args()
    if args.cmd == "judge":
        return judge(args)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", args.run_id):
        raise SystemExit("run_id must match [A-Za-z0-9_.-]{1,64}")
    if args.cmd == "run-q1":
        use_request_runner()
        args.results = args.results or str(REPO / "results" / f"S26_M5_Q1_{args.run_id}")
        return M5Runner(args, "q1").run()
    if args.backends.strip().upper() != "GPU":
        raise SystemExit("run-q2 is GPU only")
    args.results = args.results or str(REPO / "results" / f"S26_M5_Q2_{args.run_id}")
    return M5Runner(args, "q2").run()


if __name__ == "__main__":
    sys.exit(main())
