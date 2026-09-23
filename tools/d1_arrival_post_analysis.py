"""Read-only reproduction audit and figures for the frozen A24 arrival evaluation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from tools import d1_arrival_analysis as base
from tools import d1_arrival_plan as planlib


VERSION = "arrival-independent-evaluation-post-analysis-v1"
POLICIES = ("CPU_FIFO", "CPU_URGENT", "CONDITIONAL")
COLORS = {"CPU_FIFO": "#4C78A8", "CPU_URGENT": "#F58518", "CONDITIONAL": "#54A24B"}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else [])
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def condition(entry):
    if entry["kind"] == "burst" and entry["urgent_task"] == "classification":
        return "primary"
    if entry["kind"] == "burst":
        return "reversed"
    return entry["kind"]


def load_sessions(plan_path, results):
    plan_path, results = Path(plan_path), Path(results)
    plan = planlib.read(plan_path)
    planlib.validate(plan, plan_path.parent)
    sessions = []
    warmups = 0
    for entry in plan["entries"]:
        frozen_manifest = planlib.read(plan_path.parent / entry["manifest"])
        if sha256(plan_path.parent / entry["manifest"]) != entry["manifest_sha256"]:
            raise ValueError("frozen manifest hash mismatch")
        warmups += len(frozen_manifest["warmup_requests"])
        folder = results / f"{entry['index']:02d}_{entry['session_id']}"
        raw_manifest = folder / "artifacts" / "manifest.json"
        if sha256(raw_manifest) != entry["manifest_sha256"]:
            raise ValueError(f"raw manifest mismatch: {entry['session_id']}")
        requests = planlib.read(folder / "artifacts" / "requests.json")
        metric = base.session_metrics(entry, folder)
        if metric["status"] != "completed":
            raise ValueError(f"incomplete session: {entry['session_id']}")
        sessions.append(dict(entry=entry, manifest=frozen_manifest, requests=requests,
                             metric=metric, folder=folder, condition=condition(entry)))
    return plan, sessions, warmups


def validate_inventory(results, inventory_path):
    inventory = planlib.read(Path(inventory_path))
    files = {p.relative_to(results).as_posix(): p for p in sorted(Path(results).rglob("*")) if p.is_file()}
    expected = {row["path"]: row for row in inventory["files"]}
    if inventory["file_count"] != len(files) or set(files) != set(expected):
        raise ValueError("raw inventory membership mismatch")
    for name, path in files.items():
        if path.stat().st_size != expected[name]["bytes"] or sha256(path) != expected[name]["sha256"]:
            raise ValueError(f"raw inventory hash mismatch: {name}")
    return len(files)


def request_rows(sessions):
    rows = []
    for session in sessions:
        entry = session["entry"]
        for row in session["requests"]:
            value = dict(row)
            value.update(index=entry["index"], pair_id=entry["pair_id"], policy=entry["policy"],
                         kind=entry["kind"], urgent_task=entry["urgent_task"],
                         replicate=entry["replicate"], condition=session["condition"])
            rows.append(value)
    return rows


def pooled_p95_ms(rows):
    values = [row["response_ns"] for row in rows if row["terminal_status"] == "succeeded"]
    return base.nearest_p95(values) / 1e6 if values else None


def policy_summary(sessions, evaluation):
    requests = request_rows(sessions)
    rows = []
    for policy in POLICIES:
        group = [s for s in sessions if s["condition"] == "primary" and s["entry"]["policy"] == policy]
        primary_urgent = [r for r in requests if r["condition"] == "primary" and
                          r["policy"] == policy and r["priority"] == "urgent"]
        all_urgent = [r for r in requests if r["policy"] == policy and r["priority"] == "urgent"]
        summary = evaluation["policy"][policy]
        rows.append(dict(
            policy=policy, paired_blocks=len(group), urgent_per_session=2,
            session_p95_mean_ms=summary["urgent_p95_ms"]["mean"],
            session_p95_ci95_low_ms=summary["urgent_p95_ms"]["low"],
            session_p95_ci95_high_ms=summary["urgent_p95_ms"]["high"],
            primary_pooled_urgent_n=len(primary_urgent),
            primary_pooled_urgent_p95_ms=pooled_p95_ms(primary_urgent),
            all_condition_pooled_urgent_n=len(all_urgent),
            all_condition_pooled_urgent_p95_ms=pooled_p95_ms(all_urgent),
            normal_mean_response_ms=summary["normal_mean_response_ms"]["mean"],
            normal_mean_ci95_low_ms=summary["normal_mean_response_ms"]["low"],
            normal_mean_ci95_high_ms=summary["normal_mean_response_ms"]["high"],
            makespan_s=summary["makespan_s"]["mean"],
            makespan_ci95_low_s=summary["makespan_s"]["low"],
            makespan_ci95_high_s=summary["makespan_s"]["high"],
            throughput_per_s=summary["throughput_per_s"]["mean"],
            throughput_ci95_low=summary["throughput_per_s"]["low"],
            throughput_ci95_high=summary["throughput_per_s"]["high"]))
    return rows


def paired_rows(paired):
    return [row for row in paired if row.get("kind") == "burst" and
            row.get("urgent_task") == "classification" and row.get("status") == "paired"]


def condition_effects(sessions, paired):
    metrics = [s["metric"] for s in sessions]
    by_pair = {}
    for row in metrics:
        by_pair.setdefault(row["pair_id"], {})[row["policy"]] = row
    effects = []
    for pair_id, group in by_pair.items():
        exemplar = next(iter(group.values()))
        label = "primary" if exemplar["kind"] == "burst" and exemplar["urgent_task"] == "classification" else (
            "reversed" if exemplar["kind"] == "burst" else exemplar["kind"])
        for baseline, current in (("CPU_FIFO", "CPU_URGENT"), ("CPU_URGENT", "CONDITIONAL")):
            effects.append(dict(condition=label, pair_id=pair_id, replicate=exemplar["replicate"],
                                contrast=f"{current}-{baseline}", paired_blocks=6 if label == "primary" else 1,
                                urgent_p95_delta_ms=group[current]["urgent_p95_ms"]-group[baseline]["urgent_p95_ms"],
                                normal_mean_delta_ms=(group[current]["normal_mean_response_ms"]-
                                                      group[baseline]["normal_mean_response_ms"]),
                                makespan_delta_s=group[current]["makespan_s"]-group[baseline]["makespan_s"],
                                throughput_delta_per_s=(group[current]["throughput_per_s"]-
                                                        group[baseline]["throughput_per_s"])))
    return effects


def service_rows(sessions):
    output = []
    for session in sessions:
        requests = session["requests"]
        workload_start = planlib.read(session["folder"] / "artifacts" / "summary.json")["workload_start_ns"]
        for row in requests:
            start, release = row.get("execution_start_ns"), row.get("worker_release_ns")
            overlap = 0
            if start is not None and release is not None:
                for other in requests:
                    if other["request_id"] == row["request_id"] or other.get("selected_backend") == row.get("selected_backend"):
                        continue
                    a, b = other.get("execution_start_ns"), other.get("worker_release_ns")
                    if a is not None and b is not None:
                        overlap += max(0, min(release, b)-max(start, a))
            running = [other for other in requests if other.get("execution_start_ns") is not None and
                       other["execution_start_ns"] <= row["scheduled_arrival_ns"] < other["worker_release_ns"]]
            residual = max((other["worker_release_ns"]-row["scheduled_arrival_ns"] for other in running), default=0)
            output.append(dict(
                session_id=session["entry"]["session_id"], pair_id=session["entry"]["pair_id"],
                condition=session["condition"], policy=session["entry"]["policy"],
                request_id=row["request_id"], ordinal=row["ordinal"], task=row["task_id"],
                priority=row["priority"], backend=row.get("selected_backend"),
                scheduled_offset_ms=(row["scheduled_arrival_ns"]-workload_start)/1e6,
                arrival_lag_ms=row.get("arrival_lag_ns", 0)/1e6,
                queue_wait_ms=(row["execution_start_ns"]-row["queue_entry_ns"])/1e6 if start is not None else None,
                completion_service_ms=(row["completion_ns"]-row["execution_start_ns"])/1e6 if start is not None else None,
                worker_occupancy_ms=(release-start)/1e6 if start is not None and release is not None else None,
                inference_ms=row.get("inference_ns", 0)/1e6,
                policy_compute_ms=row.get("policy_compute_ns", 0)/1e6,
                opposite_lane_overlap_ms=overlap/1e6,
                residual_running_at_arrival_ms=residual/1e6,
                response_ms=row.get("response_ns", 0)/1e6,
                terminal_status=row["terminal_status"]))
    return output


def denominators(sessions):
    rows = []
    for policy in POLICIES:
        group = [r for s in sessions if s["entry"]["policy"] == policy for r in s["requests"]]
        rows.append(dict(policy=policy, sessions=sum(s["entry"]["policy"] == policy for s in sessions),
                         requests=len(group), urgent=sum(r["priority"] == "urgent" for r in group),
                         normal=sum(r["priority"] == "normal" for r in group),
                         succeeded=sum(r["terminal_status"] == "succeeded" for r in group),
                         failed=sum(r["terminal_status"] == "failed" for r in group),
                         rejected=sum(r["terminal_status"] == "rejected" for r in group),
                         expired=sum(r["terminal_status"] == "expired" for r in group),
                         unfinished=sum(r["terminal_status"] == "unfinished" for r in group),
                         late_success=sum(r.get("late_success") is True for r in group)))
    return rows


def representative_sessions(sessions):
    """Frozen rule from the original analyzer: first primary block (replicate zero), all policies."""
    selected = [s for s in sessions if s["condition"] == "primary" and s["entry"]["replicate"] == 0]
    if len(selected) != 3 or {s["entry"]["policy"] for s in selected} != set(POLICIES):
        raise ValueError("representative rule did not select one complete policy triple")
    if len({s["entry"]["pair_id"] for s in selected}) != 1:
        raise ValueError("representative sessions are not paired")
    return sorted(selected, key=lambda s: POLICIES.index(s["entry"]["policy"]))


def timeline_rows(selected):
    rows = []
    for session in selected:
        start = planlib.read(session["folder"] / "artifacts" / "summary.json")["workload_start_ns"]
        for row in session["requests"]:
            rows.append(dict(policy=session["entry"]["policy"], pair_id=session["entry"]["pair_id"],
                             session_id=session["entry"]["session_id"], request_id=row["request_id"],
                             ordinal=row["ordinal"], task=row["task_id"], priority=row["priority"],
                             backend=row["selected_backend"],
                             scheduled_arrival_ms=(row["scheduled_arrival_ns"]-start)/1e6,
                             actual_arrival_ms=(row["actual_arrival_ns"]-start)/1e6,
                             queue_entry_ms=(row["queue_entry_ns"]-start)/1e6,
                             execution_start_ms=(row["execution_start_ns"]-start)/1e6,
                             completion_ms=(row["completion_ns"]-start)/1e6,
                             worker_release_ms=(row["worker_release_ns"]-start)/1e6))
    return rows


def plotting():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "svg.hashsalt": VERSION, "figure.dpi": 160})
    return plt


def save_figure(fig, output, stem):
    for suffix in ("png", "svg"):
        fig.savefig(Path(output) / f"{stem}.{suffix}", bbox_inches="tight", metadata={"Date": None})
    fig.clear()


def figures(output, summary, evaluation, primary_pairs, effects, timeline):
    plt = plotting()
    labels = list(POLICIES)
    x = list(range(3))
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    means = [next(r for r in summary if r["policy"] == p)["session_p95_mean_ms"] for p in labels]
    lows = [evaluation["policy"][p]["urgent_p95_ms"]["low"] for p in labels]
    highs = [evaluation["policy"][p]["urgent_p95_ms"]["high"] for p in labels]
    ax.bar(x, means, color=[COLORS[p] for p in labels], yerr=[[m-l for m,l in zip(means,lows)],
            [h-m for m,h in zip(means,highs)]], capsize=5)
    ax.set_xticks(x, labels); ax.set_ylabel("Urgent latency (ms)")
    ax.set_title("Primary condition: mean session nearest-rank P95\n2 urgent/session, 6 paired blocks; t 95% CI")
    ax.grid(axis="y", alpha=.25)
    save_figure(fig, output, "01_urgent_latency_primary")

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.9))
    specs = (("normal_mean_response_ms", "normal_mean_response_ms", "Normal mean response (ms)"),
             ("makespan_s", "makespan_s", "Makespan (s)"),
             ("throughput_per_s", "throughput_per_s", "Throughput (req/s)"))
    for ax, (field, key, title) in zip(axes, specs):
        means = [evaluation["policy"][p][key]["mean"] for p in labels]
        lows = [evaluation["policy"][p][key]["low"] for p in labels]
        highs = [evaluation["policy"][p][key]["high"] for p in labels]
        ax.bar(x, means, color=[COLORS[p] for p in labels], yerr=[[m-l for m,l in zip(means,lows)],
               [h-m for m,h in zip(means,highs)]], capsize=4)
        ax.set_xticks(x, ["FIFO", "URGENT", "COND"]); ax.set_title(title); ax.grid(axis="y", alpha=.25)
    fig.suptitle("Primary condition, session means; 6 paired blocks; t 95% CI")
    save_figure(fig, output, "02_normal_efficiency_primary")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharex=True)
    contrasts = ("CPU_URGENT-CPU_FIFO", "CONDITIONAL-CPU_URGENT")
    markers = ("o", "s")
    for contrast, marker in zip(contrasts, markers):
        rows = sorted([r for r in primary_pairs if r["contrast"] == contrast], key=lambda r: r["replicate"])
        axes[0].plot(range(1, 7), [r["urgent_p95_delta_ms"] for r in rows], marker=marker, label=contrast)
        axes[1].plot(range(1, 7), [r["normal_mean_response_delta_ms"] for r in rows], marker=marker, label=contrast)
    for ax, title in zip(axes, ("Urgent session-P95 delta (ms)", "Normal mean-response delta (ms)")):
        ax.axhline(0, color="black", linewidth=.8); ax.set_title(title); ax.set_xlabel("Paired block")
        ax.set_xticks(range(1, 7)); ax.grid(alpha=.25); ax.legend(fontsize=7)
    fig.suptitle("Primary condition: all six paired blocks (current - baseline)")
    save_figure(fig, output, "03_primary_block_effects")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.1))
    order = ("primary", "low", "queue")
    cond_rows = {c: [r for r in effects if r["condition"] == c and
                     r["contrast"] == "CONDITIONAL-CPU_URGENT"] for c in order}
    for ax, field, title in ((axes[0], "urgent_p95_delta_ms", "Urgent session-P95 delta (ms)"),
                             (axes[1], "normal_mean_delta_ms", "Normal mean-response delta (ms)")):
        means = [sum(r[field] for r in cond_rows[c])/len(cond_rows[c]) for c in order]
        ax.bar(range(3), means, color="#54A24B")
        primary_ci = base.mean_ci95([r[field] for r in cond_rows["primary"]])
        ax.errorbar(0, means[0], yerr=[[means[0]-primary_ci["low"]],
                    [primary_ci["high"]-means[0]]], color="black", capsize=5, zorder=4)
        for i, c in enumerate(order):
            for row in cond_rows[c]:
                ax.scatter(i, row[field], color="black", s=18, zorder=3)
        ax.axhline(0, color="black", linewidth=.8); ax.set_xticks(range(3), ["primary\nn=6", "low\nn=1", "queue\nn=1"])
        ax.set_title(title); ax.grid(axis="y", alpha=.25)
    fig.suptitle("CONDITIONAL - CPU_URGENT; supporting conditions are descriptive")
    save_figure(fig, output, "04_condition_effects")

    fig, axes = plt.subplots(3, 1, figsize=(11.5, 8.2), sharex=True)
    for ax, policy in zip(axes, POLICIES):
        rows = [r for r in timeline if r["policy"] == policy]
        for y, row in enumerate(rows):
            ax.scatter(row["scheduled_arrival_ms"], y, marker="|", s=100, color="black", zorder=4)
            ax.barh(y, row["execution_start_ms"]-row["queue_entry_ms"], left=row["queue_entry_ms"],
                    height=.55, color="#BDBDBD", label="queue wait" if y == 0 else None)
            color = "#4C78A8" if row["backend"] == "CPU" else "#E45756"
            ax.barh(y, row["worker_release_ms"]-row["execution_start_ms"], left=row["execution_start_ms"],
                    height=.55, color=color, label=row["backend"] if not any(x.get_label() == row["backend"] for x in ax.patches) else None)
        ax.set_yticks(range(len(rows)), [f"{r['ordinal']} {r['priority'][0].upper()} {r['task'][0].upper()}" for r in rows])
        ax.set_title(policy); ax.grid(axis="x", alpha=.2)
    axes[-1].set_xlabel("Milliseconds from workload start; | = scheduled arrival")
    fig.suptitle("Representative rule: first planned primary paired block (replicate 0), all policies")
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    fig.legend(handles=[Line2D([0], [0], marker="|", color="black", linestyle="None",
                               markersize=12, label="scheduled arrival"),
                        Patch(color="#BDBDBD", label="queue wait"),
                        Patch(color="#4C78A8", label="CPU occupancy"),
                        Patch(color="#E45756", label="GPU occupancy")],
               loc="lower center", ncol=4, bbox_to_anchor=(.5, .005))
    fig.subplots_adjust(bottom=.11)
    save_figure(fig, output, "05_representative_gantt")


def compare_reference(output_data, reference):
    reference = Path(reference)
    result = {}
    for name, value in output_data.items():
        path = reference / name
        result[name] = dict(semantic_equal=planlib.read(path) == value, reference_sha256=sha256(path))
    if not all(row["semantic_equal"] for row in result.values()):
        raise ValueError("reproduction differs from reference analysis")
    return result


def report_text(audit, summary, evaluation):
    by = {r["policy"]: r for r in summary}
    main = evaluation["contrasts"]["CONDITIONAL-CPU_URGENT"]
    priority = evaluation["contrasts"]["CPU_URGENT-CPU_FIFO"]
    return f"""# 독립 평가 PC 재현 검증 보고서

- 버전: `{VERSION}`
- 재현 상태: **PASS** — 27세션, 평가198, warmup216, 원본694파일 hash 일치
- 동결 판정: **FAIL 유지** (`conditional_joint_primary_pass=false`)

## 계산 경계

주 긴급 지표는 각 세션의 urgent 2건에 nearest-rank P95를 적용한 값, 즉 세션 최댓값을 구한 뒤 6개 paired block에서 평균·t 95% CI를 계산한다. 모든 요청을 합친 pooled P95는 다른 추정량이며 주 판정에 사용하지 않는다. 예를 들어 주 조건 pooled urgent P95는 FIFO/긴급우선/조건부가 각각 {by['CPU_FIFO']['primary_pooled_urgent_p95_ms']:.1f}/{by['CPU_URGENT']['primary_pooled_urgent_p95_ms']:.1f}/{by['CONDITIONAL']['primary_pooled_urgent_p95_ms']:.1f}ms다.

Makespan은 workload monotonic start부터 마지막 worker release까지다. Throughput은 성공 요청 수를 이 makespan으로 나눈 값이다. 정책별 요약은 주 조건 6개 세션 KPI의 산술평균이다. CI는 요청 재표집이나 bootstrap이 아니라 같은 workload의 정책 대응을 보존한 6개 block 차이에 대한 양측 paired t 95% CI다.

## 사전 동결 주 결과

CPU 긴급 우선은 FIFO 대비 urgent P95를 {-priority['urgent_relative']['mean']*100:.2f}% 줄였고 normal 평균응답은 {priority['normal_relative']['mean']*100:.2f}% 늘었다. 조건부는 CPU 긴급 우선 대비 urgent P95를 {-main['urgent_relative']['mean']*100:.2f}% 줄여 10% 최소효과를 충족하지 못했다. normal 평균응답은 {-main['normal_relative']['mean']*100:.2f}% 줄었다. 일반 효율 개선으로 긴급 최소효과 실패를 대체하지 않는다.

## 사전 지정 보조 지표

모든 deadline 위반율은0, normal on-time과 전체 완료율은100%라 정책 구분력이 없다. Makespan과 throughput은 조건부 정책에서 개선됐지만 주 결합 PASS를 바꾸지 않는다. low와 queue는 각각 paired block 1개뿐이며 조건부 urgent P95가 CPU 긴급 우선보다 9.7ms와 6.8ms 느렸다.

## 평가 공개 후 탐색적 해석

우선순위 변경이 긴급 개선 대부분을 설명한다. 조건부 정책의 추가 GPU 사용은 일반 탐지의 대기와 makespan을 줄였지만 긴급 추가 효과는 작았다. 고정 CPU/GPU 분리 정책을 평가하지 않았으므로 적응적 판단 자체의 우월성은 주장할 수 없다.

## 완전성

정책별66건(urgent17, normal49), 전체 urgent51/normal147이다. 실패·거절·만료·미완료·late success와 제외는 모두0이다. 적용 범위는 A24, 고정 모델·canonical 입력, resident runtime, CPU thread1, CPU/GPU worker 각1, 비선점, 관측 thermal status0이다.
"""


def team_text(evaluation):
    p = evaluation["contrasts"]["CPU_URGENT-CPU_FIFO"]
    g = evaluation["contrasts"]["CONDITIONAL-CPU_URGENT"]
    return f"""# 팀원 공유용 결과 요약

## 확정 결과

- 독립 평가 27세션·198요청은 누락 없이 완료됐고 동결된 주 결합 판정은 **FAIL**이다.
- CPU 긴급 우선은 FIFO보다 urgent P95를 평균 {-p['urgent_p95_delta_ms']['mean']:.1f}ms({-p['urgent_relative']['mean']*100:.2f}%) 줄였다. normal 평균응답 비용은 +{p['normal_mean_response_delta_ms']['mean']:.1f}ms(+{p['normal_relative']['mean']*100:.2f}%)였다.
- 조건부 CPU/GPU는 CPU 긴급 우선보다 normal 평균응답을 {-g['normal_mean_response_delta_ms']['mean']:.1f}ms, makespan을 {-g['makespan_delta_s']['mean']:.3f}s 줄이고 throughput을 +{g['throughput_delta_per_s']['mean']:.3f}req/s 높였다.
- 그러나 긴급 추가 개선은 {-g['urgent_p95_delta_ms']['mean']:.1f}ms({-g['urgent_relative']['mean']*100:.2f}%)뿐이라 사전 10% 최소효과를 통과하지 못했다.

## 해석 경계

- 우선순위 변경이 긴급 개선의 핵심이고 GPU 보조는 주로 일반 처리효율을 개선했다.
- low·queue는 각1 block이고 조건부 urgent가 CPU 긴급 우선보다 조금 느렸다. 전체 조건의 긴급 비열등성은 입증되지 않았다.
- deadline 위반0은 정책 우수성 근거가 아니다.
- 고정 CPU/GPU 분리를 측정하지 않아 조건부 정책의 적응적 판단이 고정 분리보다 우월하다고 말할 수 없다.
- A24 한 대, 현재 모델·단일 입력, resident·비선점·thermal0 범위 밖으로 일반화하지 않는다.
"""


def analyze(plan_path, results, raw_inventory, reference, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    plan, sessions, warmups = load_sessions(plan_path, results)
    raw_count = validate_inventory(Path(results), raw_inventory)
    metrics = [s["metric"] for s in sessions]
    paired = base.paired_metrics(metrics)
    evaluation = base.evaluation_summary(metrics, paired)
    frozen = evaluation["frozen_decision"]
    if frozen["conditional_joint_primary_pass"] is not False:
        raise ValueError("frozen FAIL changed")
    requests = request_rows(sessions)
    if (len(sessions), len(requests), warmups) != (27, 198, 216):
        raise ValueError("budget count mismatch")
    if (sum(r["priority"] == "urgent" for r in requests),
            sum(r["priority"] == "normal" for r in requests)) != (51, 147):
        raise ValueError("priority denominator mismatch")
    output.mkdir(parents=True)
    summary = policy_summary(sessions, evaluation)
    effects = condition_effects(sessions, paired)
    primary_pairs = paired_rows(paired)
    service = service_rows(sessions)
    selected = representative_sessions(sessions)
    timeline = timeline_rows(selected)
    denoms = denominators(sessions)
    write_csv(output / "primary_policy_summary.csv", summary)
    write_csv(output / "primary_paired_effects.csv", primary_pairs)
    write_csv(output / "condition_effects.csv", effects)
    write_csv(output / "service_observations.csv", service)
    write_csv(output / "representative_timeline.csv", timeline)
    write_csv(output / "denominators.csv", denoms)
    reproduced = {"session_kpi.json": metrics, "paired_kpi.json": paired,
                  "evaluation_summary.json": evaluation}
    comparison = compare_reference(reproduced, reference)
    condition_counts = {}
    for name in ("primary", "reversed", "low", "queue"):
        subset = [s for s in sessions if s["condition"] == name]
        condition_counts[name] = dict(sessions=len(subset), paired_blocks=len({s["entry"]["pair_id"] for s in subset}),
                                      requests=sum(len(s["requests"]) for s in subset))
    service_cells = []
    for task, backend in sorted({(r["task"], r["backend"]) for r in service}):
        cell = [r for r in service if r["task"] == task and r["backend"] == backend]
        service_cells.append(dict(task=task, backend=backend, requests=len(cell),
                                  overlap_requests=sum(r["opposite_lane_overlap_ms"] > 0 for r in cell),
                                  occupancy_mean_ms=sum(r["worker_occupancy_ms"] for r in cell)/len(cell),
                                  occupancy_min_ms=min(r["worker_occupancy_ms"] for r in cell),
                                  occupancy_max_ms=max(r["worker_occupancy_ms"] for r in cell)))
    audit = dict(
        version=VERSION, status="PASS", source_plan_sha256=sha256(plan_path), raw_files=raw_count,
        counts=dict(sessions=27, evaluation_requests=198, warmup_calls=216, urgent=51, normal=147,
                    policies=denoms, conditions=condition_counts),
        formulas=dict(
            frozen_urgent_p95="nearest-rank P95 within each session's two urgent completed requests, then mean across six primary sessions",
            pooled_urgent_p95="nearest-rank P95 after pooling requests; descriptive only and not the frozen primary estimand",
            makespan="last worker_release_ns - workload_start_ns",
            throughput="successful requests / makespan",
            uncertainty="two-sided t 95% CI over six paired workload blocks; no request-level resampling"),
        representative_rule="first planned primary paired block (replicate=0), all three policies; metric-independent",
        simulation_component_support=dict(service_cells=service_cells,
            missing_cells=["classification/GPU under arrival workload"],
            confounding="detection/GPU observations all overlap and are selected by CONDITIONAL; no matched causal interference estimate"),
        reference_comparison=comparison, frozen_decision=frozen,
        exclusions=dict(sessions=0, requests=0, failures=0, retries=0, replacements=0))
    (output / "audit.json").write_bytes(planlib.canonical(audit))
    figures(output, summary, evaluation, primary_pairs, effects, timeline)
    (output / "REPRODUCTION_REPORT.md").write_text(report_text(audit, summary, evaluation), encoding="utf-8")
    (output / "TEAM_SUMMARY_KO.md").write_text(team_text(evaluation), encoding="utf-8")
    command = (f"python -B -m tools.d1_arrival_post_analysis --plan \"{Path(plan_path)}\" "
               f"--results \"{Path(results)}\" --raw-inventory \"{Path(raw_inventory)}\" "
               f"--reference-analysis \"{Path(reference)}\" --output \"{output}\"")
    (output / "REPRODUCE_COMMAND.txt").write_text(command + "\n", encoding="utf-8")
    files = {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file()}
    receipt = dict(version=VERSION, repository_base_head="b0f3a669ff2b792c0804c90b703bfc56a1da3798",
                   tool_sha256={"d1_arrival_post_analysis.py": sha256(Path(__file__)),
                                "d1_arrival_analysis.py": sha256(Path(base.__file__))},
                   output_files=files, original_analysis_preserved=True, raw_preserved=True)
    (output / "receipt.json").write_bytes(planlib.canonical(receipt))
    return dict(status="PASS", sessions=27, requests=198, warmups=216,
                frozen_joint_primary_pass=False, output=str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--raw-inventory", type=Path, required=True)
    parser.add_argument("--reference-analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.plan, args.results, args.raw_inventory,
                             args.reference_analysis, args.output), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
