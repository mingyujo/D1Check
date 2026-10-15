"""PC-only report of one registered supplemental family, never pooled with40.

Only closed, unique actual outcomes are read. A new immutable hardlink view
joins visits without altering a raw byte or treating failure repeats as success.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import os
import subprocess

from d1_a24_laptop_validator import load_json,sha256
from d1_a24_revision02_suite import require
from d1_a24_measurement_report import export
from d1_a24_all_confirm_report import link_tree,thermal_pair_eligibility,ap_gap_figure,energy_unvalidated_figure

ROOT=Path(__file__).resolve().parents[1]


def unique_actual(candidates):
    actual=[x for x in candidates if x[2].get('APP_launch_intent') is not False]
    require(len(actual)<=1,'duplicate execution of a registered ID; do not choose favorable outcome')
    return actual[0] if actual else None


def report(jobfile,roots,view,out):
    job=load_json(jobfile);plan=load_json(Path(job['plan']));rows=plan['sessions']
    require(plan.get('analysis_role') in {
        'POST_OBSERVATION_FAILED_CASE_REPLICATION_NOT_INDEPENDENT_CONFIRM',
        'POST_OBSERVATION_MATCHED_REPLICATION_NOT_INDEPENDENT_CONFIRM',
        'POST_FAILURE_INSTRUMENTATION_MATCHED_PAIR_NOT_CONFIRM',
        'POST_OBSERVATION_REBASELINE_REPLICATION_NOT_INDEPENDENT_CONFIRM40'},'not a separate registered supplemental family')
    require(plan.get('pooled_with_original_confirm') is False and len(rows)==plan['session_count']
        and all(r['stage']=='DEV' for r in rows),'do not reinterpret original confirmation')
    require(not view.exists() and not out.exists(),'write-once report/view required')
    require(roots and len({str(p.resolve()) for p in roots})==len(roots),'duplicate/missing source roots')
    require(all((r/'WINDOW_STOPPED.json').exists() for r in roots),'source visit still active')
    require(not any((p/'ACTIVE_OWNER.json').exists() for p in roots[0].parent.glob('A24*') if p.is_dir()),
        'device worker still active; defer heavy reporting')
    view.mkdir(parents=True);(view/'raw').mkdir();(view/'logcat').mkdir();evidence=[]
    with (view/'adb_commands.jsonl').open('xb') as dest:
        for root in roots:
            for name in ['adb_commands.jsonl','measurement_adb_commands.jsonl']:
                source=root/name
                if not source.exists():continue
                with source.open('rb') as stream:
                    for line in stream:
                        require(line.endswith(b'\n'),'closed audit has truncated record');dest.write(line)
    for row in rows:
        sid=row['session_id'];candidates=[]
        for root in roots:
            p=root/(sid+'.outcome.json')
            if p.exists():candidates.append((root,p,load_json(p)))
        chosen=unique_actual(candidates)
        if not chosen:continue
        root,path,outcome=chosen;os.link(path,view/path.name);raw=root/'raw'/sid
        if raw.exists():link_tree(raw,view/'raw'/sid)
        if outcome['status']=='COMPLETE_TRACE_RECOVERED':
            require(load_json(raw/'journal_closed.json')['status']=='SYNCED_AND_CLOSED','normal source not closed')
            log=root/'logcat'/(sid+'.txt');os.link(log,view/'logcat'/log.name)
        recovery=root/'read_only_recovery'/sid/'recovered_app'
        if recovery.exists():link_tree(recovery,view/'read_only_recovery'/sid/'recovered_app')
        for p in (root/'registry').glob('**/'+sid+'/*.json'):
            q=view/p.relative_to(root);q.parent.mkdir(parents=True,exist_ok=True);os.link(p,q)
        for p in (root/'references').glob('*.json'):
            q=view/'references'/p.name;q.parent.mkdir(exist_ok=True)
            if q.exists():require(sha256(q)==sha256(p),'reference changed between visits')
            else:os.link(p,q)
        manifest=raw/'session_manifest.json'
        evidence.append({'session_id':sid,'original_status':outcome['status'],'source_visit':root.name,
            'outcome_sha256':sha256(path),'source_manifest_sha256':load_json(manifest).get('source_manifest_sha256') if manifest.exists() else None,
            'raw_original_bytes_unchanged':True})
    derived={**job,'run_root':str(view)}
    (view/'DERIVED_REPORT_JOB_NOT_EXECUTABLE.json').write_text(json.dumps(derived,indent=2)+'\n',encoding='utf-8')
    contract=load_json(ROOT/'output/a24_confirmation40_frozen_window01_20261015/ANALYSIS_ENGINE_ADAPTER.json')
    export(derived,contract,out,'DEV');thermal_pair_eligibility(out);ap_gap_figure(out);energy_unvalidated_figure(out)
    provenance=load_json(out/'provenance.json');provenance.update(analysis_role=plan['analysis_role'],
        additional_retries_pooled_with_original40=False,source_evidence=evidence,
        original_failure_outcomes_preserved=True,report_generated_UTC=dt.datetime.now(dt.timezone.utc).isoformat(),
        report_helper_sha256=sha256(Path(__file__)),
        report_source_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        report_worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip()),
        mixed_source_manifest_bindings_disclosed=True,one_post_observation_block_is_not_independent5block_confirmation=True)
    (out/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'registered':len(rows),'normal':provenance['complete_sessions'],'analysis_role':plan['analysis_role'],
        'original40_pooled':False,'device_commands':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('private_view',type=Path);p.add_argument('report',type=Path)
    p.add_argument('--closed-root',type=Path,action='append',required=True);a=p.parse_args()
    print(json.dumps(report(a.job,a.closed_root,a.private_view,a.report)))
