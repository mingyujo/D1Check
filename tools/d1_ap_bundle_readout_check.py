"""PC-only bundle readout verification with copied historical raw fixtures.

Creates analysis-only fixtures, never a runnable device plan, registry or claim.
The original development/confirmation roles remain provenance, not new trials.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from tools import d1_ap_bundle_confirmation as bundle
from tools import d1_ap_transfer_confirmation as transfer
from tools import d1_ap_transfer_report as graphics


FILES=('validated.json','thermal.jsonl','launch_attempt.json','host_cleanup.json',
       'artifacts/manifest.json','artifacts/common_boundary.json','artifacts/requests.json',
       'artifacts/progress.jsonl','artifacts/start_ap.accepted.json','artifacts/cleanup.json')


def save(file,value):
    file.parent.mkdir(parents=True,exist_ok=True);graphics.save(file,value)


def close(a,b):
    if not math.isclose(float(a),float(b),rel_tol=1e-9,abs_tol=1e-8):
        raise AssertionError(f'numerical reproduction differs: {a} vs {b}')


def check(source_plan,output):
    source_plan,output=Path(source_plan),Path(output).resolve()
    source=transfer.p.read(source_plan);raw=Path(source['output_root']).resolve()
    for protected in (raw,source_plan.parent.resolve(),Path(source['registry']).resolve()):
        if output==protected or protected in output.parents:raise ValueError('protected original output')
    if output.exists():raise FileExistsError('fresh PC verification output only')
    if len(source['entries'])!=2:raise ValueError('exact historical two-session source required')
    original=Path(source['frozen_model']['path']);candidate=raw/'ap_model_freeze.json'
    if transfer.p.digest(original)!=transfer.replay.FROZEN_SHA or transfer.p.digest(candidate)!=transfer.FREEZE_SHA:
        raise ValueError('historical freeze changed')
    expected_file=bundle.ROOT/'docs/results/energy_ap_idle_response_01/run01/summary.json'
    expected=transfer.p.read(expected_file)['summaries']
    protected_files=[source_plan,original,candidate,raw/'FINAL_RECEIPT.json',expected_file]
    for e in source['entries']:
        folder=raw/f"{e['index']:02d}_{e['session_id']}"
        protected_files.extend(folder/name for name in FILES)
    before={f:transfer.p.digest(f) for f in protected_files}
    output.mkdir(parents=True)
    results=[]
    for case in ('complete','partial_progress','power_gap','ap_gap'):
        root=output/case;plan_dir=root/'fixture_plan';plan_dir.mkdir(parents=True)
        run=root/'historical_copy';run.mkdir()
        shutil.copy2(raw/'FINAL_RECEIPT.json',run/'FINAL_RECEIPT.json')
        entries=[]
        for i,(e,role) in enumerate(zip(source['entries'],bundle.ROLES)):
            src=raw/f"{e['index']:02d}_{e['session_id']}";dest=run/f"{i:02d}_{e['session_id']}"
            for name in FILES:
                target=dest/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(src/name,target)
            manifest=plan_dir/f'manifest{i}.json'
            shutil.copy2(src/'artifacts/manifest.json',manifest)
            entries.append(dict(index=i,phase=role,session_id=e['session_id'],manifest=manifest.name,
                                manifest_sha256=transfer.p.digest(manifest),source_role=e['phase']))
        for f,name in ((original,'original_freeze.json'),(candidate,'candidate_freeze.json')):
            shutil.copy2(f,plan_dir/name)
        contract=plan_dir/'analysis_contract.json'
        shutil.copy2(bundle.BUNDLE/'analysis_contract.json',contract)
        plan=dict(experiment_id=bundle.EXPERIMENT,fixture_only=True,
            status='PC_HISTORICAL_REPLAY_NOT_EXECUTABLE',approval='not_approved_no_device_executor',
            source_code=bundle.identity(),entries=entries,output_root=str(run),registry=str(root/'NO_REGISTRY'),
            frozen_model={'path':str(plan_dir/'original_freeze.json')},
            candidate_freeze={'path':str(plan_dir/'candidate_freeze.json')},
            analysis_contract={'path':str(contract),'sha256':transfer.p.digest(contract)})
        file=plan_dir/'collection_plan.json';save(file,plan)
        second=run/f"01_{entries[1]['session_id']}"
        if case=='partial_progress':
            progress=second/'artifacts/progress.jsonl';lines=progress.read_bytes().splitlines(keepends=True)
            end=next(i+1 for i,line in enumerate(lines) if json.loads(line)['kind']=='request_start')
            progress.write_bytes(b''.join(lines[:end])+b'{"partial":"\xe2\x82')
            (second/'validated.json').unlink()
            (second/'artifacts/cleanup.json').write_bytes(b'{')
            receipt=transfer.p.read(run/'FINAL_RECEIPT.json')
            receipt.update(status='stopped_no_resume',original_error='PC injection: second retrieval interrupted')
            save(run/'FINAL_RECEIPT.json',receipt)
        elif case in ('power_gap','ap_gap'):
            origin=transfer.p.read(second/'artifacts/common_boundary.json')['start_ns']
            if case=='power_gap':
                progress=second/'artifacts/progress.jsonl'
                rows=[json.loads(line) for line in progress.read_bytes().splitlines()]
                for r in rows:
                    if r['kind']=='power_sample' and 60<=(r['snapshot_start_ns']-origin)/1e9<=66:
                        r['current_valid']=False
                progress.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
            else:
                thermal=second/'thermal.jsonl';rows=[json.loads(line) for line in thermal.read_bytes().splitlines()]
                for r in rows:
                    if 90<=(r['mono_ns']-origin)/1e9<=115:r['AP']=''
                thermal.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
        # Fresh Python process, real parser/numerical/CSV/figure/HTML entrypoint.
        command=[sys.executable,'-X','utf8','-B','-m','tools.d1_ap_bundle_readout',
                 '--plan',str(file),'--output',str(root/'report'),
                 '--evidence-label','PC fixture replay - historical data, NOT NEW MEASUREMENTS']
        with (root/'stdout.txt').open('wb') as stdout,(root/'stderr.txt').open('wb') as stderr:
            result=subprocess.run(command,cwd=bundle.ROOT,stdout=stdout,stderr=stderr,timeout=90,check=False)
        save(root/'entrypoint.json',{'exit_code':result.returncode,'command':command,'device_commands':0})
        if result.returncode!=0:raise AssertionError(f'PC entrypoint failed: {case}; see stderr.txt')
        summary=transfer.p.read(root/'report/summary.json')
        if summary['expected_sessions']!=2 or summary['device_commands_by_analysis']!=0:
            raise AssertionError('lost denominator/device boundary')
        item=dict(case=case,status=summary['readout_status'],evaluated_sessions=summary['evaluated_sessions'],
                  entrypoint_exit=result.returncode,source_roles=[e['source_role'] for e in entries],sessions=[])
        for i,row in enumerate(summary['sessions']):
            scores=row['scores']
            if case=='complete' or i==0:
                if scores is None:raise AssertionError(f'unexpected ineligibility in {case}: {row}')
                close(scores['observed_energy_120s_j'],expected[i]['observed_energy_120s_j'])
                for model in ('frozen','candidate'):
                    close(scores['ap_scores'][model]['mae_c'],expected[i][model]['mae_c'])
                    close(scores['ap_scores'][model]['max_absolute_error_c'],expected[i][model]['max_absolute_error_c'])
                data=root/'report'/row['role'];graphics.validate_tables(data,scores)
                for name in ('energy','ap'):
                    if 'PC TEST FIXTURE' not in (data/(name+'.svg')).read_text(encoding='utf-8'):
                        raise AssertionError('missing PC stamp')
                    if (data/(name+'.png')).stat().st_size<5000:raise AssertionError('empty rendered figure')
                if str(scores['signed_energy_error_j']) not in (root/'report/index.html').read_text(encoding='utf-8'):
                    raise AssertionError('HTML score differs')
                if any(abs(float(r['signed_error_j']))>1e9 for r in graphics.rows(data/'energy_path.csv')):
                    raise AssertionError('invalid cumulative energy')
            elif scores is not None or list((root/'report'/row['role']).glob('*.svg')):
                raise AssertionError('incomplete session promoted to whole-window scores/figures')
            item['sessions'].append(dict(status=row['status'],
                observed_energy_120s_j=scores['observed_energy_120s_j'] if scores else None,
                candidate_mae_c=scores['ap_scores']['candidate']['mae_c'] if scores else None,
                frozen_mae_c=scores['ap_scores']['frozen']['mae_c'] if scores else None,
                rendering_status=row['rendering_status']))
        if case=='partial_progress':
            c=summary['consumption'][1]
            if c['progress_integrity']['status']!='partial_prefix' or c['counts']['request_start']!=1:
                raise AssertionError('partial consumption prefix lost')
            if summary['receipt']['original_error']!='PC injection: second retrieval interrupted':
                raise AssertionError('primary failure overwritten')
            item['partial_event_lower_bounds']=c['counts']
        if (root/'NO_REGISTRY').exists() or list(root.rglob('claimed.json')):
            raise AssertionError('PC replay created an execution claim')
        results.append(item)
    if before!={f:transfer.p.digest(f) for f in protected_files}:raise AssertionError('original evidence changed')
    verification=dict(status='passed',cases=results,source_data_role='already observed development and confirmation, posthoc PC replay',
        new_independent_sessions=0,device_commands=0,claims_created=0,model_fits=0,
        original_evidence_files_preserved=len(before),original_freeze_sha256=transfer.replay.FROZEN_SHA,
        candidate_freeze_sha256=transfer.FREEZE_SHA,
        analysis_source_sha256=transfer.p.digest(bundle.ROOT/'tools/d1_ap_bundle_readout.py'))
    save(output/'verification.json',verification)
    return verification


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-plan',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(check(args.source_plan,args.output),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
