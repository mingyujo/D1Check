"""M5 plan generator (2026-10-12) — deterministic bytes, no timestamps. mixreq_plan.py is NOT modified; its runtime_specs / pinned are imported.

  py -3 -X utf8 s26/tools/mixreq/statesplit_plan.py statesplit --out s26/results/statesplit_1012/plan_v4ss
      --cls-model local_models/efficientnet_lite0.tflite --det-model local_inputs/public/efficientdet_lite0.tflite
      --aot-model npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite
      --png local_inputs/canonical_v123/00575b9132bb3746.png --anchors local_inputs/reference_pc/anchors.json
      --cls-labels local_inputs/reference_pc/labels_without_background.txt --det-labels local_inputs/reference_pc/labels.txt
  py -3 -X utf8 s26/tools/mixreq/statesplit_plan.py abba --out s26/results/statesplit_1012/plan_abba
      --source s26/results/mixreq_1008/plan_v3s

statesplit (등록 상태분리 v2 §1): 12 session manifests in the registered order (index 0..11 = block 1 C·G·N · block 2 N·G·C · block 3 C·G·N ·
  block 4 N·G·C) + 1 smoke manifest (C, full 522 requests, time_scale 1, split diagnostic). Every manifest key except the request table, the
  ids and the registration dict is built exactly like mixreq_plan.manifest (anchors · image · labels · phases · runtimes · start_check ·
  stop_rules · used_keys · warmup_gate · sample_period_ms · time_scale). Session manifests keep split "confirmation" (the app's word for a
  real session: time_scale 1 · full request count) and carry the registered analysis split in analysis_split ("dev" | "confirm") +
  statesplit_block (1..4) · statesplit_letter (C/G/N); pair = block − 1.
abba (등록 지속감속 확인 v1 §1): the plan_v3s block-A manifests of CPU_URGENT_ONLINE_V1 (index 0) and B2_PARALLEL_ONLINE_V1 (index 1) are
  copied; ONLY experiment_id · session_id · session_index · pair · requests[].request_id change (request table · phases · deadlines ·
  common 720 s identical). The changed-key list is written into plan.json and checked here (any other difference = stop).
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_plan as P  # noqa: E402
import policy_ref  # noqa: E402
import statesplit_common as S  # noqa: E402

PLAN_SCHEMA = "s26-statesplit-plan-v1"
ABBA_PLAN_SCHEMA = "s26-sustain-abba-plan-v1"
ABBA_CHANGED_KEYS = ["experiment_id", "session_id", "session_index", "pair", "requests[].request_id"]


def ss_manifest(experiment_id: str, split: str, index: int, letter: str, device: dict, block_no: int | None, analysis_split: str | None) -> dict:
    block, policy = S.LETTER_BLOCK[letter], S.LETTER_POLICY[letter]
    if policy not in policy_ref.BLOCK_POLICIES[block]:
        raise ValueError(f"policy {policy} not in block {block}")
    sid = S.session_id(experiment_id, index)
    m = dict(
        protocol=C.PROTOCOL, experiment_id=experiment_id, split=split, session_id=sid, session_index=index, block=block,
        pair=(block_no - 1) if block_no else 0, attempt=1, policy=policy, runtimes=P.runtime_specs(block, device),
        image=dict(path=device["png"]["device_path"], sha256=device["png"]["sha256"], width=C.IMAGE_WIDTH, height=C.IMAGE_HEIGHT,
                   rgb_sha256=C.RGB_SHA256, canonical_input_contract="canonical-srgb-png-v2"),
        anchors=dict(path=device["anchors"]["device_path"], sha256=device["anchors"]["sha256"]),
        labels=dict(classification=dict(path=device["cls_labels"]["device_path"], sha256=device["cls_labels"]["sha256"]),
                    detection=dict(path=device["det_labels"]["device_path"], sha256=device["det_labels"]["sha256"])),
        requests=S.requests(sid), phases=C.phases_of(experiment_id, block), sample_period_ms=C.SAMPLE_PERIOD_MS, time_scale=1, warmup_gate=True,
        stop_rules=dict(C.STOP_RULES), start_check=dict(C.START_CHECK), used_keys=list(policy_ref.USED_KEYS[policy]),
        registration={k: v for k, v in S.REGISTRATION_SS.items() if k != "time"},
        statesplit_letter=letter,
    )
    if block_no is not None:
        m.update(analysis_split=analysis_split, statesplit_block=block_no)
    return m


def build_statesplit(args) -> dict:
    device = dict(
        cls_model=P.pinned(args.cls_model, C.CLS_MODEL_SHA256, "classification model", C.DEVICE_INPUT_DIR),
        det_model=P.pinned(args.det_model, C.DET_MODEL_SHA256, "detection model", C.DEVICE_INPUT_DIR),
        aot_model=P.pinned(args.aot_model, C.AOT_MODEL_SHA256, "classification NPU AOT", C.DEVICE_INPUT_DIR),
        png=P.pinned(args.png, C.PNG_SHA256, "canonical PNG", C.DEVICE_INPUT_DIR),
        anchors=P.pinned(args.anchors, C.ANCHORS_SHA256, "anchors.json", C.DEVICE_INPUT_DIR),
        cls_labels=P.pinned(args.cls_labels, C.CLS_LABEL_SHA256, "classification labels", C.DEVICE_INPUT_DIR),
        det_labels=P.pinned(args.det_labels, C.DET_LABEL_SHA256, "detection labels", C.DEVICE_INPUT_DIR),
    )
    sessions = []
    for index, (block_no, split, letter) in enumerate(S.SESSION_ORDER):
        m = ss_manifest(S.STATESPLIT_ID, "confirmation", index, letter, device, block_no, split)
        rel = f"manifests/{index:02d}_{m['session_id']}.json"
        sessions.append(dict(index=index, statesplit_block=block_no, analysis_split=split, letter=letter, block=m["block"], pair=m["pair"],
                             policy=m["policy"], session_id=m["session_id"], manifest=rel, manifest_sha256=C.sha256_bytes(C.canonical_json(m)),
                             requests=S.REQUEST_COUNT, _manifest=m))
    sm = ss_manifest(S.STATESPLIT_SMOKE_ID, "diagnostic", 0, "C", device, None, None)
    smoke = [dict(name="SS_smoke_C", index=0, block=sm["block"], policy=sm["policy"], session_id=sm["session_id"], manifest="smoke/SS_smoke_C.json",
                  manifest_sha256=C.sha256_bytes(C.canonical_json(sm)), requests=S.REQUEST_COUNT, _manifest=sm)]
    per_policy = {p: sum(1 for s in sessions if s["policy"] == p) for p in policy_ref.POLICIES}
    assert per_policy == {policy_ref.POLICY_CPU: 4, policy_ref.POLICY_PAR: 4, policy_ref.POLICY_PAR_NPU: 4}, per_policy
    plan = dict(schema=PLAN_SCHEMA, experiment_id=S.STATESPLIT_ID, protocol=C.PROTOCOL, registration=S.REGISTRATION_SS,
                inputs={k: {kk: vv for kk, vv in v.items() if kk != "host_path"} for k, v in device.items()},
                device_input_dir=C.DEVICE_INPUT_DIR, device_session_dir=C.DEVICE_SESSION_DIR, app_package=C.APP_PACKAGE, app_output_dir=C.APP_OUTPUT_DIR,
                phases={b: C.phases_of(S.STATESPLIT_ID, b) for b in ("A", "N")}, sample_period_ms=C.SAMPLE_PERIOD_MS, stop_rules=C.STOP_RULES,
                start_check=C.START_CHECK, request_count=S.REQUEST_COUNT, segments=list(S.SEGMENTS), segment_windows_s=S.SEGMENT_WINDOWS_S,
                validation_window_s=list(S.WINDOW_S), block_order=[dict(block=b, analysis_split=s, letters=l) for b, s, l in S.BLOCK_ORDER],
                execution_order=list(range(len(sessions))), smoke_experiment_id=S.STATESPLIT_SMOKE_ID,
                sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions],
                smoke=[{k: v for k, v in s.items() if k != "_manifest"} for s in smoke],
                notes=["split = confirmation (app: real session) · analysis_split = 등록 dev / confirm",
                       "S4 쉼 (공통창 시각 125 ~ 155 s) = drain 30 s + 냉각 앞 5 s — 요청 없음",
                       "registration = 상태분리_사전등록_v2.md (v1 e789b97c… 쓰지 않음)"])
    return dict(plan=plan, sessions=sessions, smoke=smoke, device=device)


def build_abba(args) -> dict:
    src = Path(args.source)
    src_plan = C.read_json(src / "plan.json")
    if src_plan["experiment_id"] != "S26-MIXREQ-03":
        raise SystemExit(f"source plan {src} is not the (S) plan_v3s")
    by_policy = {}
    for s in sorted(src_plan["sessions"], key=lambda s: s["index"]):
        if s["block"] == "A":
            by_policy.setdefault(s["policy"], s)
    sources = {letter: by_policy[pol] for letter, pol in S.ABBA_POLICY.items()}
    sessions = []
    for index, letter in enumerate(S.ABBA_ORDER):
        entry = sources[letter]
        original = C.read_json(src / entry["manifest"])
        if C.sha256_bytes(C.canonical_json(original)) != entry["manifest_sha256"]:
            raise SystemExit(f"source manifest {entry['manifest']} SHA != plan_v3s record")
        m = copy.deepcopy(original)
        sid = S.session_id(S.ABBA_ID, index)
        m.update(experiment_id=S.ABBA_ID, session_id=sid, session_index=index, pair=index // 2)
        for q in m["requests"]:
            q["request_id"] = C.request_id(sid, q["ordinal"])
        C.validate_requests(m["requests"], 3000)
        # the only differences vs the source manifest are the listed keys
        a, b = copy.deepcopy(original), copy.deepcopy(m)
        for d in (a, b):
            for k in ("experiment_id", "session_id", "session_index", "pair"):
                d.pop(k)
            for q in d["requests"]:
                q.pop("request_id")
        if a != b:
            raise SystemExit("ABBA manifest differs from the source beyond the changed keys — stop")
        changed = sorted(k for k in ("experiment_id", "session_id", "session_index", "pair") if original[k] != m[k])
        rel = f"manifests/{index:02d}_{letter}_{sid}.json"
        sessions.append(dict(index=index, letter=letter, block=m["block"], pair=m["pair"], policy=m["policy"], session_id=sid, manifest=rel,
                             manifest_sha256=C.sha256_bytes(C.canonical_json(m)), requests=3000,
                             source=dict(plan="s26/results/mixreq_1008/plan_v3s", manifest=entry["manifest"], manifest_sha256=entry["manifest_sha256"],
                                         index=entry["index"]),
                             changed_keys=changed + ["requests[].request_id"], _manifest=m))
    plan = dict(schema=ABBA_PLAN_SCHEMA, experiment_id=S.ABBA_ID, protocol=C.PROTOCOL, registration=S.REGISTRATION_ABBA,
                session_form_registration=src_plan["registration"], frozen_model=S.FROZEN_SUSTAIN_MODEL,
                source_plan=dict(path="s26/results/mixreq_1008/plan_v3s/plan.json", sha256=C.sha256_file(src / "plan.json")),
                changed_keys=ABBA_CHANGED_KEYS, order=list(S.ABBA_ORDER), inputs=src_plan["inputs"], device_input_dir=C.DEVICE_INPUT_DIR,
                device_session_dir=C.DEVICE_SESSION_DIR, app_package=C.APP_PACKAGE, app_output_dir=C.APP_OUTPUT_DIR,
                phases={"A": C.phases_of(S.ABBA_ID, "A")}, request_count=3000, common_s=720, execution_order=[0, 1, 2, 3],
                sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions], smoke=[],
                notes=["registration (inside the manifests) = 혼합요청 v3 (session form, unchanged) · confirmation registration = plan.registration",
                       "판정기 = d1sim/sustain_v1/fit.py judge (Cowork) — 이 세션은 readout 까지"])
    device = C.read_json(src / "device_inputs.json")
    if args.device_inputs:   # host paths of this clone (same files: SHA · device path must equal the source's)
        mine = C.read_json(args.device_inputs)
        if {k: (v["sha256"], v["device_path"]) for k, v in mine.items()} != {k: (v["sha256"], v["device_path"]) for k, v in device.items()}:
            raise SystemExit("--device-inputs differ from plan_v3s device inputs (SHA / device path) — stop")
        device = mine
    return dict(plan=plan, sessions=sessions, smoke=[], device_inputs=device)


def write(out: Path, built: dict) -> str:
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifests").mkdir(exist_ok=True)
    if built["smoke"]:
        (out / "smoke").mkdir(exist_ok=True)
    for s in built["sessions"] + built["smoke"]:
        (out / s["manifest"]).write_bytes(C.canonical_json(s["_manifest"]))
    plan_bytes = C.canonical_json(built["plan"])
    (out / "plan.json").write_bytes(plan_bytes)
    digest = C.sha256_bytes(plan_bytes)
    (out / "plan_sha256.txt").write_text(digest + "\n", encoding="utf-8")
    if "device" in built:
        dev = {k: dict(host_path=v["host_path"], device_path=v["device_path"], sha256=v["sha256"], bytes=v["bytes"]) for k, v in built["device"].items()}
    else:
        dev = built["device_inputs"]
    (out / "device_inputs.json").write_bytes(C.canonical_json(dev))
    return digest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="kind", required=True)
    a = sub.add_parser("statesplit")
    a.add_argument("--out", required=True, type=Path)
    for name in ("cls-model", "det-model", "aot-model", "png", "anchors", "cls-labels", "det-labels"):
        a.add_argument("--" + name, required=True, type=Path)
    b = sub.add_parser("abba")
    b.add_argument("--out", required=True, type=Path)
    b.add_argument("--source", required=True, type=Path)
    b.add_argument("--device-inputs", type=Path, help="device_inputs.json of plan_v4ss (this clone's host paths)")
    args = ap.parse_args()
    built = build_statesplit(args) if args.kind == "statesplit" else build_abba(args)
    digest = write(args.out, built)
    print(f"plan {args.out / 'plan.json'} sha256 {digest} sessions {len(built['sessions'])} smoke {len(built['smoke'])}")
    for s in built["sessions"] + built["smoke"]:
        print(f"  {s['manifest']} {s['manifest_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
