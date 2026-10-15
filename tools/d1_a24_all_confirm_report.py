"""PC-only report of the original40 across closed visits, without pooling retries.

Build a private, write-once hard-linked evidence view; reuse the frozen analysis
and plotting code. No ADB, engine execution, source/raw mutation, or calibration.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import statistics

from d1_a24_laptop_validator import load_json, sha256
from d1_a24_measurement_report import export, save_csv
from d1_a24_revision02_suite import require

ROOT=Path(__file__).resolve().parents[1]


def thermal_pair_eligibility(out):
    """Keep the frozen export, then exclude incomplete HAL windows from deltas.

    An observed maximum remains a descriptive sample statistic. It cannot be a
    comparable whole-window peak when either member has an ineligible gap.
    """
    with (out/'sessions.csv').open(encoding='utf-8-sig',newline='') as f:sessions=list(csv.DictReader(f))
    with (out/'paired.csv').open(encoding='utf-8-sig',newline='') as f:paired=list(csv.DictReader(f))
    from d1_a24_measurement_report import CONTRASTS
    for row in paired:
        spec=next(c for c in CONTRASTS if c[3]==row['comparison'])
        members=[s for s in sessions if (s['block'],s['recipe'])==(row['block'],spec[0]) and s['arm'] in spec[1:3]]
        good=len(members)==2 and all(s['thermal_window_status']=='READOUT_WINDOW_COVERED' for s in members)
        row['thermal_pair_eligible']=good
        if not good:
            for k in ['delta_mean_AP_c','delta_observed_peak_AP_c']:row[k]=None
    (out/'paired.csv').rename(out/'paired_frozen_export.csv');save_csv(out/'paired.csv',paired)
    with (out/'paired_intervals.csv').open(encoding='utf-8-sig',newline='') as f:intervals=list(csv.DictReader(f))
    from scipy.stats import t
    for row in intervals:
        if row['metric'] not in {'delta_mean_AP_c','delta_observed_peak_AP_c'}:continue
        values=[float(p[row['metric']]) for p in paired if p['comparison']==row['comparison'] and p.get(row['metric']) not in (None,'')]
        n=len(values);mean=statistics.mean(values) if n else None
        width=float(t.ppf(.975,n-1))*statistics.stdev(values)/n**.5 if n>=2 else None
        row.update(n_independent_blocks=n,mean=mean,lower95=mean-width if width is not None else None,
            upper95=mean+width if width is not None else None,
            method='unadjusted paired Student-t; exploratory; both original HAL windows must meet frozen gap bound')
    (out/'paired_intervals.csv').rename(out/'paired_intervals_frozen_export.csv');save_csv(out/'paired_intervals.csv',intervals)


def link_tree(source,destination):
    require(source.is_dir() and not source.is_symlink(),'raw directory missing/unsafe')
    destination.mkdir(parents=True,exist_ok=False)
    for path in source.rglob('*'):
        require(not path.is_symlink(),'raw symlink is not an immutable original')
        relative=path.relative_to(source);target=destination/relative
        if path.is_dir():target.mkdir(exist_ok=True)
        elif path.is_file():os.link(path,target)


def aggregate(jobfile,view,out,allow_snapshot=False):
    require(not view.exists() and not out.exists(),'fresh evidence view/output required')
    job=load_json(jobfile);binding=load_json(Path(job['global_binding']));plan=load_json(Path(job['plan']))
    require(plan['session_count']==len(plan['sessions'])==40 and all(r['stage']=='CONFIRM' for r in plan['sessions']),
            'this report is only for the exact original40')
    roots=[Path(x['root']) for x in binding['previous_visits']]+[Path(job['run_root'])]
    require(len({str(r) for r in roots})==len(roots),'duplicate visit roots')
    if not allow_snapshot:
        require(all((r/'WINDOW_STOPPED.json').exists() for r in roots),'original visit still running')
        require(not any((r/'ACTIVE_OWNER.json').exists() for r in roots[-1].parent.glob('A24*') if r.is_dir()),
                'a device worker is active; defer final report')
    view.mkdir(parents=True);(view/'raw').mkdir();(view/'logcat').mkdir();evidence=[]
    # Stream bounded prefixes to keep the laptop's small RAM available for DAQ.
    with (view/'adb_commands.jsonl').open('xb') as audit:
        for root in roots:
            for name in ['adb_commands.jsonl','measurement_adb_commands.jsonl']:
                path=root/name
                if not path.is_file():continue
                remaining=path.stat().st_size
                with path.open('rb') as stream:
                    while remaining:
                        line=stream.readline(remaining);remaining-=len(line)
                        if not line or not line.endswith(b'\n'):break
                        audit.write(line)
    for row in plan['sessions']:
        sid=row['session_id'];candidates=[]
        for root in roots:
            p=root/(sid+'.outcome.json')
            if p.exists():candidates.append((root,p,load_json(p)))
        executed=[x for x in candidates if x[2].get('APP_launch_intent') is not False]
        require(len(executed)<=1,'multiple actual outcomes for one original ID')
        chosen=executed[-1] if executed else None
        if not chosen:
            continue
        root,path,outcome=chosen
        os.link(path,view/path.name)
        item={'session_id':sid,'original_status':outcome['status'],'outcome_sha256':sha256(path),
            'source_visit':root.name,'raw_original_bytes_unchanged':True,'pooled_with_supplement':False}
        raw=root/'raw'/sid
        if outcome['status']=='COMPLETE_TRACE_RECOVERED':
            require(load_json(raw/'journal_closed.json')['status']=='SYNCED_AND_CLOSED','normal raw not closed')
            link_tree(raw,view/'raw'/sid)
            logfile=root/'logcat'/(sid+'.txt');os.link(logfile,view/'logcat'/logfile.name)
            item.update(events_sha256=sha256(raw/'events.jsonl'),journal_closed_sha256=sha256(raw/'journal_closed.json'))
        elif raw.exists():link_tree(raw,view/'raw'/sid)
        recovered=root/'read_only_recovery'/sid/'recovered_app'
        if recovered.exists():link_tree(recovered,view/'read_only_recovery'/sid/'recovered_app')
        registry=root/'registry'
        if registry.exists():
            for entry in registry.glob('**/'+sid+'/*.json'):
                dest=view/entry.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True)
                os.link(entry,dest)
        if (root/'references').exists():
            dest=view/'references';dest.mkdir(exist_ok=True)
            for p in (root/'references').glob('*.json'):
                q=dest/p.name
                if q.exists():require(sha256(q)==sha256(p),'same block reference changed across visits')
                else:os.link(p,q)
        evidence.append(item)
    derived={**job,'run_root':str(view)}
    (view/'DERIVED_REPORT_JOB_NOT_EXECUTABLE.json').write_text(json.dumps(derived,indent=2)+'\n',encoding='utf-8')
    # Keep the exact original plan; the read-only view changes only where its
    # closed observations are found, never their IDs/settings/denominator.
    contract=load_json(ROOT/'output/a24_confirmation40_frozen_window01_20261015/ANALYSIS_ENGINE_ADAPTER.json')
    export(derived,contract,out,'CONFIRM')
    thermal_pair_eligibility(out)
    provenance=load_json(out/'provenance.json')
    provenance.update(original_execution_plan_sha256=sha256(Path(job['plan'])),original_planned_sessions=40,
        original_planned_requests=sum(x['request_count'] for x in plan['sessions']),
        historical_failures_and_unattempted_not_replaced=True,additional_retries_pooled=False,
        final_report_not_device_or_calibrated_energy_PASS=True,read_only_snapshot=allow_snapshot,
        source_visit_labels=[r.name for r in roots],source_evidence=evidence)
    (out/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={'original40_preserved':True,'normal_completed':provenance['complete_sessions'],
        'original_failure_records_preserved':sum(x['original_status']!='COMPLETE_TRACE_RECOVERED' for x in evidence),
        'original_unattempted':40-len(evidence),'energy_J':None,'surface_temperature_verified':False,
        'additional_post_observation_replications_pooled':False,'device_commands':0}
    (out/'COUNTS.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('private_view',type=Path);p.add_argument('report',type=Path)
    p.add_argument('--closed-snapshot-only',action='store_true');a=p.parse_args()
    print(json.dumps(aggregate(a.job,a.private_view,a.report,a.closed_snapshot_only)))
