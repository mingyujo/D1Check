"""Read-only post-run analysis of the separately frozen fixed-split comparison."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
from pathlib import Path
import statistics

from scipy.stats import t

from tools import d1_arrival_plan as p
from tools.d1_arrival_analysis import session_metrics
from tools.d1_arrival_device import allocation_gate, quality_gate

CONTRASTS = (("FIXED_SPLIT", "CPU_URGENT"),
             ("CPU_URGENT", "CONDITIONAL"), ("FIXED_SPLIT", "CONDITIONAL"))
METRICS = ("urgent_session_max_ms", "normal_mean_response_ms", "makespan_s",
           "throughput_per_s", "policy_compute_total_ms", "urgent_deadline_miss_rate",
           "normal_on_time_rate", "completion_rate")
KINDS = ("burst", "low", "queue")


def interval(values, confidence, allowed=True):
    values = list(values)
    if not values:
        return dict(n=0, mean=None, low=None, high=None, confidence=confidence)
    mean = statistics.mean(values)
    if len(values) < 2 or not allowed:
        return dict(n=len(values), mean=mean, low=None, high=None, confidence=confidence)
    sd = statistics.stdev(values)
    half = float(t.ppf((1 + confidence) / 2, len(values) - 1)) * sd / math.sqrt(len(values))
    return dict(n=len(values), mean=mean, sd=sd, low=mean - half, high=mean + half,
                confidence=confidence)


def summarize(plan, metrics):
    """All conditions/contrasts, block-relative differences, no request resampling."""
    expected = len(plan["entries"]) // 9
    all_validated = len(metrics) == len(plan["entries"]) and all(m.get("fully_validated") for m in metrics)
    effects, blocks, policy = [], [], []
    for kind in KINDS:
        members = [m for m in metrics if m["kind"] == kind]
        groups = {}
        for m in members:
            groups.setdefault(m["pair_id"], {})[m["policy"]] = m
        for name in p.FIXED_POLICIES:
            all_rows = [m for m in members if m["policy"] == name]
            complete = [m for m in all_rows if m.get("fully_validated")]
            item = dict(kind=kind, policy=name, planned_sessions=expected,
                        validated_sessions=len(complete))
            for key in METRICS:
                vals = [m[key] for m in complete if m.get(key) is not None]
                item[key] = interval(vals, .95, len(vals) == expected)
            policy.append(item)
        for baseline, current in CONTRASTS:
            pairs = [(pid, group[baseline], group[current]) for pid, group in groups.items()
                     if baseline in group and current in group and
                     group[baseline].get("fully_validated") and group[current].get("fully_validated")]
            for key in METRICS:
                primary = kind == "burst" and (baseline, current) == ("FIXED_SPLIT", "CONDITIONAL") and key in METRICS[:2]
                absolute, relative = [], []
                for pid, base, now in pairs:
                    if base.get(key) is None or now.get(key) is None:
                        continue
                    delta = now[key] - base[key]
                    rel = delta / base[key] if base[key] != 0 else None
                    absolute.append(delta)
                    if rel is not None:
                        relative.append(rel)
                    blocks.append(dict(kind=kind, pair_id=pid, replicate=now["replicate"],
                                       contrast=f"{current}-{baseline}", metric=key,
                                       baseline=base[key], current=now[key], difference=delta,
                                       relative_difference=rel, sign=(delta > 0) - (delta < 0)))
                effects.append(dict(kind=kind, contrast=f"{current}-{baseline}", metric=key,
                                    primary_relative_endpoint=primary, planned_pairs=expected,
                                    complete_pairs=len(pairs),
                                    absolute=interval(absolute, .95, len(absolute) == expected),
                                    relative=interval(relative, .975 if primary else .95,
                                                      len(relative) == expected and (all_validated or not primary))))
    return dict(policy=policy, effects=effects, block_effects=blocks,
                primary_decision="estimation only; no equivalence/noninferiority or joint PASS",
                old_conditional_joint_primary_pass=False)


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def figures(output, summary, metrics, timelines):
    """Preselected all-condition views and replicate-zero burst timeline."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = ("CPU urgent", "Fixed split", "Conditional")
    keys = METRICS[:4]
    titles = ("Urgent session max (ms; burst/low: 2 requests, queue: 1)",
              "Normal mean response (ms)", "Makespan (s)", "Throughput (requests/s)")
    fig, axes = plt.subplots(4, 3, figsize=(13, 12), constrained_layout=True)
    for column, kind in enumerate(KINDS):
        for row, (key, title) in enumerate(zip(keys, titles)):
            ax = axes[row, column]
            sample_labels = []
            for x, policy in enumerate(p.FIXED_POLICIES):
                vals = [m[key] for m in metrics if m['kind'] == kind and m['policy'] == policy
                        and m.get('fully_validated') and m.get(key) is not None]
                sample_labels.append(f'{labels[x]}\nn={len(vals)}')
                if vals:
                    ax.scatter([x]*len(vals), vals, color='0.4', s=17)
                    ax.scatter([x], [statistics.mean(vals)], color='#006D77', marker='D', s=40)
            ax.set_xticks(range(3), sample_labels, rotation=20)
            ax.set_title(f'{kind}: {title}', fontsize=9)
            ax.grid(axis='y', alpha=.25)
    fig.suptitle('All frozen conditions; dots = independent sessions, diamonds = equal-session means\n'
                 f'Planned {len(metrics)//9} blocks/condition; observed n shown; unbalanced means are descriptive', fontsize=12)
    for extension in ('png','svg'):
        fig.savefig(output / ('01_policy_kpi.' + extension), dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12,4), constrained_layout=True)
    for ax, key in zip(axes, METRICS[:2]):
        for y, kind in enumerate(KINDS):
            e=next(e for e in summary['effects'] if e['kind']==kind and e['contrast']=='CONDITIONAL-FIXED_SPLIT' and e['metric']==key)
            ci=e['relative']
            if ci['mean'] is not None:
                err=[[100*(ci['mean']-ci['low'])],[100*(ci['high']-ci['mean'])]] if ci['low'] is not None else None
                ax.errorbar(100*ci['mean'],y,xerr=err,fmt='o',capsize=4,color='#006D77')
                ax.annotate(f" n={ci['n']}",(100*ci['mean'],y),xytext=(5,8),textcoords='offset points',fontsize=8)
        ax.axvline(0,color='0.5',linestyle='--'); ax.set_yticks(range(3),KINDS)
        ax.set_ylim(-.4, 2.4); ax.margins(x=.15)
        ax.set_title(key); ax.set_xlabel('Mean paired relative difference (%)')
    fig.suptitle('Conditional - Fixed split: negative means lower latency\n'
                 'CI: burst 97.5% / supporting 95%; omitted for incomplete sets; no margin or PASS claim')
    for extension in ('png','svg'):
        fig.savefig(output / ('02_conditional_fixed_effects.' + extension),dpi=170)
    plt.close(fig)
    representative=[r for r in timelines if r['kind']=='burst' and r['replicate']==0]
    if representative:
        fig, axes=plt.subplots(3,1,figsize=(12,10),constrained_layout=True,sharex=True)
        for ax,policy,label in zip(axes,p.FIXED_POLICIES,labels):
            rows=sorted([r for r in representative if r['policy']==policy],key=lambda r:r['scheduled_arrival_ns'])
            if not rows:
                continue
            origin=min(r['scheduled_arrival_ns'] for r in rows)
            for y,r in enumerate(rows):
                start=(r['scheduled_arrival_ns']-origin)/1e6
                ax.plot(start,y,'|',color='black',markersize=12)
                if r.get('execution_start_ns') is None or r.get('worker_release_ns') is None:
                    continue
                execute=(r['execution_start_ns']-origin)/1e6
                release=(r['worker_release_ns']-origin)/1e6
                ax.barh(y,execute-start,left=start,height=.55,color='#cccccc')
                ax.barh(y,release-execute,left=execute,height=.55,color='#0077B6' if r['selected_backend']=='CPU' else '#E76F51')
                if r.get('completion_ns') is not None:
                    ax.plot((r['completion_ns']-origin)/1e6,y,'o',color='black',markersize=3)
            ax.set_yticks(range(len(rows)),[f"{i}: {r['priority']}" for i,r in enumerate(rows)])
            ax.set_title(label); ax.set_xlabel('ms from first scheduled arrival'); ax.invert_yaxis()
        fig.suptitle('Representative rule: first burst paired block (replicate 0), all policies\n'
                     'Gray: scheduled arrival to start; blue CPU / orange GPU: start to recorded release; dot completion')
        for extension in ('png','svg'):
            fig.savefig(output / ('03_representative_gantt.' + extension),dpi=170)
        plt.close(fig)


def analyze(plan_file, results, output):
    plan_file, results, output = map(Path, (plan_file, results, output))
    plan = p.read(plan_file)
    if plan["protocol"] != p.FIXED_PROTOCOL:
        raise ValueError("fixed comparison plan required")
    p.validate(plan, plan_file.parent)
    if not any((results / name).exists() for name in ("run_complete.json", "run_error.json")):
        raise ValueError("run is not finalized; do not analyze intermediate outcomes")
    if output.exists():
        raise FileExistsError(output)
    inventory = {str(f.relative_to(results)): p.digest(f) for f in sorted(results.rglob("*")) if f.is_file()}
    metrics, denominators, timelines = [], [], []
    for entry in plan["entries"]:
        folder = results / f"{entry['index']:02d}_{entry['session_id']}"
        manifest = p.read(plan_file.parent / entry["manifest"])
        rows_file = folder / "artifacts/requests.json"
        rows = p.read(rows_file) if rows_file.exists() else []
        if rows:
            planned = {q["request_id"] for q in manifest["requests"]}
            if len(rows) != len(planned) or {r["request_id"] for r in rows} != planned:
                raise ValueError("request identity/count mismatch")
        base = {k: entry[k] for k in ("index", "session_id", "pair_id", "kind", "replicate", "policy")}
        valid = (folder / "validated.json").exists() and (folder / "host_cleanup.json").exists()
        valid = valid and not any((folder / name).exists() for name in ("error.json", "cleanup_error.txt", "recovery_error.txt"))
        if valid:
            art = folder / "artifacts"
            if p.digest(art / "manifest.json") != entry["manifest_sha256"]:
                raise ValueError("artifact manifest hash mismatch")
            if p.read(art / "cleanup.json")["status"] != "completed":
                raise ValueError("runtime cleanup not completed")
            quality_gate(p.read(art / "summary.json"), rows, p.read(art / "environment.json"))
            allocation_gate(manifest, rows)
            for row in rows:
                if p.read(art / (row["request_id"] + ".event.json")) != row:
                    raise ValueError("event/ledger mismatch")
                if row["terminal_status"] == "succeeded" and p.digest(art / (row["request_id"] + ".result.json")) != row["result_sha256"]:
                    raise ValueError("payload hash mismatch")
        m = base | session_metrics(entry, folder)
        m["fully_validated"] = bool(valid)
        m["urgent_session_max_ms"] = m.pop("urgent_p95_ms", None)
        envfile = folder / "artifacts/environment.json"
        env = p.read(envfile) if envfile.exists() else []
        m["sampled_pss_max_mib"] = max((e.get("pss_bytes", 0) / 2**20 for e in env), default=None)
        m["sampled_pss_mean_mib"] = statistics.mean(e["pss_bytes"] / 2**20 for e in env if "pss_bytes" in e) if any("pss_bytes" in e for e in env) else None
        m["thermal_statuses"] = sorted({e["thermal_status"] for e in env if "thermal_status" in e})
        m["admission_counts"] = {reason: sum(e.get("admission_reason") == reason for e in env) for reason in sorted({e["admission_reason"] for e in env if "admission_reason" in e})}
        metrics.append(m)
        for priority in ("urgent", "normal"):
            selected = [r for r in rows if r["priority"] == priority]
            scheduled = sum(q["priority"] == priority for q in manifest["requests"])
            arrived = sum(r.get("actual_arrival_ns") is not None for r in selected)
            counts = {status: sum(r["terminal_status"] == status for r in selected)
                      for status in ("succeeded", "failed", "rejected", "expired", "unfinished")}
            denominators.append(base | dict(priority=priority, planned=scheduled,
                session_attempted=(folder / "attempt.json").exists(), observed_ledger=len(selected),
                observed_arrivals=arrived, unobserved=scheduled-len(selected),
                late_success=sum(r.get("late_success") is True for r in selected), **counts))
        for row in rows:
            timelines.append(base | row)
    summary = summarize(plan, metrics)
    summary["budget"] = dict(planned_sessions=plan["session_cap"],
        attempted_sessions=sum((results / f"{e['index']:02d}_{e['session_id']}" / "attempt.json").exists() for e in plan["entries"]),
        validated_sessions=sum(m["fully_validated"] for m in metrics),
        planned_requests=sum(e["request_count"] for e in plan["entries"]),
        successful_requests=sum(d["succeeded"] for d in denominators),
        planned_warmup_calls=8*len(plan["entries"]),
        warmup_calls_in_validated_sessions=8*sum(m["fully_validated"] for m in metrics),
        warmup_evidence="control flow before_workload after all eight calls; no per-call warmup ledger")
    output.mkdir(parents=True)
    for name, data in (("summary.json", summary), ("session_kpi.json", metrics),
                       ("denominators.json", denominators), ("raw_inventory.json", inventory)):
        (output / name).write_bytes(p.canonical(data))
    write_csv(output / "session_kpi.csv", [{k:v for k,v in m.items() if not isinstance(v,(dict,list))} for m in metrics])
    write_csv(output / "denominators.csv", denominators)
    write_csv(output / "paired_effects.csv", summary["block_effects"])
    write_csv(output / "request_timeline.csv", timelines)
    figures(output, summary, metrics, timelines)
    after = {str(f.relative_to(results)): p.digest(f) for f in sorted(results.rglob("*")) if f.is_file()}
    if after != inventory:
        raise RuntimeError("raw artifacts changed during analysis")
    (output / "receipt.json").write_bytes(p.canonical(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        plan_sha256=p.digest(plan_file), analyzer_sha256=p.digest(__file__),
        source_metrics_sha256=p.digest(Path(__file__).with_name("d1_arrival_analysis.py")),
        raw_files=len(inventory), raw_preserved=True, results=str(results.resolve()))))
    return summary["budget"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "results", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    import json
    print(json.dumps(analyze(args.plan, args.results, args.output), indent=2))


if __name__ == "__main__":
    main()
