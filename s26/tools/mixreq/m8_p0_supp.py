"""M8 P0 보충 계획 (2026-10-15 · 등록 v3 부록 · 영훈 08:xx): P0 PERFETTO_ON_C32 (L64 index 2) 는 유효 기록이나 perfetto_cmd 가 config 를 못 읽어 trace 0 (계측 오류 · 원장 04:02)
→ 원 세션 보존 · 재실행 0 · **새 index** 로 L64 BASE Perfetto-on 1세션을 추가한다 (stdin config · 드라이버 perfetto_start 고침 · 같은 게이트). blocks.json · plan_m8l64 는 바꾸지 않는다.

  py -3 -X utf8 s26/tools/mixreq/m8_p0_supp.py            → s26/results/m8_prep/plan_m8l64_supp/ (plan.json · manifests/008_… · device_inputs.json · plan_sha256.txt)
                                                             + s26/results/m8_prep/plan_m8/p0_supp.json (stages.p0 = [PERFETTO_ON_C32_r2]) · 결정적 바이트 (시각 0)
Index = L64 BASE 다음 반복 (P0 0·2 · 블록 1 4 · 블록 2 6 → **8**) · session_id = uuid5(M8_NS, "S26-M8-L64/8") · 소비된 ID 재사용 0 · DEV 대역 (< 200) · 등록 = v2 SHA (계약 v2 그대로 · v3 는 부록만).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m8_common as M8  # noqa: E402
import m8_plan as PL  # noqa: E402
import mixreq_common as C  # noqa: E402
import m6_plan as MP  # noqa: E402

OUT_ROOT = M8.REPO / "s26" / "results" / "m8_prep"
SRC = OUT_ROOT / "plan_m8l64"
DST = OUT_ROOT / "plan_m8l64_supp"
LABEL = "PERFETTO_ON_C32_r2"
ARM = "L64_BASE"
REPETITION = 4   # 0 = P0 off (idx 0) · 1 = P0 on (idx 2 · trace 0) · 2 = 블록 1 (idx 4) · 3 = 블록 2 (idx 6) → 4 = idx 8


def main() -> int:
    M8.activate()
    src_plan = C.read_json(SRC / "plan.json")
    device = C.read_json(SRC / "device_inputs.json")
    eid = M8.L64_ID
    index = M8.index_of(eid, ARM, REPETITION)
    used = {s["index"] for s in src_plan["sessions"]}
    if index in used:
        raise SystemExit(f"index {index} already in plan_m8l64 (소비된 자리 재사용 0)")
    assert index < M8.dev_count(eid)
    labels = dict(analysis_split="dev", stage="p0", run_label=LABEL, block_no=None, order_pos=None, perfetto="on",
                  supplement="P0 보충 (등록 v3 부록 · PERFETTO_ON_C32 idx 2 trace 0 → 새 index · stdin config · 셈 여부 = 조민규)")
    m = PL.manifest(eid, "confirmation", index, device, 1, labels)
    e = PL.entry(m, f"manifests/{index:03d}_{m['arm']}_{m['session_id']}.json", stage="p0", run_label=LABEL, block_no=None, order_pos=None, perfetto="on")
    plan = dict(src_plan)
    plan["sessions"] = [{k: v for k, v in e.items() if k != "_manifest"}]
    plan["smoke"] = []
    plan["supplement"] = dict(of="plan_m8l64", source_plan_sha256=C.sha256_file(SRC / "plan.json"), reason="P0 PERFETTO_ON_C32 (idx 2) trace 0 (perfetto config errno 13) → 보충 1세션 · 새 index · 등록 v3 부록",
                              registration_v2=M8.registration())
    built = dict(plan=plan, sessions=[e], smoke=[], device=device)
    digest = MP.write_sessions(DST, built)
    item = dict(stage="p0", label=LABEL, experiment_id=eid, index=index, arm=ARM, session_id=m["session_id"], manifest_sha256=e["manifest_sha256"], plan_dir=DST.name,
                block_no=None, order_pos=None, perfetto="on", supplement=labels["supplement"])
    supp = dict(schema="s26-m8-p0-supp-v1", registration=M8.registration(), registration_v3_note="등록 v3 = v2 전문 + 부록 (P0 Perfetto on 보충 1세션) · 블록 1·2 는 v2 계약 그대로",
                of_blocks_sha256=C.sha256_file(OUT_ROOT / "plan_m8" / "blocks.json"), plan_sha256={DST.name: digest},
                stages=dict(p0=[item]), counts=dict(p0=1),
                notes=["원 PERFETTO_ON_C32 (L64 idx 2 · 04:01 유효 · trace 0) 보존 · 재실행 0 · 자리 소비 유지", "이 세션 = Perfetto on (stdin config · 06:20 블록 밖 probe 1,772 B 근거) · 같은 Tref 게이트 · L64 BASE · 셈 여부 = 조민규",
                       "Perfetto 가 또 0 이면 그대로 기록 (재시도 0) · 블록 1·2 는 off 만 (미지원 (권한))", "계산 · 판정 없음"])
    bb = C.canonical_json(supp)
    (OUT_ROOT / "plan_m8" / "p0_supp.json").write_bytes(bb)
    print(f"{DST.name} {digest} index {index} session {m['session_id']} manifest {e['manifest_sha256']} p0_supp.json {C.sha256_bytes(bb)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
