"""Saved-only report: common-stage reward effects, selected FINAL, full harms."""
import gzip
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from tools import d1_atc_energy_study as s
from tools import d1_atc_waitlink_report as helpers


def independent_masks(raw):
    """Reconstruct current owners from exact public clocks, without using saved masks."""
    tickets = {row["id"]: row for row in raw["result"]["ledger"]}
    phase_times = {}
    for event in raw["events"]:
        if event["event"] in ("dispatch_ns", "lane_available_ns"):
            phase_times.setdefault(event["request_id"], {})[event["event"]] = event["at_ns"]
    dispatch = {rid: item["dispatch_ns"] for rid, item in phase_times.items() if "dispatch_ns" in item}
    available = {rid: item["lane_available_ns"] for rid, item in phase_times.items() if "lane_available_ns" in item}

    def legal(job, queue, owners):
        request = queue.get(job["request_id"]); backend = job["backend"]
        if request is None or backend not in (("CPU", "GPU") if request["task"] == "classification" else ("CPU",)) or backend in owners:
            return False
        labels = [row["task"] + "_" + resource for resource, row in owners.items()] + [request["task"] + "_" + backend]
        return len(labels) == 1 or (len(labels) == 2 and set(labels) == {"classification_GPU", "detection_CPU"})

    def physical(action, queue, owners):
        if action is None:
            return False
        if action["kind"] == "resource_wait":
            target = action["target"]; request = queue.get(target["request_id"])
            return bool(request and owners and target["backend"] in (("CPU", "GPU") if request["task"] == "classification" else ("CPU",)) and not legal(target, queue, owners))
        jobs = action.get("jobs", [])
        if action["kind"] not in ("single", "bundle") or len(jobs) != (1 if action["kind"] == "single" else 2):
            return False
        if len({job["request_id"] for job in jobs}) != len(jobs) or len({job["backend"] for job in jobs}) != len(jobs):
            return False
        virtual = dict(owners)
        for job in jobs:
            if not legal(job, queue, virtual):
                return False
            virtual[job["backend"]] = queue[job["request_id"]]
        return True

    for snap in raw["snapshots"]:
        now = snap["now_ns"]; queue = {rid: tickets[rid] for rid in snap["ranked_ids"]}
        if len(queue) != snap["queue_size"] or any(request["arrival_ns"] > now for request in queue.values()):
            raise ValueError("snapshot future/duplicate/current queue")
        owners = {request["backend"]: request for rid, request in tickets.items() if rid in dispatch and
                  dispatch[rid] <= now < available.get(rid, 120e9 + 1) and rid not in queue}
        expected = np.asarray([physical(action, queue, owners) for action in snap["actions"]], dtype=bool)
        if not np.array_equal(expected, snap["mask"]) or not np.array_equal(expected, snap["physical_mask"]):
            raise ValueError("independent current-owner physical mask mismatch")
        if sum(action is not None for action in snap["actions"]) > 29 or len([rid for rid in snap["request_ids"] if rid is not None]) > 8:
            raise ValueError("candidate/action resource bound")
    return len(raw["snapshots"])


def paired(rows, role, reference):
    by = {(row["condition"], row["policy"]): row for row in rows}
    output = []
    for row in [item for item in rows if item["policy"] == role]:
        ref = by[row["condition"], reference]
        item = dict(role=role, reference=reference, condition=row["condition"], family=row["family"],
                    factor=row["factor"], primary=row["primary"], release_domain=row["release_domain"])
        for key in (*s.SERVICE, "energy_j", "peak_ap_c"):
            item["delta_" + key] = row[key] - ref[key] if row[key] is not None and ref[key] is not None else None
        output.append(item)
    return output


def pair_summary(rows):
    output = []
    for role, reference in dict.fromkeys((row["role"], row["reference"]) for row in rows):
        for scope in ("full", "primary", "release"):
            q = [row for row in rows if row["role"] == role and row["reference"] == reference and
                 (scope == "full" or (scope == "primary" and row["primary"]) or (scope == "release" and row["release_domain"]))]
            item = dict(role=role, reference=reference, scope=scope, conditions=len(q))
            for key in (*s.SERVICE, "energy_j", "peak_ap_c"):
                values = [row["delta_"+key] for row in q if row["delta_"+key] is not None]
                item.update({key+"_valid": len(values), key+"_wins": sum(v < 0 for v in values),
                    key+"_ties": sum(v == 0 for v in values), key+"_losses": sum(v > 0 for v in values),
                    key+"_mean_delta": float(np.mean(values)) if values else None,
                    key+"_worst_delta": max(values) if values else None})
            output.append(item)
    return output


def timing_rows(timing):
    return [dict(role=role, stage=stage, count=len(values), mean_ms=float(np.mean(values)),
                 P95_ms=float(np.quantile(values, .95)), max_ms=max(values), shared_PC_host=True)
            for (role, stage), values in timing.items()]


def report(root):
    root = Path(root); reg = s.check(root); freeze = s.budget.read(root / "freeze.json")
    rows = s.budget.read(root / "final_rows.json"); cons = s.budget.read(root / "consumption.json")
    out = s.ROOT.parent.parent / "outputs" / s.budget.TASK; out.mkdir(parents=True, exist_ok=True)
    for name, data in (("final_rows", rows), ("summary_full", helpers.summary(rows)),
                       ("summary_primary", helpers.summary(s.parent.primary(rows))),
                       ("summary_release", helpers.summary([row for row in rows if row["release_domain"]])),
                       ("paired_win_tie_loss", helpers.pairdiff(rows))):
        helpers.csvwrite(out / (name + ".csv"), data)
    verdict = {role: dict(full=helpers.strict(rows, role), primary=helpers.strict(s.parent.primary(rows), role))
               for role in (*freeze["selections"], *freeze["original_selections"])}
    s.write(out / "strict_verdict.json", verdict)
    slo = {}
    for role in dict.fromkeys(row["policy"] for row in rows):
        q = [row for row in rows if row["release_domain"] and row["policy"] == role]
        bad = [row["condition"] for row in q if row["completed"] != row["planned"] or
               row["completed_work_units"] != row["planned_work_units"] or any(row[key] for key in
               ("urgent_failure", "normal_failure", "urgent_original_cap_failure", "normal_original_cap_failure")) or
               row["urgent_p95_ms"] is None or row["urgent_p95_ms"] > 400]
        slo[role] = dict(feasible=not bad, conditions=len(q), failed_conditions=bad, proposed_urgent_P95_budget_ms=400)
    s.write(out / "conditional_release_400ms.json", slo)
    comparisons = [(arm, "CONTROL") for arm in s.COST_ARMS] + [("GATED_ECO5", "ECO5"), ("GATED_ECO5_AP180", "GATED_ECO5")]
    final_pairs = []
    for seed in s.SEEDS:
        for arm in s.ARMS:
            final_pairs.extend(paired(rows, f"{arm}_{seed}", f"ORIGINAL4096_{seed}"))
        for arm, baseline in comparisons:
            final_pairs.extend(paired(rows, f"{arm}_{seed}", f"{baseline}_{seed}"))
    helpers.csvwrite(out / "selected_final_paired.csv", final_pairs)
    helpers.csvwrite(out / "selected_final_paired_summary.csv", pair_summary(final_pairs))
    common = []
    for episode in freeze["completed_by_all12"]:
        stage_rows = s.rows(root, f"dev{episode}_")
        for seed in s.SEEDS:
            for arm, baseline in comparisons:
                common.extend(dict(episode=episode, **item) for item in paired(stage_rows, f"{arm}_{seed}", f"{baseline}_{seed}"))
    helpers.csvwrite(out / "common_stage_reward_paired.csv", common)
    for episode in freeze["completed_by_all12"]:
        helpers.csvwrite(out / f"common_stage{episode}_summary.csv", pair_summary([row for row in common if row["episode"] == episode]))
    timing = defaultdict(list); queues = defaultdict(list); behavior = defaultdict(lambda: defaultdict(int)); raw_receipts = []
    snapshot_count = 0
    worker = root / "worker"
    for path in sorted((worker / "rows").glob("*.json")):
        receipt = s.budget.read(path); raw_path = worker / "items" / (path.stem + ".json.gz")
        if s.budget.digest(raw_path) != receipt["raw_sha256"]:
            raise ValueError("raw SHA changed " + str(path))
        raw = json.loads(gzip.decompress(raw_path.read_bytes())); s.parent.audit_ledger(raw["result"])
        independent_masks(raw)
        raw_receipts.append(dict(identity=path.stem, raw_sha256=receipt["raw_sha256"], source="new13"))
        for snap in raw["snapshots"]:
            if (np.asarray(snap["state"]).shape != (226,) or np.asarray(snap["candidates"]).shape != (32, 57) or
                not snap["physical_mask"][snap["chosen"]] or snap["online_forecast_calls"] != 0 or
                not np.array_equal(snap["physical_mask"], snap["mask"])):
                raise ValueError("saved ABI/physical mask/no-forecast violated")
            snapshot_count += 1
        if not path.stem.startswith("confirmation_"):
            continue
        role = raw["row"]["policy"]
        for snap in raw["snapshots"]:
            behavior[role]["decisions"] += 1
            behavior[role][snap["actions"][snap["chosen"]]["kind"]] += 1
            behavior[role]["teacher_overrides"] += snap["chosen"] != snap["base"]
            behavior[role]["nonhead"] += snap["nonhead_selected"]
            behavior[role]["max_queue"] = max(behavior[role]["max_queue"], snap["queue_size"])
        for frame in raw["stage_times"]:
            for key, value in frame.items():
                if key.endswith("seconds"):
                    timing[role, key].append(value * 1000)
        for callback in raw["callbacks"]:
            queues[role, callback["queue"]].append(callback["event_to_dispatch_seconds"] * 1000)
    for key, item in s.budget.read(root / "references.json").items():
        if s.budget.digest(item["raw_path"]) != item["raw_sha256"] or s.budget.digest(item["receipt_path"]) != item["receipt_sha256"]:
            raise ValueError("reused raw/receipt SHA changed")
        raw_receipts.append(dict(identity=key, raw_sha256=item["raw_sha256"], source="reused12", new_environments=0))
    helpers.csvwrite(out / "raw_sha_receipts.csv", raw_receipts)
    helpers.csvwrite(out / "PC_timing.csv", timing_rows(timing)); helpers.csvwrite(out / "PC_queue_timing.csv", timing_rows(queues))
    helpers.csvwrite(out / "actual_behavior.csv", [dict(role=role, **value) for role, value in behavior.items()])
    weights = out / "weights"; weights.mkdir(exist_ok=True); mechanics = []; gate_receipts = []; stages = []
    for seed in s.SEEDS:
        for arm in s.ARMS:
            role = f"{arm}_{seed}"; item = freeze["selections"][role]; selected = s.learner_path(root, arm, seed, item["episodes"])
            if s.budget.digest(selected) != item["sha256"]:
                raise ValueError("selected weights changed")
            shutil.copy2(selected, weights / selected.name)
            model = s.learning.Learner.load(s.learner_path(root, arm, seed), s.deps(reg, arm, seed))
            mechanics.append(dict(role=role, fresh_episodes=model.episodes, fresh_native_updates=len(model.logs),
                fresh_Adam_steps=model.steps, pending=len(model.pending), inherited_learning=0,
                selected_episode=item["episodes"], selected_sha256=item["sha256"], development_guard=item["development_guard_pass"]))
            gate_receipts.extend(dict(role=role, episode=row["episode"], **row["energy_label_receipt"]) for row in model.episode_logs)
        for episode in freeze["completed_by_all12"]:
            for arm, item in s.budget.read(s.stage_path(root, seed, episode)).items():
                stages.append(dict(role=f"{arm}_{seed}", **s.parent.serial(item)))
    for role, item in freeze["original_selections"].items():
        shutil.copy2(item["path"], weights / (role + ".pt"))
    helpers.csvwrite(out / "native_fresh_learning.csv", mechanics)
    helpers.csvwrite(out / "energy_label_receipts.csv", gate_receipts)
    s.write(out / "development_stages.json", stages)
    io = [json.loads(line) for line in (root / "checkpoint_io.jsonl").read_text("utf8").splitlines()]
    helpers.csvwrite(out / "checkpoint_io.csv", io)
    helpers.csvwrite(out / "checkpoint_io_summary.csv", [dict(role=f"{arm}_{seed}", count=len(values),
        mean_seconds=float(np.mean([item["seconds"] for item in values])),
        P95_seconds=float(np.quantile([item["seconds"] for item in values], .95)),
        max_seconds=max(item["seconds"] for item in values), max_bytes=max(item["bytes"] for item in values))
        for arm in s.ARMS for seed in s.SEEDS
        for values in [[item for item in io if item["reward_arm"] == arm and item["seed"] == seed]] if values])
    starts = [row for row in s.budget.Budget(worker).rows if row["event"] == "start" and row["phase"] == "confirmation"]
    freeze_time = datetime.fromisoformat(freeze["frozen_utc"])
    if any(datetime.fromisoformat(row["at_utc"]) <= freeze_time for row in starts):
        raise ValueError("FINAL started before freeze")
    s.write(out / "saved_audit.json", dict(raw_receipts=len(raw_receipts), new_raw=cons["environments"],
            reused_raw=4400, checked_snapshots=snapshot_count, ledger_AVAILABLE_response_physics=True,
            all_new_physical_masks_independently_reconstructed=True, complete_grid=3696, before_FINAL_freeze=True,
            online_future_forecast_calls=0, new_environments=0, new_learning=0))
    for name in ("registration.json", "inputs.json", "references.json", "namespace_receipt.json", "fresh_initialization.json",
                 "freeze.json", "consumption.json", "development_continuation.json", "partial59_audit.json", "PROTOCOL_REGISTERED.md"):
        if (root / name).exists():
            shutil.copy2(root / name, out / name)
    shutil.copytree(root / "REGISTERED_SOURCE_TREE", out / "REGISTERED_SOURCE_TREE", dirs_exist_ok=True)
    if (root / "partial59_checkpoints").exists():
        shutil.copytree(root / "partial59_checkpoints", out / "partial59_checkpoints", dirs_exist_ok=True)
    shutil.copy2(worker / "executions.jsonl", out / "executions.jsonl")
    text = ["# 별도 에너지·AP 보상 실험13", "", f"신규환경 {cons['environments']:,}, 신규학습 {cons['learning']:,}, 환경실패 {cons['failed']}입니다. 기존4400참조의 신규소비는0입니다.",
        "4보상×3seed의12fresh모델은 같은seed에서 network/Adam초기/action·shuffleRNG를같게시작했습니다. 원11 terminal4096 3개는평가전용이며12 장기학습가중치를읽지않았습니다.",
        "동일학습량 DEV 보상대조는common_stage_reward_paired.csv, 개발선정을포함한최종대조는selected_final_paired.csv로구분합니다. 모든seed와조건손해는삭제하지않았습니다.",
        "CONTROL→ECO5는계수, ECO5→GATED_ECO5는episode서비스gate, GATED_ECO5→GATED_ECO5_AP180은사후AP창변경의대조입니다. weight5는채널계수5배이며PPO정규화후gradient/효과5배보장이아닙니다.",
        "E/J는120초모형값, AP평가는35..180초모형peak입니다. 세기존arm의AP학습prefix는120초, AP180arm만사후180초peak증분을사용합니다. 실제폰에너지/표면온도/물리냉각/실기기납기보장이아닙니다.",
        "gate는전체episode가RuleATC대비완료·units·선언/원U/N·P95비악화일때만음수E/AP target혜택을유지합니다. gate실패에도양수비용손해·응답reward·서비스/P95 penalty를유지합니다.",
        "원strict epsilon0/full176/primary160과별도release80·400ms SLO는분리합니다. CP0선정0이며DEV적격이없으면실패checkpoint로공개합니다.", "", helpers.table(helpers.summary(rows)), "",
        "PC판단·queue·checkpoint시간은12번장기학습과공유한호스트의시간입니다. CPU분류4표본·고정plant·K8·n1합성범위및조건별손해한계는학습량으로해결했다고주장하지않습니다.",
        "실제AVAILABLE·응답별도·비선점·CG_DC≤2·resourceWAIT를유지했습니다. EFT0, Greedy/RR/FIFO독립군, 미래queue/duration/J/AP온라인입력0, 기기/APK/S26/NPU/fit/냉각/외부전송0, 자동채택0입니다."]
    (out / "RESULTS.md").write_text("\n".join(text) + "\n", encoding="utf8")
    manifest = {path.relative_to(out).as_posix(): s.budget.digest(path) for path in sorted(out.rglob("*")) if path.is_file() and path.name != "manifest.json"}
    s.write(out / "manifest.json", manifest)
    return dict(reported=True, output=str(out), fresh_models=12, final_rows=3696, automatic_adoption=False)
