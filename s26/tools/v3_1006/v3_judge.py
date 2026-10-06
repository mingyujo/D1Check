# -*- coding: utf-8 -*-
"""v3_judge.py — V3 판정 스크립트 (BG 부하율 타임라인 재생의 열 반응, S26 NPU · EffNet).
`V3_사전등록_v1.md` (등록 커밋 036f87b, SHA 40b9c3d4…) §4 · §5 를 글자 그대로. 10 s 칸 · 배율 · HAL 창 · 게이트 줄 · 하한 표시 · 비교 열
고르기는 `night1005_judge.py` (SHA 접두 ca8680c2) 의 함수, 구간 모델 SHA · 통화·화면 감시는 `night1005e_judge.py` (2db1cda5) 의 함수를
import 한다 — 복사·수정 금지 (다르면 IMPORT_ERROR). 결과 보기 전 (2026-10-06 P1g 1부, V3 폰 칸 0) 고정. results\\ 는 읽기만.
같은 입력 두 번 = 같은 바이트.

  py v3_judge.py selftest
  py v3_judge.py run <run_dir> --cell A_base|A_ours|B_base|B_ours --block 1|2 --gate-label <정확한 label> [--watch csv] [--gate-log csv]
                     [--phone-watch csv] --out f.json
  py v3_judge.py pair --base f.json --ours f.json --out f.json
  py v3_judge.py cond --pairs p_b1.json p_b2.json --pred <d1sim/out/v3_prediction_1006.json> --out f.json
  (watchcheck = `night1005e_judge.py watchcheck` 그대로)

규칙 (등록 글자 그대로):
  §4 런: 창 = 체인 구간 0 시작 ~ 마지막 구간 끝 (HAL 1 s 표본). 최고 SKIN · AP · BAT · SKIN ≥ 38 / 40 / 42 ℃ 시간 (s = 표본 수) ·
     status ≥ 1 시간 · 창 끝 SKIN · 완료 추론 수 n (체인 구간 Σ) · 조임 시간 = 가동 구간 10 s 칸 중 지연 배율 ≥ ×1.06 인 칸 수 × 10
     (기준 = 런 첫 가동 구간 처음 30 s 지연 중앙).
  §4 작업량 비 r = n_ours / n_기준선 (블록마다) — 늘 표시. r < 1 이면 "ours 가 (1 − r) × 100 % 덜 함".
  §5 ③: Δ_k = 기준선 최고 SKIN − ours 최고 SKIN. 두 블록 모두 Δ_k ≥ +1.0 → "BG 재생 열 반응 같은 방향 (기준 넘음, 작업량 비 r)" ·
     두 블록 모두 > 0 · 하나라도 < 1.0 → "같은 부호, 기준 안" · 하나라도 ≤ 0 → "같은 방향 아님" · 어느 블록이든 r < 0.95 →
     "작업량 차 큼 — 비교 기술만" (위 판정 대신). 보조 (기술만): Δt38 · Δt40 · Δ조임 시간 · Δ창 끝 SKIN.
  §5 ④: 두 블록 모두 (예측 Δ 부호 = 실측 Δ 부호) 그리고 |예측 Δ − 실측 Δ| ≤ 1.0 ℃ → "전이 확인 (V3 · 1밤 · 2블록)" · 아니면
     "전이 미확인 유지". 예측 = 동결 예측 JSON (그 블록 두 런의 실제 시작 SKIN 평균에 가까운 열 — 보간 없음). 판정 = 주 모형 v2.2 ·
     민감도 (v2.1 · v2 θ0.3 · θ0.75) 는 같은 계산을 나란히 기술.
  §5 결론 표: ③ 기준 넘음 + ④ 전이 확인 → 1행 (조건 A 는 가족 대조군 문장) · ③ 기준 넘음 + ④ 미확인 → 4행 (보류) ·
     ③ 같은 부호 기준 안 / 같은 방향 아님 → 4행 (재현 안 됨).

P1g 가 정함 (결과 전 — 등록이 정하지 않은 곳):
  ① "가동 구간" = duty ≥ 10 인 체인 구간 (d1 = 휴지). 조임 칸 = 가동 구간마다 bins10 (floor(L/10) 칸, 칸 0 포함) 의 지연 중앙 / 기준 —
     night1005_judge 의 throttle_time 은 칸 0 을 빼지만 V3 는 등록 문장대로 가동 구간의 모든 칸을 센다.
  ② 창 끝 SKIN = 마지막 구간 end_ns 에 가장 가까운 HAL 표본 · 시작 SKIN = 구간 0 start_ns 에 가장 가까운 HAL 표본 (night1005 와 같음).
  ③ 비교 수 반올림: Δ · r · |예측 − 실측| 는 소수 6자리 반올림 뒤 비교 (night1005 _sign 과 같음). r 경계: r ≥ 0.95 는 "큼" 아님.
  ④ 부호: + (> 0) · − (< 0) · 0 (= 0). 실측 0 이면 예측 부호와 다름 (예측이 0 이 아닌 한).
  ⑤ 열 고르기 = night1003_judge._pick_col (가까운 쪽 · 같으면 29.5). 범위 [28.3, 31.6] 밖이어도 판정은 하되 "범위 밖" 표시.
  ⑥ ③ 이 "작업량 차 큼" 이면 결론 표 행은 등록이 정하지 않았다 → "행 없음 — 작업량 차 큼 (비교 기술만), 1행 아님" 으로 적고
     영훈 · Cowork 결정으로 넘긴다 (결과 전 고정). ④ 는 그래도 계산해 기술한다.
  ⑦ 감시 이벤트가 있는 런 · 블록이 다른 런 · 조건이 다른 런은 pair 가 받지 않는다 (오류). "하한 미달" 런은 받되 표시한다.
  ⑧ 블록이 2개가 아니면 cond 는 ③ · ④ 를 판정하지 않는다 ("블록 부족 — 판정 안 함").
"""
import argparse, contextlib, hashlib, importlib.util, io, json, os, re, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
OD_SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


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


# --- import (복사·수정 금지) ---------------------------------------------------------------------
N5E_PREFIX = "2db1cda5"
_N5E_PATH = _first_existing(os.path.join(HERE, "night1005e_judge.py"), os.path.join(OD_SIM, "night1005e_judge.py"),
                            os.path.join(REPO, "s26", "tools", "night_1005e", "night1005e_judge.py"))
if not _sha(_N5E_PATH).startswith(N5E_PREFIX):
    raise SystemExit(f"IMPORT_ERROR: night1005e_judge.py SHA {_sha(_N5E_PATH)[:8]} ≠ {N5E_PREFIX} ({_N5E_PATH})")
N5E = _load_module("night1005e_judge", _N5E_PATH)       # 이것이 night1005_judge (ca8680c2) 를 SHA 확인 뒤 import 한다
N5 = N5E.N5
J = N5.J
JudgeError, load_run, segments_of, load_watch, dumps = N5.JudgeError, N5.load_run, N5.segments_of, N5.load_watch, N5.dumps

NPU_SHA = N5E.NPU_SHA
THR = N5.THR["NPU"]                  # 1.06
EPS = N5.EPS
SEL_C = 1.0                          # ③ 기준 ℃
WORK_MIN = N5.WORK_RATIO_MIN         # 0.95
TRANSFER_TOL_C = 1.0                 # ④
MAIN_MODEL = "v22"
SENS_MODELS = ("v21", "v2_t0.3", "v2_t0.75")
ACTIVE_MIN_DUTY = 10
CELLS = {
    "A_base": dict(cond="A", role="base", chain="v3_A_base_v1",
                   segs=[(1, 10), (100, 340), (1, 580), (100, 340), (1, 530), (100, 350), (1, 860)]),
    "A_ours": dict(cond="A", role="ours", chain="v3_A_ours_v1",
                   segs=[(1, 10), (50, 330), (25, 540), (10, 30), (1, 20), (50, 300), (25, 550), (10, 30), (50, 300), (25, 560), (10, 30), (1, 310)]),
    "B_base": dict(cond="B", role="base", chain="v3_B_base_v1",
                   segs=[(1, 50), (100, 340), (1, 540), (100, 340), (1, 550), (100, 350), (1, 559)]),
    "B_ours": dict(cond="B", role="ours", chain="v3_B_ours_v1",
                   segs=[(1, 50), (75, 60), (50, 530), (25, 10), (1, 280), (75, 50), (50, 530), (25, 30), (1, 280), (75, 60), (50, 530), (25, 10),
                         (10, 10), (1, 299)]),
}
COND_NAME = {"A": "NPU-R20-s3.0-l0.2 (λ 0.5 와 같은 타임라인)", "B": "NPU-R20-s2.0-l0.5 (λ 0.2 와 같은 타임라인)"}
A_FAMILY = "가족 대조군 (늘 d50) 도 시뮬에서 같은 이득 — 기한 인지 규칙 고유의 효과라고 쓰지 않는다"
L3 = dict(over="BG 재생 열 반응 같은 방향 (기준 넘음, 작업량 비 r)", inside="같은 부호, 기준 안", notsame="같은 방향 아님",
          work="작업량 차 큼 — 비교 기술만")
L4 = dict(ok="전이 확인 (V3 · 1밤 · 2블록)", no="전이 미확인 유지")


def import_check_v3():
    out = dict(night1005e_judge=dict(path=_N5E_PATH, sha256=_sha(_N5E_PATH), expected_prefix=N5E_PREFIX, ok=_sha(_N5E_PATH).startswith(N5E_PREFIX)))
    out.update(N5E.import_check_e())
    return out


def _load_json(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _r6(x):
    return None if x is None else round(float(x), 6)


def _label(i, d):
    return f"s{i:02d}_d{d}"


# ============================================================ 런 (§4)
def _expect(S, cell):
    c = CELLS[cell]
    segs = S["segments"]
    if len(segs) != len(c["segs"]):
        raise JudgeError(f"구간이 {len(segs)}개 — 기대 {len(c['segs'])} ({cell})")
    for i, (s, (d, L)) in enumerate(zip(segs, c["segs"])):
        if s["label"] != _label(i, d):
            raise JudgeError(f"구간 {i} 라벨 {s['label']} ≠ {_label(i, d)}")
        if s["accelerator"] != "NPU":
            raise JudgeError(f"구간 {i} 가속기 {s['accelerator']} ≠ NPU")
        if s["duty"] != d:
            raise JudgeError(f"구간 {i} duty {s['duty']} ≠ {d}")
        if s["duration_s"] != L:
            raise JudgeError(f"구간 {i} duration_s {s['duration_s']} ≠ {L}")
    cid = (S["meta"].get("chain_spec") or {}).get("chain_id")
    if cid != c["chain"]:
        raise JudgeError(f"chain_id {cid} ≠ {c['chain']} (칸 {cell})")
    return segs


def throttle_bins(segs):
    """가동 구간 (duty ≥ 10) 의 10 s 칸 배율 — 기준 = 첫 가동 구간 처음 30 s 지연 중앙."""
    act = [s for s in segs if s["duty"] is not None and s["duty"] >= ACTIVE_MIN_DUTY]
    if not act:
        raise JudgeError("가동 구간 없음")
    ref, n_ref = J.window_median(act[0], 0, N5.REF_S)
    if ref is None:
        raise JudgeError("첫 가동 구간 처음 30 s 에 추론 없음 — 기준 없음")
    out = []
    for s in act:
        for k, r in enumerate(N5._ratio_bins(s, ref)):
            out.append(dict(seg=s["index"], k=k, ratio=r))
    n_thr = sum(1 for b in out if b["ratio"] is not None and b["ratio"] >= THR - EPS)
    return dict(ref_ms=ref, n_ref=n_ref, first_active_index=act[0]["index"], bins=out, n_bins=len(out), n_throttled=n_thr,
                throttle_time_s=N5.BIN_S * n_thr)


def run_v3(run, cell, block, watch=None, gate_log=None, gate_label=None, phone_watch=None):
    if cell not in CELLS:
        raise JudgeError(f"칸 {cell} ∉ {list(CELLS)}")
    if block not in (1, 2):
        raise JudgeError(f"블록 {block} ∉ (1, 2)")
    if not gate_label:
        raise JudgeError("--gate-label 필수 (부분 문자열 매칭 금지)")
    c = CELLS[cell]
    S = N5E._segments_with_end_sha(run)
    segs = _expect(S, cell)
    msc = N5E.model_sha_check(S, "NPU")
    tb = throttle_bins(segs)
    a_ns, b_ns = segs[0]["start_ns"], segs[-1]["end_ns"]
    hw = N5.hal_window(run, a_ns, b_ns)
    st = N5._th_ns(run, a_ns)
    sk = None if st is None else st["SKIN"]
    grow, gnote = N5._gate_row(gate_log, gate_label, cell, block)
    m = S["meta"]
    n = sum(s["n"] for s in segs)
    return dict(
        kind="v3_run", cell=cell, cond=c["cond"], role=c["role"], block=block, run_id=m.get("run_id"),
        chain_id=(m.get("chain_spec") or {}).get("chain_id"), chain_sha256=m.get("chain_sha256"), termination_reason=m.get("termination_reason"),
        model_sha_check=msc, threshold_ratio=THR,
        work=dict(n=n, n_by_segment=[dict(index=s["index"], label=s["label"], duty=s["duty"], length_s=s["length_s"], n=s["n"],
                                          achieved_duty=s["achieved_duty"], termination_reason=s["termination_reason"],
                                          start_soc=J.soc_at(watch, s["start_wall_ms"])) for s in segs],
                  throttle_time_s=tb["throttle_time_s"], ref30_ms=tb["ref_ms"], n_ref30=tb["n_ref"], first_active_index=tb["first_active_index"],
                  n_active_bins=tb["n_bins"], n_throttled_bins=tb["n_throttled"], bins=tb["bins"]),
        temps=dict(window="구간 0 start_ns ~ 마지막 구간 end_ns", window_s=(b_ns - a_ns) / 1e9, **hw, end=N5._th_ns(run, b_ns)),
        start=dict(start_thermal=st, start_skin=sk, load_start_thermal=N5._th_ns(run, S["load_start_ns"]),
                   band=None if sk is None else ("밴드 안 (29.1~31.6)" if N5.BAND[0] <= sk <= N5.BAND[1] else "밴드 밖 (29.1~31.6)"),
                   gate_row=grow, gate_note=gnote, lower=N5._lower_flag(grow)),
        start_skin=sk, transitions=S["transitions"],
        phone_watch=None if phone_watch is None else N5E.watch_stats(S, N5E.load_phone_watch(phone_watch), phone_watch),
        imports_v3=import_check_v3())


def _events(j):
    return N5E._events_of(j)


# ============================================================ 블록 (pair)
def pair_v3(base, ours):
    for x, role in ((base, "base"), (ours, "ours")):
        if x.get("kind") != "v3_run":
            raise JudgeError(f"{role} 자리가 V3 런 JSON 이 아님")
        if x["role"] != role:
            raise JudgeError(f"{role} 자리에 {x['cell']} ({x['role']})")
        if _events(x):
            raise JudgeError(f"{role} ({x['cell']} b{x['block']}) 에 감시 이벤트 {_events(x)}건 — 무효 런")
    if base["cond"] != ours["cond"]:
        raise JudgeError(f"조건 다름: {base['cond']} vs {ours['cond']}")
    if base["block"] != ours["block"]:
        raise JudgeError(f"블록 다름: {base['block']} vs {ours['block']}")
    tb, to = base["temps"], ours["temps"]

    def dd(x, y):
        return None if (x is None or y is None) else _r6(x - y)
    nb, no = base["work"]["n"], ours["work"]["n"]
    r = _r6(no / nb) if nb else None
    d = dict(d_max_skin=dd(tb["max_SKIN"], to["max_SKIN"]), d_t38_s=dd(tb["t38_s"], to["t38_s"]), d_t40_s=dd(tb["t40_s"], to["t40_s"]),
             d_t42_s=dd(tb["t42_s"], to["t42_s"]), d_throttle_time_s=dd(base["work"]["throttle_time_s"], ours["work"]["throttle_time_s"]),
             d_end_skin=dd((tb.get("end") or {}).get("SKIN"), (to.get("end") or {}).get("SKIN")),
             d_max_ap=dd(tb["max_AP"], to["max_AP"]), d_max_bat=dd(tb["max_BAT"], to["max_BAT"]))
    less = None if r is None or r >= 1 else _r6((1 - r) * 100)
    lower = dict(base=(base["start"].get("lower") or {}).get("label"), ours=(ours["start"].get("lower") or {}).get("label"))
    return dict(kind="v3_pair", cond=base["cond"], block=base["block"],
                base=dict(cell=base["cell"], run_id=base["run_id"], start_skin=base["start_skin"], max_skin=tb["max_SKIN"], n=nb),
                ours=dict(cell=ours["cell"], run_id=ours["run_id"], start_skin=ours["start_skin"], max_skin=to["max_SKIN"], n=no),
                start_skin_mean=None if (base["start_skin"] is None or ours["start_skin"] is None) else (base["start_skin"] + ours["start_skin"]) / 2,
                deltas=d, r=r, r_small=(r is not None and r < WORK_MIN - EPS),
                r_note=None if less is None else f"ours 가 {less:.1f} % 덜 함",
                lower_flags=lower, any_lower_fail=any(v == "하한 미달" for v in lower.values()),
                phone_watch_events=dict(base=_events(base), ours=_events(ours)), imports_v3=import_check_v3())


# ============================================================ 조건 (cond: ③ · ④ · 결론 표)
def _sgn(x):
    x = _r6(x)
    return None if x is None else ("+" if x > 0 else ("-" if x < 0 else "0"))


def judge_3(pairs):
    ds = [p["deltas"]["d_max_skin"] for p in pairs]
    rs = [p["r"] for p in pairs]
    if any(r is None or r < WORK_MIN - EPS for r in rs):
        lab = L3["work"]
    elif all(d is not None and d >= SEL_C - EPS for d in ds):
        lab = L3["over"]
    elif all(d is not None and d > 0 for d in ds):
        lab = L3["inside"]
    else:
        lab = L3["notsame"]
    rtxt = " / ".join("—" if r is None else f"{r:.3f}" for r in rs)
    notes = [p["r_note"] for p in pairs if p.get("r_note")]
    sent = f"{lab} — Δ최고 SKIN 블록1 / 블록2 = " + " / ".join("—" if d is None else f"{d:+.2f} ℃" for d in ds) + f" · 작업량 비 r = {rtxt}"
    if notes:
        sent += " (" + " · ".join(f"블록{p['block']} {p['r_note']}" for p in pairs if p.get("r_note")) + ")"
    aux = {k: [p["deltas"][k] for p in pairs] for k in ("d_t38_s", "d_t40_s", "d_throttle_time_s", "d_end_skin")}
    return dict(label=lab, sentence=sent, deltas=ds, r=rs, aux=aux)


def judge_4(pairs, pred, cond, model):
    blocks = []
    for p in pairs:
        cols = pred["blocks"][cond][model]
        sk = p["start_skin_mean"]
        col = N5._pick_col(list(cols.keys()), sk) if sk is not None else None
        pd = None if col is None else cols[col]["d_max_skin"]
        md = p["deltas"]["d_max_skin"]
        same = (pd is not None and md is not None and _sgn(pd) == _sgn(md))
        diff = None if (pd is None or md is None) else _r6(abs(pd - md))
        ok = same and diff is not None and diff <= TRANSFER_TOL_C + EPS
        rng = None if sk is None else (N5.DEV_RANGE[0] <= sk <= N5.DEV_RANGE[1])
        blocks.append(dict(block=p["block"], start_skin_mean=sk, column=col, in_range=rng, range_note=None if rng in (None, True) else "범위 밖 [28.3, 31.6] — 판정은 함",
                           pred_d=pd, meas_d=md, sign_pred=_sgn(pd), sign_meas=_sgn(md), sign_same=same, abs_diff=diff, ok=ok,
                           pred_r=None if col is None else cols[col]["r_model"]))
    return dict(model=model, label=L4["ok"] if (len(blocks) == 2 and all(b["ok"] for b in blocks)) else L4["no"], blocks=blocks)


def conclusion_row(cond, j3, j4):
    if j3["label"] == L3["over"] and j4["label"] == L4["ok"]:
        row, txt = 1, "1행"
        if cond == "A":
            txt += " — " + A_FAMILY
    elif j3["label"] == L3["over"]:
        row, txt = 4, "4행 — 전이 미확인이라 폰 효과 결론 보류 (폰 관측은 기술)"
    elif j3["label"] in (L3["inside"], L3["notsame"]):
        row, txt = 4, "4행 — 시뮬 결과가 폰 BG 재생에서 재현되지 않았다"
    else:
        row, txt = None, "행 없음 — 작업량 차 큼 (비교 기술만), 1행 아님 (등록이 정하지 않음 → 영훈 · Cowork 결정)"
    return dict(row=row, text=txt)


def cond_v3(pairs, pred, pred_path=None):
    if len(pairs) != 2:
        return dict(kind="v3_cond", judged=False, label="블록 부족 — 판정 안 함", n_pairs=len(pairs))
    pairs = sorted(pairs, key=lambda p: p["block"])
    if [p["block"] for p in pairs] != [1, 2]:
        raise JudgeError(f"블록이 1 · 2 가 아님: {[p['block'] for p in pairs]}")
    if pairs[0]["cond"] != pairs[1]["cond"]:
        raise JudgeError("두 블록의 조건이 다름")
    for p in pairs:
        if p.get("kind") != "v3_pair":
            raise JudgeError("V3 블록 JSON 이 아님")
        if any((p.get("phone_watch_events") or {}).values()):
            raise JudgeError(f"블록 {p['block']} 에 감시 이벤트 런")
    cond = pairs[0]["cond"]
    j3 = judge_3(pairs)
    j4 = judge_4(pairs, pred, cond, MAIN_MODEL)
    sens = {m: judge_4(pairs, pred, cond, m) for m in SENS_MODELS}
    return dict(kind="v3_cond", judged=True, cond=cond, condition=COND_NAME[cond], j3=j3, j4_main=j4, j4_sensitivity=sens,
                conclusion=conclusion_row(cond, j3, j4), any_lower_fail=[p["block"] for p in pairs if p.get("any_lower_fail")],
                pred=dict(path=pred_path, sha256=None if pred_path is None else _sha(pred_path), main_model=MAIN_MODEL),
                imports_v3=import_check_v3())


# ============================================================ selftest (합성 — 결과 보기 전 양방향)
def _mk(tmp, tag, cell, lat_fn, skin_fn, rate=50.0):
    c = CELLS[cell]
    segs = [dict(accelerator="NPU", duty=d, duration_s=L, lat_ms=lat_fn, label=_label(i, d)) for i, (d, L) in enumerate(c["segs"])]
    rd = J._synth_run(os.path.join(tmp, tag), c["chain"], segs, rate=rate, thermal=False)
    S = segments_of(load_run(rd))
    N5._write_hal(rd, S["load_start_ns"], S["load_end_ns"], skin_fn)
    return rd, S


def _fp(cond, block, d, r, sk=30.0):
    return dict(kind="v3_pair", cond=cond, block=block, deltas=dict(d_max_skin=d, d_t38_s=0.0, d_t40_s=0.0, d_throttle_time_s=0.0, d_end_skin=0.0),
                r=r, r_note=None if r >= 1 else f"ours 가 {(1 - r) * 100:.1f} % 덜 함", start_skin_mean=sk, phone_watch_events=dict(base=0, ours=0))


def _fpred(cond, d295, d305, model=MAIN_MODEL):
    cols = {"29.5": dict(d_max_skin=d295, r_model=0.9), "30.5": dict(d_max_skin=d305, r_model=0.9)}
    return dict(blocks={cond: {m: cols for m in (MAIN_MODEL,) + SENS_MODELS}})


def selftest():
    res = []

    def check(name, cond, got):
        res.append((name, bool(cond), got))
    # import · 고정 셀이 체인 파일과 같은지
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rce = N5E.selftest()
    mm = re.findall(r"selftest 전체: \w+ \((\d+)/(\d+)\)", buf.getvalue())
    m = mm[-1] if mm else None                     # 마지막 줄 = night1005e 자신 (앞 줄은 그 안의 night1005 49/49)
    check("import night1005e_judge selftest 그대로 35/35", rce == 0 and m and m[0] == m[1] == "35", m if m else buf.getvalue()[-200:])
    ic = import_check_v3()
    check("import SHA 접두 (night1005e 2db1cda5 · night1005 ca8680c2 · m1m2 ea282d4a · night1003 a5ceab41)", all(v["ok"] for v in ic.values()),
          {k: v["sha256"][:8] for k, v in ic.items()})
    same = {}
    for cell, c in CELLS.items():
        p = os.path.join(REPO, "tools", "chains", c["chain"] + ".json")
        ch = _load_json(p)
        same[cell] = [(s["duty"], s["duration_s"]) for s in ch["segments"]] == c["segs"] and [s["label"] for s in ch["segments"]] == \
            [_label(i, d) for i, (d, _) in enumerate(c["segs"])]
    check("칸 표 = tools/chains/v3_*.json (duty · 길이 · 라벨)", all(same.values()), same)
    # ③ 네 갈래 + r 경계
    j = judge_3([_fp("A", 1, 1.0, 1.0), _fp("A", 2, 2.5, 0.97)])
    check("③ 두 블록 Δ ≥ 1.0 (경계 1.0 포함) → 기준 넘음", j["label"] == L3["over"], j["label"])
    j = judge_3([_fp("A", 1, 0.999999, 1.0), _fp("A", 2, 2.5, 1.0)])
    check("③ 0.999999 → 같은 부호, 기준 안", j["label"] == L3["inside"], j["label"])
    j = judge_3([_fp("A", 1, 0.0, 1.0), _fp("A", 2, 2.5, 1.0)])
    check("③ 하나라도 ≤ 0 (0.0) → 같은 방향 아님", j["label"] == L3["notsame"], j["label"])
    j = judge_3([_fp("A", 1, -0.5, 1.0), _fp("A", 2, 2.5, 1.0)])
    check("③ 음수 → 같은 방향 아님", j["label"] == L3["notsame"], j["label"])
    j = judge_3([_fp("A", 1, 3.0, 0.949999), _fp("A", 2, 3.0, 1.0)])
    check("③ r 0.949999 < 0.95 → 작업량 차 큼 (위 판정 대신)", j["label"] == L3["work"], j["label"])
    j = judge_3([_fp("A", 1, 3.0, 0.95), _fp("A", 2, 3.0, 0.95)])
    check("③ r = 0.95 → 큼 아님 · 기준 넘음 · 문장에 5.0 % 덜 함", j["label"] == L3["over"] and "5.0 % 덜 함" in j["sentence"], j["sentence"])
    j = judge_3([_fp("A", 1, -3.0, 0.90), _fp("A", 2, -3.0, 1.0)])
    check("③ r < 0.95 이면 방향 아님보다 앞선다", j["label"] == L3["work"], j["label"])
    # ④ 부호 · |차| 1.0 경계 · 열 고르기
    pr = _fpred("A", 3.0, 2.0)
    j = judge_4([_fp("A", 1, 2.0, 1.0, 29.9), _fp("A", 2, 2.0, 1.0, 29.9)], pr, "A", MAIN_MODEL)
    check("④ |3.0 − 2.0| = 1.0 → 경계 포함 확인 (29.9 → 열 29.5)", j["label"] == L4["ok"] and j["blocks"][0]["column"] == "29.5", [(b["column"], b["abs_diff"]) for b in j["blocks"]])
    j = judge_4([_fp("A", 1, 1.999, 1.0, 29.9), _fp("A", 2, 2.0, 1.0, 29.9)], pr, "A", MAIN_MODEL)
    check("④ |3.0 − 1.999| = 1.001 > 1.0 → 미확인", j["label"] == L4["no"], [b["abs_diff"] for b in j["blocks"]])
    j = judge_4([_fp("A", 1, -0.5, 1.0, 30.6), _fp("A", 2, 2.0, 1.0, 30.6)], _fpred("A", 3.0, 0.3), "A", MAIN_MODEL)
    check("④ 부호 다름 (예측 +0.3 · 실측 −0.5, |차| 0.8) → 미확인", j["label"] == L4["no"] and j["blocks"][0]["sign_same"] is False, j["blocks"][0])
    j = judge_4([_fp("A", 1, 2.0, 1.0, 30.0), _fp("A", 2, 2.0, 1.0, 30.1)], pr, "A", MAIN_MODEL)
    check("④ 열 고르기: 30.0 (같은 거리) → 29.5 · 30.1 → 30.5", [b["column"] for b in j["blocks"]] == ["29.5", "30.5"], [b["column"] for b in j["blocks"]])
    j = judge_4([_fp("A", 1, 2.0, 1.0, 32.0), _fp("A", 2, 2.0, 1.0, 30.0)], pr, "A", MAIN_MODEL)
    check("④ 범위 밖 (32.0) 표시 · 판정은 함", j["blocks"][0]["range_note"] is not None and j["blocks"][0]["column"] == "30.5", j["blocks"][0]["range_note"])
    # 결론 표
    check("결론: 기준 넘음 + 확인 → 1행 (A 는 가족 대조군 문장)", conclusion_row("A", dict(label=L3["over"]), dict(label=L4["ok"]))["row"] == 1
          and A_FAMILY in conclusion_row("A", dict(label=L3["over"]), dict(label=L4["ok"]))["text"]
          and A_FAMILY not in conclusion_row("B", dict(label=L3["over"]), dict(label=L4["ok"]))["text"], "")
    check("결론: 기준 넘음 + 미확인 → 4행 보류", "보류" in conclusion_row("A", dict(label=L3["over"]), dict(label=L4["no"]))["text"], "")
    check("결론: 기준 안 · 같은 방향 아님 → 4행 재현 안 됨", all("재현되지 않았다" in conclusion_row("B", dict(label=x), dict(label=L4["ok"]))["text"]
                                                     for x in (L3["inside"], L3["notsame"])), "")
    check("결론: 작업량 차 큼 → 행 없음 (1행 아님)", conclusion_row("A", dict(label=L3["work"]), dict(label=L4["ok"]))["row"] is None, "")
    c1 = cond_v3([_fp("A", 1, 2.0, 1.0)], pr)
    check("cond 블록 1개 → 판정 안 함", c1["judged"] is False, c1["label"])
    tmp = tempfile.mkdtemp(prefix="v3_selftest_")
    try:
        # 런: 합성 체인 (A_base) — n · 조임 · 창 온도 · 창 끝 · 칸 착오
        base_lat = lambda t: 10.0
        rd, S = _mk(tmp, "ab", "A_base", base_lat, lambda t: 31.0 if t < 100 else (38.5 if t < 2000 else 33.0))
        run = load_run(rd)
        j = run_v3(run, "A_base", 1, gate_label="x")
        n_exp = sum(s["n"] for s in S["segments"])
        check("run: n = 구간 Σ", j["work"]["n"] == n_exp and n_exp > 0, (j["work"]["n"], n_exp))
        check("run: 조임 0 (지연 일정) · 가동 칸 = 34+34+35", j["work"]["throttle_time_s"] == 0 and j["work"]["n_active_bins"] == 103,
              (j["work"]["throttle_time_s"], j["work"]["n_active_bins"]))
        check("run: 창 끝 SKIN 33.0 · 최고 38.5 · t38 > 0", j["temps"]["end"]["SKIN"] == 33.0 and j["temps"]["max_SKIN"] == 38.5 and j["temps"]["t38_s"] > 0,
              (j["temps"]["end"]["SKIN"], j["temps"]["max_SKIN"], j["temps"]["t38_s"]))
        check("run: 모델 SHA 미기록 표시 (합성)", j["model_sha_check"]["label"] == "모델 SHA 미기록", j["model_sha_check"]["label"])
        try:
            run_v3(run, "B_base", 1, gate_label="x")
            check("run: 다른 칸 표 → 오류", False, "no error")
        except JudgeError as e:
            check("run: 다른 칸 표 → 오류", True, str(e)[:60])
        try:
            run_v3(run, "A_base", 1)
            check("run: --gate-label 없음 → 오류", False, "no error")
        except JudgeError as e:
            check("run: --gate-label 없음 → 오류", True, str(e)[:40])
        # 조임: 두 번째 가동 구간부터 ×1.2 → 그 구간 칸 수만큼
        seg_t = {}
        acc = 0.0
        for i, (d, L) in enumerate(CELLS["A_ours"]["segs"]):
            seg_t[i] = L
        rd2, S2 = _mk(tmp, "ao", "A_ours", lambda t: 10.0, lambda t: 31.0)
        run2 = load_run(rd2)
        # 구간 2 (d25 540 s) 지연을 ×1.2 로 바꾼 런
        jp = [os.path.join(rd2, "gpu", f) for f in os.listdir(os.path.join(rd2, "gpu"))][0]
        seg2 = S2["segments"][2]
        lines = open(jp, encoding="utf-8").readlines()
        out = []
        for ln in lines:
            e = json.loads(ln)
            if e.get("event") == "inference" and seg2["start_ns"] <= int(e["start_mono_ns"]) and int(e["mono_ns"]) <= seg2["end_ns"]:
                e["latency_ns"] = int(e["latency_ns"] * 1.2)
            out.append(json.dumps(e, separators=(",", ":")) + "\n")
        open(jp, "w", encoding="utf-8").writelines(out)
        j2 = run_v3(load_run(rd2), "A_ours", 2, gate_label="x")
        check("run: d25 540 s 구간 ×1.2 → 조임 540 s (54칸, 문턱 1.06)", j2["work"]["throttle_time_s"] == 540, j2["work"]["throttle_time_s"])
        check("run: 가동 칸 수 (d1 구간 제외) = 33+54+3+30+55+3+30+56+3", j2["work"]["n_active_bins"] == 267, j2["work"]["n_active_bins"])
        # pair: r · Δ · 감시 이벤트 거부 · 역할 착오
        jb = dict(j, block=2)
        p = pair_v3(jb, j2)
        check("pair: Δ = base − ours (38.5 − 31.0 = 7.5) · r = n_ours / n_base", p["deltas"]["d_max_skin"] == 7.5 and
              p["r"] == _r6(j2["work"]["n"] / j["work"]["n"]), (p["deltas"]["d_max_skin"], p["r"]))
        try:
            pair_v3(j2, jb)
            check("pair: 자리 바뀜 → 오류", False, "no error")
        except JudgeError as e:
            check("pair: 자리 바뀜 → 오류", True, str(e)[:40])
        try:
            pair_v3(dict(jb, phone_watch=dict(n_events=1)), j2)
            check("pair: 감시 이벤트 런 → 오류", False, "no error")
        except JudgeError as e:
            check("pair: 감시 이벤트 런 → 오류", True, str(e)[:40])
        try:
            pair_v3(j, j2)
            check("pair: 블록 다름 → 오류", False, "no error")
        except JudgeError as e:
            check("pair: 블록 다름 → 오류", True, str(e)[:40])
        # cond 끝까지 (합성) + 결정성
        p1 = dict(p, block=1)
        cpred = _fpred("A", 7.0, 7.0)
        c = cond_v3([p, p1], cpred)
        c_again = cond_v3([p1, p], cpred)
        check("cond: 합성 끝까지 · 같은 입력 = 같은 바이트", dumps(c) == dumps(c_again) and c["j3"]["label"] in L3.values(), c["j3"]["label"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(1 for _, ok, _ in res if ok)
    for name, ok, got in res:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  got={got}"))
    print(f"selftest {'PASS' if n_ok == len(res) else 'FAIL'} ({n_ok}/{len(res)})")
    return 0 if n_ok == len(res) else 1


# ============================================================ CLI
def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    r = sub.add_parser("run")
    r.add_argument("run_dir"); r.add_argument("--cell", required=True, choices=list(CELLS)); r.add_argument("--block", type=int, required=True)
    r.add_argument("--gate-label", required=True); r.add_argument("--watch"); r.add_argument("--gate-log"); r.add_argument("--phone-watch")
    r.add_argument("--out", required=True)
    p = sub.add_parser("pair")
    p.add_argument("--base", required=True); p.add_argument("--ours", required=True); p.add_argument("--out", required=True)
    c = sub.add_parser("cond")
    c.add_argument("--pairs", nargs="+", required=True); c.add_argument("--pred", required=True); c.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return selftest()
    try:
        if a.cmd == "run":
            out = run_v3(load_run(a.run_dir), a.cell, a.block, load_watch(a.watch), a.gate_log, a.gate_label, a.phone_watch)
        elif a.cmd == "pair":
            out = pair_v3(_load_json(a.base), _load_json(a.ours))
        else:
            out = cond_v3([_load_json(x) for x in a.pairs], _load_json(a.pred), a.pred)
    except JudgeError as e:
        print("JUDGE_ERROR:", e)
        return 2
    s = dumps(out)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(s + "\n")
    print(s[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
