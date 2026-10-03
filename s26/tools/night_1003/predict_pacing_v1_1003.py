# -*- coding: utf-8 -*-
"""predict_pacing_v1_1003.py — 동결 v1 (M-P r3, 커밋 3050e09) 로 GPU 페이싱 체인 예측 (측정 전 동결용).
d1sim 코드는 수정하지 않는다 — `d1sim.throttle_v1` 과 `d1sim/profiles/throttle_v1_*.json` 을 읽기만 한다
(`d1sim/tools/predict_night_1003.py` 의 params()·duty_flags 와 같은 방식).

  체인 gpu_pacing_v1.json: GPU d10 60 → d100 600 → d10 60 → d100 300 (Σ 1020). 시작 SKIN 29.5 · 30.5, A0 = −1.0.
  출력: D1_ondevice/sim/out_1003/night_1003_prediction_v1_pacing.json
  판정 정의 = night1003_judge_pacing.py 와 같다 (ref_d100 = 구간 1 처음 30 s · 재조임 = 구간 3 칸 k + 뒤 3칸 ≥ ×1.10 · 휴지 회복 = ≤ ref_d10×1.10, k ≤ 2).
"""
import json, os, sys

REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
sys.path.insert(0, REPO)
from d1sim import throttle_v1 as tv1  # noqa: E402

PROFILES = os.path.join(REPO, "d1sim", "profiles")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out_1003")


def params():
    tp = json.load(open(os.path.join(PROFILES, "throttle_v1_thermal.json"), encoding="utf-8"))
    tp = {k: tp[k] for k in ("tau_f", "G_f", "G_s", "tau_s", "tau_a", "G_a", "P_idle")}
    ctrl, power, L0 = {}, {}, {}
    for res, fn in (("GPU", "GPU_compiledmodel"), ("NPU", "NPU"), ("CPU4", "CPU4_interpreter")):
        d = json.load(open(os.path.join(PROFILES, f"throttle_v1_{fn}.json"), encoding="utf-8"))
        ctrl[res] = dict(d["ctrl"]); power[res] = {k: d["power"][k] for k in ("P_idle", "P0", "alpha")}; L0[res] = d["L0_ms"]
    return dict(thermal=tp, ctrl=ctrl, power=power, L0=L0)


def duty_flags(duty, dur):
    return [(k % 10) < duty // 10 for k in range(dur)]


def med(rows, seg, a, b):
    v = sorted(r["ratio"] for r in rows if r["seg"] == seg and a <= r["t"] < b and r["ratio"] is not None)
    return v[len(v) // 2] if v else None


def at(rows, seg, t):
    return next((r for r in rows if r["seg"] == seg and r["t"] == t), None)


def pacing(p, T0):
    sch = [(0, "GPU", duty_flags(10, 60), 60), (1, "GPU", True, 600), (2, "GPU", duty_flags(10, 60), 60), (3, "GPU", True, 300)]
    rows = tv1.simulate(p, sch, T0, -1.0)
    ref_d10 = med(rows, 0, 0, 60)
    ref_d100 = med(rows, 1, 0, 30)
    hb = tv1.bins_ratio(rows, 1)
    onset = tv1.onset_time_ref(hb, ref_d100)
    pb2 = [None if m is None else m / ref_d10 for t, m in tv1.bins_ratio(rows, 2)]
    rec = None
    for k in range(0, min(2, len(pb2) - 4) + 1):
        if all(x is not None and x <= 1.10 for x in pb2[k:k + 4]):
            rec = 10 * k
            break
    pb3 = [None if m is None else m / ref_d100 for t, m in tv1.bins_ratio(rows, 3)]
    ret = None
    for k in range(0, len(pb3) - 3):
        if all(x is not None and x >= 1.10 for x in pb3[k:k + 4]):
            ret = 10 * k
            break
    if ret is None:
        cls = "재조임 없음 (300 s 안)"
    elif ret <= 20:
        cls = "60 s 휴지로는 재조임을 못 늦춘다"
    elif ret >= 60:
        cls = "60 s 휴지가 재조임을 늦춘다 (페이싱 후보)"
    else:
        cls = "중간"
    rest_end = at(rows, 2, 59); heat_end = at(rows, 1, 599); re_row = None if ret is None else at(rows, 3, ret)
    return dict(T_start=T0, ref_d10_ratio=ref_d10, ref_d100_ratio=ref_d100, heat_onset_s=onset, ratio_540_600=(med(rows, 1, 540, 600) / ref_d100),
                heat_end_skin=heat_end["skin"], heat_end_ap=heat_end["ap"], heat_end_status=heat_end["status"],
                rest_bins_ratio=pb2, rest_recovery=dict(recovery_s=rec, censored=rec is None),
                rest_end_skin=rest_end["skin"], rest_end_ap=rest_end["ap"],
                reheat_bins_ratio_first12=pb3[:12], retighten=dict(retighten_s=ret, label=("재조임 없음" if ret is None else ("즉시(0 s)" if ret == 0 else f"{ret} s"))),
                retighten_skin_ap=(None if re_row is None else dict(skin=re_row["skin"], ap=re_row["ap"])),
                classification=cls, reheat_ratio_240_300=(med(rows, 3, 240, 300) / ref_d100 if med(rows, 3, 240, 300) else None),
                reheat_end_skin=at(rows, 3, 299)["skin"], reheat_end_ap=at(rows, 3, 299)["ap"])


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = params()
    R = dict(model="v1 M-P r3 (d1sim/throttle_v1.py + profiles/throttle_v1_*.json, 커밋 3050e09) — 페이싱 체인 gpu_pacing_v1 (밤 1003 세션에서 d1sim 무수정으로 산출)",
             chain="gpu_pacing_v1: GPU d10 60 → d100 600 → d10 60 → d100 300", pacing={})
    for T0 in (29.5, 30.5):
        R["pacing"][str(T0)] = pacing(p, T0)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, "night_1003_prediction_v1_pacing.json")
    json.dump(R, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(R, indent=1, ensure_ascii=False, default=str))
    print("->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
