"""Separate missing-condition confirmation. prepare/check are PC-only; no refit."""
import argparse
import copy
from pathlib import Path
import time
import uuid
import json
from tools import d1_arrival_collection as c

EXPERIMENT='ARRIVAL-CONFIRM-FOLLOWUP-01'
ORDER=('shadow_cpu_sparse','active_cpu_sparse','shadow_split_queue_lanes')
OLD_CONFIRMED=('shadow_split_queue_serial','shadow_cpu_queue','shadow_split_sparse')

def evidence_gate(plan):
    for name,sha in plan['parent_evidence'].items():c.v.require(c.p.digest(name)==sha,'parent evidence changed')
    old=c.p.read(plan['parent_plan']);freeze=c.p.read(plan['frozen_development'])
    c.v.require(freeze['plan_sha256']==c.p.digest(plan['parent_plan']) and
        c.p.digest(plan['frozen_development'])==plan['frozen_development_sha256'],'old development freeze binding')
    for name,sha in freeze['input_hashes'].items():c.v.require(c.p.digest(name)==sha,'development artifact changed')
    stop=c.p.read(Path(old['registry'])/'stopped.json')
    c.v.require(stop['completed']==3 and stop['attempts']==4 and stop['stage']=='stage_inputs','parent partial denominator changed')
    for e in old['entries']:
        if e['phase']=='development' or e['condition'] in OLD_CONFIRMED:
            folder=Path(old['output_root'])/e['phase']/f"{e['index']:02d}_{e['session_id']}"
            c.verify_recovery(folder)
            c.v.require(c.p.read(folder/'host_cleanup.json')['status']=='completed','parent cleanup')

def prepare(parent,freeze,output):
    parent,freeze,output=map(Path,(parent,freeze,output))
    c.v.require(not output.exists(),'new plan directory required')
    old=c.p.read(parent);c.v.require(old['experiment_id']=='ARRIVAL-COLLECT-03','wrong parent')
    p=copy.deepcopy(old)
    for key in ('recovery_receipt','workflow_root'):p.pop(key,None)
    evidence=[parent,freeze,Path(old['registry'])/'stopped.json',Path(old['workflow_root'])/'stopped.json',
        Path(old['registry'])/'confirmation_consumed.json']
    p.update(experiment_id=EXPERIMENT,installation_contract='followup-exact-installed-v1',
        status='PREPARED_NOT_APPROVED',source_code=c.identity(),parent_plan=str(parent.resolve()),
        frozen_development=str(freeze.resolve()),frozen_development_sha256=c.p.digest(freeze),
        parent_evidence={str(f.resolve()):c.p.digest(f) for f in evidence},
        registry=str(output.parent/'collection_execution_registry'/EXPERIMENT),
        output_root=str(output.parent/'confirmation_followup_run_v1'),session_cap=3,request_cap=12,warmup_cap=24,
        install_cap=0,host_phase_wall_seconds=1755,cleanup_seconds=45,maximum_active_seconds=1800,
        adb_exe='C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe',
        adb_sha256=c.p.digest('C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe'),
        parallel_gate='immutable six development + three prior confirmation validated; current two serial sessions validated+cleanup; current admission; two host-API overlaps',
        freeze_rule='reuse original development freeze only; no new development/no refit',
        combination_rule='condition-stratified descriptive comparison to old freeze; preserve separate plan denominators; dates/order/host observation differ; never relabel original complete',
        analysis_contract='three missing conditions only; one independent new session per condition; no CI/tail/accuracy or policy PASS')
    evidence_gate(p)
    c.v.require(c.cal.apk_sources(c.p.read(old['build_receipt'])['source_code'])==c.cal.apk_sources(c.identity()),'Android source changed')
    output.mkdir(parents=True);(output/'manifests').mkdir();p['entries']=[]
    for i,condition in enumerate(ORDER):
        e=next(e for e in old['entries'] if e['phase']=='confirmation' and e['condition']==condition)
        m=c.p.read(parent.parent/e['manifest']);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{EXPERIMENT}/{old["seed"]}/{condition}'))
        m.update(session_id=sid,experiment_id=EXPERIMENT)
        for spec in m['models'].values():spec['identity']['session_id']=sid
        for key in ('requests','warmup_requests'):
            for n,q in enumerate(m[key]):q['request_id']=str(uuid.uuid5(uuid.UUID(sid),f'{key}/{n}'))
        f=output/'manifests'/f'{sid}.json';c.cal.write_new(f,m)
        p['entries'].append(dict(index=i,session_id=sid,phase='confirmation',condition=condition,
            manifest='manifests/'+f.name,manifest_sha256=c.p.digest(f)))
    c.cal.write_new(output/'collection_plan.json',p)
    return check(output/'collection_plan.json')

def check(path):
    from tools import d1_apk_identity as apk
    p=c.p.read(path);c.v.require(p['experiment_id']==EXPERIMENT,'namespace')
    result=c.check(path);evidence_gate(p)
    c.v.require(c.p.digest(p['adb_exe'])==p['adb_sha256'],'ADB executable changed')
    for key,sha in p['apk_preflight']['tool_sha256'].items():c.v.require(c.p.digest(p['apk_preflight']['toolchain'][key])==sha,'signature tool changed')
    c.v.require(apk.inspect(p['apk_path'],p['apk_preflight']['toolchain'])==p['apk_preflight']['candidate'],'APK signature/identity changed')
    old=c.p.read(p['parent_plan'])
    for e in p['entries']:
        m=c.p.read(Path(path).parent/e['manifest'])
        oe=next(x for x in old['entries'] if x['phase']=='confirmation' and x['condition']==e['condition'])
        om=c.p.read(Path(p['parent_plan']).parent/oe['manifest'])
        def semantics(m):
            m=copy.deepcopy(m)
            for key in ('session_id','experiment_id'):m.pop(key)
            for spec in m['models'].values():spec['identity'].pop('session_id')
            for key in ('requests','warmup_requests'):
                for q in m[key]:q.pop('request_id')
            return m
        c.v.require(semantics(m)==semantics(om),'workload/Android contract changed')
        c.v.require(e['session_id'] not in {x['session_id'] for x in old['entries']},'reused session')
    return dict(collection=result,explicit_inferences=36,install_cap=0,total_seconds=1800,approval='REQUIRED',device_calls=0)

def run(path,serial,approved,expected):
    c.v.require(approved and c.p.digest(path)==expected,'explicit new confirmation budget/hash approval required')
    check(path);p=c.p.read(path)
    c.v.require(not Path(p['registry']).exists() and not Path(p['output_root']).exists(),'consumed; no resume')
    from tools import d1_arrival_collection_device as runner
    start=time.monotonic()
    result=runner.run(path,'confirmation',p['adb_exe'],serial,3,expected,p['frozen_development'],overall_deadline=start+1800)
    stats=c.summarize(path,'confirmation');frozen=c.p.read(p['frozen_development'])
    stats['frozen_development_sha256']=p['frozen_development_sha256']
    stats['median_errors']={key:{name:metric['median']-frozen['conditions'][key]['metrics'][name]['median']
        for name,metric in row['metrics'].items()} for key,row in stats['conditions'].items()}
    stats['combination_rule']=p['combination_rule'];stats['original_plan_complete']=False
    c.cal.write_new(Path(p['output_root'])/'followup_analysis.json',stats)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('prepare')
    for arg in ('parent','freeze','output'):s.add_argument('--'+arg,required=True)
    for action in ('check','run'):
        s=sub.add_parser(action);s.add_argument('--plan',required=True)
        if action=='run':
            s.add_argument('--serial',required=True);s.add_argument('--approved',action='store_true');s.add_argument('--expected-sha256',required=True)
    a=parser.parse_args()
    result=prepare(a.parent,a.freeze,a.output) if a.cmd=='prepare' else check(a.plan) if a.cmd=='check' else run(a.plan,a.serial,a.approved,a.expected_sha256)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
