"""M6 plan generator (2026-10-12) — deterministic bytes, no timestamps. mixreq_plan.py · statesplit_plan.py are NOT modified (imported).

  py -3 -X utf8 s26/tools/mixreq/m6_plan.py --out-root s26/results/m6_1012
      --cls-model local_models/efficientnet_lite0.tflite --det-model local_inputs/public/efficientdet_lite0.tflite
      --aot-model npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite
      --png local_inputs/canonical_v123/00575b9132bb3746.png --anchors local_inputs/reference_pc/anchors.json
      --cls-labels local_inputs/reference_pc/labels_without_background.txt --det-labels local_inputs/reference_pc/labels.txt

Writes three plan folders under --out-root (등록 M6 v3):
  plan_m6p/  P 12 session manifests (index 0..11 = 등록 §3-5 order: 개발 D L-C · B-G · L-N · B-C · L-G · B-N / 확인 K B-N · L-G · B-C · L-N ·
             B-G · L-C) + smoke (S26-M6-P-SMOKE index 3 = B-C · 100 requests · time_scale 1 · split diagnostic) + projection.json
             (per load: SHA-256 of the five columns ordinal · task · priority · offset · deadline for the three rules — must be equal)
  plan_m6k/  K 4 session manifests (S26-M6-K index 0..3 · requests 0 · common 780 s · policy label CPU_URGENT_ONLINE_V1) + smoke
             (S26-M6-K-SMOKE index 0 · time_scale 10 · diagnostic)
  plan_m6e/  GaugeDiagActivity configs E1 · E2 · E3 · ET (S26-M6-E · 60/120/120 s · 20 ms) + E_smoke (S26-M6-E-SMOKE · 6/12/12 s)
Every session manifest key except the request table, the ids and the M6 labels is built exactly like statesplit_plan.ss_manifest
(= mixreq_plan.manifest): block M (5 resident keys) for all three rules. Session manifests keep split "confirmation" (app: a real
session) + analysis_split "dev" | "confirm" · m6_load · m6_letter; pair = 0 (dev) / 1 (confirm). Execution order (등록 §3-5 · §4-3):
M6-A = K0 · K1 → P0..P5 · M6-B = P6..P11 → K2 · K3 (plan_m6p/plan.json "execution").
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_plan as P  # noqa: E402
import policy_ref  # noqa: E402
import m6_common as M  # noqa: E402

PLAN_SCHEMA = "s26-m6-plan-v1"
GAUGE_SCHEMA = "s26-m6-gauge-plan-v1"


def device_inputs(args) -> dict:
    return dict(
        cls_model=P.pinned(args.cls_model, C.CLS_MODEL_SHA256, "classification model", C.DEVICE_INPUT_DIR),
        det_model=P.pinned(args.det_model, C.DET_MODEL_SHA256, "detection model", C.DEVICE_INPUT_DIR),
        aot_model=P.pinned(args.aot_model, C.AOT_MODEL_SHA256, "classification NPU AOT", C.DEVICE_INPUT_DIR),
        png=P.pinned(args.png, C.PNG_SHA256, "canonical PNG", C.DEVICE_INPUT_DIR),
        anchors=P.pinned(args.anchors, C.ANCHORS_SHA256, "anchors.json", C.DEVICE_INPUT_DIR),
        cls_labels=P.pinned(args.cls_labels, C.CLS_LABEL_SHA256, "classification labels", C.DEVICE_INPUT_DIR),
        det_labels=P.pinned(args.det_labels, C.DET_LABEL_SHA256, "detection labels", C.DEVICE_INPUT_DIR),
    )


def manifest(experiment_id: str, split: str, index: int, policy: str, device: dict, time_scale: int, labels: dict) -> dict:
    if policy not in policy_ref.BLOCK_POLICIES[M.BLOCK]:
        raise ValueError(f"policy {policy} not in block {M.BLOCK}")
    sid = M.session_id(experiment_id, index)
    m = dict(
        protocol=C.PROTOCOL, experiment_id=experiment_id, split=split, session_id=sid, session_index=index, block=M.BLOCK,
        pair=1 if labels.get("analysis_split") == "confirm" else 0, attempt=1, policy=policy, runtimes=P.runtime_specs(M.BLOCK, device),
        image=dict(path=device["png"]["device_path"], sha256=device["png"]["sha256"], width=C.IMAGE_WIDTH, height=C.IMAGE_HEIGHT,
                   rgb_sha256=C.RGB_SHA256, canonical_input_contract="canonical-srgb-png-v2"),
        anchors=dict(path=device["anchors"]["device_path"], sha256=device["anchors"]["sha256"]),
        labels=dict(classification=dict(path=device["cls_labels"]["device_path"], sha256=device["cls_labels"]["sha256"]),
                    detection=dict(path=device["det_labels"]["device_path"], sha256=device["det_labels"]["sha256"])),
        requests=M.requests(experiment_id, index, sid), phases=C.phases_of(experiment_id, M.BLOCK), sample_period_ms=C.SAMPLE_PERIOD_MS,
        time_scale=time_scale, warmup_gate=True, stop_rules=dict(C.STOP_RULES), start_check=dict(C.START_CHECK),
        used_keys=list(policy_ref.USED_KEYS[policy]), registration={k: v for k, v in M.REGISTRATION.items() if k != "time"},
    )
    m.update(labels)
    return m


def entry(m: dict, rel: str, **extra) -> dict:
    return dict(index=m["session_index"], policy=m["policy"], block=m["block"], pair=m["pair"], session_id=m["session_id"], manifest=rel,
                manifest_sha256=C.sha256_bytes(C.canonical_json(m)), requests=len(m["requests"]), _manifest=m, **extra)


def build_p(device: dict) -> dict:
    sessions = []
    for index in range(len(M.P_ORDER)):
        split = "dev" if index in M.P_DEV else "confirm"
        load, letter = M.load_of(index), M.letter_of(index)
        m = manifest(M.P_ID, "confirmation", index, M.policy_of(index), device, 1, dict(analysis_split=split, m6_load=load, m6_letter=letter))
        rel = f"manifests/{index:02d}_{load}-{letter}_{m['session_id']}.json"
        sessions.append(entry(m, rel, analysis_split=split, load=load, letter=letter,
                              projection_sha256=M.projection_sha256(m["requests"])))
    sm = manifest(M.P_SMOKE_ID, "diagnostic", M.P_SMOKE_INDEX, M.policy_of(M.P_SMOKE_INDEX), device, 1,
                  dict(m6_load=M.load_of(M.P_SMOKE_INDEX), m6_letter=M.letter_of(M.P_SMOKE_INDEX), smoke=True))
    smoke = [entry(sm, "smoke/P_smoke_B-C.json", name="P_smoke_B-C", load="B", letter="C", projection_sha256=M.projection_sha256(sm["requests"]))]
    # 등록 §3-2: same load → the three rules have the same five columns (SHA per load must be one value)
    projection = {}
    for load in ("L", "B"):
        shas = {s["letter"]: s["projection_sha256"] for s in sessions if s["load"] == load and s["analysis_split"] == "dev"}
        shas_conf = {s["letter"]: s["projection_sha256"] for s in sessions if s["load"] == load and s["analysis_split"] == "confirm"}
        values = set(shas.values()) | set(shas_conf.values()) | {M.projection_sha256(M.load_requests(M.session_id(M.P_ID, 0), load))}
        projection[load] = dict(dev=shas, confirm=shas_conf, equal=len(values) == 1, sha256=sorted(values)[0] if len(values) == 1 else sorted(values),
                                fields=list(M.PROJECTION_FIELDS), rows=M.REQUEST_COUNT)
        if len(values) != 1:
            raise SystemExit(f"projection SHA differs within load {load}: {values} — stop")
    per_policy = {p: sum(1 for s in sessions if s["policy"] == p) for p in policy_ref.POLICIES}
    assert per_policy == {policy_ref.POLICY_CPU: 4, policy_ref.POLICY_PAR: 4, policy_ref.POLICY_PAR_NPU: 4}, per_policy
    plan = dict(schema=PLAN_SCHEMA, experiment_id=M.P_ID, protocol=C.PROTOCOL, registration=M.REGISTRATION, block=M.BLOCK,
                inputs={k: {kk: vv for kk, vv in v.items() if kk != "host_path"} for k, v in device.items()},
                device_input_dir=C.DEVICE_INPUT_DIR, device_session_dir=C.DEVICE_SESSION_DIR, app_package=C.APP_PACKAGE, app_output_dir=C.APP_OUTPUT_DIR,
                phases={M.BLOCK: C.phases_of(M.P_ID, M.BLOCK)}, sample_period_ms=C.SAMPLE_PERIOD_MS, stop_rules=C.STOP_RULES, start_check=C.START_CHECK,
                request_count=M.REQUEST_COUNT, order=list(M.P_ORDER), dev=list(M.P_DEV), confirm=list(M.P_CONFIRM),
                loads=dict(L="i = 0..99 · 35,000 + 400·i ms · 짝 = 분류 urgent 1,500 · 홀 = 탐지 normal 6,000",
                           B="k, j = 0..9 · i = 10k + j · 35,000 + 4,000·k + 50·j ms · j 짝 = 분류 · 홀 = 탐지"),
                projection=projection, v2_bound_s=M.V2_BOUND_S, soc_band=[M.SOC_MIN, M.SOC_MAX],
                execution=dict(m6a=[f"K{i}" for i in M.K_DEV] + [f"P{i}" for i in M.P_DEV], m6b=[f"P{i}" for i in M.P_CONFIRM] + [f"K{i}" for i in M.K_CONFIRM],
                               note="K = plan_m6k index · P = plan_m6p index (등록 §3-5 · §4-3). M6-B 는 조민규 동결 SHA 뒤"),
                execution_order=list(M.P_DEV), smoke_experiment_id=M.P_SMOKE_ID,
                sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions],
                smoke=[{k: v for k, v in s.items() if k != "_manifest"} for s in smoke],
                notes=["split = confirmation (app: real session) · analysis_split = 등록 개발 dev / 확인 confirm",
                       "block M = classification_CPU/GPU/NPU · detection_CPU/GPU 상주 (세 규칙 같음)",
                       "registration = M6_동일APK_사전등록_v3.md (v1 74e7d583… · v2 c376554f… 쓰지 않음)"])
    return dict(plan=plan, sessions=sessions, smoke=smoke, device=device)


def build_k(device: dict) -> dict:
    sessions = []
    for index in range(4):
        split = "dev" if index in M.K_DEV else "confirm"
        m = manifest(M.K_ID, "confirmation", index, policy_ref.POLICY_CPU, device, 1, dict(analysis_split=split, m6_run=f"K{index + 1}"))
        sessions.append(entry(m, f"manifests/{index:02d}_K{index + 1}_{m['session_id']}.json", analysis_split=split, letter=f"K{index + 1}"))
    sm = manifest(M.K_SMOKE_ID, "diagnostic", M.K_SMOKE_INDEX, policy_ref.POLICY_CPU, device, M.K_SMOKE_TIME_SCALE, dict(m6_run="K_smoke", smoke=True))
    smoke = [entry(sm, "smoke/K_smoke.json", name="K_smoke", letter="K_smoke")]
    plan = dict(schema=PLAN_SCHEMA, experiment_id=M.K_ID, protocol=C.PROTOCOL, registration=M.REGISTRATION, block=M.BLOCK,
                inputs={k: {kk: vv for kk, vv in v.items() if kk != "host_path"} for k, v in device.items()},
                device_input_dir=C.DEVICE_INPUT_DIR, device_session_dir=C.DEVICE_SESSION_DIR, app_package=C.APP_PACKAGE, app_output_dir=C.APP_OUTPUT_DIR,
                phases={M.BLOCK: C.phases_of(M.K_ID, M.BLOCK)}, sample_period_ms=C.SAMPLE_PERIOD_MS, stop_rules=C.STOP_RULES, start_check=C.START_CHECK,
                request_count=0, common_s=780, windows_s=M.K_WINDOWS_S, dev=list(M.K_DEV), confirm=list(M.K_CONFIRM), soc_band=[M.SOC_MIN, M.SOC_MAX],
                execution_order=list(M.K_DEV), smoke_experiment_id=M.K_SMOKE_ID, smoke_time_scale=M.K_SMOKE_TIME_SCALE,
                sessions=[{k: v for k, v in s.items() if k != "_manifest"} for s in sessions],
                smoke=[{k: v for k, v in s.items() if k != "_manifest"} for s in smoke],
                notes=["요청 0 · 공통창 780 s · 엔진 무변경 (창 길이만 실험 표 행) · 정책 표기 CPU_URGENT_ONLINE_V1 (실행 경로 없음)",
                       "W = [0, 180) s · S = [600, 780) s (등록 §4-2, 계산은 Cowork)", "K1 · K2 = 개발 (P 개발 전) · K3 · K4 = 확인 (P 확인 뒤)"])
    return dict(plan=plan, sessions=sessions, smoke=smoke, device=device)


def gauge_config(experiment_id: str, run_id: str, device: dict, segments: dict) -> dict:
    return dict(schema="s26-m6-gauge-config-v1", experiment_id=experiment_id, run_id=run_id, **segments, poll_target_ms=M.E_POLL_TARGET_MS,
                model=dict(path=device["cls_model"]["device_path"], sha256=device["cls_model"]["sha256"]),
                image=dict(path=device["png"]["device_path"], sha256=device["png"]["sha256"]),
                labels=dict(path=device["cls_labels"]["device_path"], sha256=device["cls_labels"]["sha256"]),
                registration={k: v for k, v in M.REGISTRATION.items() if k != "time"})


def build_e(device: dict) -> dict:
    runs = [dict(run_id=r, config=f"configs/{r}.json", _config=gauge_config(M.E_ID, r, device, M.E_SEGMENTS_MS)) for r in M.E_RUNS]
    smoke = [dict(run_id="E_smoke", config="configs/E_smoke.json", _config=gauge_config(M.E_SMOKE_ID, "E_smoke", device, M.E_SMOKE_SEGMENTS_MS))]
    for r in runs + smoke:
        r["config_sha256"] = C.sha256_bytes(C.canonical_json(r["_config"]))
    plan = dict(schema=GAUGE_SCHEMA, experiment_id=M.E_ID, registration=M.REGISTRATION, activity=f"{C.APP_PACKAGE}/.GaugeDiagActivity",
                device_config_dir=f"{C.DEVICE_INPUT_DIR}/gauge", app_output_dir=f"/storage/emulated/0/Android/data/{C.APP_PACKAGE}/files/gauge",
                segments_ms=M.E_SEGMENTS_MS, poll_target_ms=M.E_POLL_TARGET_MS, order=list(M.E_RUNS),
                et_device_loop="while true; do cat /proc/uptime; dumpsys thermalservice | sed -n '/Current temperatures from HAL/,/Current cooling devices/p'; "
                               "for z in /sys/class/thermal/thermal_zone*; do echo $z $(cat $z/type 2>&1) $(cat $z/temp 2>&1); done; done",
                inputs={k: {kk: vv for kk, vv in v.items() if kk != "host_path"} for k, v in device.items() if k in ("cls_model", "png", "cls_labels")},
                runs=[{k: v for k, v in r.items() if k != "_config"} for r in runs], smoke=[{k: v for k, v in r.items() if k != "_config"} for r in smoke],
                notes=["E1 ~ E3 = 같은 꼴 3회 · ET = E 와 같은 꼴 + 기기 쪽 셸 반복 (E3 뒤 1회) — 계산 (E-a ~ E-f) 은 Cowork",
                       "유효: plugged 0 · 화면 켜짐 · 시작 SKIN 29.5 ~ 31.5 · 폴링 간격 중앙 ≤ 25 ms · 안전 멈춤 없음 (등록 §2-4)"])
    return dict(plan=plan, runs=runs, smoke=smoke)


def write_sessions(out: Path, built: dict) -> str:
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifests").mkdir(exist_ok=True)
    (out / "smoke").mkdir(exist_ok=True)
    for s in built["sessions"] + built["smoke"]:
        (out / s["manifest"]).write_bytes(C.canonical_json(s["_manifest"]))
    plan_bytes = C.canonical_json(built["plan"])
    (out / "plan.json").write_bytes(plan_bytes)
    digest = C.sha256_bytes(plan_bytes)
    (out / "plan_sha256.txt").write_text(digest + "\n", encoding="utf-8", newline="\n")
    dev = {k: dict(host_path=v["host_path"], device_path=v["device_path"], sha256=v["sha256"], bytes=v["bytes"]) for k, v in built["device"].items()}
    (out / "device_inputs.json").write_bytes(C.canonical_json(dev))
    if "projection" in built["plan"]:
        (out / "projection.json").write_bytes(C.canonical_json(built["plan"]["projection"]))
    return digest


def write_gauge(out: Path, built: dict) -> str:
    (out / "configs").mkdir(parents=True, exist_ok=True)
    for r in built["runs"] + built["smoke"]:
        (out / r["config"]).write_bytes(C.canonical_json(r["_config"]))
    plan_bytes = C.canonical_json(built["plan"])
    (out / "plan.json").write_bytes(plan_bytes)
    digest = C.sha256_bytes(plan_bytes)
    (out / "plan_sha256.txt").write_text(digest + "\n", encoding="utf-8", newline="\n")
    return digest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-root", required=True, type=Path)
    for name in ("cls-model", "det-model", "aot-model", "png", "anchors", "cls-labels", "det-labels"):
        ap.add_argument("--" + name, required=True, type=Path)
    args = ap.parse_args()
    device = device_inputs(args)
    p = build_p(device)
    k = build_k(device)
    e = build_e(device)
    dp = write_sessions(args.out_root / "plan_m6p", p)
    dk = write_sessions(args.out_root / "plan_m6k", k)
    de = write_gauge(args.out_root / "plan_m6e", e)
    print(f"plan_m6p {dp} sessions {len(p['sessions'])} smoke {len(p['smoke'])}")
    for s in p["sessions"] + p["smoke"]:
        print(f"  {s['manifest']} {s['manifest_sha256']} proj {s['projection_sha256']}")
    print(f"projection L {p['plan']['projection']['L']['sha256']} equal={p['plan']['projection']['L']['equal']} · "
          f"B {p['plan']['projection']['B']['sha256']} equal={p['plan']['projection']['B']['equal']}")
    print(f"plan_m6k {dk} sessions {len(k['sessions'])} smoke {len(k['smoke'])}")
    for s in k["sessions"] + k["smoke"]:
        print(f"  {s['manifest']} {s['manifest_sha256']}")
    print(f"plan_m6e {de} runs {len(e['runs'])} smoke {len(e['smoke'])}")
    for r in e["runs"] + e["smoke"]:
        print(f"  {r['config']} {r['config_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
