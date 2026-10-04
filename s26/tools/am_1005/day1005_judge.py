# -*- coding: utf-8 -*-
"""day1005_judge.py — 측정 1005 추가 판정 (사전 등록 `측정1005_사전등록_v1.md` §3~§5 의 새 항목만).

입력 = 고정 판정기 `night1004_judge.py` (SHA fd22d3ba…, 무변경) 의 출력 JSON — 이번 런 (--cur) 과 10/4 같은 칸 (--prev).
기존 판정 (해제·재조임·분류·가설·전제) 은 다시 계산하지 않는다 — 읽어서 옮기고, 아래 새 항목만 계산한다.
10/4 런 (--prev) 은 이 규칙을 정하기 전에 본 자료 (개발) 라서 같은 함수로 계산하되 "기술" 로만 나란히 둔다.
같은 입력 두 번 = 같은 바이트. results\\ 는 읽지 않는다 (판정 JSON 만).

  py day1005_judge.py selftest
  py day1005_judge.py n50p2   --cur <N50P2.json>   --prev <out_1004\\N50P.json>  [--out f.json]
  py day1005_judge.py g50p2   --cur <G50P2.json>   --prev <out_1004\\G50P.json>  [--out f.json]
  py day1005_judge.py ni300r2 --cur <NI300r2.json> --prev <out_1004\\NI300.json> [--out f.json]

새 항목 (사전 등록 글자 그대로 — 결과 본 뒤 바꾸지 않는다):
  공통: 시작 상태 = 판정 JSON 의 start_skin (구간 0 시작 HAL SKIN) 이 [29.1, 31.6] 안이면 "밴드 안", 아니면 "밴드 밖" (판정은 한다, 표시)
  N50P2 §3:
    2계단 전제 = 가열 구간 1-1 진입 (heat.onset_1_1_s) 이 있다. 없으면 "2계단 미도달 — 뜨거운 채 해제 시험 불가"
    뜨거운 채 해제 = (2계단 도달 · 해제 있음 · 1계단 온도 있음) 일 때만: dS = 해제 칸 SKIN_k − 1계단 진입 SKIN,
      dA = 해제 칸 AP_k − 1계단 진입 AP (같은 런). dS ≥ +0.2 이고 dA ≥ +0.2 → "위에서" · dS ≤ −0.2 또는 dA ≤ −0.2 → "아래에서" ·
      나머지 → "경계". 해제 없음 (R50-none) → "해제 없음"
    v2 변형 대응 (v2_예측_밤1004 §5 표) 은 2계단 도달일 때만 · R50-fast 는 "위에서" 일 때만 — 아니면 "판정 안 함"
    정책 입력 (기술) = 탐침 1~5 칸 중앙 배율 + 그때 상태 ("2계단" / "1계단")
  G50P2 §4:
    d50 재조임 = 해제 칸 k 뒤의 첫 칸 k′ (k < k′ ≤ 44) 로서 칸 k′ 와 뒤 3칸이 모두 ≥ ref_d50 × 1.10 → 10k′ s, SKIN_k′·AP_k′.
      해제 없음 → "해제 없음" · k′ 없음 → "탐침 480 s 안 재조임 없음"
    온도 차 Δ = SKIN_k′ − (같은 런 d100 1-1 진입 SKIN). Δ ≥ +0.5 → "높은 온도" · |Δ| < 0.5 → "같은 온도대" · Δ ≤ −0.5 → "낮은 온도".
      d100 진입이 없으면 "d100 진입 없음 — 비교 불가"
    기술: 탐침 끝 60 s (칸 42~47) 배율 중앙
  NI300r2 §5:
    분류 재현 = 이번 재조임 분류 (class_token) 가 10/4 와 같으면 "분류 재현", 다르면 "분류 불일치" · 재조임 시각 차 (s, 기술)
    전환 잔재 = 재가열 칸 0·1 배율 둘 다 ≥ ×2.0 → "전환 잔재 재현" · 하나만 → "한 칸만" · 둘 다 아니면 "없음"
    기술: 휴지 0 → 299 s ΔSKIN·ΔAP·ΔBAT (Δ℃) · 재가열 시작 온도
"""
import argparse
import hashlib
import json
import os
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BAND = (29.1, 31.6)
HOT_TOL = 0.2          # ℃ — 뜨거운 채 해제의 경계 폭
G_RETIGHTEN = 1.10     # G50P2 d50 재조임 배율 (1-1 진입과 같은 꼴)
G_LAST_K = 44          # 마지막 검정 칸 (탐침 480 s = 48칸, 뒤 3칸)
G_DELTA = 0.5          # ℃ — d50 재조임 온도 vs d100 진입 온도
RESIDUE = 2.0          # NI300 전환 잔재 배율


class JudgeError(Exception):
    pass


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(path):
    if not path or not os.path.exists(path):
        raise JudgeError(f"파일 없음: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _get(d, *keys):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            raise JudgeError(f"필드 없음: {'.'.join(keys)}")
        cur = cur[k]
    return cur


def band_label(j):
    s = j.get("start_skin")
    if s is None:
        return dict(start_skin=None, label="start_skin 없음")
    inside = BAND[0] <= s <= BAND[1]
    return dict(start_skin=s, in_band=inside, label=("밴드 안 (29.1~31.6)" if inside else "밴드 밖 (29.1~31.6)"))


def _ratios(bins, ref):
    if not ref or ref <= 0:
        raise JudgeError("ref 가 0 이하")
    for i, b in enumerate(bins):
        if b.get("k") != i:
            raise JudgeError(f"칸 번호가 연속이 아님: index {i} k {b.get('k')}")
    return [b["median_ms"] / ref for b in bins]


def _t(d):
    if not d:
        return None
    return {k: d.get(k) for k in ("SKIN", "AP", "BAT", "status") if k in d}


# ---------------------------------------------------------------- N50P2
def hot_release(j):
    heat = _get(j, "heat")
    probe = _get(j, "probe")
    rel = probe.get("release") or {}
    two_step = heat.get("onset_1_1_s") is not None
    step1 = heat.get("step1_thermal")
    if not two_step:
        return dict(token="시험 불가", two_step=False,
                    label="2계단 미도달 (가열 420 s 안 1-1 진입 없음) — 뜨거운 채 해제 시험 불가")
    if not rel.get("recovered"):
        return dict(token="해제 없음", two_step=True, label="2계단 도달 · 탐침 안 해제 없음 — 온도 비교 해당 없음")
    if not step1 or step1.get("SKIN") is None or step1.get("AP") is None:
        return dict(token="시험 불가", two_step=True, label="1계단 진입 온도 없음 — 비교 불가")
    dS = round(rel["SKIN_k"] - step1["SKIN"], 3)
    dA = round(rel["AP_k"] - step1["AP"], 3)
    if dS >= HOT_TOL and dA >= HOT_TOL:
        tok, lab = "위에서", "1계단 진입 온도 위에서 풀림 (SKIN·AP 둘 다 +0.2 ℃ 이상)"
    elif dS <= -HOT_TOL or dA <= -HOT_TOL:
        tok, lab = "아래에서", "1계단 진입 온도 아래에서 풀림 — 온도 히스테리시스와 못 가름"
    else:
        tok, lab = "경계", "1계단 진입 온도와 0.2 ℃ 안 — 못 가름"
    return dict(token=tok, two_step=True, label=lab, dSKIN=dS, dAP=dA,
                release_SKIN_k=rel["SKIN_k"], release_AP_k=rel["AP_k"],
                step1_SKIN=step1["SKIN"], step1_AP=step1["AP"])


def n50p2_verdict(cls, hot_tok):
    if hot_tok == "시험 불가":
        return "2계단 미도달 — \"뜨거운 채 풀리나\" 시험 불가 (v1 판정은 기록만)"
    if cls == "R50-fast" and hot_tok == "위에서":
        return ("R50-fast · 1계단 진입 온도 위에서 해제 — 온도만의 지도 + 히스테리시스로는 안 나오는 관측 (2런째, 10/3 d10 과 같은 방향) · "
                "v1 표: H-timer 와 H-load(θ > 50 %) 유지 → 다음은 d75")
    if cls == "R50-fast":
        return "R50-fast · 해제 온도가 진입 온도 아래 또는 경계 — 온도 히스테리시스와 못 가름 · 다음은 d75"
    if cls == "R50-slow":
        return f"R50-slow · v1 표: H-timer 기각 · H-load(θ ≤ 50 %) 쪽 · 해제 온도 비교: {hot_tok}"
    if cls == "R50-none":
        return "R50-none · v1 표: H-timer 기각 · H-load(θ ≤ 50 %) 쪽 — d75 불필요"
    return f"{cls} · v1 규칙대로 (분류 없음) · 해제 온도 비교: {hot_tok}"


V2_N50P = {  # v2_예측_밤1004.md §5 (동결 f0b8f383…) 의 대응표 [D]
    "R50-fast": "θ_NPU > 0.5 변형 유지 · θ ≤ 0.5 기각",
    "R50-none": "θ ≤ 0.5 유지",
    "R50-slow": "이진형 기각 → 연속형 (Lk κ_lo) 쪽",
}


def n50p2_variant(cls, hot_tok):
    """v2 변형 대응은 2계단 상태에서만 (모형 조건과 같은 상태). R50-fast 는 '위에서' 일 때만."""
    if hot_tok == "시험 불가":
        return "판정 안 함 — 2계단 미도달 (모형 조건과 다른 상태)"
    if cls == "R50-fast" and hot_tok != "위에서":
        return "판정 안 함 — 해제 온도가 진입 온도 아래·경계 (히스테리시스와 못 가름)"
    return V2_N50P.get(cls, "대응 없음 (미분류)")


def _n50_summary(j):
    heat, probe = j["heat"], j["probe"]
    rel = probe.get("release") or {}
    return dict(run_id=j.get("run_id"), start=band_label(j), start_thermal=_t(j.get("start_thermal")),
                heat_start=_t(heat.get("start_thermal")), step1_s=heat.get("step1_s"), step1=_t(heat.get("step1_thermal")),
                onset_1_1_s=heat.get("onset_1_1_s"), onset=_t(heat.get("onset_thermal")),
                ratio_360_420=heat.get("ratio_window"), heat_end=_t(heat.get("end_thermal")),
                class_token=probe.get("class_token"), release_s=probe.get("release_s"),
                release_SKIN_k=rel.get("SKIN_k"), release_AP_k=rel.get("AP_k"),
                probe_1_5=probe.get("bins_1_5_median"))


def n50p2(cur, prev):
    cls = _get(cur, "probe", "class_token")
    hot = hot_release(cur)
    two = hot.get("two_step")
    return dict(
        rule="측정1005_사전등록_v1 §3 (N50P2) — 2계단 전제 · 뜨거운 채 해제 (해제 칸 SKIN_k·AP_k − 같은 런 1계단 진입 SKIN·AP, 경계 ±0.2 ℃)",
        start=band_label(cur),
        v1=dict(class_token=cls, classification=_get(cur, "probe", "classification"), release_s=cur["probe"].get("release_s"),
                premise_ok=cur["heat"].get("premise_ok"), premise_label=cur["heat"].get("premise_label"),
                conclusion=cur.get("conclusion"), hypotheses=cur.get("hypotheses")),
        hot_release=hot,
        verdict=n50p2_verdict(cls, hot["token"]),
        v2_variant=n50p2_variant(cls, hot["token"]),
        policy_input=dict(probe_1_5_median=cur["probe"].get("bins_1_5_median"),
                          state=("2계단" if two else "1계단 또는 미도달"),
                          label="뜨거운 NPU d50 첫 1분 배율 (기술)"),
        side_by_side=dict(cur=_n50_summary(cur), prev_1004=_n50_summary(prev),
                          note="10/4 = 이 규칙을 정하기 전에 본 자료 (개발) — 기술만"),
        prev_hot_release_desc=hot_release(prev),
    )


# ---------------------------------------------------------------- G50P2
def d50_retighten(j):
    probe = _get(j, "probe")
    rel = probe.get("release") or {}
    if not rel.get("recovered"):
        return dict(token="해제 없음", label="해제 없음 — 재조임 판정 해당 없음")
    ref = _get(j, "ref_d50_ms")
    bins = probe["bins"]
    r = _ratios(bins, ref)
    rk = rel["k"]
    hit = None
    for k in range(rk + 1, G_LAST_K + 1):
        if k + 3 < len(r) and all(x >= G_RETIGHTEN for x in r[k:k + 4]):
            hit = k
            break
    tail = sorted(r[42:48])
    tail_med = round((tail[2] + tail[3]) / 2, 6) if len(tail) == 6 else None
    if hit is None:
        return dict(token="재조임 없음", label="탐침 480 s 안 재조임 없음 (칸 k′ + 뒤 3칸 ≥ ×1.10 없음)",
                    release_k=rk, tail_42_47_median_ratio=tail_med)
    onset = (j.get("heat") or {}).get("onset_thermal")
    out = dict(token="재조임", k=hit, t_s=10 * hit, ratio_k=round(r[hit], 6), SKIN_k=bins[hit]["SKIN"], AP_k=bins[hit]["AP"],
               release_k=rk, tail_42_47_median_ratio=tail_med)
    if not onset or onset.get("SKIN") is None:
        out.update(delta=None, temp_token="비교 불가", temp_label="d100 진입 없음 — 비교 불가")
        return out
    d = round(bins[hit]["SKIN"] - onset["SKIN"], 3)
    if d >= G_DELTA:
        tt, tl = "높은 온도", "d50 은 같은 런 d100 진입보다 높은 온도에서 다시 조여졌다"
    elif d <= -G_DELTA:
        tt, tl = "낮은 온도", "d50 은 같은 런 d100 진입보다 낮은 온도에서 다시 조여졌다"
    else:
        tt, tl = "같은 온도대", "d50 은 같은 런 d100 진입과 같은 온도대 (±0.5 ℃ 안) 에서 다시 조여졌다"
    out.update(delta=d, onset_SKIN=onset["SKIN"], onset_AP=onset.get("AP"), temp_token=tt, temp_label=tl,
               label=f"재조임 {10 * hit} s · SKIN {bins[hit]['SKIN']} · AP {bins[hit]['AP']}")
    return out


V2_G50P = {  # v2_예측_밤1004.md §5 [D]
    "R50-fast": "v2 GPU gate 기각 (θ_GPU 0.3 틀림 — d50 도 푼다) → v1 AP 적분형 쪽",
    "R50-none": "v2 GPU gate 와 같은 방향",
    "R50-slow": "깊이가 온도 따라 서서히 풀리는 쪽",
}


def g50p2(cur, prev):
    cls = _get(cur, "probe", "class_token")
    rt = d50_retighten(cur)
    return dict(
        rule="측정1005_사전등록_v1 §4 (G50P2) — 해제 뒤 d50 재조임 (칸 k′ + 뒤 3칸 ≥ ref_d50 × 1.10, k′ ≤ 44) · Δ = SKIN_k′ − d100 진입 SKIN (±0.5 ℃)",
        start=band_label(cur),
        v1=dict(class_token=cls, classification=_get(cur, "probe", "classification"), release_s=cur["probe"].get("release_s"),
                hypotheses=cur.get("hypotheses"), premise_ok=cur["heat"].get("premise_ok"), premise_label=cur["heat"].get("premise_label"),
                release_AP_k=(cur["probe"].get("release") or {}).get("AP_k")),
        retighten=rt,
        v2_variant=V2_G50P.get(cls, "대응 없음 (미분류)"),
        side_by_side=dict(cur=dict(start=band_label(cur), onset_1_1_s=cur["heat"].get("onset_1_1_s"), onset=_t(cur["heat"].get("onset_thermal")),
                                   ratio_240_300=cur["heat"].get("ratio_window"), class_token=cls, release_s=cur["probe"].get("release_s")),
                          prev_1004=dict(start=band_label(prev), onset_1_1_s=prev["heat"].get("onset_1_1_s"), onset=_t(prev["heat"].get("onset_thermal")),
                                         ratio_240_300=prev["heat"].get("ratio_window"), class_token=prev["probe"].get("class_token"),
                                         release_s=prev["probe"].get("release_s"), retighten_desc=d50_retighten(prev)),
                          note="10/4 = 이 규칙을 정하기 전에 본 자료 (개발) — 기술만"),
    )


# ---------------------------------------------------------------- NI300r2
def _residue(j):
    reh = _get(j, "reheat")
    ref = _get(j, "ref_d100_ms")
    r = _ratios(reh["bins"], ref)
    a, b = r[0], r[1]
    n = int(a >= RESIDUE) + int(b >= RESIDUE)
    tok = {2: "전환 잔재 재현", 1: "한 칸만", 0: "없음"}[n]
    return dict(token=tok, bin0=round(a, 6), bin1=round(b, 6))


def _rest_cooling(j):
    temps = {t["t"]: t for t in _get(j, "rest", "temps")}
    t0, t1 = temps.get(0), temps.get(299)
    if not t0 or not t1:
        return dict(label="휴지 0 · 299 s 표본 없음")
    return dict(t0=_t(t0), t299=_t(t1), dSKIN=round(t1["SKIN"] - t0["SKIN"], 2), dAP=round(t1["AP"] - t0["AP"], 2),
                dBAT=round(t1["BAT"] - t0["BAT"], 2))


def ni300r2(cur, prev):
    c_tok = _get(cur, "reheat", "class_token")
    p_tok = _get(prev, "reheat", "class_token")
    c_s = cur["reheat"].get("retighten_s")
    p_s = prev["reheat"].get("retighten_s")
    return dict(
        rule="측정1005_사전등록_v1 §5 (NI300r2) — 분류 재현 (10/4 와 같은 분류) · 전환 잔재 (재가열 칸 0·1 ≥ ×2.0) · 휴지 냉각 Δ℃ (기술)",
        start=band_label(cur),
        v1=dict(class_token=c_tok, classification=cur["reheat"].get("classification"), retighten_s=c_s,
                premise_ok=cur["heat"].get("premise_ok"), premise_label=cur["heat"].get("premise_label"),
                retighten_SKIN_k=cur["reheat"].get("SKIN_k"), retighten_AP_k=cur["reheat"].get("AP_k")),
        reproduction=dict(token=("분류 재현" if c_tok == p_tok else "분류 불일치"), cur=c_tok, prev_1004=p_tok,
                          retighten_s_cur=c_s, retighten_s_prev=p_s,
                          dt_s=(None if c_s is None or p_s is None else c_s - p_s)),
        residue=dict(cur=_residue(cur), prev_1004_desc=_residue(prev)),
        rest_cooling=dict(cur=_rest_cooling(cur), prev_1004=_rest_cooling(prev)),
        side_by_side=dict(cur=dict(start=band_label(cur), step1_s=cur["heat"].get("step1_s"), onset_1_1_s=cur["heat"].get("onset_1_1_s"),
                                   ratio_240_300=cur["heat"].get("ratio_window"), heat_end=_t(cur["heat"].get("end_thermal")),
                                   reheat_start=_t(cur["reheat"].get("start_thermal"))),
                          prev_1004=dict(start=band_label(prev), step1_s=prev["heat"].get("step1_s"), onset_1_1_s=prev["heat"].get("onset_1_1_s"),
                                         ratio_240_300=prev["heat"].get("ratio_window"), heat_end=_t(prev["heat"].get("end_thermal")),
                                         reheat_start=_t(prev["reheat"].get("start_thermal"))),
                          note="10/4 = 이 규칙을 정하기 전에 본 자료 (개발) — 기술만"),
    )


# ---------------------------------------------------------------- 합성 시험
def _bins(ratios, ref=1.0, skin=None, ap=None):
    out = []
    for i, x in enumerate(ratios):
        out.append(dict(k=i, t0=10 * i, median_ms=x * ref, ratio=x, n=100,
                        SKIN=(skin[i] if skin else 38.0), AP=(ap[i] if ap else 40.0), BAT=34.0, status=0))
    return out


def _n50(onset, step1, rel, cls="R50-fast", start=30.5):
    return dict(start_skin=start, run_id="t", conclusion="c", hypotheses={},
                start_thermal=dict(SKIN=start, AP=30.0, BAT=28.0, status=0),
                heat=dict(onset_1_1_s=onset, onset_thermal=(dict(SKIN=39.9, AP=44.1, BAT=38.0, status=0) if onset else None),
                          step1_s=150, step1_thermal=step1, premise_ok=True, premise_label="가열 충분", ratio_window=1.12,
                          start_thermal=dict(SKIN=31.0, AP=32.0, BAT=29.0, status=0), end_thermal=dict(SKIN=41.0, AP=45.0, BAT=40.0, status=1)),
                probe=dict(class_token=cls, classification=cls, release_s=(rel or {}).get("release_s"), release=rel, bins_1_5_median=1.0))


def _g50(ratios, rel_k, onset_skin=37.0, skins=None):
    rel = dict(recovered=True, k=rel_k, SKIN_k=37.4, AP_k=39.6, release_s=10 * rel_k) if rel_k is not None else dict(recovered=False)
    return dict(start_skin=30.6, ref_d50_ms=2.0, hypotheses={},
                heat=dict(onset_1_1_s=60, onset_thermal=(dict(SKIN=onset_skin, AP=43.0, BAT=33.0, status=0) if onset_skin is not None else None),
                          ratio_window=1.9, premise_ok=True, premise_label="가열 충분"),
                probe=dict(class_token=("R50-fast" if rel_k is not None else "R50-none"), classification="x",
                           release_s=(10 * rel_k if rel_k is not None else None), release=rel, bins=_bins(ratios, 2.0, skins)))


def _ni(c0, c1, cls="중간", rs=40, start=31.0):
    temps = [dict(t=t, SKIN=40.0 - t / 100.0, AP=44.0 - t / 50.0, BAT=38.0 - t / 150.0, status=0) for t in (0, 60, 120, 180, 240, 299)]
    return dict(start_skin=start, ref_d100_ms=0.75,
                heat=dict(step1_s=130, onset_1_1_s=260, ratio_window=1.11, premise_ok=True, premise_label="가열 충분",
                          end_thermal=dict(SKIN=40.2, AP=44.3, BAT=38.7, status=1)),
                rest=dict(temps=temps),
                reheat=dict(class_token=cls, classification=cls, retighten_s=rs, SKIN_k=38.1, AP_k=41.3,
                            start_thermal=dict(SKIN=36.2, AP=37.2, BAT=35.0, status=0),
                            bins=_bins([c0, c1] + [1.0, 1.0, 1.1, 1.1] + [1.1] * 12, 0.75)))


def selftest():
    res = []

    def check(name, cond, info=None):
        res.append((name, bool(cond)))
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  → {info}"))

    s1 = dict(SKIN=37.7, AP=41.7)
    rel_hot = dict(recovered=True, k=2, SKIN_k=41.4, AP_k=43.9, release_s=20)
    rel_cold = dict(recovered=True, k=2, SKIN_k=37.8, AP_k=40.9, release_s=20)
    rel_edge = dict(recovered=True, k=2, SKIN_k=37.8, AP_k=41.8, release_s=20)
    rel_mixed = dict(recovered=True, k=2, SKIN_k=38.5, AP_k=41.4, release_s=20)
    j = _n50(None, s1, rel_hot)
    check("n50p2: 1-1 진입 없음 → 시험 불가", hot_release(j)["token"] == "시험 불가" and "시험 불가" in n50p2(j, j)["verdict"])
    j = _n50(290, s1, rel_hot)
    out = n50p2(j, j)
    check("n50p2: 2계단 · 해제 41.4/43.9 vs 1계단 37.7/41.7 → 위에서 · d75", out["hot_release"]["token"] == "위에서" and "d75" in out["verdict"], out["verdict"])
    check("n50p2: 10/3 d10 해제 값 → dS +3.7 · dA +2.2", out["hot_release"]["dSKIN"] == 3.7 and out["hot_release"]["dAP"] == 2.2, out["hot_release"])
    j = _n50(290, dict(SKIN=38.2, AP=42.8), rel_cold)
    check("n50p2: 해제 37.8/40.9 vs 1계단 38.2/42.8 → 아래에서", hot_release(j)["token"] == "아래에서", hot_release(j))
    j = _n50(290, s1, rel_edge)
    check("n50p2: dS +0.1 · dA +0.1 → 경계", hot_release(j)["token"] == "경계", hot_release(j))
    j = _n50(290, s1, rel_mixed)
    check("n50p2: dS +0.8 · dA −0.3 → 아래에서 (하나라도 아래)", hot_release(j)["token"] == "아래에서", hot_release(j))
    j = _n50(290, s1, dict(recovered=True, k=2, SKIN_k=37.9, AP_k=41.9, release_s=20))
    check("n50p2: dS·dA 정확히 +0.2 → 위에서 (≥)", hot_release(j)["token"] == "위에서", hot_release(j))
    j = _n50(290, s1, dict(recovered=False), cls="R50-none")
    out = n50p2(j, j)
    check("n50p2: R50-none → 해제 없음 · H-timer 기각 · θ ≤ 0.5 유지", out["hot_release"]["token"] == "해제 없음" and "H-timer 기각" in out["verdict"]
          and out["v2_variant"] == "θ ≤ 0.5 유지", out)
    j = _n50(290, s1, dict(recovered=True, k=10, SKIN_k=39.0, AP_k=42.0, release_s=100), cls="R50-slow")
    out = n50p2(j, j)
    check("n50p2: R50-slow → 이진형 기각 대응 · 판정문에 해제 온도 비교", "이진형 기각" in out["v2_variant"] and "해제 온도 비교: 위에서" in out["verdict"], out)
    j = _n50(290, None, rel_hot)
    check("n50p2: 1계단 온도 없음 → 시험 불가", hot_release(j)["token"] == "시험 불가", hot_release(j))
    check("n50p2: 2계단 · 위에서 · R50-fast → θ > 0.5 유지 대응", n50p2(_n50(290, s1, rel_hot), j)["v2_variant"].startswith("θ_NPU > 0.5"))
    check("n50p2: 2계단 미도달 → 변형 판정 안 함", n50p2(_n50(None, s1, rel_hot), j)["v2_variant"].startswith("판정 안 함 — 2계단 미도달"))
    check("n50p2: 2계단 · 아래에서 · R50-fast → 변형 판정 안 함", n50p2(_n50(290, dict(SKIN=38.2, AP=42.8), rel_cold), j)["v2_variant"].startswith("판정 안 함 — 해제 온도"))
    check("공통: 시작 SKIN 28.4 → 밴드 밖 · 29.1 → 밴드 안", band_label(dict(start_skin=28.4))["label"].startswith("밴드 밖")
          and band_label(dict(start_skin=29.1))["label"].startswith("밴드 안"))

    base = [1.6, 1.0] + [1.02] * 15 + [1.2] * 31
    g = _g50(base, 1, onset_skin=37.3, skins=[38.0] * 48)
    rt = d50_retighten(g)
    check("g50p2: 칸 17 부터 ×1.2 → 재조임 170 s · Δ +0.7 → 높은 온도", rt["token"] == "재조임" and rt["t_s"] == 170 and rt["temp_token"] == "높은 온도", rt)
    g = _g50([1.6, 1.0] + [1.02] * 46, 1)
    check("g50p2: 끝까지 ×1.02 → 재조임 없음", d50_retighten(g)["token"] == "재조임 없음", d50_retighten(g))
    g = _g50([1.6, 1.0] + [1.02] * 15 + [1.2] * 31, 1, onset_skin=37.8, skins=[38.0] * 48)
    check("g50p2: Δ +0.2 → 같은 온도대", d50_retighten(g)["temp_token"] == "같은 온도대", d50_retighten(g))
    g = _g50([1.6, 1.0] + [1.02] * 15 + [1.2] * 31, 1, onset_skin=38.6, skins=[38.0] * 48)
    check("g50p2: Δ −0.6 → 낮은 온도", d50_retighten(g)["temp_token"] == "낮은 온도", d50_retighten(g))
    g = _g50([1.6, 1.0] + [1.02] * 43 + [1.2] * 3, 1)
    check("g50p2: 칸 45 부터 상승 (k′ ≤ 44 못 채움) → 재조임 없음", d50_retighten(g)["token"] == "재조임 없음", d50_retighten(g))
    g = _g50([1.6, 1.0] + [1.02] * 8 + [1.10] * 38, 1)
    check("g50p2: 경계 ×1.10 은 재조임 (≥) → 100 s", d50_retighten(g)["t_s"] == 100, d50_retighten(g))
    g = _g50([1.6, 1.0] + [1.2, 1.05] * 7 + [1.2] * 32, 1)
    check("g50p2: ×1.2 와 ×1.05 가 번갈다 칸 16 부터 유지 → 160 s", d50_retighten(g)["t_s"] == 160, d50_retighten(g))
    g = _g50([1.9] * 48, None)
    check("g50p2: 해제 없음 → 해제 없음", d50_retighten(g)["token"] == "해제 없음", d50_retighten(g))
    g = _g50([1.6, 1.0] + [1.02] * 15 + [1.2] * 31, 1, onset_skin=None)
    check("g50p2: d100 진입 없음 → 비교 불가", d50_retighten(g)["temp_token"] == "비교 불가", d50_retighten(g))
    out = g50p2(_g50(base, 1, onset_skin=37.3, skins=[38.0] * 48), _g50(base, 1))
    check("g50p2: R50-fast → v2 GPU gate 기각 대응", out["v2_variant"].startswith("v2 GPU gate 기각"), out["v2_variant"])

    n_cur, n_prev = _ni(2.9, 3.2), _ni(2.88, 3.23)
    out = ni300r2(n_cur, n_prev)
    check("ni300r2: 같은 분류 → 분류 재현 · 칸 0·1 ≥ ×2 → 전환 잔재 재현", out["reproduction"]["token"] == "분류 재현"
          and out["residue"]["cur"]["token"] == "전환 잔재 재현", out)
    out = ni300r2(_ni(2.9, 1.0, cls="못 늦춘다", rs=20), n_prev)
    check("ni300r2: 다른 분류 → 분류 불일치 · dt −20 · 한 칸만", out["reproduction"]["token"] == "분류 불일치"
          and out["reproduction"]["dt_s"] == -20 and out["residue"]["cur"]["token"] == "한 칸만", out)
    out = ni300r2(_ni(1.0, 1.0), n_prev)
    check("ni300r2: 칸 0·1 ×1.0 → 전환 잔재 없음", out["residue"]["cur"]["token"] == "없음", out["residue"])
    check("ni300r2: 휴지 ΔSKIN −2.99 · ΔAP −5.98", out["rest_cooling"]["cur"]["dSKIN"] == -2.99 and out["rest_cooling"]["cur"]["dAP"] == -5.98,
          out["rest_cooling"]["cur"])
    bad = _ni(2.9, 3.2)
    bad["reheat"]["bins"][3]["k"] = 7
    try:
        _residue(bad)
        ok = False
    except JudgeError:
        ok = True
    check("공통: 칸 번호 불연속 → 오류로 멈춤", ok)
    try:
        n50p2(dict(probe={}), dict())
        ok = False
    except JudgeError:
        ok = True
    check("공통: 필드 빠진 JSON → 오류로 멈춤", ok)
    a = json.dumps(n50p2(_n50(290, s1, rel_hot), _n50(None, s1, rel_cold)), ensure_ascii=False, indent=1)
    b = json.dumps(n50p2(_n50(290, s1, rel_hot), _n50(None, s1, rel_cold)), ensure_ascii=False, indent=1)
    check("공통: 같은 입력 두 번 = 같은 바이트", a == b)
    n_pass = sum(1 for _, ok in res if ok)
    print(f"selftest {n_pass}/{len(res)}")
    return 0 if n_pass == len(res) else 1


def main(argv=None):
    p = argparse.ArgumentParser(description="측정 1005 추가 판정 (사전 등록 §3~§5 새 항목)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    for name in ("n50p2", "g50p2", "ni300r2"):
        a = sub.add_parser(name)
        a.add_argument("--cur", required=True)
        a.add_argument("--prev", required=True)
        a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        cur, prev = _load(args.cur), _load(args.prev)
        fn = dict(n50p2=n50p2, g50p2=g50p2, ni300r2=ni300r2)[args.cmd]
        res = fn(cur, prev)
        res["inputs"] = dict(cur=dict(path=args.cur, sha256=_sha256(args.cur)), prev=dict(path=args.prev, sha256=_sha256(args.prev)))
        res["script"] = dict(path=os.path.abspath(__file__), sha256=_sha256(__file__))
    except JudgeError as err:
        print(f"JUDGE_ERROR: {err}", file=sys.stderr)
        return 2
    text = json.dumps(res, ensure_ascii=False, indent=1)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
