"""Plan generator — 16 session manifests (block A 0~7 · block N 8~15) + smoke manifests, deterministic bytes.

  py -3 s26/tools/mixreq/mixreq_plan.py --out <plan_dir>
      --cls-model local_models/efficientnet_lite0.tflite --det-model local_inputs/public/efficientdet_lite0.tflite
      --aot-model npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite
      --png local_inputs/canonical_v123/00575b9132bb3746.png --anchors local_inputs/reference_pc/anchors.json
      --cls-labels local_inputs/reference_pc/labels_without_background.txt --det-labels local_inputs/reference_pc/labels.txt
      [--experiment 02|02C|03]   (v3, R4: 02 = v2 plan (byte-identical to plan_v2) · 02C = (C) confirmation, reversed order · 03 = (S) sustained 3,000 · 720 s)

Every pinned SHA is checked against 등록 §1-3 / §1-4 before a manifest is written (mismatch = stop). The plan contains no
timestamps, so two runs give byte-identical files (plan.json + manifests/*.json + smoke/*.json); the SHA-256 of plan.json is
printed and written to plan_sha256.txt. Device paths: models/inputs under /data/local/tmp/mixreq/<basename>.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mixreq_common as C  # noqa: E402
import policy_ref  # noqa: E402

PLAN_SCHEMA = "s26-mixreq-plan-v1"


def runtime_specs(block: str, device: dict) -> list[dict]:
    specs = []
    for key in sorted(policy_ref.BLOCK_KEYS[block]):
        task, lane = key.rsplit("_", 1)
        if lane == "NPU":
            model = device["aot_model"]
        elif task == "classification":
            model = device["cls_model"]
        else:
            model = device["det_model"]
        spec = dict(key=key, task=task, backend=lane, model_path=model["device_path"], model_sha256=model["sha256"])
        if lane == "GPU":
            spec["gpu_precision"] = "FP32"
        if lane == "CPU":
            spec["cpu_threads"] = 1
        specs.append(spec)
    return specs


def manifest(experiment_id: str, split: str, index: int, block: str, policy: str, device: dict, count: int,
             attempt: int = 1, warmup_only: bool = False) -> dict:
    sid = C.session_id(experiment_id, index)
    rows = C.requests(sid, count)
    C.validate_requests(rows, count)
    if policy not in policy_ref.BLOCK_POLICIES[block]:
        raise ValueError(f"policy {policy} not in block {block}")
    if split == "confirmation" and count != C.request_count_of(experiment_id):
        raise ValueError(f"{experiment_id}: confirmation needs {C.request_count_of(experiment_id)} requests")
    m = dict(
        protocol=C.PROTOCOL, experiment_id=experiment_id, split=split, session_id=sid, session_index=index, block=block,
        pair=C.pair_of(block, index), attempt=attempt, policy=policy, runtimes=runtime_specs(block, device),
        image=dict(path=device["png"]["device_path"], sha256=device["png"]["sha256"], width=C.IMAGE_WIDTH, height=C.IMAGE_HEIGHT,
                   rgb_sha256=C.RGB_SHA256, canonical_input_contract="canonical-srgb-png-v2"),
        anchors=dict(path=device["anchors"]["device_path"], sha256=device["anchors"]["sha256"]),
        labels=dict(classification=dict(path=device["cls_labels"]["device_path"], sha256=device["cls_labels"]["sha256"]),
                    detection=dict(path=device["det_labels"]["device_path"], sha256=device["det_labels"]["sha256"])),
        requests=rows, phases=C.phases_of(experiment_id, block), sample_period_ms=C.SAMPLE_PERIOD_MS, time_scale=1, warmup_gate=True,
        stop_rules=dict(C.STOP_RULES), start_check=dict(C.START_CHECK),
        used_keys=list(policy_ref.USED_KEYS[policy]),
        **C.registration_fields(experiment_id),
    )
    if warmup_only:
        m["warmup_only"] = True
    return m


def pinned(path: Path, expected: str, name: str, device_dir: str) -> dict:
    actual = C.sha256_file(path)
    if actual != expected:
        raise SystemExit(f"{name}: SHA-256 {actual} != pinned {expected} ({path}) — stop (등록 §1-3/§1-4)")
    return dict(host_path=str(path), basename=path.name, bytes=path.stat().st_size, sha256=actual,
                device_path=f"{device_dir}/{path.name}")


def build(args) -> dict:
    exp_id = C.EXPERIMENT_BY_ARG[getattr(args, "experiment", "02")]
    smoke_id = C.EXPERIMENTS[exp_id]["smoke_id"]
    count = C.request_count_of(exp_id)
    order = C.session_order_of(exp_id)
    device = dict(
        cls_model=pinned(args.cls_model, C.CLS_MODEL_SHA256, "classification model", C.DEVICE_INPUT_DIR),
        det_model=pinned(args.det_model, C.DET_MODEL_SHA256, "detection model", C.DEVICE_INPUT_DIR),
        aot_model=pinned(args.aot_model, C.AOT_MODEL_SHA256, "classification NPU AOT", C.DEVICE_INPUT_DIR),
        png=pinned(args.png, C.PNG_SHA256, "canonical PNG", C.DEVICE_INPUT_DIR),
        anchors=pinned(args.anchors, C.ANCHORS_SHA256, "anchors.json", C.DEVICE_INPUT_DIR),
        cls_labels=pinned(args.cls_labels, C.CLS_LABEL_SHA256, "classification labels", C.DEVICE_INPUT_DIR),
        det_labels=pinned(args.det_labels, C.DET_LABEL_SHA256, "detection labels", C.DEVICE_INPUT_DIR),
    )
    if device["aot_model"]["basename"] != "efficientnet_lite0_Samsung_E9965.tflite":
        raise SystemExit("AOT model basename must stay efficientnet_lite0_Samsung_E9965.tflite (app checks the _Samsung_E9965 suffix)")
    sessions, smoke = [], []
    for index, (block, policy) in enumerate(order):
        m = manifest(exp_id, "confirmation", index, block, policy, device, count)
        rel = f"manifests/{index:02d}_{m['session_id']}.json"
        sessions.append(dict(index=index, block=block, pair=m["pair"], policy=policy, session_id=m["session_id"], manifest=rel,
                             manifest_sha256=C.sha256_bytes(C.canonical_json(m)), requests=count,
                             warmup=len(policy_ref.BLOCK_KEYS[block]) * C.WARMUPS_PER_KEY,
                             runtime_creations=len(policy_ref.BLOCK_KEYS[block]), _manifest=m))
    s1 = manifest(smoke_id, "diagnostic", C.SMOKE_WARMUP_ONLY_INDEX, "N", policy_ref.POLICY_CPU, device,
                  C.SMOKE_REQUEST_COUNT, warmup_only=True)
    smoke.append(dict(name="S1_warmup_only_blockN", index=C.SMOKE_WARMUP_ONLY_INDEX, block="N", policy=policy_ref.POLICY_CPU,
                      session_id=s1["session_id"], manifest="smoke/S1_warmup_only_blockN.json",
                      manifest_sha256=C.sha256_bytes(C.canonical_json(s1)), requests=0, warmup=10, _manifest=s1))
    for index, block, policy in C.SMOKE_SESSIONS:
        m = manifest(smoke_id, "diagnostic", index, block, policy, device, C.SMOKE_REQUEST_COUNT)
        name = f"S2_{policy}"
        smoke.append(dict(name=name, index=index, block=block, policy=policy, session_id=m["session_id"], manifest=f"smoke/{name}.json",
                          manifest_sha256=C.sha256_bytes(C.canonical_json(m)), requests=C.SMOKE_REQUEST_COUNT,
                          warmup=len(policy_ref.BLOCK_KEYS[block]) * C.WARMUPS_PER_KEY, _manifest=m))
    cls_cpu = sum(count // 2 for b, p in order if p == policy_ref.POLICY_CPU)
    cls_gpu = sum(count // 2 for b, p in order if p == policy_ref.POLICY_PAR)
    cls_npu = sum(count // 2 for b, p in order if p == policy_ref.POLICY_PAR_NPU)
    common_s = C.common_s_of(exp_id)
    budget = dict(sessions=16, requests=16 * count, warmup_block_a=8 * 8, warmup_block_n=8 * 10,
                  calls_block_a=8 * (count + 8), calls_block_n=8 * (count + 10),
                  calls_total=8 * (count + 8) + 8 * (count + 10), retry_cap_sessions=32,
                  retry_cap_calls=2 * (8 * (count + 8) + 8 * (count + 10)),
                  smoke_calls=10 + 3 * C.SMOKE_REQUEST_COUNT + 8 + 8 + 10,
                  per_runtime_requests=dict(classification_CPU=cls_cpu, classification_GPU=cls_gpu, classification_NPU=cls_npu, detection_CPU=16 * (count // 2), detection_GPU=0),
                  fixed_observation_s=16 * (30 + common_s + 30 + 30))
    if exp_id == C.EXPERIMENT_ID:
        assert budget["calls_total"] == 3216 and budget["smoke_calls"] == 108, budget
    reg = C.registration_fields(exp_id)
    reg["registration"] = dict(reg["registration"], time=C.registration_time_of(exp_id))
    reg["registration_v1"] = dict(reg["registration_v1"], time=C.REGISTRATION_V1_TIME)
    if "registration_v2" in reg:
        reg["registration_v2"] = dict(reg["registration_v2"], time=C.REGISTRATION_TIME)
    phases = C.PHASES if common_s == C.COMMON_S else {b: C.phases_of(exp_id, b) for b in ("A", "N")}
    plan = dict(schema=PLAN_SCHEMA, experiment_id=exp_id, protocol=C.PROTOCOL,
                registration_version=C.registration_version(exp_id), step_ms=C.STEP_MS,
                inputs={k: {kk: vv for kk, vv in v.items() if kk != "host_path"} for k, v in device.items()},
                device_input_dir=C.DEVICE_INPUT_DIR, device_session_dir=C.DEVICE_SESSION_DIR, app_package=C.APP_PACKAGE,
                app_output_dir=C.APP_OUTPUT_DIR, phases=phases, sample_period_ms=C.SAMPLE_PERIOD_MS, stop_rules=C.STOP_RULES,
                start_check=C.START_CHECK, budget=budget,
                sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions],
                smoke=[{k: v for k, v in s.items() if k != "_manifest"} for s in smoke], **reg)
    if C.registration_version(exp_id) >= 3:   # v3-only keys (the v2 plan stays byte-identical to plan_v2)
        plan.update(request_count=count, common_s=common_s, experiment_kind=C.experiment_kind(exp_id),
                    execution_order=list(C.EXECUTION_ORDER_C if C.experiment_kind(exp_id) == "confirm" else C.EXECUTION_ORDER_S),
                    smoke_experiment_id=smoke_id)
    return dict(plan=plan, sessions=sessions, smoke=smoke, device=device)


def write(out: Path, built: dict) -> str:
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifests").mkdir(exist_ok=True)
    (out / "smoke").mkdir(exist_ok=True)
    for s in built["sessions"] + built["smoke"]:
        (out / s["manifest"]).write_bytes(C.canonical_json(s["_manifest"]))
    plan_bytes = C.canonical_json(built["plan"])
    (out / "plan.json").write_bytes(plan_bytes)
    digest = C.sha256_bytes(plan_bytes)
    (out / "plan_sha256.txt").write_text(digest + "\n", encoding="utf-8")
    # host copy list for mixreq_session.py (host path -> device path)
    (out / "device_inputs.json").write_bytes(C.canonical_json(
        {k: dict(host_path=v["host_path"], device_path=v["device_path"], sha256=v["sha256"], bytes=v["bytes"]) for k, v in built["device"].items()}))
    return digest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    for name in ("cls-model", "det-model", "aot-model", "png", "anchors", "cls-labels", "det-labels"):
        ap.add_argument("--" + name, required=True, type=Path)
    ap.add_argument("--experiment", choices=sorted(C.EXPERIMENT_BY_ARG), default="02", help="v3: 02 (v2 plan) · 02C ((C) confirmation) · 03 ((S) sustained)")
    args = ap.parse_args()
    built = build(args)
    digest = write(args.out, built)
    print(f"plan {args.out / 'plan.json'} sha256 {digest} sessions {len(built['sessions'])} smoke {len(built['smoke'])} "
          f"calls_total {built['plan']['budget']['calls_total']} smoke_calls {built['plan']['budget']['smoke_calls']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
