"""Plan generator — 16 session manifests (block A 0~7 · block N 8~15) + smoke manifests, deterministic bytes.

  py -3 s26/tools/mixreq/mixreq_plan.py --out <plan_dir>
      --cls-model local_models/efficientnet_lite0.tflite --det-model local_inputs/public/efficientdet_lite0.tflite
      --aot-model npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite
      --png local_inputs/canonical_v123/00575b9132bb3746.png --anchors local_inputs/reference_pc/anchors.json
      --cls-labels local_inputs/reference_pc/labels_without_background.txt --det-labels local_inputs/reference_pc/labels.txt

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
    m = dict(
        protocol=C.PROTOCOL, experiment_id=experiment_id, split=split, session_id=sid, session_index=index, block=block,
        pair=C.pair_of(block, index), attempt=attempt, policy=policy, runtimes=runtime_specs(block, device),
        image=dict(path=device["png"]["device_path"], sha256=device["png"]["sha256"], width=C.IMAGE_WIDTH, height=C.IMAGE_HEIGHT,
                   rgb_sha256=C.RGB_SHA256, canonical_input_contract="canonical-srgb-png-v2"),
        anchors=dict(path=device["anchors"]["device_path"], sha256=device["anchors"]["sha256"]),
        labels=dict(classification=dict(path=device["cls_labels"]["device_path"], sha256=device["cls_labels"]["sha256"]),
                    detection=dict(path=device["det_labels"]["device_path"], sha256=device["det_labels"]["sha256"])),
        requests=rows, phases=dict(C.PHASES[block]), sample_period_ms=C.SAMPLE_PERIOD_MS, time_scale=1, warmup_gate=True,
        stop_rules=dict(C.STOP_RULES), start_check=dict(C.START_CHECK),
        registration=dict(file=C.REGISTRATION_FILE, sha256=C.REGISTRATION_SHA256, commit=C.REGISTRATION_COMMIT),
        registration_v1=dict(file=C.REGISTRATION_V1_FILE, sha256=C.REGISTRATION_V1_SHA256, commit=C.REGISTRATION_V1_COMMIT),
        used_keys=list(policy_ref.USED_KEYS[policy]),
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
    for index, (block, policy) in enumerate(C.SESSION_ORDER):
        m = manifest(C.EXPERIMENT_ID, "confirmation", index, block, policy, device, C.REQUEST_COUNT)
        rel = f"manifests/{index:02d}_{m['session_id']}.json"
        sessions.append(dict(index=index, block=block, pair=m["pair"], policy=policy, session_id=m["session_id"], manifest=rel,
                             manifest_sha256=C.sha256_bytes(C.canonical_json(m)), requests=C.REQUEST_COUNT,
                             warmup=len(policy_ref.BLOCK_KEYS[block]) * C.WARMUPS_PER_KEY,
                             runtime_creations=len(policy_ref.BLOCK_KEYS[block]), _manifest=m))
    s1 = manifest(C.SMOKE_EXPERIMENT_ID, "diagnostic", C.SMOKE_WARMUP_ONLY_INDEX, "N", policy_ref.POLICY_CPU, device,
                  C.SMOKE_REQUEST_COUNT, warmup_only=True)
    smoke.append(dict(name="S1_warmup_only_blockN", index=C.SMOKE_WARMUP_ONLY_INDEX, block="N", policy=policy_ref.POLICY_CPU,
                      session_id=s1["session_id"], manifest="smoke/S1_warmup_only_blockN.json",
                      manifest_sha256=C.sha256_bytes(C.canonical_json(s1)), requests=0, warmup=10, _manifest=s1))
    for index, block, policy in C.SMOKE_SESSIONS:
        m = manifest(C.SMOKE_EXPERIMENT_ID, "diagnostic", index, block, policy, device, C.SMOKE_REQUEST_COUNT)
        name = f"S2_{policy}"
        smoke.append(dict(name=name, index=index, block=block, policy=policy, session_id=m["session_id"], manifest=f"smoke/{name}.json",
                          manifest_sha256=C.sha256_bytes(C.canonical_json(m)), requests=C.SMOKE_REQUEST_COUNT,
                          warmup=len(policy_ref.BLOCK_KEYS[block]) * C.WARMUPS_PER_KEY, _manifest=m))
    budget = dict(sessions=16, requests=16 * C.REQUEST_COUNT, warmup_block_a=8 * 8, warmup_block_n=8 * 10,
                  calls_block_a=8 * (C.REQUEST_COUNT + 8), calls_block_n=8 * (C.REQUEST_COUNT + 10),
                  calls_total=8 * (C.REQUEST_COUNT + 8) + 8 * (C.REQUEST_COUNT + 10), retry_cap_sessions=32,
                  retry_cap_calls=2 * (8 * (C.REQUEST_COUNT + 8) + 8 * (C.REQUEST_COUNT + 10)),
                  smoke_calls=10 + 3 * C.SMOKE_REQUEST_COUNT + 8 + 8 + 10,
                  per_runtime_requests=dict(classification_CPU=768, classification_GPU=384, classification_NPU=384, detection_CPU=1536, detection_GPU=0),
                  fixed_observation_s=16 * 210)
    assert budget["calls_total"] == 3216 and budget["smoke_calls"] == 108, budget
    plan = dict(schema=PLAN_SCHEMA, experiment_id=C.EXPERIMENT_ID, protocol=C.PROTOCOL,
                registration=dict(file=C.REGISTRATION_FILE, sha256=C.REGISTRATION_SHA256, commit=C.REGISTRATION_COMMIT,
                                  time=C.REGISTRATION_TIME),
                registration_v1=dict(file=C.REGISTRATION_V1_FILE, sha256=C.REGISTRATION_V1_SHA256, commit=C.REGISTRATION_V1_COMMIT,
                                     time=C.REGISTRATION_V1_TIME),
                registration_version=C.registration_version(C.EXPERIMENT_ID), step_ms=C.STEP_MS,
                inputs={k: {kk: vv for kk, vv in v.items() if kk != "host_path"} for k, v in device.items()},
                device_input_dir=C.DEVICE_INPUT_DIR, device_session_dir=C.DEVICE_SESSION_DIR, app_package=C.APP_PACKAGE,
                app_output_dir=C.APP_OUTPUT_DIR, phases=C.PHASES, sample_period_ms=C.SAMPLE_PERIOD_MS, stop_rules=C.STOP_RULES,
                start_check=C.START_CHECK, budget=budget,
                sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions],
                smoke=[{k: v for k, v in s.items() if k != "_manifest"} for s in smoke])
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
    args = ap.parse_args()
    built = build(args)
    digest = write(args.out, built)
    print(f"plan {args.out / 'plan.json'} sha256 {digest} sessions {len(built['sessions'])} smoke {len(built['smoke'])} "
          f"calls_total {built['plan']['budget']['calls_total']} smoke_calls {built['plan']['budget']['smoke_calls']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
