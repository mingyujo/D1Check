"""make_plan_h.py — GH (1011) 3단계-5: write d1sim/gpu_holdout_v1/plan_gpuho.json (cell plan, written before any phone cell).
Blocks 1..8 in the energy-C mirror order (등록 §2-3): odd k = A -> B · even k = B -> A. Cell names GAh_b<k> · GBh_b<k>, folders
results/S26_<cell>_b<k>_1011h ([_re] retry · _abort_<HHmmss> operational abort), gate = 밤1005e_사전등록_v1 §1 · §3 GPU values
(= energy C §6-5), orchestrator args = 밤1005e_체인기록 §2 GAe · GBe · 스모크 G rows (dryrun_table_h.txt), smoke G first.
  py -X utf8 make_plan_h.py
"""
import hashlib, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
sys.path.insert(0, REPO)
from d1sim.gpu_holdout_v1 import common as C  # noqa: E402

T = C.load_json(os.path.join(C.OUT_OD, "T_calc.json"))["T"]
LONG = "--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600"
SMOKE = "--runner-timeout-seconds 900 --logger-exit-timeout-seconds 600 --analyze-timeout-seconds 300 --cooling-min-seconds 60"
COMMON = ("--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 --accuracy-preflight off --start-policy stable "
          "--cooling-policy stable --stability-timeout-seconds 1800 --cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3")
spec = {
    "GAh": dict(side="A", chain="gpu_eff_work100_v1", canonical=C.CELLS["GAh"]["canonical"], segments=[["work_d100", "GPU", 100, 300], ["tail_idle", "GPU", 1, 600]], sigma_s=900, spans=400000, timeouts=LONG),
    "GBh": dict(side="B", chain="gpu_eff_work50eq_v1", canonical=C.CELLS["GBh"]["canonical"], segments=[["work_d50", "GPU", 50, T], ["tail_idle", "GPU", 1, 900 - T]], sigma_s=900, spans=400000, timeouts=LONG),
    "smokeG": dict(side=None, chain="smoke_gpu_eff_v1", canonical=C.SMOKE["canonical"], segments=[["work_d100", "GPU", 100, 30], ["tail_idle", "GPU", 1, 30]], sigma_s=60, spans=50000, timeouts=SMOKE),
}
for k, s in spec.items():
    s["orchestrator_args"] = f"--npu-chain tools\\chains\\{s['chain']}.json --duration {s['sigma_s']} --npu-max-inference-spans {s['spans']} {s['timeouts']} {COMMON}"
cells = [dict(seq=0, block=0, cell="smokeG", key="smokeG", out_name=f"S26_smokeG_{C.SESSION_SFX}", role="칸 0 = 스모크 G (판정 밖 · GPU 실행 증거 PASS 필요 · FAIL → 2 분 뒤 1번 더 → 또 FAIL 이면 등록 §0-2)")]
seq = 1
for k in C.BLOCKS:
    for i, cell in enumerate(C.ORDER[k]):
        cells.append(dict(seq=seq, block=k, cell=cell, key=f"{cell}_b{k}", out_name=f"S26_{cell}_b{k}_{C.SESSION_SFX}", first_in_block=(i == 0), judge_json=f"sim/out_gpuho/{cell}_b{k}.json"))
        seq += 1
plan = dict(kind="gpuho_plan_v1", registration=f"{C.REG} ({C.REG_COMMIT[:7]}) §2", session="H", session_suffix=C.SESSION_SFX, T_s=T, blocks=list(C.BLOCKS),
            order_rule="거울 순서 (등록 §2-3 · 에너지 C 와 같음): 홀수 블록 A → B · 짝수 블록 B → A", order={str(k): list(v) for k, v in C.ORDER.items()}, cells=cells, cell_spec=spec,
            gate=dict(upper=dict(plugged=0, soc=[30, 100], SKIN_max=32.0, AP_max=32.0, BAT_max=30.0, script="s26/tools/night_1005e/start_gate_1005e.py (120 s poll)"),
                      lower=dict(SKIN_min=29.1, BAT_min=27.5, policy="mark — 미달이면 칸을 바꾸지 않고 '하한 미달' 표시로 실행 (등록 §2-5)"),
                      cooling="orchestrator --cooling-min-seconds 600 (+ --start-policy stable · --cooling-policy stable)", airplane_mode=1, dnd=1,
                      watch="phone_watch_1005e.ps1 (10 s · 통화 · 오디오 · 맨 앞 창 · 화면) + s26_skin_watch_npu.py (15 s · SKIN ≥ 45 → runner force-stop)",
                      emergency="orchestrator BAT 42 · android thermal status 3 (--emergency-max-android-thermal-status 3)", screen="brightness mode 0 · 0 · screen_off_timeout 86400000 유지"),
            soc_rules=dict(first_measured_cell_min=85, block_start_min=45, cell_floor=30, charge_between_blocks="SOC < 45 at a block start → 드라이버 멈춤 → '충전 필요 — 케이블 꽂아 주세요 (SOC 90 까지)' → 90 → 뽑음 → 게이트 → 그 블록부터 (-Blocks -Resume -NoSmoke)"),
            invalid_rules=dict(invalid="FAILED · 감시 이벤트 · 비상 · 유효성 (run_check GPU) 실패 → 게이트 뒤 같은 칸 _re 1번", invalid_twice="또 무효 → invalid_twice: 그 블록 계산 불가 (분모 8 유지) · 블록의 남은 칸 건너뜀 → 다음 블록",
                               abort="adb 끊김 · PC 절전 등 운영 중단 → results\\<out>_abort_<HHmmss> · 시도 소모 안 함 · 다시 붙으면 게이트 뒤 같은 칸", emergency_stop="세션 3번째 비상 → 멈춤 (안전)"),
            driver="s26/tools/gpuho_1011/session_driver_h.ps1 (-Blocks · -Resume · -RetryFirst · -NoSmoke) · run_cell_h.ps1 · dryrun_h.ps1 · launch_cell_h.ps1 · stall_watch_h.ps1 (600 s idle / Σ + 150 min)",
            judge="sim/night1005e_judge_h.py run (칸마다) · pair (블록 두 칸 valid 뒤) · watchcheck → sim/out_gpuho/ · 판정 = d1sim/gpu_holdout_v1/judge_gpuho.py 한 번 (8블록 뒤)",
            expected_hours="[E] 칸 31 ~ 37 분 (N2) → 스모크 + 16칸 ≈ 9 ~ 10 h + 충전 대기")
p = os.path.join(REPO, "d1sim", "gpu_holdout_v1", "plan_gpuho.json")
s = json.dumps(plan, ensure_ascii=False, indent=1, sort_keys=True)
open(p, "w", encoding="utf-8", newline="\n").write(s + "\n")
print(f"wrote {p} sha256 {hashlib.sha256((s + chr(10)).encode('utf-8')).hexdigest()} · cells {len(cells)} · T {T}")
