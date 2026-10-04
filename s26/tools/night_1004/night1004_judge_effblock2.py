# -*- coding: utf-8 -*-
"""night1004_judge_effblock2.py — EffNet 확인 블록 (블록 2, 8런) 분석 + 두 블록 대조. `밤1004_사전등록_v1.md` §6 글자 그대로.
런·셀·상호작용 분석은 `night1003_judge_effblock.py` (SHA bd4bbd87…) 를 import 해 그대로 쓴다 (복사·수정 금지). 이 파일이 바꾸는 것은
순서 목록 (블록 2 거울) 과 두 블록 대조뿐. results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트.
확인 블록 — 개발 블록과 나란히, 재보정 없음, CI·검정력 주장 없음. 결과가 아슬아슬해도 블록을 늘리지 않는다.

  py night1004_judge_effblock2.py selftest
  py night1004_judge_effblock2.py block2 <result_dir> [<result_dir> ...] [--block1 sim\\out_1003\\EffB1_block.json] [--gate-log csv] [--no-evidence] [--out f.json]

규칙 (§6):
  순서 (블록 2, 자원 순서를 바꾼 거울): G50 → G100 → C50 → C100 → C100 → C50 → G100 → G50 · seed 20261003 · preflight off (운영, 판정 무관)
  런·셀 분석 = night1003_judge_effblock.block_report 그대로 (런별 run_only 중앙 · write+run+read 중앙 · 추론 수 · SKIN 상승 · 잠정 전력 · 자원 증거 규칙 v1)
  두 블록 대조: 셀마다 |블록 2 평균 − 블록 1 평균| / 블록 1 평균 ≤ 3 % → "블록 간 재현", 아니면 "블록 간 차이" (기술) — 주 지표 run_only 중앙
       (블록의 주 지연, 블록 1 과 같은 정의); write+run+read 는 같은 식으로 기술만. 경계 비교는 부동소수 오차 1e-12 허용
  CPU 상호작용: 블록 2 의 run-only d50/d100 비 (셀 평균 비) 가 창 [0.8645, 0.8998] (= MobileNet C5 0.88217 × (1 ± 0.02), 블록 1 과 같은 창)
       밖 → "상호작용 있음 — 2블록 확인", 안 → "확인 실패 — 결론 보류" · GPU d50/d100 비는 기술
  게이트 기록: gate_log CSV 의 label "03_<nn>_…" (3단계 순번) 통과 행
"""
import argparse, csv, importlib.util, json, os, re, shutil, sys, tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
OD_SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _first_existing(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(paths[0])


_EB_PATH = _first_existing(os.path.join(HERE, "night1003_judge_effblock.py"), os.path.join(OD_SIM, "night1003_judge_effblock.py"),
                           os.path.join(REPO, "s26", "tools", "night_1003", "night1003_judge_effblock.py"))
EB = _load_module("night1003_judge_effblock", _EB_PATH)
JudgeError, dumps = EB.JudgeError, EB.dumps

BLOCK2_ORDER = ["G50", "G100", "C50", "C100", "C100", "C50", "G100", "G50"]
REPRO_TOL = 0.03
EPS = 1e-12
WINDOW = (EB.MOBILENET_C5_RUN_ONLY_D50_D100 * (1 - EB.INTERACTION_TOL), EB.MOBILENET_C5_RUN_ONLY_D50_D100 * (1 + EB.INTERACTION_TOL))
BLOCK1_DEFAULT = os.path.join(OD_SIM, "out_1003", "EffB1_block.json")
HEADER = "확인 블록 — 개발 블록과 나란히, 재보정 없음, CI·검정력 주장 없음 (결과가 아슬아슬해도 블록을 늘리지 않는다)"


def _sha(p):
    import hashlib
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_gate2(path):
    rows = {}
    if not path or not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m = re.match(r"03_(\d+)_", r.get("label", ""))
            if m and r.get("pass") == "True":
                rows[int(m.group(1))] = dict(label=r["label"], local_time=r["local_time"], waited_s=int(r["waited_s"]), SKIN=float(r["SKIN"]),
                                             AP=float(r["AP"]), BAT=float(r["BAT"]), soc=int(r["soc"]))
    return rows


def _cell_mean(block, cell, key):
    return (((block or {}).get("cells") or {}).get(cell) or {}).get(key, {}).get("mean")


def compare_blocks(b2, b1):
    out = dict(rule="셀마다 |블록 2 평균 − 블록 1 평균| / 블록 1 평균 ≤ 3 % → 블록 간 재현, 아니면 블록 간 차이 (기술) — 주 지표 run_only 중앙",
               block1_present=b1 is not None, cells={})
    if b1 is None:
        out["note"] = "블록 1 자료 없음 — 대조 안 함"
        return out
    for c in ("C50", "C100", "G50", "G100"):
        row = {}
        for key, primary in (("run_only_median_ms", True), ("latency_median_ms", False)):
            m1, m2 = _cell_mean(b1, c, key), _cell_mean(b2, c, key)
            if m1 is None or m2 is None or m1 == 0:
                row[key] = dict(block1_mean=m1, block2_mean=m2, rel_diff=None,
                                verdict="판정 불가 (셀 결측)" if primary else "—")
            else:
                rel = abs(m2 - m1) / m1
                v = ("블록 간 재현" if rel <= REPRO_TOL + EPS else "블록 간 차이") if primary else "기술만"
                row[key] = dict(block1_mean=m1, block2_mean=m2, rel_diff=rel, verdict=v)
        out["cells"][c] = row
    return out


def interaction2(b2, b1):
    r = (b2.get("interaction_cpu") or {}).get("ratio_run_only_d50_d100")
    if r is None:
        v = "판정 불가 (C50 또는 C100 셀 결측)"
    elif WINDOW[0] <= r <= WINDOW[1]:
        v = "확인 실패 — 결론 보류"
    else:
        v = "상호작용 있음 — 2블록 확인"
    b1r = None if b1 is None else (b1.get("interaction_cpu") or {}).get("ratio_run_only_d50_d100")
    b1v = None if b1 is None else (b1.get("interaction_cpu") or {}).get("verdict")
    g2 = (b2.get("interaction_gpu") or {}).get("ratio_run_only_d50_d100")
    g1 = None if b1 is None else (b1.get("interaction_gpu") or {}).get("ratio_run_only_d50_d100")
    return dict(rule="블록 2 run-only CPU d50/d100 비가 창 [0.8645, 0.8998] 밖 → 상호작용 있음 — 2블록 확인, 안 → 확인 실패 — 결론 보류",
                window=list(WINDOW), block2_ratio=r, verdict=v, block1_ratio=b1r, block1_verdict=b1v,
                gpu=dict(block2_ratio=g2, block1_ratio=g1, verdict="기술만 (GPU d50/d100 비)"))


def block2_report(result_dirs, block1=None, with_evidence=True, gate_rows=None):
    B = EB.block_report(result_dirs, with_evidence, gate_rows)
    obs = B["design"]["observed_order"]
    B["design"]["block1_mirror_check_from_import"] = dict(order=EB.MIRROR_ORDER, matches=B["design"].pop("order_matches_mirror"))
    B["design"]["block2_order"] = BLOCK2_ORDER
    B["design"]["order_matches_block2"] = obs == BLOCK2_ORDER
    B["design"]["mirror_order"] = BLOCK2_ORDER
    B["design"]["orders_present"] = [r.get("order") for r in B["runs"]]
    B["design"]["cells_by_order_match"] = [dict(order=r.get("order"), cell=r.get("cell"),
                                                 expected=(BLOCK2_ORDER[r["order"] - 1] if isinstance(r.get("order"), int) and 1 <= r["order"] <= 8 else None))
                                            for r in B["runs"]]
    B["note"] = HEADER
    B["rule_block2"] = "밤1004_사전등록_v1 §6: 순서 G50 G100 C50 C100 C100 C50 G100 G50 · 런·셀 분석 = night1003_judge_effblock 그대로 · 두 블록 대조 ≤ 3 % · CPU 창 [0.8645, 0.8998]"
    B["two_block"] = compare_blocks(B, block1)
    B["interaction_cpu_block2"] = interaction2(B, block1)
    B["import"] = dict(path=_EB_PATH, sha256=_sha(_EB_PATH), expected_prefix="bd4bbd87", ok=_sha(_EB_PATH).startswith("bd4bbd87"))
    return B


# ============================================================ selftest
def selftest():
    res = []

    def check(name, cond, got):
        res.append((name, bool(cond), got))
    tmp = tempfile.mkdtemp(prefix="effblock2_selftest_")
    try:
        check("import night1003_judge_effblock SHA 접두 bd4bbd87", _sha(_EB_PATH).startswith("bd4bbd87"), _sha(_EB_PATH)[:8])

        def mk(i, accel, duty, lat, ro, tag=""):
            return EB._synth_single(tmp, f"S26_EffB2_{i:02d}_{accel.lower()}{duty}_1004{tag}", accel, duty, 60, lat, ro)
        b1 = dict(cells=dict(C50=dict(run_only_median_ms=dict(mean=4.0), latency_median_ms=dict(mean=4.2)),
                             C100=dict(run_only_median_ms=dict(mean=4.0), latency_median_ms=dict(mean=4.2)),
                             G50=dict(run_only_median_ms=dict(mean=1.4), latency_median_ms=dict(mean=3.3)),
                             G100=dict(run_only_median_ms=dict(mean=1.4), latency_median_ms=dict(mean=3.3))),
                  interaction_cpu=dict(ratio_run_only_d50_d100=1.0, verdict="상호작용 있음 — 2수준만으로는 부족"),
                  interaction_gpu=dict(ratio_run_only_d50_d100=1.0))
        # 블록 2: C50 4.116 (2.9 %) · C100 4.124 (3.1 %) · G50 1.442 (3.0 % 경계) · G100 1.40 → CPU 비 0.998 → 상호작용 있음
        order = [("GPU", 50, 1.442), ("GPU", 100, 1.40), ("CPU", 50, 4.116), ("CPU", 100, 4.124), ("CPU", 100, 4.124), ("CPU", 50, 4.116), ("GPU", 100, 1.40), ("GPU", 50, 1.442)]
        dirs = [mk(i + 1, a, d, ro + 0.2, ro) for i, (a, d, ro) in enumerate(order)]
        B = block2_report(dirs, b1, with_evidence=False)
        check("8런 파싱 · 블록 2 거울 순서 일치 (G50 G100 C50 C100 C100 C50 G100 G50)", B["design"]["order_matches_block2"] and len(B["runs"]) == 8, B["design"]["observed_order"])
        check("블록 1 거울 검사는 import 값으로 따로 보관 (블록 2 에선 False)", B["design"]["block1_mirror_check_from_import"]["matches"] is False, B["design"]["block1_mirror_check_from_import"])
        tb = B["two_block"]["cells"]
        check("3 % 경계 안쪽: C50 2.9 % → 블록 간 재현", tb["C50"]["run_only_median_ms"]["verdict"] == "블록 간 재현", tb["C50"]["run_only_median_ms"])
        check("3 % 경계 바깥쪽: C100 3.1 % → 블록 간 차이", tb["C100"]["run_only_median_ms"]["verdict"] == "블록 간 차이", tb["C100"]["run_only_median_ms"])
        check("정확히 3.0 % (G50 1.442 vs 1.4) → 블록 간 재현 (≤)", tb["G50"]["run_only_median_ms"]["verdict"] == "블록 간 재현", tb["G50"]["run_only_median_ms"])
        check("write+run+read 는 기술만", tb["C50"]["latency_median_ms"]["verdict"] == "기술만", tb["C50"]["latency_median_ms"])
        check("CPU 비 ~0.998 (창 밖) → 상호작용 있음 — 2블록 확인", B["interaction_cpu_block2"]["verdict"] == "상호작용 있음 — 2블록 확인", B["interaction_cpu_block2"]["block2_ratio"])
        # 비 0.882 → 확인 실패
        order2 = [("GPU", 50, 1.4), ("GPU", 100, 1.4), ("CPU", 50, 3.528), ("CPU", 100, 4.0), ("CPU", 100, 4.0), ("CPU", 50, 3.528), ("GPU", 100, 1.4), ("GPU", 50, 1.4)]
        dirs2 = [mk(i + 1, a, d, ro + 0.2, ro, "b") for i, (a, d, ro) in enumerate(order2)]
        B2 = block2_report(dirs2, b1, with_evidence=False)
        check("CPU 비 0.882 (창 안) → 확인 실패 — 결론 보류", B2["interaction_cpu_block2"]["verdict"] == "확인 실패 — 결론 보류" and abs(B2["interaction_cpu_block2"]["block2_ratio"] - 0.882) < 1e-6,
              B2["interaction_cpu_block2"]["block2_ratio"])
        # 비 1.02 → 확인
        order3 = [("CPU", 50, 4.08), ("CPU", 100, 4.0)]
        dirs3 = [mk(3, "CPU", 50, 4.28, 4.08, "c"), mk(4, "CPU", 100, 4.2, 4.0, "c")]
        B3 = block2_report(dirs3, b1, with_evidence=False)
        check("CPU 비 1.02 → 상호작용 있음 — 2블록 확인 · GPU 셀 결측 → 대조 판정 불가", B3["interaction_cpu_block2"]["verdict"] == "상호작용 있음 — 2블록 확인"
              and B3["two_block"]["cells"]["G50"]["run_only_median_ms"]["verdict"].startswith("판정 불가"), B3["interaction_cpu_block2"]["block2_ratio"])
        B4 = block2_report([dirs3[1]], b1, with_evidence=False)
        check("C50 전부 결측 → 상호작용 판정 불가", B4["interaction_cpu_block2"]["verdict"].startswith("판정 불가"), B4["interaction_cpu_block2"]["verdict"])
        B5 = block2_report(dirs, None, with_evidence=False)
        check("블록 1 자료 없음 → 대조 안 함 기록", B5["two_block"]["block1_present"] is False and "없음" in B5["two_block"]["note"], B5["two_block"].get("note"))
        g = os.path.join(tmp, "gate.csv")
        with open(g, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["label", "local_time", "waited_s", "SKIN", "AP", "BAT", "thermal_status", "soc", "plugged", "pass"])
            w.writerow(["03_01_gpu50", "2026-10-05T02:00:00", "0", "30.1", "29.0", "28.0", "0", "80", "False", "True"])
            w.writerow(["06_01_cpu50", "2026-10-04T05:50:37", "120", "31.5", "30.3", "29.8", "0", "60", "False", "True"])
        gr = load_gate2(g)
        check("게이트 CSV: '03_<nn>_' 통과 행만 (06_ 은 무시)", list(gr.keys()) == [1] and gr[1]["SKIN"] == 30.1, gr)
        a1 = dumps(block2_report([mk(1, "GPU", 50, 1.6, 1.4, "detA")], b1, with_evidence=False))
        a2 = dumps(block2_report([mk(1, "GPU", 50, 1.6, 1.4, "detB")], b1, with_evidence=False))
        check("결정성: 같은 입력 두 번 = 같은 바이트 (이름 제외)", a1.replace("detA", "X") == a2.replace("detB", "X"), f"{len(a1)} B")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(c for _, c, _ in res)
    print("| 시험 | 결과 | 값 |\n|---|---|---|")
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:170]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    a = sub.add_parser("block2")
    a.add_argument("result_dirs", nargs="+")
    a.add_argument("--block1", default=BLOCK1_DEFAULT)
    a.add_argument("--gate-log")
    a.add_argument("--no-evidence", action="store_true")
    a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        b1 = None
        if args.block1 and os.path.exists(args.block1):
            with open(args.block1, encoding="utf-8") as fh:
                b1 = json.load(fh)
        res = block2_report(args.result_dirs, b1, not args.no_evidence, load_gate2(args.gate_log))
        res["block1_source"] = dict(path=args.block1, present=b1 is not None, sha256=(_sha(args.block1) if b1 is not None else None))
    except JudgeError as err:
        print(f"JUDGE_ERROR: {err}", file=sys.stderr)
        return 2
    text = dumps(res)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
