# -*- coding: utf-8 -*-
"""night1003_judge_npu600.py — EffNet × NPU d100 600 s · N1300 2런째 판정. `NPU600_EffNet_N1300r2_사전등록_v1.md` §2 글자 그대로.
판정 = 고정 스크립트 `sim\\throttle_curve_0928.py` (SHA 31822678…) `analyze --duration D --duty 100` (**--equilibrium 없이**)
+ 1계단 시각 `step1_time` (`d1sim\\tools\\fit_throttle_v1.py`, +4.5 % 유지 첫 칸) + 계단 진입 SKIN·AP. results\\ 는 읽기만.

  py night1003_judge_npu600.py selftest
  py night1003_judge_npu600.py analyze <result_dir> --duration 600 [--duty 100] [--out f.json]
  py night1003_judge_npu600.py effnet <analyze.json> [--out f.json]            # 계단 온도대 = 모델 무관 (1런) / 모델 의존 후보
  py night1003_judge_npu600.py n1300r2 <analyze.json> --first <N1300_1002 analyze.json> [--out f.json]   # 1런째와 재현

규칙:
  EffNet: 1계단 (SKIN_1, AP_1) · 2계단 = 1-1 진입 (SKIN_2, AP_2) 가 MobileNet 3런 (N1300 · 6b H1·H2) 값 1계단 SKIN 38.3 · AP 42.5 / 2계단 SKIN 40.0 · AP 44.2 의
          **±0.5 ℃ 안 (넷 다)** → "계단 온도대 = 모델 무관 (1런)", 밖 → "모델 의존 후보". 계단 폭(+%)은 기술만. 계단·진입이 없으면 "판정 불가 (…)"
  N1300 r2: 1런째(S26_N1300_npu_1002: 1계단 300 s · 진입 470 s)와 1계단·진입 시각 차 **둘 다 ≤ 20 s** → "재현", 아니면 "1런씩 보고". 시작 SKIN 밴드 29.1~31.6 안 여부 기록
"""
import argparse, glob, hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

THROTTLE = os.path.join(HERE, "throttle_curve_0928.py")
if not os.path.exists(THROTTLE):
    THROTTLE = os.path.join(REPO, "s26", "tools", "s26_throttle_curve_0928.py")
THROTTLE_SHA_PREFIX = "3182267894b23813802f0e3f3c3146fbbe2d52581bb494339f1dc623cb6d0b4e"   # [D 스로틀곡선_사전등록_0928 §0 · 작업결과_1002 §6]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, REPO)
F = _load_module("fit_throttle_v1", os.path.join(REPO, "d1sim", "tools", "fit_throttle_v1.py"))
step1_time = F.step1_time

ND = 6
STEP1_LEVEL = 1.045
REF_MOBILENET = dict(step1=dict(SKIN=38.3, AP=42.5), step2=dict(SKIN=40.0, AP=44.2))   # [D 프롬프트 1-B-4 · M1_NPU_사전등록_v1 §3 · NPU1300_결과_1002]
TEMP_TOL = 0.5
REPRO_S = 20
FIRST_RUN = dict(step1_s=300, onset_s=470, source="sim/out_1002/N1300_throttle_analyze.json (onset 470 [P]; step1 300 = step1_time(lat10/ref_ms) 재계산 [P])")
BAND = (29.1, 31.6)


class JudgeError(RuntimeError):
    pass


def _r(x):
    if isinstance(x, float):
        return round(x, ND)
    if isinstance(x, dict):
        return {k: _r(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r(v) for v in x]
    if isinstance(x, np.floating):
        return round(float(x), ND)
    if isinstance(x, np.integer):
        return int(x)
    return x


def dumps(obj):
    return json.dumps(_r(obj), ensure_ascii=False, sort_keys=True, indent=1)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def frozen_analyze(result_dir, duration, duty=100):
    """고정 스크립트를 그대로 실행 (--equilibrium 없이). 기록 1개(런 1개)를 돌려준다."""
    sha = sha256(THROTTLE)
    if sha != THROTTLE_SHA_PREFIX:
        raise JudgeError(f"throttle_curve_0928.py SHA 불일치: {sha[:16]}… ≠ {THROTTLE_SHA_PREFIX[:16]}…")
    tmp = tempfile.mkdtemp(prefix="npu600_analyze_")
    out = os.path.join(tmp, "analyze.json")
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", THROTTLE, "analyze", result_dir, "--duration", str(duration), "--duty", str(duty), "--out", out],
                           capture_output=True, text=True, timeout=1800, encoding="utf-8", errors="replace")
        if p.returncode != 0 or not os.path.exists(out):
            raise JudgeError(f"throttle_curve_0928 analyze 실패 rc={p.returncode}: {(p.stderr or p.stdout)[-600:]}")
        recs = json.load(open(out, encoding="utf-8"))
        text = p.stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not isinstance(recs, list) or len(recs) != 1:
        raise JudgeError(f"analyze 기록 {len(recs) if isinstance(recs, list) else '?'}개 (1 기대)")
    rec = recs[0]
    if rec.get("error"):
        raise JudgeError(f"analyze 오류: {rec['error']}")
    return rec, text, sha


def _thermal_series(result_dir, run_id):
    rd = os.path.join(result_dir, "runs", run_id)
    f = sorted(glob.glob(os.path.join(rd, "gpu", "*.jsonl")))
    if len(f) != 1:
        raise JudgeError(f"러너 JSONL {len(f)}개")
    load_start = None
    for line in open(f[0], encoding="utf-8"):
        if '"load_start"' in line:
            e = json.loads(line)
            if e.get("event") == "load_start":
                load_start = int(e["mono_ns"]); break
    if load_start is None:
        raise JudgeError("load_start 없음")
    th = []
    tp = os.path.join(rd, "raw", "thermalservice.jsonl")
    if os.path.exists(tp):
        for line in open(tp, encoding="utf-8"):
            try:
                s = json.loads(line)
            except ValueError:
                continue
            if s.get("parse_status") in (None, "ok") and isinstance(s.get("mono_ns"), int):
                th.append(((s["mono_ns"] - load_start) / 1e9, s))
    th.sort(key=lambda x: x[0])
    return th


def _th_at(th, t):
    if not th:
        return None
    i = int(np.argmin([abs(x[0] - t) for x in th]))
    rel, s = th[i]
    return dict(t=rel, SKIN=float(s["SKIN"]) if s.get("SKIN") not in (None, "") else None, AP=float(s["AP"]) if s.get("AP") not in (None, "") else None,
                BAT=float(s["BAT"]) if s.get("BAT") not in (None, "") else None, PA=float(s["PA"]) if s.get("PA") not in (None, "") else None,
                thermal_status=int(s["thermal_status"]) if s.get("thermal_status") not in (None, "") else None)


def post(rec, th=None):
    """고정 분석 기록 + 1계단 시각·온도·계단 수준 (기술)."""
    ref = rec.get("ref_ms")
    lat10 = rec.get("lat10") or []
    bins = [(int(b[0]), (b[1] / ref) if (b[1] and ref) else None) for b in lat10]
    s1 = step1_time(bins, level=STEP1_LEVEL) if ref else None
    onset = rec.get("onset_s")
    step1_temps = _th_at(th, s1) if (th is not None and s1 is not None) else None
    def level(a, b):
        v = [r for t, r in bins if r is not None and a <= t < b]
        return float(np.median(v)) if v else None
    lvl1 = level(s1, onset) if (s1 is not None and onset is not None and onset > s1) else None
    lvl2 = level(onset, onset + 120) if onset is not None else None
    return dict(
        run_id=rec.get("run_id"), resource=rec.get("resource"), load_s=rec.get("load_s"), n_inf=rec.get("n_inf"), ref_ms=ref,
        onset_1_1_s=onset, onset_edge_candidate_s=rec.get("onset_edge_candidate_s"), onset_temps=rec.get("onset_temps"),
        step1_s=s1, step1_temps=step1_temps, level_step1_ratio=lvl1, level_step2_first120_ratio=lvl2,
        end60=rec.get("end60"), end_temps=rec.get("end_temps"), load_start_temps=rec.get("load_start_temps"),
        load_start_skin_in_band=rec.get("load_start_skin_in_band"), thermal_status=rec.get("thermal_status"),
        conservation=rec.get("conservation"), run_summary=rec.get("run_summary"), runner_termination=rec.get("runner_termination"),
        bins_ratio=bins, power_p0_w=rec.get("power_p0_w"), power10=rec.get("power10"),
    )


def effnet_rule(j):
    s1t, s2t = j.get("step1_temps"), j.get("onset_temps")
    if j.get("step1_s") is None or j.get("onset_1_1_s") is None:
        what = []
        if j.get("step1_s") is None: what.append("1계단 없음")
        if j.get("onset_1_1_s") is None: what.append("1-1 미진입")
        return dict(verdict="판정 불가 (" + " · ".join(what) + ")", checks=None, reference=REF_MOBILENET, tol=TEMP_TOL)
    checks = {}
    for lab, meas, refv in (("step1", s1t, REF_MOBILENET["step1"]), ("step2", s2t, REF_MOBILENET["step2"])):
        for k in ("SKIN", "AP"):
            mv = None if meas is None else meas.get(k)
            checks[f"{lab}_{k}"] = None if mv is None else dict(measured=mv, reference=refv[k], within=bool(abs(mv - refv[k]) <= TEMP_TOL))
    if any(v is None for v in checks.values()):
        verdict = "판정 불가 (온도 표본 없음)"
    elif all(v["within"] for v in checks.values()):
        verdict = "계단 온도대 = 모델 무관 (1런)"
    else:
        verdict = "모델 의존 후보"
    return dict(verdict=verdict, checks=checks, reference=REF_MOBILENET, tol=TEMP_TOL,
                step_widths_desc=dict(level_step1_ratio=j.get("level_step1_ratio"), level_step2_first120_ratio=j.get("level_step2_first120_ratio"), end60=j.get("end60")),
                rule="두 계단 진입 SKIN·AP 가 MobileNet 3런 값 ±0.5 ℃ 안(넷 다) → 모델 무관 (1런), 밖 → 모델 의존 후보")


def n1300r2_rule(j, first=None):
    f = first or FIRST_RUN
    s1, on = j.get("step1_s"), j.get("onset_1_1_s")
    d1 = None if (s1 is None or f.get("step1_s") is None) else abs(s1 - f["step1_s"])
    d2 = None if (on is None or f.get("onset_s") is None) else abs(on - f["onset_s"])
    if d1 is None or d2 is None:
        verdict = "1런씩 보고 (계단·진입 중 하나가 없음)"
    elif d1 <= REPRO_S and d2 <= REPRO_S:
        verdict = "재현"
    else:
        verdict = "1런씩 보고"
    sk = (j.get("load_start_temps") or {}).get("SKIN")
    return dict(verdict=verdict, first_run=f, second=dict(step1_s=s1, onset_s=on), diff=dict(step1_s=d1, onset_s=d2), tol_s=REPRO_S,
                start_skin=sk, start_skin_in_band=(None if sk is None else bool(BAND[0] <= sk <= BAND[1])), band=BAND,
                note="1런째 시작 SKIN 28.3 (밴드 밖) [P NPU1300_결과_1002] — 2런째가 밴드 안이면 그 사실을 적는다",
                rule="1계단·진입 시각 차 둘 다 ≤ 20 s → 재현")


def analyze_cmd(result_dir, duration, duty=100):
    rec, text, sha = frozen_analyze(result_dir, duration, duty)
    th = _thermal_series(result_dir, rec["run_id"])
    j = post(rec, th)
    j["frozen_script"] = dict(path=THROTTLE, sha256=sha, args=["analyze", "--duration", duration, "--duty", duty], equilibrium=False)
    j["frozen_stdout_tail"] = text[-1500:]
    return j


# ============================================================ selftest
def selftest():
    res = []
    def check(name, cond, got):
        res.append((name, bool(cond), got))
    # 1) 고정 스크립트 경로 회귀: 어젯밤 N1300 (이미 판정된 자료 — 홀드아웃 아님) 에서 진입 470 · 1계단 300 재현
    n1300 = os.path.join(REPO, "results", "S26_N1300_npu_1002")
    if os.path.isdir(n1300):
        try:
            j = analyze_cmd(n1300, 1300, 100)
            check("고정 analyze 경로: N1300_1002 진입 470 · 1계단 300 재현", j["onset_1_1_s"] == 470 and j["step1_s"] == 300, (j["onset_1_1_s"], j["step1_s"], j["frozen_script"]["sha256"][:12]))
            check("N1300_1002 진입 온도 SKIN 39.9 · AP 44.3", j["onset_temps"]["SKIN"] == 39.9 and j["onset_temps"]["AP"] == 44.3, j["onset_temps"])
            check("N1300_1002 1계단 온도 표본 있음", j["step1_temps"] is not None and j["step1_temps"]["SKIN"] is not None, j["step1_temps"])
            r = n1300r2_rule(j)
            check("자기 자신과 비교 → 재현 · 시작 SKIN 28.3 밴드 밖", r["verdict"] == "재현" and r["start_skin_in_band"] is False, (r["diff"], r["start_skin"]))
            e = effnet_rule(j)
            check("EffNet 규칙을 MobileNet N1300 에 적용 → 모델 무관 (자기 기준 안) 또는 1계단 온도 ±0.5 밖이면 후보 (기술)", e["verdict"] in ("계단 온도대 = 모델 무관 (1런)", "모델 의존 후보"), (e["verdict"], {k: (v["measured"], v["within"]) for k, v in e["checks"].items()}))
        except JudgeError as err:
            check("고정 analyze 경로 (N1300_1002)", False, str(err))
    else:
        check("고정 analyze 경로 (N1300_1002 폴더 없음 — 건너뜀)", True, n1300)
    # 2) 규칙 (가짜 기록)
    def fake(s1, on, s1_skin, s1_ap, on_skin, on_ap, start_skin=30.0):
        bins = []
        for t in range(0, 600, 10):
            r = 1.0 if (s1 is None or t < s1) else (1.09 if (on is None or t < on) else 1.13)
            bins.append([t, 0.75 * r, 100])
        rec = dict(run_id="fake", ref_ms=0.75, lat10=bins, onset_s=on, onset_temps=(None if on is None else dict(t=on, SKIN=on_skin, AP=on_ap)),
                   load_start_temps=dict(SKIN=start_skin), load_start_skin_in_band=(29.1 <= start_skin <= 31.6), end60=dict(lat_ratio=1.13))
        th = [(t, dict(SKIN=f"{s1_skin:.1f}", AP=f"{s1_ap:.1f}", BAT="35.0", PA="40.0", thermal_status="0")) for t in range(0, 600)]
        j = post(rec, th)
        return j
    j = fake(150, 300, 38.3, 42.5, 40.0, 44.2)
    check("가짜: 1계단 150 (+4.5 % 유지) · 진입 300", j["step1_s"] == 150 and j["onset_1_1_s"] == 300, (j["step1_s"], j["onset_1_1_s"]))
    e = effnet_rule(j)
    check("온도 넷 다 기준값 → 모델 무관 (1런)", e["verdict"] == "계단 온도대 = 모델 무관 (1런)", e["verdict"])
    e = effnet_rule(fake(150, 300, 38.8, 42.9, 40.4, 43.8))
    check("넷 다 ±0.5 경계 안 → 모델 무관", e["verdict"] == "계단 온도대 = 모델 무관 (1런)", {k: v["within"] for k, v in e["checks"].items()})
    e = effnet_rule(fake(150, 300, 37.6, 42.5, 40.0, 44.2))
    check("1계단 SKIN 37.6 (−0.7) → 모델 의존 후보", e["verdict"] == "모델 의존 후보" and e["checks"]["step1_SKIN"]["within"] is False, e["verdict"])
    e = effnet_rule(fake(150, 300, 38.3, 42.5, 40.0, 44.9))
    check("2계단 AP 44.9 (+0.7) → 모델 의존 후보", e["verdict"] == "모델 의존 후보", e["verdict"])
    e = effnet_rule(fake(None, None, 0, 0, 0, 0))
    check("계단·진입 없음 → 판정 불가", e["verdict"].startswith("판정 불가"), e["verdict"])
    r = n1300r2_rule(fake(300, 470, 38.3, 42.5, 39.9, 44.3, start_skin=29.8))
    check("N1300 r2: 300·470 vs 1런째 300·470 → 재현 · 밴드 안", r["verdict"] == "재현" and r["start_skin_in_band"] is True, r["diff"])
    r = n1300r2_rule(fake(280, 490, 38.3, 42.5, 39.9, 44.3))
    check("N1300 r2: 차 20·20 → 재현 (경계)", r["verdict"] == "재현", r["diff"])
    r = n1300r2_rule(fake(270, 470, 38.3, 42.5, 39.9, 44.3))
    check("N1300 r2: 1계단 차 30 → 1런씩 보고", r["verdict"] == "1런씩 보고", r["diff"])
    r = n1300r2_rule(fake(None, 470, 38.3, 42.5, 39.9, 44.3))
    check("N1300 r2: 1계단 없음 → 1런씩 보고 (사유)", r["verdict"].startswith("1런씩 보고 ("), r["verdict"])
    a1 = dumps(fake(150, 300, 38.3, 42.5, 40.0, 44.2)); a2 = dumps(fake(150, 300, 38.3, 42.5, 40.0, 44.2))
    check("결정성: 같은 입력 두 번 = 같은 바이트", a1 == a2, f"{len(a1)} B")
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
    a = sub.add_parser("analyze"); a.add_argument("result_dir"); a.add_argument("--duration", type=float, required=True); a.add_argument("--duty", type=float, default=100); a.add_argument("--out")
    a = sub.add_parser("effnet"); a.add_argument("analyze_json"); a.add_argument("--out")
    a = sub.add_parser("n1300r2"); a.add_argument("analyze_json"); a.add_argument("--first"); a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "analyze":
            res = analyze_cmd(args.result_dir, args.duration, args.duty)
        elif args.cmd == "effnet":
            res = effnet_rule(json.load(open(args.analyze_json, encoding="utf-8")))
        else:
            first = None
            if args.first:
                fr = json.load(open(args.first, encoding="utf-8"))
                fr = fr[0] if isinstance(fr, list) else fr
                b = [(int(x[0]), (x[1] / fr["ref_ms"]) if (x[1] and fr.get("ref_ms")) else None) for x in fr.get("lat10", [])]
                first = dict(step1_s=step1_time(b, STEP1_LEVEL), onset_s=fr.get("onset_s"), source=args.first)
            res = n1300r2_rule(json.load(open(args.analyze_json, encoding="utf-8")), first)
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
