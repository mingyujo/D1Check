"""Build isolated archived fixtures; never create production output or a claim."""
import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import d1_ap_background_contrast as m
from tools import d1_ap_background_contrast_readout as readout


def build(archive,output,mode):
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True);folder=output/'fixture_plan';folder.mkdir()
    evidence=output/'archived_copies';evidence.mkdir()
    plan=copy.deepcopy(m.p.read(archive/'energy_ap_memory_confirm_plan_v1/collection_plan.json'))
    plan.update(experiment_id=m.EXPERIMENT,source_code=m.identity(),ap_background_contrast=True,
        output_root=str(evidence),registry=str(output/'unused_fixture_registry'),entries=[],
        analysis_contract={'path':str(m.BUNDLE/'analysis_contract.json'),'sha256':m.p.digest(m.BUNDLE/'analysis_contract.json')})
    originals={}
    sources={
        'C':archive/'energy_ap_resident_control_run_v3/00_b7fba334-03c5-521c-b420-6825d37a5a8f',
        'L35':archive/'energy_ap_memory_confirm_run_v1/00_ab81488e-c00f-58b7-b10f-a77b93106c2e',
        'L65':archive/'energy_ap_memory_confirm_run_v1/01_6386ece5-6935-5d25-98b1-4077e2c5d96b'}
    for i,(role,condition) in enumerate(zip(m.ROLES,m.CONDITIONS)):
        source=sources[condition];dest=evidence/f'{i:02d}_fixture{i}';(dest/'artifacts').mkdir(parents=True)
        for name in ('thermal.jsonl','validated.json','artifacts/manifest.json','artifacts/common_boundary.json',
                     'artifacts/cleanup.json','artifacts/requests.json','artifacts/progress.jsonl','artifacts/start_ap.accepted.json'):
            f=source/name;originals[str(f.relative_to(archive))]=m.p.digest(f)
            shutil.copyfile(f,dest/name)
        manifest=m.p.read(dest/'artifacts/manifest.json')
        manifest.update(resident_control_version=m.memory.base.control.VERSION,
                        resident_control_role='no_load_control' if condition=='C' else 'registered_load')
        # Only fixture manifests receive generic control tags. No original is changed.
        file=folder/f'{i}.json';m.cal.write_new(file,manifest)
        (dest/'artifacts/manifest.json').write_bytes(file.read_bytes())
        plan['entries'].append(dict(index=i,session_id=f'fixture{i}',phase=role,condition=condition,
            manifest=file.name,manifest_sha256=m.p.digest(file),requests=0 if condition=='C' else 24))
        if mode=='missing_ap' and i==0:
            boundary=m.p.read(dest/'artifacts/common_boundary.json')['start_ns']
            rows=[json.loads(s) for s in (dest/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
            for row in rows:
                if row['mono_ns']>=boundary+35_000_000_000:row['AP']=''
            (dest/'thermal.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in rows),encoding='utf-8')
        if mode=='partial' and i==2:
            (dest/'validated.json').write_text('{"status":"failed"}\n',encoding='utf-8')
    for key,name in [('memory_candidate','memory_candidate_freeze.json'),('analysis_contract','memory_analysis_contract.json')]:
        (evidence/name).write_bytes(Path(plan[key]['path']).read_bytes())
    m.cal.write_new(evidence/'FINAL_RECEIPT.json',dict(status='PC_FIXTURE_NOT_A_DEVICE_EXECUTION',session_attempts=6))
    file=folder/'collection_plan.json';m.cal.write_new(file,plan)
    result=readout.report(file,output/'readout',fixture=True)
    statuses=[s['status'] for s in result['sessions']]
    assert statuses==(['not_evaluable' if i==0 and mode=='missing_ap' or i==2 and mode=='partial' else 'evaluated_fixed_candidate' for i in range(6)])
    assert [c['planned_requests'] for c in result['consumption']]==[0,24,24,24,24,0]
    if mode!='complete':assert all(v['L35_minus_C'] is None for v in result['contrasts'])
    for name,h in originals.items():assert m.p.digest(archive/name)==h,name
    record=dict(mode=mode,statuses=statuses,device_commands=0,production_claims=0,
        original_files_verified=len(originals),source_sha256=originals,
        meaning='same three archived sessions duplicated only to exercise six parser slots; not six independent data')
    m.cal.write_new(output/'fixture_verification.json',record)
    return record


if __name__=='__main__':
    q=argparse.ArgumentParser(description=__doc__);q.add_argument('--archive',type=Path,required=True)
    q.add_argument('--output',type=Path,required=True);q.add_argument('--mode',choices=['complete','missing_ap','partial'],default='complete')
    a=q.parse_args();print(json.dumps(build(a.archive,a.output,a.mode),indent=2))
