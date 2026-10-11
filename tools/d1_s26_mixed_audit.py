"""Read-only mixed-7interval adapter audit; never fits or starts a simulator."""
import argparse
import collections
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

from tools.d1_atc_pilot_budget import write

FIXED=dict(measure="0a0749890fba2452c5907433c6bea476a2da7e24",
    mixreq="21cba44faa5fff1fb9703b590aa536a6207f8de5",
    quality20="5857152ad8244c41975843ded77dd33024f38f2d")
POINTS=("dispatch_ns","execution_start_ns","host_inference_start_ns","host_inference_return_ns",
        "output_ready_ns","persist_complete_ns","worker_release_ns","lane_available_ns")


def load(path):
    return json.loads(Path(path).read_text("utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def phase_adapter(row):
    """Preserve 7 source intervals and their exact 5phase aggregation separately."""
    points=[row.get(k) for k in POINTS]
    if any(type(v) is not int for v in points) or any(b<a for a,b in zip(points,points[1:])):
        raise ValueError("missing/unordered seven-interval request")
    intervals=[b-a for a,b in zip(points,points[1:])]
    five=[intervals[0],sum(intervals[1:4]),*intervals[4:]]
    response_field="output_ready_ns" if row["priority"]=="urgent" else "persist_complete_ns"
    arrival=row.get("scheduled_arrival_ns")
    if type(arrival) is not int or points[0]<arrival:
        raise ValueError("request clock domain/order")
    return dict(source_intervals_ns=intervals,phase5_ns=five,
        response_ns=row[response_field]-arrival,occupied_ns=points[-1]-points[0],
        response_boundary=response_field,available_boundary="lane_available_ns",
        eligible_for_policy=False)


def power_counts(events):
    selected=[e for e in events if e.get("kind")=="power_sample"]
    sensors=[e for e in events if e.get("kind")=="admission" and
             ("current_raw" in e or "sensors" in e)]
    return dict(power_samples=len(selected),admission_sensor_events=len(sensors),
        duplicate_timestamps=len(selected)-len({e.get("mono_ns",e.get("t_ns")) for e in selected}),
        current_unit="microampere",current_fields=sorted({k for e in selected for k in e if "current" in k}),
        integration_only_power_sample=True,sensor_absolute_accuracy_certified=False)


def audit(workspace,attachments):
    workspace=Path(workspace);roots={k:workspace/("s26-"+k) for k in FIXED}
    identities={}
    for k,root in roots.items():
        head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
        if head!=FIXED[k]:raise ValueError("fixed S26 tree mismatch: "+k)
        identities[k]=dict(commit=head,source="https://github.com/mingyujo/D1Check")
    mix=roots["mixreq"];base=mix/"s26/results/mixreq_1008"
    sessions=[];sources=[];cells=collections.defaultdict(list)
    for mp in sorted(base.glob("**/device/manifest.json")):
        session=mp.parent.parent;rp=mp.parent/"requests.json"
        manifest=load(mp);rows=load(rp) if rp.exists() else [];vp=session/"validated.json"
        if not isinstance(rows,list):raise ValueError("unexpected requests journal")
        counts=collections.Counter(r.get("terminal_status","unknown") for r in rows)
        if not rp.exists() and manifest.get("requests"):counts["unobserved_journal"]=len(manifest["requests"])
        complete=[r for r in rows if r.get("terminal_status")=="succeeded"]
        converted=[];errors=[]
        for r in complete:
            try:
                v=phase_adapter(r);converted.append(v)
                cells[(r["task_id"],r["selected_backend"],manifest.get("experiment_id"),manifest.get("policy"))].append(v["phase5_ns"])
            except ValueError as e:errors.append(dict(id=r.get("request_id"),error=str(e)))
        progress=mp.parent/"progress.jsonl"
        events=[json.loads(s) for s in progress.read_text("utf8").splitlines()] if progress.exists() else []
        power=power_counts(events)
        # Mono event timestamps and HAL boottime are distinct recorded contracts.
        hal=session/"host/hal.csv";channel={}
        if hal.exists():
            with hal.open(encoding="utf-8-sig",newline="") as f:hrows=list(csv.DictReader(f))
            for name in ("AP","SKIN"):
                values=[]
                for row in hrows:
                    try:
                        v=float(row[name])
                        if math.isfinite(v):values.append(v)
                    except (ValueError,TypeError,KeyError):pass
                channel[name]=dict(samples=len(values),peak=max(values) if values else None)
            times=[]
            for r in hrows:
                try:times.append(float(r["device_boottime_s"]))
                except (ValueError,TypeError,KeyError):pass
            channel["boottime"]=dict(samples=len(times),ordered=all(b>=a for a,b in zip(times,times[1:])),
                maximum_gap_s=max((b-a for a,b in zip(times,times[1:])),default=None),
                device_before_after_brackets=False,alignment_uncertainty="one observed interval sensitivity; not CI")
        validation=load(vp) if vp.exists() else {}
        sources.extend(dict(path=p.relative_to(mix).as_posix(),sha256=sha(p)) for p in (mp,rp,vp,progress,hal) if p.exists())
        sessions.append(dict(path=session.relative_to(base).as_posix(),session=manifest.get("session_id",session.name),experiment=manifest.get("experiment_id"),
            role=manifest.get("split"),block=manifest.get("block"),pair=manifest.get("pair"),policy=manifest.get("policy"),
            planned=len(manifest.get("requests",[])),journal_rows=len(rows),statuses=dict(counts),
            request_journal_present=rp.exists(),
            interval_adapter_pass=len(converted),adapter_errors=errors,
            original_validation_eligible=validation.get("eligible"),original_validation_reasons=validation.get("reasons"),
            runtimes=manifest.get("runtimes"),power=power,thermal_channels=channel,
            eligible_for_new_CPU_GPU_policy=False))
    summaries=[]
    for key,values in sorted(cells.items(),key=lambda x:str(x[0])):
        summaries.append(dict(task=key[0],backend=key[1],experiment=key[2],policy=key[3],requests=len(values),
            observed_phase5_mean_ns=[sum(col)/len(col) for col in zip(*values)],
            use="descriptive observed workload only; not an approved/newly fitted simulation profile"))
    qfiles=list((roots["quality20"]/"s26/results/quality20_1008").glob("**/*judgement*.md"))
    qtext="\n".join(p.read_text("utf8") for p in qfiles)
    attachment_receipts=[]
    for p in attachments:
        p=Path(p);attachment_receipts.append(dict(name=p.name,sha256=sha(p),scope="user supplied reference; not executed"))
    return dict(task="ATC-PPO-DESKTOP-PILOT-01",trees=identities,sessions=sessions,
        phase_summaries=summaries,source_receipts=sources,attachments=attachment_receipts,
        quality_judgement_files=[dict(path=p.relative_to(roots["quality20"]).as_posix(),sha256=sha(p)) for p in qfiles],
        quality_precision_pending=("보류" in qtext),status="S26_POLICY_TRAINING_HELD",
        reasons=["Q20 outcome is scoped to quality-runner; mixed APK quality transfer is not certified",
                 "GPU actual precision and mixed quality eligibility remain unresolved",
                 "mixed CPU1 seven intervals cannot inherit legacy MobileNet/CPU4/chunk coefficients",
                 "HAL brackets/energy coverage and state-identification gates do not yet approve a mixed cost profile"],
        new_fit=0,new_simulation=0,new_learning=0,device_commands=0,
        bulk_request_outputs_downloaded=False,legacy_holdout_script_executed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument("--workspace",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--attachment",action="append",default=[])
    a=p.parse_args();r=audit(a.workspace,a.attachment);write(a.output,r)
    print(json.dumps(dict(status=r["status"],sessions=len(r["sessions"]),
        requests=sum(s["journal_rows"] for s in r["sessions"]),
        interval_adapter_pass=sum(s["interval_adapter_pass"] for s in r["sessions"]),
        adapter_errors=sum(len(s["adapter_errors"]) for s in r["sessions"]),
        new_fit=0,new_simulation=0,new_learning=0,device_commands=0),ensure_ascii=False))


if __name__=="__main__":main()
