"""M8 plan generator (2026-10-14 · 계약표 v1 · gate_m8.json blocks · 프롬프트 D-0) — deterministic bytes, no timestamps. mixreq_plan.pinned · m6_plan.device_inputs are imported unchanged.

  py -3 -X utf8 s26/tools/mixreq/m8_plan.py --out-root s26/results/m8_prep
      --cls-model local_models/efficientnet_lite0.tflite --det-model local_inputs/public/efficientdet_lite0.tflite
      --aot-model npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite
      --png local_inputs/canonical_v123/00575b9132bb3746.png --anchors local_inputs/reference_pc/anchors.json
      --cls-labels local_inputs/reference_pc/labels_without_background.txt --det-labels local_inputs/reference_pc/labels.txt

Writes <out-root>/plan_m8<exp>/ (plan.json · manifests/ · smoke/ · device_inputs.json · plan_sha256.txt) for the 7 M8 experiments (DEV 대역 index 만 · CONFIRM 대역은 M8-B 에서)
and <out-root>/plan_m8/blocks.json = 실행 설계 (D-1 스모크 · D-2 P0 10 · D-3 DEV 블록 1 · 2 (19 세션 · 같은 블록 안 무작위 순서 · seed DEV 20261014 · 결과 전 고정) · CONFIRM 5 설계 (index 대역 · seed 20261022 · 순서는 동결 뒤)).
Index 자리: arm 자리 + arm 수 × 반복 (m8_common.index_of) · P0 와 DEV 블록은 반복 번호를 이어서 쓴다 (쓴 자리 재사용 0). session/request ID = uuid5(M8_NS, …).
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m8_common as M8  # noqa: E402
import mixreq_common as C  # noqa: E402
import mixreq_plan as P  # noqa: E402
import m6_plan as MP  # noqa: E402

PLAN_SCHEMA = "s26-m8-plan-v1"
BLOCKS_SCHEMA = "s26-m8-blocks-v1"

# DEV 블록 1 세션 (19) — 11군 (L64 2 · C252 3 = RECENT IDLE60 · M128 6) + P2 DEV (SMOOTH 3 · RECENT CPU60 3 · WAIT200x12 · WAIT1000x12)
BLOCK_GROUPS = [
    (M8.L64_ID, "L64_BASE"), (M8.L64_ID, "L64_PAIR_G"),
    (M8.RECENT_ID, "RECENT_IDLE60_C252_CPU"), (M8.RECENT_ID, "RECENT_IDLE60_C252_GPU"), (M8.RECENT_ID, "RECENT_IDLE60_C252_NPU"),
    (M8.M128_ID, "M128_BASE"), (M8.M128_ID, "M128_ORDER"), (M8.M128_ID, "M128_PAIR_G"), (M8.M128_ID, "M128_WAIT200x16"), (M8.M128_ID, "M128_NPU_SERIAL"), (M8.M128_ID, "M128_PAIR_N"),
    (M8.S128_ID, "SMOOTH128_BASE"), (M8.S128_ID, "SMOOTH128_ORDER"), (M8.S128_ID, "SMOOTH128_PAIR_G"),
    (M8.RECENT_ID, "RECENT_CPU60_C252_CPU"), (M8.RECENT_ID, "RECENT_CPU60_C252_GPU"), (M8.RECENT_ID, "RECENT_CPU60_C252_NPU"),
    (M8.M128_ID, "M128_WAIT200x12"), (M8.M128_ID, "M128_WAIT1000x12"),
]
# P0 계측 4 · 기능 6 (핵심 87 안의 10)
P0_SESSIONS = [
    ("IDLE_NO_RUNTIME", M8.IDLE_ID, "IDLE_NO_RUNTIME"), ("IDLE_RESIDENT", M8.IDLE_ID, "IDLE_RESIDENT"),
    ("PERFETTO_OFF_C32", M8.L64_ID, "L64_BASE"), ("PERFETTO_ON_C32", M8.L64_ID, "L64_BASE"),
    ("FN_C252_CPU", M8.FN_ID, "C252_CPU"), ("FN_C252_GPU", M8.FN_ID, "C252_GPU"), ("FN_C252_NPU", M8.FN_ID, "C252_NPU"),
    ("FN_M128_BASE", M8.FN_ID, "M128_BASE"), ("FN_M128_PAIR_G", M8.FN_ID, "M128_PAIR_G"), ("FN_M128_PAIR_N", M8.FN_ID, "M128_PAIR_N"),
]
# D-1 스모크 (별도 ID · 예산 원장 · 판정 밖)
SMOKES = [
    ("SMOKE_M128_BASE", M8.M128_ID, "M128_BASE", 1), ("SMOKE_M128_WAIT200x16", M8.M128_ID, "M128_WAIT200x16", 1), ("SMOKE_M128_PAIR_G", M8.M128_ID, "M128_PAIR_G", 1),
    ("SMOKE_RECENT_CPU60", M8.RECENT_ID, "RECENT_CPU60_C252_CPU", 1), ("SMOKE_IDLE_NO_RUNTIME", M8.IDLE_ID, "IDLE_NO_RUNTIME", 10), ("SMOKE_L64_BASE", M8.L64_ID, "L64_BASE", 1),
]
CONFIRM_BLOCKS = 5
DEV_BLOCKS = 2


def manifest(experiment_id: str, split: str, index: int, device: dict, time_scale: int, labels: dict) -> dict:
    a = M8.arm_of(experiment_id, index)
    sid = M8.session_id(experiment_id, index)
    block = a["block"]
    runtimes = P.runtime_specs(block, device) if block != M8.BLOCK_NONE else []
    m = dict(
        protocol=C.PROTOCOL, experiment_id=experiment_id, split=split, contract=M8.CONTRACT, session_id=sid, session_index=index, block=block,
        pair=1 if labels.get("analysis_split") == "confirm" else 0, attempt=1, policy=a["policy"], policy_args=a["wait"], prep=dict(kind=a["prep"], prep_s=M8.PREP_S, gap_s=M8.PREP_GAP_S),
        runtimes=runtimes,
        image=dict(path=device["png"]["device_path"], sha256=device["png"]["sha256"], width=C.IMAGE_WIDTH, height=C.IMAGE_HEIGHT, rgb_sha256=C.RGB_SHA256, canonical_input_contract="canonical-srgb-png-v2"),
        anchors=dict(path=device["anchors"]["device_path"], sha256=device["anchors"]["sha256"]),
        labels=dict(classification=dict(path=device["cls_labels"]["device_path"], sha256=device["cls_labels"]["sha256"]), detection=dict(path=device["det_labels"]["device_path"], sha256=device["det_labels"]["sha256"])),
        requests=M8.requests(experiment_id, index, sid), phases=M8.phases(block), sample_period_ms=C.SAMPLE_PERIOD_MS, time_scale=time_scale, warmup_gate=True,
        stop_rules=dict(C.STOP_RULES), start_check=dict(C.START_CHECK), used_keys=list(M8.USED_KEYS_M8[a["policy"]]), registration=M8.registration(),
        input_binding=dict(image_sha256=device["png"]["sha256"], note="요청마다 같은 canonical PNG 1장 (banks_m8.json input_binding · 질문 #8)"),
        cycle=M8.CYCLE, arm=a["name"], bank=a["bank"], m8_label=f"{a['name']}#{M8.repetition_of(experiment_id, index)}",
    )
    m.update(labels)
    return m


def entry(m: dict, rel: str, **extra) -> dict:
    return dict(index=m["session_index"], policy=m["policy"], block=m["block"], pair=m["pair"], session_id=m["session_id"], manifest=rel,
                manifest_sha256=C.sha256_bytes(C.canonical_json(m)), requests=len(m["requests"]), arm=m["arm"], bank=m["bank"], policy_args=m["policy_args"],
                prep=m["prep"]["kind"], analysis_split=m.get("analysis_split"), _manifest=m, **extra)


class Allocator:
    """arm 마다 다음 반복 번호 (DEV 대역 안) — P0 → DEV 블록 1 → 2 순서로 자리를 잇는다 (쓴 자리 재사용 0)."""

    def __init__(self):
        self.next = {}

    def take(self, experiment_id: str, arm_name: str) -> int:
        rep = self.next.get((experiment_id, arm_name), 0)
        self.next[(experiment_id, arm_name)] = rep + 1
        index = M8.index_of(experiment_id, arm_name, rep)
        if index >= M8.dev_count(experiment_id):
            raise SystemExit(f"DEV band exhausted for {experiment_id} {arm_name}")
        return index


def design(device: dict) -> tuple[dict, dict]:
    """blocks.json + the manifests per experiment (DEV band only)."""
    alloc = Allocator()
    per_exp: dict[str, list[dict]] = {eid: [] for eid in M8.EXPERIMENT_IDS}
    smoke_per_exp: dict[str, list[dict]] = {eid: [] for eid in M8.EXPERIMENT_IDS}

    def add(stage: str, label: str, eid: str, arm_name: str, block_no=None, order_pos=None, extra=None) -> dict:
        index = alloc.take(eid, arm_name)
        m = manifest(eid, "confirmation", index, device, 1, dict(analysis_split="dev", stage=stage, run_label=label, block_no=block_no, order_pos=order_pos, **(extra or {})))
        e = entry(m, f"manifests/{index:03d}_{m['arm']}_{m['session_id']}.json", stage=stage, run_label=label, block_no=block_no, order_pos=order_pos, **(extra or {}))
        per_exp[eid].append(e)
        return dict(stage=stage, label=label, experiment_id=eid, index=index, arm=arm_name, session_id=m["session_id"], manifest_sha256=e["manifest_sha256"], plan_dir=M8.PLAN_DIR[eid],
                    block_no=block_no, order_pos=order_pos, **(extra or {}))

    smokes = []
    for label, eid, arm_name, ts in SMOKES:
        sm_id = f"{eid}-SMOKE"
        a = M8.arms(eid)
        index = next(i for i, x in enumerate(a) if x["name"] == arm_name)
        m = manifest(sm_id, "diagnostic", index, device, ts, dict(stage="smoke", run_label=label, smoke=True))
        e = entry(m, f"smoke/{label}.json", name=label, stage="smoke", run_label=label, time_scale=ts)
        smoke_per_exp[eid].append(e)
        smokes.append(dict(stage="smoke", label=label, experiment_id=sm_id, index=index, arm=arm_name, session_id=m["session_id"], manifest_sha256=e["manifest_sha256"], plan_dir=M8.PLAN_DIR[eid], time_scale=ts,
                           name=label, note="별도 ID · 예산 원장 · 판정 밖 · 실패 = 코드 고침 → 재스모크"))
    p0 = [add("p0", label, eid, arm_name, extra=dict(perfetto=("on" if "PERFETTO_ON" in label else "off" if "PERFETTO_OFF" in label else None))) for label, eid, arm_name in P0_SESSIONS]
    rng = random.Random(M8.DEV_SEED)
    dev_blocks = []
    for b in range(1, DEV_BLOCKS + 1):
        order = list(range(len(BLOCK_GROUPS)))
        rng.shuffle(order)
        sessions = []
        for pos, gi in enumerate(order):
            eid, arm_name = BLOCK_GROUPS[gi]
            sessions.append(add("dev", f"B{b}-{pos:02d}-{arm_name}", eid, arm_name, block_no=b, order_pos=pos, extra=dict(group_index=gi)))
        dev_blocks.append(dict(block_no=b, seed=M8.DEV_SEED, order=order, sessions=sessions))
    # CONFIRM 설계 (대역 · seed · 순서는 동결 뒤 생성 — M8-B): index = dev_count + arm 자리 + arm 수 × 반복 (반복 0..4)
    confirm = dict(blocks=CONFIRM_BLOCKS, seed=M8.CONFIRM_SEED, groups=[dict(experiment_id=e, arm=a) for e, a in BLOCK_GROUPS], index_rule="dev_count(exp) + index_of(exp, arm, rep) · rep = 0..4",
                   note="CONFIRM 매니페스트 · 순서는 DEV 2블록 뒤 동결 파일 (후보 · 설정 · 지표 · 분석 기준 · 허용치 · SHA) 다음 M8-B 에서 생성 · 같은 seed 로 결정적 · 반복 5 축소 없음")
    blocks = dict(schema=BLOCKS_SCHEMA, registration=M8.registration(), cycle=M8.CYCLE, contract=M8.CONTRACT, dev_seed=M8.DEV_SEED, confirm_seed=M8.CONFIRM_SEED,
                  groups_per_block=[dict(experiment_id=e, arm=a) for e, a in BLOCK_GROUPS], sessions_per_block=len(BLOCK_GROUPS),
                  stages=dict(smoke=smokes, p0=p0, dev_blocks=dev_blocks, confirm=confirm),
                  counts=dict(smoke=len(smokes), p0=len(p0), dev=len(BLOCK_GROUPS) * DEV_BLOCKS, confirm_planned=len(BLOCK_GROUPS) * CONFIRM_BLOCKS),
                  rules=dict(gate="gate_m8.json (SOC 시작 하한 20 · 상한 없음 = 영훈 운영 결정 · Tref 제안 v1 · 10 min PRESTART_REJECT) · 세션 사이 ≥ 90 s · 무효 1회 재시도 (a2) → invalid_twice · a2 재사용 0 · 쓴 ID 재사용 0",
                             prestart_reject="그 자리에 기록 · 그 블록 안 1회 재시도 · 자리 이동 없음 · 계획 밖 재시도 0", charge="블록 밖 원칙 · SOC < 20 이면 블록 안 충전 허용 (표시) · 분리 + 1,200 s 뒤 이어서",
                             c252_in_block="C252 CPU/GPU/NPU (P1) = RECENT IDLE60 arm (cold 기준 · 같은 60 s idle 준비 · 5 s) · RECENT = CPU60 arm (REQUEST P2-B)",
                             perfetto="PERFETTO_OFF/ON = L64 BASE 2세션 · on 은 호스트 perfetto battery counters 동시 기록 (미지원이면 off 1 + 기록 · 질문 #11)"),
                  notes=["index = arm 자리 + arm 수 × 반복 · P0 → 블록 1 → 블록 2 순서로 반복 번호를 잇는다", "계산 · 판정 (J · 열 · 정책 비교) 없음 — 조민규 / Cowork"])
    built = {}
    for eid in M8.EXPERIMENT_IDS:
        sessions = sorted(per_exp[eid], key=lambda e: e["index"])
        plan = dict(schema=PLAN_SCHEMA, experiment_id=eid, smoke_experiment_id=f"{eid}-SMOKE", protocol=C.PROTOCOL, cycle=M8.CYCLE, contract=M8.CONTRACT, registration=M8.registration(),
                    inputs={k: {kk: vv for kk, vv in v.items() if kk != "host_path"} for k, v in device.items()},
                    device_input_dir=C.DEVICE_INPUT_DIR, device_session_dir=C.DEVICE_SESSION_DIR, app_package=C.APP_PACKAGE, app_output_dir=C.APP_OUTPUT_DIR,
                    phases={M8.BLOCK_M: M8.phases(M8.BLOCK_M), M8.BLOCK_NONE: M8.phases(M8.BLOCK_NONE)}, sample_period_ms=C.SAMPLE_PERIOD_MS, stop_rules=C.STOP_RULES, start_check=C.START_CHECK,
                    arms=M8.arms(eid), index_max=M8.INDEX_MAX[eid], dev_count=M8.dev_count(eid), index_rule="arm = index % len(arms) · repetition = index // len(arms) · DEV = index < dev_count",
                    deadlines_ms=dict(classification=M8.URGENT_DEADLINE_MS, detection=M8.NORMAL_DEADLINE_MS), burst_interval_us=M8.BURST_INTERVAL_US, soc_start_band=[M8.SOC_MIN_START, M8.SOC_MAX_START],
                    sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions], smoke=[{k: v for k, v in s.items() if k != "_manifest"} for s in smoke_per_exp[eid]],
                    notes=["split = confirmation (앱: 실제 세션) · analysis_split dev · cycle m8 · contract M8 (baseline 60 · cooling 90 · 120 s 뒤 dispatch 0 · readback)",
                           "계산 · 판정 없음 — 조민규 / Cowork"])
        built[M8.PLAN_DIR[eid]] = dict(plan=plan, sessions=sessions, smoke=smoke_per_exp[eid], device=device)
    return blocks, built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-root", required=True, type=Path)
    for name in ("cls-model", "det-model", "aot-model", "png", "anchors", "cls-labels", "det-labels"):
        ap.add_argument("--" + name, required=True, type=Path)
    args = ap.parse_args()
    M8.activate()
    device = MP.device_inputs(args)
    blocks, built = design(device)
    shas = {}
    for name, b in built.items():
        shas[name] = MP.write_sessions(args.out_root / name, b)
        print(f"{name} {shas[name]} sessions {len(b['sessions'])} smoke {len(b['smoke'])}")
    (args.out_root / "plan_m8").mkdir(parents=True, exist_ok=True)
    blocks["plan_sha256"] = shas
    bb = C.canonical_json(blocks)
    (args.out_root / "plan_m8" / "blocks.json").write_bytes(bb)
    d = C.sha256_bytes(bb)
    (args.out_root / "plan_m8" / "blocks_sha256.txt").write_text(d + "\n", encoding="utf-8", newline="\n")
    print(f"blocks {d} smoke {blocks['counts']['smoke']} p0 {blocks['counts']['p0']} dev {blocks['counts']['dev']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
