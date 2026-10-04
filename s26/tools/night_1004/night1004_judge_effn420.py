# -*- coding: utf-8 -*-
"""night1004_judge_effn420.py — EffNet × NPU d100 420 s (EffN420) 판정. `밤1004_사전등록_v1.md` §7 (NPU600_EffNet v1 §2 규칙의 `_v2`) 글자 그대로.
`night1003_judge_npu600.py` (SHA cc7d1559…) 를 import — 고정 `throttle_curve_0928.py analyze --duration 420 --duty 100` (**--equilibrium 없이**)
+ 1계단 시각 step1_time (+4.5 % 유지 첫 칸) + 계단 진입 SKIN·AP (복사·수정 금지). results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트.

  py night1004_judge_effn420.py selftest
  py night1004_judge_effn420.py range [--out f.json]                     # MobileNet 5런 기준 범위 — EffN420 결과 전에 freeze_1004.txt 에 적고 고정
  py night1004_judge_effn420.py analyze <result_dir> [--duration 420] [--out f.json]
  py night1004_judge_effn420.py effnet <analyze.json> --range <range.json> [--out f.json]

규칙 (§7):
  기준 = MobileNet 5런 (N1300 1002 · 6b H1 · H2 · M1-NPU a · b) 의 계단 진입 SKIN·AP 의 [최소, 최대] ± 0.3 ℃ — 각 판정 JSON 에서 읽는다:
      N1300: 1계단 시각 = step1_time(out_1002\\N1300_throttle_analyze.json lat10 / ref_ms) · 1계단 온도 = out_1002\\N1300_table.json bins10 중
             끝 시각(t0+10)이 1계단 시각인 칸의 HAL 표본 (long_run_table: 칸 끝에 가장 가까운 표본 = 1계단 시각의 표본) · 2계단 = onset_temps
      6b H1·H2: out_1002\\M2r_H{1,2}_seg0_throttle.json onset_temps (2계단). 1계단 온도는 JSON 에 없으면 그 런을 1계단 범위에서 뺀다 (기록)
      M1-NPU a·b: out_1003\\M1_npu_{a,b}.json heat.step1_thermal (1계단) · heat.onset_thermal (2계단)
  EffNet 두 계단 (1계단 = +4.5 % 유지 첫 칸의 HAL 표본, 2계단 = 1-1 진입 칸의 HAL 표본) SKIN·AP 넷 다 범위 안 → "계단 온도대 = 모델 무관 (1런)" ·
      하나라도 밖 → "모델 의존 후보" · 420 s 안에 2계단 없으면 "2계단 판정 불가" (1계단 안/밖은 기술) · 1계단 없으면 "판정 불가 (1계단 없음)" ·
      계단 폭 · 잠정 전력 (MobileNet 대비 비율) 은 기술 — H-load 라면 전력이 다르면 진입 온도도 달라질 수 있다 [E]
"""
import argparse, hashlib, importlib.util, json, os, sys

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


_NP_PATH = _first_existing(os.path.join(HERE, "night1003_judge_npu600.py"), os.path.join(OD_SIM, "night1003_judge_npu600.py"),
                           os.path.join(REPO, "s26", "tools", "night_1003", "night1003_judge_npu600.py"))
NP = _load_module("night1003_judge_npu600", _NP_PATH)
JudgeError, dumps, step1_time = NP.JudgeError, NP.dumps, NP.step1_time

MARGIN = 0.3
DURATION = 420
SRC = dict(
    n1300_analyze=os.path.join(OD_SIM, "out_1002", "N1300_throttle_analyze.json"),
    n1300_table=os.path.join(OD_SIM, "out_1002", "N1300_table.json"),
    h1=os.path.join(OD_SIM, "out_1002", "M2r_H1_seg0_throttle.json"),
    h2=os.path.join(OD_SIM, "out_1002", "M2r_H2_seg0_throttle.json"),
    m1a=os.path.join(OD_SIM, "out_1003", "M1_npu_a.json"),
    m1b=os.path.join(OD_SIM, "out_1003", "M1_npu_b.json"),
)


def _sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _jl(p):
    if not p or not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        j = json.load(fh)
    return j[0] if isinstance(j, list) and j else j


def _temps(d):
    if not d:
        return None
    s, a = d.get("SKIN"), d.get("AP")
    return None if (s is None or a is None) else dict(SKIN=float(s), AP=float(a))


def mobilenet_runs(src=None):
    """5런의 1계단·2계단 진입 SKIN·AP (판정 JSON 에서). 못 찾은 값은 None + 사유."""
    src = src or SRC
    runs = []
    # N1300 1002
    an, tb = _jl(src["n1300_analyze"]), _jl(src["n1300_table"])
    s1 = None
    st1 = None
    why1 = None
    if an is not None and an.get("ref_ms"):
        bins = [(int(b[0]), (b[1] / an["ref_ms"]) if b[1] else None) for b in an.get("lat10", [])]
        s1 = step1_time(bins, level=NP.STEP1_LEVEL)
    if s1 is not None and tb is not None:
        row = next((b for b in tb.get("bins10", []) if b.get("t0") == s1 - 10), None)
        st1 = None if row is None else _temps(row)
        why1 = None if st1 is not None else "N1300_table bins10 에 끝 시각 = 1계단 시각 칸 없음"
    else:
        why1 = "N1300 1계단 시각 또는 table 없음"
    runs.append(dict(run="N1300_1002", step1_s=s1, step1=st1, step1_missing=why1,
                     step1_source="out_1002/N1300_table.json bins10 (t0 = step1 − 10, HAL 표본 = 칸 끝 = 1계단 시각) · 시각 = step1_time(N1300_throttle_analyze lat10/ref_ms)",
                     onset_s=None if an is None else an.get("onset_s"), step2=None if an is None else _temps(an.get("onset_temps")),
                     step2_source="out_1002/N1300_throttle_analyze.json onset_temps", power_p0_w=None if an is None else an.get("power_p0_w")))
    for tag, key in (("6b_H1", "h1"), ("6b_H2", "h2")):
        j = _jl(src[key])
        runs.append(dict(run=tag, step1_s=None, step1=None, step1_missing="1계단 온도가 판정 JSON 에 없음 — 1계단 범위에서 뺀다 (사전 등록 지시)",
                         step1_source=None, onset_s=None if j is None else j.get("onset_s"), step2=None if j is None else _temps(j.get("onset_temps")),
                         step2_source=f"out_1002/{os.path.basename(src[key])} onset_temps", power_p0_w=None if j is None else j.get("power_p0_w")))
    for tag, key in (("M1_npu_a", "m1a"), ("M1_npu_b", "m1b")):
        j = _jl(src[key])
        h = (j or {}).get("heat") or {}
        st = _temps(h.get("step1_thermal"))
        runs.append(dict(run=tag, step1_s=h.get("step1_s"), step1=st, step1_missing=None if st is not None else "heat.step1_thermal 없음",
                         step1_source=f"out_1003/{os.path.basename(src[key])} heat.step1_thermal", onset_s=h.get("onset_1_1_s"),
                         step2=_temps(h.get("onset_thermal")), step2_source=f"out_1003/{os.path.basename(src[key])} heat.onset_thermal", power_p0_w=None))
    return runs


def build_range(src=None):
    src = src or SRC
    runs = mobilenet_runs(src)
    out = dict(rule="MobileNet 5런 계단 진입 SKIN·AP [최소, 최대] ± 0.3 ℃ (밤1004_사전등록_v1 §7)", margin=MARGIN, runs=runs, ranges={}, used={},
               sources={k: dict(path=v, sha256=(_sha(v) if os.path.exists(v) else None)) for k, v in src.items()})
    for step in ("step1", "step2"):
        vals = [(r["run"], r[step]) for r in runs if r[step] is not None]
        out["used"][step] = [n for n, _ in vals]
        for k in ("SKIN", "AP"):
            v = [t[k] for _, t in vals]
            if v:
                out["ranges"][f"{step}_{k}"] = dict(min=min(v), max=max(v), lo=round(min(v) - MARGIN, 6), hi=round(max(v) + MARGIN, 6), n=len(v))
            else:
                out["ranges"][f"{step}_{k}"] = None
    out["dropped"] = {step: [r["run"] for r in runs if r[step] is None] for step in ("step1", "step2")}
    p0 = [r["power_p0_w"] for r in runs if r.get("power_p0_w")]
    out["mobilenet_power_p0_w"] = dict(values=p0, mean=(float(np.mean(p0)) if p0 else None), note="잠정 전력 (단위 가정) — 비율 기술만")
    return out


def effnet_rule2(j, rng):
    s1, on = j.get("step1_s"), j.get("onset_1_1_s")
    s1t, s2t = j.get("step1_temps"), j.get("onset_temps")
    R = rng["ranges"]
    checks = {}
    for lab, meas in (("step1", s1t if s1 is not None else None), ("step2", s2t if on is not None else None)):
        for k in ("SKIN", "AP"):
            r = R.get(f"{lab}_{k}")
            mv = None if meas is None else meas.get(k)
            checks[f"{lab}_{k}"] = None if (mv is None or r is None) else dict(measured=mv, lo=r["lo"], hi=r["hi"], within=bool(r["lo"] <= mv <= r["hi"]))
    if s1 is None:
        verdict = "판정 불가 (1계단 없음" + (" · 2계단 없음" if on is None else "") + ")"
    elif on is None:
        s1in = [checks.get("step1_SKIN"), checks.get("step1_AP")]
        verdict = "2계단 판정 불가 (420 s 안 1-1 미진입) — 1계단 SKIN·AP: " + ", ".join(
            "표본 없음" if c is None else ("범위 안" if c["within"] else "범위 밖") for c in s1in) + " (기술)"
    elif any(v is None for v in checks.values()):
        verdict = "판정 불가 (온도 표본 없음)"
    elif all(v["within"] for v in checks.values()):
        verdict = "계단 온도대 = 모델 무관 (1런)"
    else:
        verdict = "모델 의존 후보"
    p0 = j.get("power_p0_w")
    mp = (rng.get("mobilenet_power_p0_w") or {}).get("mean")
    return dict(rule="EffNet 두 계단 SKIN·AP 넷 다 MobileNet 5런 [최소, 최대] ± 0.3 ℃ 안 → 모델 무관 (1런) · 하나라도 밖 → 모델 의존 후보 · 2계단 없음 → 2계단 판정 불가",
                verdict=verdict, checks=checks, step1_s=s1, onset_1_1_s=on, ranges=R, range_used=rng.get("used"), range_dropped=rng.get("dropped"),
                step_widths_desc=dict(level_step1_ratio=j.get("level_step1_ratio"), level_step2_first120_ratio=j.get("level_step2_first120_ratio"), end60=j.get("end60")),
                power_desc=dict(effnet_p0_w=p0, mobilenet_p0_w_mean=mp, ratio=(p0 / mp) if (p0 and mp) else None,
                                note="잠정 전력 (단위 가정 · 절대 정확도 미인증) — 기술만. H-load 라면 전력이 다르면 진입 온도도 달라질 수 있다 [E]"),
                counter_interpretations=["시작 SKIN 밴드(29.1~31.6) 밖 여부", "SOC (세션 후반)", "실내 온도", "1런",
                                         "span 차이 (run-only — N1300·M1 과 같음 · 6b H 는 write+run+read)",
                                         "EffNet 절대 지연·추론 수·전력이 다르다 → '온도대' 비교지 '시각' 비교가 아님 (시각 차이는 기술만)"])


def analyze_cmd(result_dir, duration=DURATION):
    j = NP.analyze_cmd(result_dir, duration, 100)
    j["import"] = dict(path=_NP_PATH, sha256=_sha(_NP_PATH), expected_prefix="cc7d1559", ok=_sha(_NP_PATH).startswith("cc7d1559"))
    return j


# ============================================================ selftest
def selftest():
    res = []

    def check(name, cond, got):
        res.append((name, bool(cond), got))
    check("import night1003_judge_npu600 SHA 접두 cc7d1559", _sha(_NP_PATH).startswith("cc7d1559"), _sha(_NP_PATH)[:8])
    rng = build_range()
    R = rng["ranges"]
    check("실제 판정 JSON → 2계단 5런 (N1300 · 6b H1 · H2 · M1 a · b)", rng["used"]["step2"] == ["N1300_1002", "6b_H1", "6b_H2", "M1_npu_a", "M1_npu_b"], rng["used"])
    check("1계단: 6b H1·H2 는 JSON 에 1계단 온도 없음 → 뺌 (3런) · N1300 1계단 300 s", rng["dropped"]["step1"] == ["6b_H1", "6b_H2"] and rng["runs"][0]["step1_s"] == 300,
          (rng["dropped"], rng["runs"][0]["step1_s"]))
    check("N1300 1계단 표본 = SKIN 38.3 · AP 42.6 ([D] npu600 selftest 재계산과 같음)", rng["runs"][0]["step1"] == dict(SKIN=38.3, AP=42.6), rng["runs"][0]["step1"])
    check("범위 = [D] 요약 ± 0.3 (1계단 SKIN 37.6~38.3 · AP 41.7~42.6 / 2계단 SKIN 39.8~40.0 · AP 44.0~44.3)",
          (R["step1_SKIN"]["min"], R["step1_SKIN"]["max"], R["step1_AP"]["min"], R["step1_AP"]["max"], R["step2_SKIN"]["min"], R["step2_SKIN"]["max"],
           R["step2_AP"]["min"], R["step2_AP"]["max"]) == (37.6, 38.3, 41.7, 42.6, 39.8, 40.0, 44.0, 44.3),
          {k: (v["lo"], v["hi"]) for k, v in R.items()})

    def fake(s1, on, t1, t2, p0=5.0):
        return dict(step1_s=s1, onset_1_1_s=on, step1_temps=t1, onset_temps=t2, power_p0_w=p0, level_step1_ratio=1.09, level_step2_first120_ratio=1.13, end60=None)
    e = effnet_rule2(fake(150, 300, dict(SKIN=38.0, AP=42.0), dict(SKIN=40.0, AP=44.2)), rng)
    check("넷 다 범위 안 → 계단 온도대 = 모델 무관 (1런)", e["verdict"] == "계단 온도대 = 모델 무관 (1런)", e["verdict"])
    e = effnet_rule2(fake(150, 300, dict(SKIN=38.6, AP=42.9), dict(SKIN=39.5, AP=44.6)), rng)
    check("넷 다 경계 (38.6 · 42.9 · 39.5 · 44.6) → 모델 무관 (≤ 포함)", e["verdict"] == "계단 온도대 = 모델 무관 (1런)", {k: v["within"] for k, v in e["checks"].items()})
    e = effnet_rule2(fake(150, 300, dict(SKIN=38.7, AP=42.0), dict(SKIN=40.0, AP=44.2)), rng)
    check("1계단 SKIN 38.7 (+0.1 밖) → 모델 의존 후보", e["verdict"] == "모델 의존 후보" and e["checks"]["step1_SKIN"]["within"] is False, e["verdict"])
    e = effnet_rule2(fake(150, 300, dict(SKIN=38.0, AP=42.0), dict(SKIN=40.0, AP=43.6)), rng)
    check("2계단 AP 43.6 (−0.1 밖) → 모델 의존 후보", e["verdict"] == "모델 의존 후보", e["verdict"])
    e = effnet_rule2(fake(150, None, dict(SKIN=38.0, AP=42.0), None), rng)
    check("420 s 안 2계단 없음 → '2계단 판정 불가' (1계단 범위 안 기술)", e["verdict"].startswith("2계단 판정 불가") and "범위 안" in e["verdict"], e["verdict"])
    e = effnet_rule2(fake(None, None, None, None), rng)
    check("1계단·2계단 없음 → 판정 불가 (1계단 없음 · 2계단 없음)", e["verdict"] == "판정 불가 (1계단 없음 · 2계단 없음)", e["verdict"])
    e = effnet_rule2(fake(150, 300, dict(SKIN=38.0, AP=42.0), dict(SKIN=40.0, AP=44.2), p0=6.0), rng)
    check("잠정 전력 비 = EffNet p0 / MobileNet p0 평균 (기술)", e["power_desc"]["ratio"] is not None and e["power_desc"]["mobilenet_p0_w_mean"] is not None, e["power_desc"])
    # 소스 결측 → 그 런 뺌
    src2 = dict(SRC)
    src2["h1"] = os.path.join(OD_SIM, "out_1002", "__no_such__.json")
    r2 = build_range(src2)
    check("6b H1 JSON 없음 → 2계단 4런 (기록)", r2["used"]["step2"] == ["N1300_1002", "6b_H2", "M1_npu_a", "M1_npu_b"] and "6b_H1" in r2["dropped"]["step2"], r2["used"]["step2"])
    a1 = dumps(build_range())
    a2 = dumps(build_range())
    check("결정성: 범위 두 번 = 같은 바이트", a1 == a2, f"{len(a1)} B")
    # 고정 analyze 경로 회귀 (N1300_1002 를 420 s 창으로 — 판정 자료 아님, 경로 확인만)
    n1300 = os.path.join(REPO, "results", "S26_N1300_npu_1002")
    if os.path.isdir(n1300):
        try:
            j = analyze_cmd(n1300, 1300)
            check("고정 analyze 경로 (N1300_1002, 1300 s): 진입 470 · 1계단 300 재현", j["onset_1_1_s"] == 470 and j["step1_s"] == 300, (j["onset_1_1_s"], j["step1_s"]))
        except JudgeError as err:
            check("고정 analyze 경로 (N1300_1002)", False, str(err))
    else:
        check("고정 analyze 경로 (N1300_1002 폴더 없음 — 건너뜀)", True, n1300)
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
    a = sub.add_parser("range")
    a.add_argument("--out")
    a = sub.add_parser("analyze")
    a.add_argument("result_dir")
    a.add_argument("--duration", type=float, default=DURATION)
    a.add_argument("--out")
    a = sub.add_parser("effnet")
    a.add_argument("analyze_json")
    a.add_argument("--range", required=True)
    a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "range":
            res = build_range()
        elif args.cmd == "analyze":
            res = analyze_cmd(args.result_dir, args.duration)
        else:
            with open(args.analyze_json, encoding="utf-8") as fh:
                j = json.load(fh)
            with open(args.range, encoding="utf-8") as fh:
                rng = json.load(fh)
            res = effnet_rule2(j, rng)
            res["range_file"] = dict(path=args.range, sha256=_sha(args.range))
    except JudgeError as err:
        print(f"JUDGE_ERROR: {err}", file=sys.stderr)
        return 2
    text = dumps(res)
    if getattr(args, "out", None):
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
