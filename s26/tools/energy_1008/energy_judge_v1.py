# -*- coding: utf-8 -*-
"""energy_judge_v1.py — 에너지 판정기 (같은 창 기기 에너지 · S26 연료게이지): 에너지 C 판정 (주) + 에너지 B · V3 기술 표.
`에너지_사전등록_v1.md` (SHA 01314501…) §2 ~ §5 · §10 + `에너지_사전등록_v2.md` (SHA 782b97a7…) §9 · §10 머리 · "바꾼 곳 3" 를 글자 그대로.
결과 보기 전 (2026-10-08 P1i 1부 — 대상 런의 전류 · 잔량계 · 전압 값 열람 0, 에너지 C 칸 0) 고정. results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트.

  py energy_judge_v1.py selftest
  py energy_judge_v1.py qc  <run_dir> --cell C --block k --session S [--out f.json]    런별 QC 만 (§2-9 제외 사유 · ① PASS/FAIL · 시계 맞춤) — E · ΔE · R 숫자 출력 없음
  py energy_judge_v1.py run <run_dir> --cell C --block k --session S --out f.json      런별 E_cc · E_int · R_run · q_J · n (파일로만 — 화면에는 QC 만)
  py energy_judge_v1.py pair --a f.json --b f.json --out f.json                       에너지 B · V3 쌍 기술 (에너지 C 칸 NAc · NBc 는 거부 — judgeC 에서만)
  py energy_judge_v1.py session --runs f… --out f.json                                 ② 세션 내부 일관성 (에너지 B · V3 — 에너지 C 칸 거부)
  py energy_judge_v1.py judgeC --runs f… --out f.json                                  에너지 C §4 판정 · ② · ②′ · v2 §9-4 적격 · §10 문장 (한 번 — --out 이 있으면 거부)

칸 (창 · 시계 = 판정기 함수 import — 등록 §2-1 · §2-2):
  N1 (MobileNet, out_1005n)  NA NB GA GB          → night1005_judge.py (ca8680c2) `_expect`
  N2 (EffNet, out_1005e)     NAe NBe GAe GBe      → night1005e_judge.py (2db1cda5) 가 더한 칸 (같은 `_expect`)
  에너지 C                   NAc NBc              → night1005e_judge_c.py (4e4dbcd3) 가 더한 칸
  V3 v1                      A_base A_ours B_base B_ours      → v3_judge.py (67ad5d42) `_expect`
  V3 v2                      A2_base A2_ours B2_base B2_ours  → v3_judge_v2.py (b4462d58) 칸 표로 같은 `_expect`
  창 = 구간 0 start_ns ~ 마지막 구간 end_ns (열 판정 창과 같음). 시계 = d1check 표본 mono_ns 를 그대로 구간 경계 (러너 mono_ns) 와 비교 —
  열 판정기가 같은 logger 의 HAL 표본에 쓰는 방식 (night1005_judge.hal_window · m1m2_judge_1002.power_series) 그대로 (변환 = 항등).
  단위 함수: s26_energy.py (ada0308f) 의 `integrate` (사다리꼴 ∫current_raw dt) 만 import — 런 전체 비 `total_ratio` 는 쓰지 않는다.

규칙 (등록 그대로):
  §2-3 표본 = 창 안 current_valid · charge_valid 둘 다 True. 시작 · 끝 = 창 안 첫 · 마지막 유효 표본.
  §2-4 E_cc = Σ_{잔량계가 준 표본 i} (cc_{i−1} − cc_i) µAh × 3.6e-3 C/µAh × V_i/1000.
  §2-5 E_int = Σ 사다리꼴 [(−I_i)·V_i + (−I_{i+1})·V_{i+1}]/2 · Δt (I = current_raw × 1e-6 A · V = voltage_mV × 1e-3).
  §2-6 R_run = Q_int / ΔQ_cc (창 안) · Q_int = −∫I dt / 3600 (µAh) · ΔQ_cc = 시작 − 끝 (µAh).
  §2-7 q = 4,275 µAh → q_J = 15.39 C × (창 안 유효 전압 중앙값 / 1000) · 쌍 q̄_J = 두 런 평균.
  §2-8 n = 창 안 구간 n 의 합 · r = n_B / n_A (V3 = n_ours / n_기준선).
  §2-9 런 제외: plugged ≠ 0 표본 · 무효 > 1 % · 표본 간격 > 10 s · 잔량계 증가 · 4,275 배수 아닌 변화 · ① FAIL · 창 마지막 60 s 명령 duty > 1 ·
       시계 맞춤 실패 (첫 가동 구간 시작 뒤 30 s 평균 방전 전류 > 시작 전 30 s 평균 × 1.3 이 아님).
  §2-10 ê_B = [E_int(B work) − P_tail × T_work] / n_work · P_tail = B 마지막 쉼 구간 마지막 min(120 s, 길이) 의 E_int 평균 전력 · ΔE_adj = ΔE + (n_B − n_A)·ê_B.
  §3 ① R_run ∈ [0.5, 2] · 방전 표본 음수. ② 세션마다 |ΣQ_int/ΣΔQ_cc − 1| ≤ 3·σ_R/√N (σ_R 모집단 sd · N < 8 이면 0.080).
     ②′ 쌍마다 d_R = R(A) − R(B): |평균 d_R| > max(0.03, 3·SE(d_R)) (SE = 표본 sd/√n) 이거나, 방향 판정인데 E_int 평균 차 부호 ≠ E_cc → "계기 불일치 — 기술만".
  §4 ΔE_p = E_cc(A) − E_cc(B) (양수 = B 적음) · 판정 쌍 = 같은 블록 NAc·NBc 중 §2-9 제외 · r ∉ [0.96, 1.04] 뺀 것 ·
     SE = max(표본 sd(ΔE_p), 0.58·q̄_J)/√n · ②′ 먼저 → 1 n < 4 "쌍 부족 — 기술만" → 2 |Δ̄| > 3·SE 이고 |Δ̄| > q̄_J → "B 낮음"/"B 높음"
     (동등 범위 여부 덧붙임) → 3 |Δ̄| + 3·SE ≤ 2·q̄_J "동등 범위 안 (±2 눈금)" → 4 "구분 안 됨".
  v2 §9-4 판정 쌍 n ≥ 4 이고 ②′ 가 "계기 불일치" 가 아니면 "적격 (등록 검사 통과 · v2 §9)" → §10 문장을 결론으로. 아니면
     "적격 미확보 — 부록 관측" (쌍 부족 / 계기 불일치) — 판정 이름 · 숫자 · 분해능 · ② · 미확보 사유.

P1i 가 정함 (결과 전 — 등록이 정하지 않은 곳, 2026-10-08 03:1x):
  a. "방전 표본 음수" (①) = 창 안 유효 표본 current_raw 중앙값 < 0 (양수 표본 수는 기술).
  b. 표본 간격 = 창 시작 → 첫 유효 표본 · 유효 표본 사이 · 마지막 유효 표본 → 창 끝 중 최대 (> 10 s 이면 제외).
  c. plugged 필드가 없는 표본은 "≠ 0" 으로 세지 않고 수만 기술. 무효 비율 분모 = 창 안 d1check 표본 전부.
  d. "창 마지막 60 s 의 명령 duty" = [창 끝 − 60 s, 창 끝] 과 겹치는 구간의 duty (하나라도 > 1 이면 제외).
  e. 시계 맞춤: "첫 가동 구간" = 세기 A/B · 에너지 C 는 구간 0, V3 는 duty ≥ 10 인 첫 구간 (등록 §2-2). 시작 전 30 s = [s − 30 s, s) ·
     뒤 30 s = [s, s + 30 s) 의 유효 표본 평균 (−I). 어느 쪽이든 표본 0 이면 실패.
  f. ê 의 "work" = duty ≥ 10 인 구간 전부 (세기 B · NBc 는 구간 0 하나, V3 ours 는 여러 개) · "tail" = 마지막 구간 (duty ≤ 1 이 아니면 ê 없음) ·
     구간 E_int = 그 구간 [start_ns, end_ns] 안 유효 표본 사다리꼴 (경계 보간 없음) · P_tail = 마지막 min(120 s, 길이) 안 유효 표본 E_int ÷ 첫 · 끝 표본 시각 차.
  g. 비교는 소수 6자리 반올림 뒤 (night1005_judge 와 같음). r 거름 경계 0.96 · 1.04 는 포함 (판정에 넣음).
  h. ②′ 는 판정 쌍 (제외 · r 거름 뒤) 으로 계산. n < 2 이면 SE(d_R) 산출 불가 → ②′ "산출 불가" (불일치 아님) → 규칙 1 로.
  i. q̄_J (판정) = 판정 쌍 q̄_J 의 평균. §10 의 Y % = 100 × |Δ̄| / 평균 E_cc(A) (판정 쌍) · "창 에너지의 약 Y %" = 100 × 2·q̄_J / 평균 E_cc(A).
     "B 높음" 문장의 "…" = "B 낮음" 문장의 같은 자리 ("S26 NPU 에서 같은 일을 d50 으로 나눠 하면, d100 으로 몰아 할 때보다" ·
     "같은 일 쌍 n개 · 잔량계 기준 · 절대 정확도 미인증"). 숫자 표기: J 정수 · % 소수 1자리 · d_R 소수 3자리.
  j. ② (에너지 C) = 세션 (런 JSON 의 session) 마다 §2-9 제외 뒤 런 전부 (r 거름 무관). 같은 블록 · 칸 런이 둘이면 오류 (무효 런은 넣지 않는다).
  k. judgeC 는 출력 파일이 이미 있으면 거부 (한 번). pair · session 은 NAc · NBc 를 거부 (에너지 C 쌍 숫자는 judgeC 에서만 — 등록 §4 중간 판정 금지).
"""
import argparse, hashlib, importlib.util, json, math, os, shutil, statistics, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
OD_SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _first_existing(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(paths[0])


def _load(name, path, prefix):
    if not _sha(path).startswith(prefix):
        raise SystemExit(f"IMPORT_ERROR: {name} SHA {_sha(path)[:8]} ≠ {prefix} ({path})")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- import (복사·수정 금지) ---------------------------------------------------------------------
_C_PATH = _first_existing(os.path.join(HERE, "night1005e_judge_c.py"), os.path.join(OD_SIM, "night1005e_judge_c.py"),
                          os.path.join(REPO, "s26", "tools", "energy_1008", "night1005e_judge_c.py"))
_V2_PATH = _first_existing(os.path.join(HERE, "v3_judge_v2.py"), os.path.join(OD_SIM, "v3_judge_v2.py"),
                           os.path.join(REPO, "s26", "tools", "v3_1006", "v3_judge_v2.py"))
_EN_PATH = _first_existing(os.path.join(REPO, "s26", "tools", "s26_energy.py"))
IMPORTS = {"night1005e_judge_c": (_C_PATH, "4e4dbcd3"), "v3_judge_v2": (_V2_PATH, "b4462d58"), "s26_energy": (_EN_PATH, "ada0308f")}
JC = _load("night1005e_judge_c", _C_PATH, "4e4dbcd3")      # → night1005e_judge (2db1cda5) → night1005_judge (ca8680c2) → m1m2 · night1003
V2 = _load("v3_judge_v2", _V2_PATH, "b4462d58")             # → v3_judge (67ad5d42) → (자기 사본) night1005e_judge
EN = _load("s26_energy", _EN_PATH, "ada0308f")
E, N5 = JC.E, JC.N5
V = V2.V
J = N5.J
JudgeError, load_run, segments_of, dumps = N5.JudgeError, N5.load_run, N5.segments_of, N5.dumps

# --- 상수 (등록) -----------------------------------------------------------------------------------
Q_UAH = 4275                     # §2-7 한 눈금
C_PER_UAH = 3.6e-3               # §2-4
Q_C = Q_UAH * C_PER_UAH          # 15.39 C
R_UNIT = (0.5, 2.0)              # ① §3
INVALID_MAX = 0.01               # §2-9
GAP_MAX_S = 10.0                 # §2-9
TAIL_S = 60                      # §2-9
CLOCK_S = 30                     # §2-2
CLOCK_X = 1.3                    # §2-2
SIGMA_R_FALLBACK = 0.080         # ② N < 8 (§10.2)
N_SIGMA_MIN = 8
DR_MIN = 0.03                    # ②′
R_FILTER = (0.96, 1.04)          # §4
SE_FLOOR = 0.58                  # §4 (× q̄_J)
N_MIN = 4                        # §4 규칙 1 · v2 §9-4
EQ_TICKS = 2                     # §4 규칙 3 (±2 눈금)
P_TAIL_S = 120                   # §2-10
ACTIVE_MIN_DUTY = 10
EPS = 1e-9

N1_CELLS = ("NA", "NB", "GA", "GB")
N2_CELLS = ("NAe", "NBe", "GAe", "GBe")
C_CELLS = ("NAc", "NBc")
V3V1_CELLS = ("A_base", "A_ours", "B_base", "B_ours")
V3V2_CELLS = ("A2_base", "A2_ours", "B2_base", "B2_ours")
ALL_CELLS = N1_CELLS + N2_CELLS + C_CELLS + V3V1_CELLS + V3V2_CELLS

L4 = dict(low="B 낮음", high="B 높음", eq="동등 범위 안 (±2 눈금)", nd="구분 안 됨", few="쌍 부족 — 기술만", inst="계기 불일치 — 기술만")
ELIG_OK = "적격 (등록 검사 통과 · v2 §9)"
ELIG_FEW = "적격 미확보 — 부록 관측 (쌍 부족)"
ELIG_INST = "적격 미확보 — 부록 관측 (계기 불일치)"
ALWAYS = "연료게이지 잔량계 기준 · 절대 정확도 미인증"
V2_ATTACH = "같은 폰 · 같은 블록 같은 일 쌍 · 연료게이지 잔량계 기준 · 절대 정확도 미인증"
V2_LIMIT = ("남는 한계 (v2 §9-4): ②′ 는 팔 사이 치우침 차가 max(0.03, 3·SE) 아래면 거르지 못한다 — 0.03 은 창 에너지 (~2,000 J [E v1 §1-4]) 의 ~3 % ≈ 60 J ≈ 한 눈금이다. "
            "v1 §7-1 (잔량계가 SOC 추정에서 나온 값일 가능성) 은 미확인 그대로다.")


def import_check():
    out = {k: dict(path=p, sha256=_sha(p), expected_prefix=pre, ok=_sha(p).startswith(pre)) for k, (p, pre) in IMPORTS.items()}
    out["night1005e_judge"] = dict(path=JC._N5E_PATH, sha256=_sha(JC._N5E_PATH), expected_prefix=JC.N5E_PREFIX, ok=_sha(JC._N5E_PATH).startswith(JC.N5E_PREFIX))
    out["v3_judge"] = dict(path=V2._V3_PATH, sha256=_sha(V2._V3_PATH), expected_prefix=V2.V3_PREFIX, ok=_sha(V2._V3_PATH).startswith(V2.V3_PREFIX))
    out.update(N5.import_check())
    return out


def _r6(x):
    return None if x is None else round(float(x), 6)


def _load_json(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


# ============================================================ 창 (판정기 함수)
def cell_info(cell):
    if cell in N1_CELLS + N2_CELLS + C_CELLS:
        c = N5.CELLS[cell]
        fam = "N1" if cell in N1_CELLS else ("N2" if cell in N2_CELLS else "C")
        return dict(family=fam, side=c["side"], resource=c["resource"], chain=c["chain"])
    if cell in V3V1_CELLS:
        c = V.CELLS[cell]
        return dict(family="V3v1", side="A" if c["role"] == "base" else "B", resource="NPU", chain=c["chain"], cond=c["cond"], role=c["role"])
    if cell in V3V2_CELLS:
        c = V2.CELLS_V2[cell]
        return dict(family="V3v2", side="A" if c["role"] == "base" else "B", resource="NPU", chain=c["chain"], cond=c["cond"], role=c["role"])
    raise JudgeError(f"칸 {cell} ∉ {list(ALL_CELLS)}")


def window_segments(run, cell):
    """판정기의 칸 표 검사 (`_expect`) 를 통과한 구간 목록 · 창 · 첫 가동 구간."""
    info = cell_info(cell)
    if info["family"] in ("N1", "N2", "C"):
        S = segments_of(run)
        segs = N5._expect(S, cell)
        first_active = segs[0]
    else:
        S = segments_of(run)
        try:                                    # v3_judge 는 자기 사본의 m1m2 를 import 한다 → 그 JudgeError 를 이쪽 JudgeError 로
            if info["family"] == "V3v1":
                segs = V._expect(S, cell)
            else:
                with V2._cells(V2.CELLS_V2):
                    segs = V._expect(S, cell)
        except V.JudgeError as err:
            raise JudgeError(str(err))
        first_active = next(s for s in segs if s["duty"] is not None and s["duty"] >= ACTIVE_MIN_DUTY)
    msc = None
    if info["family"] == "C":
        msc = E.model_sha_check(E._segments_with_end_sha(run), "NPU")
    return S, segs, first_active, msc


# ============================================================ 계산 (표본)
def _valid(s):
    return s.get("current_valid") is True and s.get("charge_valid") is True


def _plug_nonzero(s):
    p = s.get("plugged")
    if p is None:
        return False
    try:
        return int(p) != 0
    except (TypeError, ValueError):
        return str(p).strip().lower() not in ("false", "0", "")


def _trap_energy(vs):
    """§2-5 사다리꼴 E_int (J)."""
    e = 0.0
    for a, b in zip(vs, vs[1:]):
        dt = (int(b["mono_ns"]) - int(a["mono_ns"])) / 1e9
        pa = -float(a["current_raw"]) * 1e-6 * float(a["voltage_mV"]) * 1e-3
        pb = -float(b["current_raw"]) * 1e-6 * float(b["voltage_mV"]) * 1e-3
        e += (pa + pb) / 2.0 * dt
    return e


def _sub(vs, a_ns, b_ns, right_open=False):
    if right_open:
        return [s for s in vs if a_ns <= int(s["mono_ns"]) < b_ns]
    return [s for s in vs if a_ns <= int(s["mono_ns"]) <= b_ns]


def _mean_discharge(vs):
    return None if not vs else statistics.fmean(-float(s["current_raw"]) for s in vs)


def tail_duty_check(segs, b_ns):
    t0 = b_ns - TAIL_S * 1_000_000_000
    over = [dict(index=s["index"], duty=s["duty"]) for s in segs if s["end_ns"] > t0 and s["start_ns"] < b_ns]
    bad = [o for o in over if o["duty"] is None or o["duty"] > 1]
    return dict(segments_in_last_60s=over, ok=not bad)


def clock_check(vs, s_ns):
    pre = _sub(vs, s_ns - CLOCK_S * 1_000_000_000, s_ns, right_open=True)
    post = _sub(vs, s_ns, s_ns + CLOCK_S * 1_000_000_000, right_open=True)
    mp, mq = _mean_discharge(pre), _mean_discharge(post)
    ok = mp is not None and mq is not None and _r6(mq) > _r6(CLOCK_X * mp)
    return dict(n_pre=len(pre), n_post=len(post), mean_pre_uA=mp, mean_post_uA=mq, ok=bool(ok))


def e_hat(vs, segs):
    """§2-10 ê (B · ours 쪽에서만 쓴다)."""
    work = [s for s in segs if s["duty"] is not None and s["duty"] >= ACTIVE_MIN_DUTY]
    tail = segs[-1]
    if not work or tail["duty"] is None or tail["duty"] > 1:
        return dict(e_hat_J=None, note="work 또는 끝 쉼 구간 없음")
    e_work = sum(_trap_energy(_sub(vs, s["start_ns"], s["end_ns"])) for s in work)
    t_work = sum(s["length_s"] for s in work)
    n_work = sum(s["n"] for s in work)
    span = min(P_TAIL_S, tail["length_s"])
    tv = _sub(vs, tail["end_ns"] - int(span * 1e9), tail["end_ns"])
    if len(tv) < 2 or n_work == 0:
        return dict(e_hat_J=None, note="끝 쉼 표본 부족 또는 work 추론 0")
    p_tail = _trap_energy(tv) / ((int(tv[-1]["mono_ns"]) - int(tv[0]["mono_ns"])) / 1e9)
    return dict(e_hat_J=(e_work - p_tail * t_work) / n_work, e_int_work_J=e_work, t_work_s=t_work, n_work=n_work, p_tail_W=p_tail, tail_span_s=span,
                work_indices=[s["index"] for s in work])


def energy_run(run, cell, block, session):
    """런 하나 — QC (§2-9 · ①) + 에너지 (§2-4 ~ §2-8 · §2-10). 반환 dict 의 'qc' 는 숫자 없는 판정만."""
    info = cell_info(cell)
    S, segs, fa, msc = window_segments(run, cell)
    a_ns, b_ns = segs[0]["start_ns"], segs[-1]["end_ns"]
    allw = [s for s in run["d1"] if a_ns <= int(s["mono_ns"]) <= b_ns]
    vs = [s for s in allw if _valid(s)]
    n_all = len(allw)
    n_inv = n_all - len(vs)
    n_plug = sum(1 for s in allw if _plug_nonzero(s))
    n_plug_missing = sum(1 for s in allw if s.get("plugged") is None)
    pts = [a_ns] + [int(s["mono_ns"]) for s in vs] + [b_ns]
    max_gap = max((pts[i] - pts[i - 1]) / 1e9 for i in range(1, len(pts)))
    n_up = n_nonmult = n_drop_events = 0
    ticks_hist = {}
    e_cc = 0.0
    for p, c in zip(vs, vs[1:]):
        d = int(p["charge_counter_raw"]) - int(c["charge_counter_raw"])
        if d < 0:
            n_up += 1
        if d != 0 and d % Q_UAH != 0:
            n_nonmult += 1
        if d > 0:
            n_drop_events += 1
            if d % Q_UAH == 0:
                ticks_hist[str(d // Q_UAH)] = ticks_hist.get(str(d // Q_UAH), 0) + 1
            e_cc += d * C_PER_UAH * float(c["voltage_mV"]) / 1000.0
    e_int = _trap_energy(vs)
    q_int = None if len(vs) < 2 else -EN.integrate(vs) / 3600.0
    dq_cc = None if len(vs) < 2 else int(vs[0]["charge_counter_raw"]) - int(vs[-1]["charge_counter_raw"])
    R = (q_int / dq_cc) if (q_int is not None and dq_cc and dq_cc > 0) else None
    med_I = statistics.median(float(s["current_raw"]) for s in vs) if vs else None
    n_pos = sum(1 for s in vs if float(s["current_raw"]) > 0)
    v_med = statistics.median(float(s["voltage_mV"]) for s in vs) if vs else None
    q_J = None if v_med is None else Q_C * v_med / 1000.0
    unit_ok = R is not None and R_UNIT[0] - EPS <= _r6(R) <= R_UNIT[1] + EPS and med_I is not None and med_I < 0
    tchk = tail_duty_check(segs, b_ns)
    cchk = clock_check([s for s in run["d1"] if _valid(s)], fa["start_ns"])     # 시작 전 30 s 는 창 밖이다 → 런 전체 유효 표본에서
    inv_frac = (n_inv / n_all) if n_all else 1.0
    reasons = []
    if n_plug:
        reasons.append(f"plugged ≠ 0 표본 {n_plug}")
    if n_all == 0 or _r6(inv_frac) > INVALID_MAX:
        reasons.append(f"무효 표본 > 1 % ({n_inv}/{n_all})")
    if _r6(max_gap) > GAP_MAX_S:
        reasons.append(f"표본 간격 > 10 s (최대 {max_gap:.1f} s)")
    if n_up:
        reasons.append(f"잔량계 증가 {n_up}회")
    if n_nonmult:
        reasons.append(f"4,275 µAh 배수 아닌 잔량계 변화 {n_nonmult}회")
    if not unit_ok:
        reasons.append("① 단위 FAIL")
    if not tchk["ok"]:
        reasons.append("창 마지막 60 s 명령 duty > 1 (끝이 쉼이 아님)")
    if not cchk["ok"]:
        reasons.append("시계 맞춤 실패")
    m = S["meta"]
    qc = dict(run_id=m.get("run_id"), cell=cell, block=block, session=session, family=info["family"], side=info["side"],
              chain_id=(m.get("chain_spec") or {}).get("chain_id"), window_s=(b_ns - a_ns) / 1e9,
              n_samples=n_all, n_invalid=n_inv, invalid_pct=round(100.0 * inv_frac, 3), max_gap_s=round(max_gap, 3),
              n_plugged_nonzero=n_plug, n_plugged_missing=n_plug_missing, n_cc_increase=n_up, n_cc_nonmultiple=n_nonmult,
              unit_1=("PASS" if unit_ok else "FAIL"), clock_check=("PASS" if cchk["ok"] else "FAIL"), tail_ok=tchk["ok"],
              model_sha_label=None if msc is None else msc["label"],
              excluded=bool(reasons), exclusion_reasons=reasons)
    energy = dict(E_cc_J=e_cc, E_int_J=e_int, Q_int_uAh=q_int, dQ_cc_uAh=dq_cc, R_run=R, q_J=q_J, V_median_mV=v_med,
                  n=sum(s["n"] for s in segs), n_drop_events=n_drop_events, drop_ticks_hist=ticks_hist,
                  median_current_raw=med_I, n_positive_current=n_pos,
                  e_window_mJ_per_inference=None if not sum(s["n"] for s in segs) else 1000.0 * e_cc / sum(s["n"] for s in segs),
                  e_hat=e_hat(vs, segs) if info["side"] == "B" else None,
                  clock=cchk, tail=tchk)
    return dict(kind="energy_run_v1", qc=qc, energy=energy,
                segments=[dict(index=s["index"], label=s["label"], duty=s["duty"], length_s=s["length_s"], n=s["n"]) for s in segs],
                model_sha_check=msc, imports=import_check())


# ============================================================ 쌍 · 세션 · 판정
def pair_energy(a, b, allow_c=False):
    if a.get("kind") != "energy_run_v1" or b.get("kind") != "energy_run_v1":
        raise JudgeError("런 에너지 JSON 이 아님")
    qa, qb = a["qc"], b["qc"]
    if not allow_c and (qa["cell"] in C_CELLS or qb["cell"] in C_CELLS):
        raise JudgeError("에너지 C 칸 (NAc · NBc) 쌍은 judgeC 에서만 (등록 §4 — 중간 판정 금지)")
    if qa["side"] != "A" or qb["side"] != "B":
        raise JudgeError(f"A 자리 {qa['cell']} ({qa['side']}) · B 자리 {qb['cell']} ({qb['side']})")
    if qa["family"] != qb["family"]:
        raise JudgeError(f"칸 묶음 다름: {qa['family']} vs {qb['family']}")
    ea, eb = a["energy"], b["energy"]
    r = eb["n"] / ea["n"]
    excl = qa["excluded"] or qb["excluded"]
    dE = ea["E_cc_J"] - eb["E_cc_J"]
    dE_int = ea["E_int_J"] - eb["E_int_J"]
    eh = (eb.get("e_hat") or {}).get("e_hat_J")
    dE_adj = None if eh is None else dE + (eb["n"] - ea["n"]) * eh
    qbar = None if (ea["q_J"] is None or eb["q_J"] is None) else (ea["q_J"] + eb["q_J"]) / 2.0
    dR = None if (ea["R_run"] is None or eb["R_run"] is None) else ea["R_run"] - eb["R_run"]
    in_r = R_FILTER[0] - EPS <= _r6(r) <= R_FILTER[1] + EPS
    return dict(kind="energy_pair_v1", family=qa["family"], block=qa["block"], session_a=qa["session"], session_b=qb["session"],
                a=dict(cell=qa["cell"], run_id=qa["run_id"]), b=dict(cell=qb["cell"], run_id=qb["run_id"]),
                excluded=excl, exclusion=(["A: " + x for x in qa["exclusion_reasons"]] + ["B: " + x for x in qb["exclusion_reasons"]]),
                n_a=ea["n"], n_b=eb["n"], r=r, r_in_filter=in_r,
                E_cc_a=ea["E_cc_J"], E_cc_b=eb["E_cc_J"], dE_p=dE, dE_pct_of_a=100.0 * dE / ea["E_cc_J"] if ea["E_cc_J"] else None,
                E_int_a=ea["E_int_J"], E_int_b=eb["E_int_J"], dE_int=dE_int,
                e_hat_b_J=eh, dE_adj=dE_adj, q_bar_J=qbar, dE_in_ticks=None if not qbar else dE / qbar,
                R_a=ea["R_run"], R_b=eb["R_run"], d_R=dR,
                mJ_per_inf_a=ea["e_window_mJ_per_inference"], mJ_per_inf_b=eb["e_window_mJ_per_inference"],
                sign="+" if _r6(dE) > 0 else ("-" if _r6(dE) < 0 else "0"))


def session_check(runs):
    """② 세션 내부 일관성 — runs = 런 에너지 JSON (§2-9 제외 뒤만 넣는다)."""
    use = [j for j in runs if not j["qc"]["excluded"] and j["energy"]["R_run"] is not None]
    N = len(use)
    if N == 0:
        return dict(N=0, verdict="런 없음", line="② 런 없음")
    sq = sum(j["energy"]["Q_int_uAh"] for j in use)
    sc = sum(j["energy"]["dQ_cc_uAh"] for j in use)
    Rs = [j["energy"]["R_run"] for j in use]
    sd = statistics.pstdev(Rs) if N > 1 else 0.0
    sig = SIGMA_R_FALLBACK if N < N_SIGMA_MIN else sd
    R_sum = sq / sc
    tol = 3.0 * sig / math.sqrt(N)
    ok = _r6(abs(R_sum - 1.0)) <= _r6(tol)
    src = f"σ_R {SIGMA_R_FALLBACK:.3f} 대체 (N < 8)" if N < N_SIGMA_MIN else f"σ_R {sd:.3f}"
    return dict(N=N, R_sum=R_sum, sigma_R_pop=sd, sigma_used=sig, sigma_source=src, tolerance=tol, dev=R_sum - 1.0,
                verdict="PASS" if ok else "FAIL",
                line=f"② 내부 일관성: R_sum {R_sum:.3f} (편차 {R_sum - 1:+.3f}) · 허용 ±{tol:.3f} ({src} · N {N}) → {'PASS' if ok else 'FAIL'}")


def _mean(x):
    return statistics.fmean(x)


def _sd(x):
    return statistics.stdev(x) if len(x) > 1 else 0.0


def verdict_C(judged):
    """§4 + ②′ — judged = 판정 쌍 (제외 · r 거름 뒤). 반환: verdict · 숫자."""
    n = len(judged)
    out = dict(n=n)
    if n:
        dEs = [p["dE_p"] for p in judged]
        qbar = _mean([p["q_bar_J"] for p in judged])
        dbar = _mean(dEs)
        se = max(_sd(dEs), SE_FLOOR * qbar) / math.sqrt(n)
        dint = _mean([p["dE_int"] for p in judged])
        out.update(d_bar_J=dbar, sd_dE=_sd(dEs), q_bar_J=qbar, SE_J=se, three_SE_J=3 * se, d_bar_int_J=dint,
                   mean_E_cc_a=_mean([p["E_cc_a"] for p in judged]), se_floor_used=_sd(dEs) < SE_FLOOR * qbar)
    # ②′ (먼저)
    if n >= 2:
        dRs = [p["d_R"] for p in judged]
        mdr = _mean(dRs)
        se_dr = _sd(dRs) / math.sqrt(n)
        lim = max(DR_MIN, 3 * se_dr)
        bad1 = _r6(abs(mdr)) > _r6(lim)
        out["inst"] = dict(mean_d_R=mdr, SE_d_R=se_dr, limit=lim, fail_bias=bad1)
    else:
        out["inst"] = dict(mean_d_R=None, SE_d_R=None, limit=None, fail_bias=False, note="n < 2 — ②′ 산출 불가")
    # §4 규칙 (방향 판정 여부는 ②′ 둘째 조건에도 쓴다)
    if n < N_MIN:
        base = L4["few"]
    else:
        dbar, se, qbar = out["d_bar_J"], out["SE_J"], out["q_bar_J"]
        if _r6(abs(dbar)) > _r6(3 * se) and _r6(abs(dbar)) > _r6(qbar):
            base = L4["low"] if dbar > 0 else L4["high"]
        elif _r6(abs(dbar) + 3 * se) <= _r6(EQ_TICKS * qbar):
            base = L4["eq"]
        else:
            base = L4["nd"]
    sign_mismatch = False
    if base in (L4["low"], L4["high"]):
        s_cc = 1 if out["d_bar_J"] > 0 else -1
        s_int = 1 if _r6(out["d_bar_int_J"]) > 0 else (-1 if _r6(out["d_bar_int_J"]) < 0 else 0)
        sign_mismatch = s_int != s_cc
    out["inst"]["fail_sign"] = sign_mismatch
    inst_fail = out["inst"]["fail_bias"] or sign_mismatch
    out["inst"]["verdict"] = "계기 불일치" if inst_fail else ("통과" if n >= 2 else "산출 불가")
    if inst_fail:
        out["verdict"] = L4["inst"]
        out["rule_verdict_without_inst"] = base
    else:
        out["verdict"] = base
    if out["verdict"] in (L4["low"], L4["high"]):
        eq_in = _r6(abs(out["d_bar_J"]) + 3 * out["SE_J"]) <= _r6(EQ_TICKS * out["q_bar_J"])
        out["equivalence_note"] = "동등 범위 안 (±2 눈금)" if eq_in else "동등 범위 밖"
    return out


def eligibility_v2(vc):
    if vc["verdict"] == L4["inst"]:
        return ELIG_INST
    if vc["n"] < N_MIN:
        return ELIG_FEW
    return ELIG_OK


def sentence_C(vc, two_lines):
    """§10 (v1) 문장 — 숫자만 채운다. 쌍 부족은 문장 없음."""
    v, n = vc["verdict"], vc["n"]
    if v == L4["few"]:
        return None
    if v == L4["inst"]:
        return f"「전류 적분과 잔량계가 A · B 에서 다르게 치우쳐 (평균 d_R = {vc['inst']['mean_d_R']:+.3f}) 에너지 차이를 판별하지 않았다.」"
    X = abs(vc["d_bar_J"])
    Y = 100.0 * X / vc["mean_E_cc_a"]
    q, Z = vc["q_bar_J"], 3 * vc["SE_J"]
    lead = "S26 NPU 에서 같은 일을 d50 으로 나눠 하면, d100 으로 몰아 할 때보다"
    tail = f"같은 일 쌍 {n}개 · 잔량계 기준 · 절대 정확도 미인증"
    if v == L4["low"]:
        s = f"「{lead} 같은 900 s 창의 기기 에너지가 평균 {X:.0f} J ({Y:.1f} %) 적었다 ({tail}).」"
    elif v == L4["high"]:
        s = f"「{lead} 같은 900 s 창의 기기 에너지가 평균 {X:.0f} J ({Y:.1f} %) 더 들었다 ({tail}) — 이 조건에서 열 부담과 에너지는 맞바뀐다.」"
    elif v == L4["eq"]:
        s = (f"「같은 일을 d50 으로 나눠 해도 같은 900 s 창의 기기 에너지 차이는 등록한 동등 범위 ±2 눈금 (≈ ±{2 * q:.0f} J, 창 에너지의 약 "
             f"{100.0 * 2 * q / vc['mean_E_cc_a']:.1f} %) 안이었다 (같은 일 쌍 {n}개 · 잔량계 기준).」")
    else:
        s = f"「같은 900 s 창의 기기 에너지 차이는 평균 {vc['d_bar_J']:+.0f} J 로, 방향도 동등 범위도 판별하지 못했다 (한 눈금 ≈ {q:.0f} J · 3SE = {Z:.0f} J · 쌍 {n}개).」"
    return s


def judge_C(runs):
    for j in runs:
        if j.get("kind") != "energy_run_v1":
            raise JudgeError("런 에너지 JSON 이 아님")
        if j["qc"]["cell"] not in C_CELLS:
            raise JudgeError(f"judgeC 는 에너지 C 칸만: {j['qc']['cell']}")
    by = {}
    for j in runs:
        key = (j["qc"]["block"], j["qc"]["cell"])
        if key in by:
            raise JudgeError(f"블록 {key[0]} 칸 {key[1]} 런이 둘 — 무효 런은 넣지 않는다")
        by[key] = j
    blocks = sorted({k[0] for k in by})
    pairs, unpaired = [], []
    for k in blocks:
        a, b = by.get((k, "NAc")), by.get((k, "NBc"))
        if a is None or b is None:
            unpaired.append(dict(block=k, have=[c for c in C_CELLS if (k, c) in by]))
            continue
        pairs.append(pair_energy(a, b, allow_c=True))
    judged = [p for p in pairs if not p["excluded"] and p["r_in_filter"]]
    vc = verdict_C(judged)
    elig = eligibility_v2(vc)
    sessions = sorted({j["qc"]["session"] for j in runs})
    two = {s: session_check([j for j in runs if j["qc"]["session"] == s]) for s in sessions}
    two_lines = " · ".join(f"[{s}] {two[s]['line']}" for s in sessions)
    sent = sentence_C(vc, two_lines)
    inst_line = None
    if vc["inst"]["mean_d_R"] is not None:
        inst_line = (f"②′ 팔 사이 일관성: 평균 d_R {vc['inst']['mean_d_R']:+.3f} · 한계 max(0.03, 3·SE) = {vc['inst']['limit']:.3f}"
                     f"{' · E_int 부호 불일치' if vc['inst']['fail_sign'] else ''} → {vc['inst']['verdict']}")
    if elig == ELIG_OK:
        head = "결론 (" + ELIG_OK + ")"
        concl = sent
        attach = f"({V2_ATTACH} · {two_lines} · {inst_line} 통과 (팔 사이 치우침 차 ≤ max(0.03, 3·SE)))"
    else:
        head = "부록 관측 (" + elig + ")"
        concl = None
        attach = f"({ALWAYS} · {two_lines}" + (f" · {inst_line}" if inst_line else "") + ")"
    return dict(kind="energy_judgeC_v1", head=head, eligibility_v2=elig, verdict=vc["verdict"], n_judged=vc["n"],
                registered_sentence=sent, conclusion_sentence=concl, attach=attach, limit_note=V2_LIMIT if elig == ELIG_OK else None,
                always=ALWAYS, numbers=vc, session_2=two, inst_line=inst_line,
                pairs=pairs, judged_blocks=[p["block"] for p in judged],
                not_judged=[dict(block=p["block"], why=("제외 (" + " · ".join(p["exclusion"]) + ")") if p["excluded"] else f"작업량 차 — 기술만 (r {p['r']:.4f})")
                            for p in pairs if p not in judged],
                unpaired=unpaired, imports=import_check())


# ============================================================ selftest (합성 — 결과 보기 전 양방향)
def _write_d1(rd, rows):
    os.makedirs(os.path.join(rd, "merged"), exist_ok=True)
    with open(os.path.join(rd, "merged", "events.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(dict(dict(source="d1check", event="sample"), **r), separators=(",", ":")) + "\n")


def _synth_power(rd, power_fn, v_fn=lambda t: 4000.0, cc0=3_000_000, cc_period_s=30.7, mutate=None, step_s=1.0, extra_ticks=None):
    """t = 구간 0 시작 기준 초. 참 전하를 누적하고 잔량계는 cc_period_s 격자에서만 4,275 배수로 갱신."""
    run = load_run(rd)
    S = segments_of(run)
    s0 = S["segments"][0]["start_ns"]
    a = S["load_start_ns"] - 60_000_000_000
    b = S["load_end_ns"] + 5_000_000_000
    rows, q = [], 0.0
    cc = cc0
    m = a
    next_upd = a
    while m <= b:
        t = (m - s0) / 1e9
        w = float(power_fn(t))
        v = float(v_fn(t))
        i_ua = -w / (v / 1000.0) * 1e6
        q += (-i_ua) * step_s / 3600.0
        if m >= next_upd:
            ticks = int(q // Q_UAH)
            cc = cc0 - ticks * Q_UAH
            next_upd = m + int(cc_period_s * 1e9)
        r = dict(mono_ns=int(m), current_raw=int(round(i_ua)), current_valid=True, charge_counter_raw=int(cc), charge_valid=True,
                 voltage_mV=int(round(v)), plugged=0)
        if mutate:
            r = mutate(t, r)
        rows.append(r)
        m += int(step_s * 1e9)
    _write_d1(rd, rows)
    return rd


def _mk(tmp, tag, cell, power_fn, rate=20.0, **kw):
    rd = N5._mk_run(tmp, tag, cell, lambda t: 0.9, lambda t: 29.5, rate=rate)
    return _synth_power(rd, power_fn, **kw)


def _pw_A(t):
    return 0.67 if (t < 0 or t >= 300) else 5.2


def _pw_B(L=620):
    def f(t):
        if t < 0 or t >= L:
            return 0.67
        return 5.2 if (t % 10.0) < 5.0 else 0.67
    return f


def _fake_pair(block, dE, q=63.0, r=1.0, dR=0.0, dEint=None, excl=False, EA=2000.0, sess="C1"):
    return dict(kind="energy_pair_v1", family="C", block=block, session_a=sess, session_b=sess, a=dict(cell="NAc"), b=dict(cell="NBc"),
                excluded=excl, exclusion=["A: x"] if excl else [], n_a=10000, n_b=int(10000 * r), r=r,
                r_in_filter=R_FILTER[0] - EPS <= _r6(r) <= R_FILTER[1] + EPS,
                E_cc_a=EA, E_cc_b=EA - dE, dE_p=dE, dE_int=dE if dEint is None else dEint, q_bar_J=q, d_R=dR, sign="+")


def _fake_run(cell, block, session, R=1.0, q_int=100000.0, excl=False):
    return dict(kind="energy_run_v1", qc=dict(cell=cell, block=block, session=session, family="C", side="A" if cell == "NAc" else "B",
                                              run_id=f"f{cell}{block}", excluded=excl, exclusion_reasons=["x"] if excl else []),
                energy=dict(E_cc_J=2000.0, E_int_J=2000.0, Q_int_uAh=q_int, dQ_cc_uAh=q_int / R, R_run=R, q_J=63.0, n=10000,
                            e_hat=None, e_window_mJ_per_inference=200.0))


def selftest():
    res = []

    def check(name, cond, got):
        res.append((name, bool(cond), got))

    def raises(name, fn):
        try:
            fn()
            check(name, False, "통과했다")
        except JudgeError as err:
            check(name, True, str(err)[:120])
    check("⓪ import SHA 접두 (래퍼 c 4e4dbcd3 · v3_judge_v2 b4462d58 · s26_energy ada0308f · night1005e 2db1cda5 · v3_judge 67ad5d42 · night1005 ca8680c2 …)",
          all(v["ok"] for v in import_check().values()), {k: v["sha256"][:8] for k, v in import_check().items()})
    tmp = tempfile.mkdtemp(prefix="energy_judge_selftest_")
    try:
        # ① 정상 런 · 갱신 몰림 (30.7 s 격자 · 1~4 눈금씩) · E_cc ≈ E_int · R ≈ 1
        rdA = _mk(tmp, "okA", "NAc", _pw_A)
        jA = energy_run(load_run(rdA), "NAc", 1, "C1")
        e = jA["energy"]
        exp_int = 5.2 * 300 + 0.67 * 600
        check("① 정상 NAc: 제외 없음 · ① PASS · 시계 PASS · E_int ≈ 5.2×300 + 0.67×600 (±1 s 경계)", not jA["qc"]["excluded"] and jA["qc"]["unit_1"] == "PASS"
              and jA["qc"]["clock_check"] == "PASS" and abs(e["E_int_J"] - exp_int) < 6.0, (round(e["E_int_J"], 1), exp_int, jA["qc"]["exclusion_reasons"]))
        check("① 갱신 몰림 (1~4 눈금 한 번에) 도 배수면 제외 아님 · 눈금 분포에 2 이상 있음 · E_cc 와 E_int 차 ≤ 2 눈금",
              any(int(k) >= 2 for k in e["drop_ticks_hist"]) and abs(e["E_cc_J"] - e["E_int_J"]) <= 2 * e["q_J"] + 1e-9,
              (e["drop_ticks_hist"], round(e["E_cc_J"], 1), round(e["E_int_J"], 1)))
        check("① R_run ≈ 1 (±2 눈금 / ΔQ) · q_J = 15.39 × 4.0 = 61.56", abs(e["R_run"] - 1.0) < 2 * Q_UAH / e["dQ_cc_uAh"] + 1e-9 and abs(e["q_J"] - 61.56) < 1e-9,
              (round(e["R_run"], 4), e["q_J"]))
        # E_cc 정의 직접: 2 눈금 한 번 · 전압 3,900 → 2 × 15.39 × 3.9
        e_one = 0.0
        vs = [dict(mono_ns=0, current_raw=-1000000, voltage_mV=4000, charge_counter_raw=100000),
              dict(mono_ns=10**9, current_raw=-1000000, voltage_mV=3900, charge_counter_raw=100000 - 2 * Q_UAH)]
        for p, c in zip(vs, vs[1:]):
            d = p["charge_counter_raw"] - c["charge_counter_raw"]
            e_one += d * C_PER_UAH * c["voltage_mV"] / 1000.0
        check("① E_cc 정의: 2 눈금 · 그 표본 전압 3.9 V → 2 × 15.39 × 3.9 = 120.042 J", abs(e_one - 120.042) < 1e-9, e_one)
        check("① E_int 정의: 1 A · 4.0/3.9 V · 1 s 사다리꼴 = 3.95 J", abs(_trap_energy(vs) - 3.95) < 1e-9, _trap_energy(vs))
        # ② 제외 사유 하나씩
        def mut_plug(t, r):
            if 400 <= t < 401:
                r["plugged"] = 1
            return r
        j = energy_run(load_run(_mk(tmp, "plug", "NAc", _pw_A, mutate=mut_plug)), "NAc", 1, "C1")
        check("② plugged ≠ 0 표본 1개 → 제외", j["qc"]["excluded"] and any("plugged" in x for x in j["qc"]["exclusion_reasons"]), j["qc"]["exclusion_reasons"])

        def mut_inv(k):
            def f(t, r):
                if 0 <= t < k:
                    r["current_valid"] = False
                return r
            return f
        j = energy_run(load_run(_mk(tmp, "inv10", "NAc", _pw_A, mutate=mut_inv(10))), "NAc", 1, "C1")
        check("② 무효 10/901 (> 1 %) → 제외", j["qc"]["excluded"] and any("무효" in x for x in j["qc"]["exclusion_reasons"]), (j["qc"]["invalid_pct"], j["qc"]["exclusion_reasons"]))
        j = energy_run(load_run(_mk(tmp, "inv9", "NAc", _pw_A, mutate=mut_inv(9))), "NAc", 1, "C1")
        check("② 무효 9/901 (≤ 1 %) → 무효 사유 없음", not any("무효" in x for x in j["qc"]["exclusion_reasons"]), (j["qc"]["invalid_pct"], j["qc"]["exclusion_reasons"]))

        def mut_gap(L):
            def f(t, r):
                if 500 < t < 500 + L:
                    r["current_valid"] = False
                    r["charge_valid"] = False
                return r
            return f
        j = energy_run(load_run(_mk(tmp, "gap11", "NAc", _pw_A, mutate=mut_gap(11.5))), "NAc", 1, "C1")
        check("② 유효 표본 간격 11 s → '표본 간격 > 10 s'", any("간격" in x for x in j["qc"]["exclusion_reasons"]), (j["qc"]["max_gap_s"], j["qc"]["exclusion_reasons"]))
        j = energy_run(load_run(_mk(tmp, "gap10", "NAc", _pw_A, mutate=mut_gap(10))), "NAc", 1, "C1")
        check("② 유효 표본 간격 10 s → 간격 사유 없음", not any("간격" in x for x in j["qc"]["exclusion_reasons"]), (j["qc"]["max_gap_s"], j["qc"]["exclusion_reasons"]))

        def mut_up(t, r):
            if 450 <= t < 460:
                r["charge_counter_raw"] += 2 * Q_UAH
            return r
        j = energy_run(load_run(_mk(tmp, "up", "NAc", _pw_A, mutate=mut_up)), "NAc", 1, "C1")
        check("② 잔량계 증가 → 제외", j["qc"]["excluded"] and any("증가" in x for x in j["qc"]["exclusion_reasons"]), j["qc"]["exclusion_reasons"])

        def mut_nm(t, r):
            if t >= 455:
                r["charge_counter_raw"] -= 1000
            return r
        j = energy_run(load_run(_mk(tmp, "nm", "NAc", _pw_A, mutate=mut_nm)), "NAc", 1, "C1")
        check("② 4,275 배수 아닌 변화 → 제외", j["qc"]["excluded"] and any("배수" in x for x in j["qc"]["exclusion_reasons"]), j["qc"]["exclusion_reasons"])

        def mut_ma(t, r):
            r["current_raw"] = int(r["current_raw"] / 1000)
            return r
        j = energy_run(load_run(_mk(tmp, "mA", "NAc", _pw_A, mutate=mut_ma)), "NAc", 1, "C1")
        check("② 전류가 mA (R ≈ 0.001) → ① FAIL → 제외", j["qc"]["unit_1"] == "FAIL" and j["qc"]["excluded"], (j["qc"]["unit_1"], round(j["energy"]["R_run"], 5)))
        j = energy_run(load_run(_mk(tmp, "flat", "NAc", lambda t: 2.0)), "NAc", 1, "C1")
        check("② 전력 평탄 (가동 전후 30 s 같음) → 시계 맞춤 실패 → 제외", j["qc"]["clock_check"] == "FAIL" and any("시계" in x for x in j["qc"]["exclusion_reasons"]),
              (j["energy"]["clock"]["mean_pre_uA"], j["energy"]["clock"]["mean_post_uA"]))

        def pw_shift(t):          # 시계가 40 s 밀린 것처럼: 가동이 구간 시작 40 s 뒤부터
            return 0.67 if (t < 40 or t >= 340) else 5.2
        j = energy_run(load_run(_mk(tmp, "shift", "NAc", pw_shift)), "NAc", 1, "C1")
        check("② 가동이 구간 시작 40 s 뒤 (시계 어긋남) → 시계 맞춤 실패", j["qc"]["clock_check"] == "FAIL", j["energy"]["clock"]["ok"])
        segs_bad = [dict(index=0, duty=1, start_ns=0, end_ns=840 * 10**9), dict(index=1, duty=100, start_ns=840 * 10**9, end_ns=900 * 10**9)]
        segs_ok = [dict(index=0, duty=100, start_ns=0, end_ns=300 * 10**9), dict(index=1, duty=1, start_ns=300 * 10**9, end_ns=900 * 10**9)]
        segs_edge = [dict(index=0, duty=50, start_ns=0, end_ns=840 * 10**9), dict(index=1, duty=1, start_ns=840 * 10**9, end_ns=900 * 10**9)]
        check("② 끝 구간 부하 (마지막 60 s 가 d100) → 실패 · 끝 600 s 쉼 → 통과 · 끝 정확히 60 s 쉼 → 통과",
              not tail_duty_check(segs_bad, 900 * 10**9)["ok"] and tail_duty_check(segs_ok, 900 * 10**9)["ok"] and tail_duty_check(segs_edge, 900 * 10**9)["ok"],
              (tail_duty_check(segs_bad, 900 * 10**9)["segments_in_last_60s"], tail_duty_check(segs_edge, 900 * 10**9)["segments_in_last_60s"]))
        # ③ 칸 · NBc ê · 쌍 · 중간 판정 금지
        rdB = _mk(tmp, "okB", "NBc", _pw_B(620))
        jB = energy_run(load_run(rdB), "NBc", 1, "C1")
        eh = jB["energy"]["e_hat"]
        exp_eh = ((5.2 + 0.67) / 2 * 620 - 0.67 * 620) / jB["energy"]["n"]
        check("③ NBc (620/280): 제외 없음 · ê_B ≈ [(5.2+0.67)/2·620 − 0.67·620] / n (±2 %)", not jB["qc"]["excluded"] and abs(eh["e_hat_J"] / exp_eh - 1) < 0.02,
              (round(eh["e_hat_J"], 5), round(exp_eh, 5), jB["qc"]["exclusion_reasons"]))
        raises("③ 620/280 런을 NBe 칸으로 → 오류 (판정기 칸 표)", lambda: energy_run(load_run(rdB), "NBe", 1, "N2"))
        raises("③ pair NAc + NBc → 거부 (judgeC 에서만)", lambda: pair_energy(jA, jB))
        p = pair_energy(jA, jB, allow_c=True)
        check("③ 부호: ΔE_p = E_cc(A) − E_cc(B) · 양수 = B 적음 · ΔE_adj = ΔE + (n_B − n_A)·ê_B",
              abs(p["dE_p"] - (jA["energy"]["E_cc_J"] - jB["energy"]["E_cc_J"])) < 1e-9 and p["sign"] == ("+" if _r6(p["dE_p"]) > 0 else ("-" if _r6(p["dE_p"]) < 0 else "0"))
              and _fake_pair(1, 30)["sign"] == "+"
              and abs(p["dE_adj"] - (p["dE_p"] + (p["n_b"] - p["n_a"]) * eh["e_hat_J"])) < 1e-9, (round(p["dE_p"], 2), p["sign"], round(p["dE_adj"], 2)))
        raises("③ pair 자리 바뀜 (B, A) → 오류", lambda: pair_energy(jB, jA, allow_c=True))
        rdN = _mk(tmp, "nbe", "NBe", _pw_B(660))
        jN = energy_run(load_run(rdN), "NBe", 1, "N2")
        jNA = energy_run(load_run(_mk(tmp, "nae", "NAe", _pw_A)), "NAe", 1, "N2")
        pN = pair_energy(jNA, jN)
        check("③ 에너지 B 쌍 NAe + NBe → 기술 쌍 (r = n_B/n_A > 1.04 → r 거름 밖)", pN["family"] == "N2" and not pN["r_in_filter"]
              and abs(pN["r"] - jN["energy"]["n"] / jNA["energy"]["n"]) < 1e-12 and pN["r"] > 1.04,
              (round(pN["r"], 4), pN["r_in_filter"]))
        raises("③ session 에 NAc 런 → main 이 거부 (아래 CLI 와 같은 검사)", lambda: _reject_c([jA]))
        # ④ r 거름 경계
        for r, exp in ((0.959, False), (0.96, True), (1.04, True), (1.041, False)):
            check(f"④ r {r} → 판정 쌍 {exp}", _fake_pair(1, 10, r=r)["r_in_filter"] is exp, _fake_pair(1, 10, r=r)["r_in_filter"])
        # ⑤ 판정 규칙
        q = 63.0
        vc = verdict_C([_fake_pair(k, 100) for k in range(1, 4)])
        check("⑤ n 3 → '쌍 부족 — 기술만' · v2 '적격 미확보 — 부록 관측 (쌍 부족)'", vc["verdict"] == L4["few"] and eligibility_v2(vc) == ELIG_FEW, vc["verdict"])
        vc = verdict_C([_fake_pair(k, 200) for k in range(1, 9)])
        se = SE_FLOOR * q / math.sqrt(8)
        check("⑤ ΔE 8쌍 모두 +200 (sd 0) → SE 바닥 0.58·q̄_J/√8 · 'B 낮음' · 동등 범위 밖", abs(vc["SE_J"] - se) < 1e-9 and vc["se_floor_used"]
              and vc["verdict"] == L4["low"] and vc["equivalence_note"] == "동등 범위 밖", (round(vc["SE_J"], 4), vc["verdict"], vc.get("equivalence_note")))
        vc = verdict_C([_fake_pair(k, -200) for k in range(1, 9)])
        check("⑤ ΔE 모두 −200 → 'B 높음'", vc["verdict"] == L4["high"], vc["verdict"])
        vc = verdict_C([_fake_pair(k, 70) for k in range(1, 9)])
        check("⑤ ΔE +70 (> 3SE 38.8 · > q̄ 63) · |Δ̄|+3SE 108.8 ≤ 2q̄ 126 → 'B 낮음' + '동등 범위 안'",
              vc["verdict"] == L4["low"] and vc["equivalence_note"] == "동등 범위 안 (±2 눈금)", (vc["verdict"], vc.get("equivalence_note"), round(vc["three_SE_J"], 2)))
        vc = verdict_C([_fake_pair(k, 50) for k in range(1, 9)])
        check("⑤ ΔE +50 (≤ q̄) · 50 + 38.8 ≤ 126 → '동등 범위 안 (±2 눈금)'", vc["verdict"] == L4["eq"], vc["verdict"])
        vals = [300, -250, 280, -240, 260, -270, 10, -20]
        vc = verdict_C([_fake_pair(k + 1, v) for k, v in enumerate(vals)])
        check("⑤ ΔE 크게 엇갈림 (평균 ≈ 9 · sd ≈ 250) → '구분 안 됨'", vc["verdict"] == L4["nd"], (round(vc["d_bar_J"], 2), round(vc["three_SE_J"], 1), vc["verdict"]))
        # ⑥ ②′
        vc = verdict_C([_fake_pair(k, 200, dR=0.05) for k in range(1, 9)])
        check("⑥ ②′ 평균 d_R 0.05 > max(0.03, 3·SE 0) → '계기 불일치 — 기술만' (방향보다 먼저) · v2 '적격 미확보 (계기 불일치)'",
              vc["verdict"] == L4["inst"] and vc["rule_verdict_without_inst"] == L4["low"] and eligibility_v2(vc) == ELIG_INST, (vc["verdict"], vc["inst"]))
        vc = verdict_C([_fake_pair(k, 200, dR=0.029) for k in range(1, 9)])
        check("⑥ ②′ 평균 d_R 0.029 (≤ 0.03) → 통과 · 'B 낮음'", vc["verdict"] == L4["low"] and vc["inst"]["verdict"] == "통과", (vc["verdict"], vc["inst"]["verdict"]))
        dRs = [0.10, -0.06, 0.09, -0.05, 0.08, -0.07, 0.10, -0.06]
        vc = verdict_C([_fake_pair(k + 1, 200, dR=d) for k, d in enumerate(dRs)])
        check("⑥ ②′ 평균 d_R 0.016 · 3·SE(d_R) > 0.03 → 한계 = 3·SE · 통과", vc["inst"]["limit"] > 0.03 and vc["inst"]["verdict"] == "통과",
              (round(vc["inst"]["mean_d_R"], 4), round(vc["inst"]["limit"], 4)))
        vc = verdict_C([_fake_pair(k, 200, dEint=-30) for k in range(1, 9)])
        check("⑥ ②′ 방향 판정 (B 낮음) 인데 E_int 평균 차 부호 반대 → '계기 불일치'", vc["verdict"] == L4["inst"] and vc["inst"]["fail_sign"], vc["inst"])
        vc = verdict_C([_fake_pair(k, 50, dEint=-30) for k in range(1, 9)])
        check("⑥ ②′ 부호 검사는 방향 판정일 때만 — 동등 범위 안 + E_int 반대 부호 → 그대로 '동등 범위 안'", vc["verdict"] == L4["eq"], vc["verdict"])
        vc = verdict_C([_fake_pair(1, 200, dR=0.5)])
        check("⑥ ②′ n 1 → 산출 불가 (불일치 아님) → '쌍 부족'", vc["verdict"] == L4["few"] and vc["inst"]["verdict"] == "산출 불가", vc["inst"])
        # ⑦ ② 세션
        s = session_check([_fake_run("NAc", k, "C1", R=0.95) for k in range(1, 5)])
        tol = 3 * 0.080 / math.sqrt(4)
        check("⑦ ② N 4 (< 8) → σ_R 0.080 대체 · 허용 ±0.120 · R_sum 0.95 → PASS", s["sigma_source"].startswith("σ_R 0.080") and abs(s["tolerance"] - tol) < 1e-12
              and s["verdict"] == "PASS", s["line"])
        runs8 = [_fake_run("NAc", k, "C1", R=0.95 + 0.001 * k) for k in range(1, 9)]
        s = session_check(runs8)
        check("⑦ ② N 8 → σ_R = 런별 R 모집단 sd · R_sum ≈ 0.955 · 허용 3·0.0023/√8 → FAIL", s["sigma_source"].startswith("σ_R 0.00")
              and abs(s["sigma_used"] - statistics.pstdev([0.95 + 0.001 * k for k in range(1, 9)])) < 1e-12 and s["verdict"] == "FAIL", s["line"])
        s = session_check([_fake_run("NAc", 1, "C1", R=0.95, excl=True)] + [_fake_run("NAc", k, "C1") for k in range(2, 4)])
        check("⑦ ② 제외 런은 빠진다 (N 2)", s["N"] == 2, s["line"])
        # ⑧ judgeC · §10 문장 · v2 적격 세 경우
        def runs_for(dEs, dR=0.0, sess=None, excl_blocks=()):
            out = []
            for k, d in enumerate(dEs, start=1):
                a = _fake_run("NAc", k, sess or ("C1" if k <= 4 else "C2"), R=1.0 + dR / 2, excl=k in excl_blocks)
                b = _fake_run("NBc", k, sess or ("C1" if k <= 4 else "C2"), R=1.0 - dR / 2)
                b["energy"] = dict(b["energy"], E_cc_J=2000.0 - d, E_int_J=2000.0 - d)
                a["qc"]["run_id"], b["qc"]["run_id"] = f"a{k}", f"b{k}"
                out += [a, b]
            return out
        r = judge_C(runs_for([200] * 8))
        check("⑧ (a) 8쌍 ΔE +200 · ②′ 통과 → '결론 (적격 …)' · §10 'B 낮음' 문장 · '평균 200 J (10.0 %) 적었다' · 쌍 8개",
              r["eligibility_v2"] == ELIG_OK and r["head"].startswith("결론") and r["conclusion_sentence"] is not None
              and "평균 200 J (10.0 %) 적었다 (같은 일 쌍 8개 · 잔량계 기준 · 절대 정확도 미인증)" in r["conclusion_sentence"] and "②′" in r["attach"]
              and "[C1] ② 내부 일관성" in r["attach"] and "[C2] ② 내부 일관성" in r["attach"] and r["limit_note"] is not None, r["conclusion_sentence"])
        r = judge_C(runs_for([200] * 3))
        check("⑧ (b) 3쌍 → '부록 관측 (적격 미확보 — 부록 관측 (쌍 부족))' · 결론 문장 없음", r["eligibility_v2"] == ELIG_FEW and r["head"].startswith("부록 관측")
              and r["conclusion_sentence"] is None and r["registered_sentence"] is None, r["head"])
        r = judge_C(runs_for([200] * 8, dR=0.06))
        check("⑧ (c) ②′ 불일치 → '부록 관측 (… 계기 불일치)' · 등록 문장은 '계기 불일치' 문장 (결론 아님)", r["eligibility_v2"] == ELIG_INST and r["conclusion_sentence"] is None
              and r["registered_sentence"].startswith("「전류 적분과 잔량계가") and "+0.060" in r["registered_sentence"], r["registered_sentence"])
        r = judge_C(runs_for([50] * 8))
        check("⑧ '동등 범위 안' 문장 · ±126 J · 6.3 %", "±2 눈금 (≈ ±126 J, 창 에너지의 약 6.3 %) 안이었다 (같은 일 쌍 8개 · 잔량계 기준)" in r["conclusion_sentence"], r["conclusion_sentence"])
        r = judge_C(runs_for(vals))
        check("⑧ '구분 안 됨' 문장 · 한 눈금 ≈ 63 J · 3SE · 쌍 8개", r["verdict"] == L4["nd"] and "한 눈금 ≈ 63 J · 3SE = " in r["conclusion_sentence"]
              and "쌍 8개" in r["conclusion_sentence"], r["conclusion_sentence"])
        r = judge_C(runs_for([-200] * 8))
        check("⑧ 'B 높음' 문장 (… 채움) · '더 들었다' · '맞바뀐다'", "평균 200 J (10.0 %) 더 들었다 (같은 일 쌍 8개 · 잔량계 기준 · 절대 정확도 미인증) — 이 조건에서 열 부담과 에너지는 맞바뀐다" in r["conclusion_sentence"],
              r["conclusion_sentence"])
        rr = runs_for([200] * 8, excl_blocks=(2,))
        r = judge_C(rr)
        check("⑧ 블록 2 의 A 런 제외 → 판정 쌍 7 · 제외 사유 표기", r["n_judged"] == 7 and any(x["block"] == 2 and x["why"].startswith("제외") for x in r["not_judged"]), r["not_judged"])
        rr = runs_for([200] * 8)
        rr = [x for x in rr if not (x["qc"]["block"] == 8 and x["qc"]["cell"] == "NBc")]
        r = judge_C(rr)
        check("⑧ 블록 8 B 런 없음 → 짝 없음 · 판정 쌍 7", r["n_judged"] == 7 and r["unpaired"] == [dict(block=8, have=["NAc"])], r["unpaired"])
        raises("⑧ 같은 블록 · 칸 런 둘 → 오류", lambda: judge_C(runs_for([200] * 2) + [_fake_run("NAc", 1, "C1")]))
        raises("⑧ judgeC 에 NAe 런 → 오류", lambda: judge_C([dict(_fake_run("NAc", 1, "C1"), qc=dict(_fake_run("NAc", 1, "C1")["qc"], cell="NAe"))]))
        # ⑨ qc 출력에 에너지 숫자 없음 · 결정성
        keys = set(jA["qc"])
        banned = {"E_cc_J", "E_int_J", "R_run", "Q_int_uAh", "dQ_cc_uAh", "q_J", "V_median_mV"}
        check("⑨ qc 출력에 E · R · Q · q · 전압 키 없음", not (keys & banned), sorted(keys & banned))
        d1 = dumps(energy_run(load_run(_mk(tmp, "detA", "NBc", _pw_B(620))), "NBc", 3, "C1")).replace(tmp.replace("\\", "\\\\"), "X")
        d2 = dumps(energy_run(load_run(_mk(tmp, "detB", "NBc", _pw_B(620))), "NBc", 3, "C1")).replace(tmp.replace("\\", "\\\\"), "X")
        d1 = d1.replace("detA", "Z")
        d2 = d2.replace("detB", "Z")
        check("⑨ 결정성: 같은 입력 두 번 = 같은 바이트 (경로 제외)", d1 == d2, f"{len(d1)} B")
        # ⑩ V3 칸 창 (v1 · v2 표) — 칸 착오 오류
        segs = [dict(accelerator="NPU", duty=d, duration_s=L, lat_ms=lambda t: 0.9, label=V._label(i, d)) for i, (d, L) in enumerate(V2.CELLS_V2["B2_base"]["segs"])]
        rdv = J._synth_run(os.path.join(tmp, "v3"), "v3_B_base_v2", segs, rate=20.0, thermal=False)
        Sv = segments_of(load_run(rdv))
        s_act = Sv["segments"][1]["start_ns"]

        def pw_v3(t):
            tt = (t * 1e9 + Sv["segments"][0]["start_ns"])
            for sg in Sv["segments"]:
                if sg["start_ns"] <= tt < sg["end_ns"]:
                    return 5.2 if sg["duty"] == 100 else 0.67
            return 0.67
        _synth_power(rdv, pw_v3)
        jv = energy_run(load_run(rdv), "B2_base", 2, "V3B2")
        wexp = sum(L for _, L in V2.CELLS_V2["B2_base"]["segs"]) + 0.5 * (len(V2.CELLS_V2["B2_base"]["segs"]) - 1)
        check("⑩ V3 v2 B2_base: 창 = 구간 0 ~ 끝 (Σ 2,729 s + 전환 6 × 0.5 s) · 첫 가동 = 구간 1 · 제외 없음", not jv["qc"]["excluded"] and abs(jv["qc"]["window_s"] - wexp) < 0.01
              and jv["energy"]["clock"]["ok"], (jv["qc"]["window_s"], jv["qc"]["exclusion_reasons"]))
        raises("⑩ V3 v2 런을 v1 칸 B_base 로 → 오류", lambda: energy_run(load_run(rdv), "B_base", 2, "V3B2"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(c for _, c, _ in res)
    print("| 시험 | 결과 | 값 |\n|---|---|---|")
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:170]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1


def _reject_c(runs):
    for j in runs:
        if j["qc"]["cell"] in C_CELLS:
            raise JudgeError("에너지 C 칸 (NAc · NBc) 은 judgeC 에서만 (등록 §4 — 중간 판정 금지)")


# ============================================================ CLI
def _qc_line(j):
    q = j["qc"]
    why = " · ".join(q["exclusion_reasons"]) if q["excluded"] else "-"
    return (f"QC {q['cell']}_b{q['block']} ({q['session']}) run={q['run_id']} excluded={q['excluded']} reasons={why} unit_1={q['unit_1']} "
            f"clock={q['clock_check']} invalid_pct={q['invalid_pct']} max_gap_s={q['max_gap_s']} plugged_nonzero={q['n_plugged_nonzero']} "
            f"cc_increase={q['n_cc_increase']} cc_nonmultiple={q['n_cc_nonmultiple']} tail_ok={q['tail_ok']} model_sha={q['model_sha_label']}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    for name in ("qc", "run"):
        a = sub.add_parser(name)
        a.add_argument("run_dir")
        a.add_argument("--cell", required=True, choices=ALL_CELLS)
        a.add_argument("--block", required=True, type=int)
        a.add_argument("--session", required=True)
        a.add_argument("--out", required=(name == "run"))
    a = sub.add_parser("pair")
    a.add_argument("--a", required=True)
    a.add_argument("--b", required=True)
    a.add_argument("--out", required=True)
    a = sub.add_parser("session")
    a.add_argument("--runs", nargs="+", required=True)
    a.add_argument("--out", required=True)
    a = sub.add_parser("judgeC")
    a.add_argument("--runs", nargs="+", required=True)
    a.add_argument("--out", required=True)
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd in ("qc", "run"):
            j = energy_run(load_run(args.run_dir), args.cell, args.block, args.session)
            if args.cmd == "qc":
                res = dict(kind="energy_qc_v1", qc=j["qc"], imports=j["imports"])
                if args.out:
                    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
                    with open(args.out, "w", encoding="utf-8") as fh:
                        fh.write(dumps(res) + "\n")
                print(_qc_line(j))
                return 0
            res = j
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(dumps(res) + "\n")
            print(_qc_line(j))
            print(f"wrote {args.out}")
            return 0
        if args.cmd == "pair":
            res = pair_energy(_load_json(args.a), _load_json(args.b))
        elif args.cmd == "session":
            runs = [_load_json(f) for f in args.runs]
            _reject_c(runs)
            res = dict(kind="energy_session_v1", **session_check(runs), runs=[r["qc"]["run_id"] for r in runs])
        else:
            if os.path.exists(args.out):
                raise JudgeError(f"judgeC 출력이 이미 있다 — 판정은 한 번 (등록 §4): {args.out}")
            res = judge_C([_load_json(f) for f in args.runs])
    except JudgeError as err:
        print(f"JUDGE_ERROR: {err}", file=sys.stderr)
        return 2
    text = dumps(res)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
