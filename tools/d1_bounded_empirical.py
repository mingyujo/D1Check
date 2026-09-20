"""Thirty-session descriptive empirical design; no device I/O on import/generate.

Execution requires a separate explicit `execute` invocation. No simulation lives
in this module. Historical predictive contracts are not edited or reinterpreted.
"""
import argparse
import copy
import json
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys

from tools import d1_empirical_plan as old
from tools import d1_telemetry_v4 as v

PROTOCOL='bounded-descriptive-empirical-v1'
SEED=2026092102
FAMILIES=['solo/'+c for c in old.CELLS]+['resident_cpu_serial','resident_corun']
SCHEMA=Path(__file__).with_name('schemas')/'bounded-empirical-plan-v1.schema.json'


def contract():
    return dict(scope='A24/current classification-detection models/thermal0/v4/resident-only',
        sessions=30,solo_per_cell=5,pairs=5,independent_holdout=0,
        runtime_transition=False,population_cold_p95_gate=False,request_PI_gate=False,
        max_device_attempts=30,reruns_per_session=0,replacement_sessions=0,
        failed_attempt='preserve and stop; incomplete; no successful-sample substitution',
        memory=v.MEMORY,thermal=[0],fallback=False,
        completeness=1,output_equivalence=1,
        states={'cold_first':[1],'early_after_cold':[2],'settling':[3,4,5,6],'warm_observed':[7,8,9,10,11,12]},
        warm_claim='ordinal observed after fixed six calls, no stationary-population guarantee',
        bootstrap={'unit':'session; paired contrast uses pair','replicates':2000,'confidence':.95,'gate_on_width':False},
        loso='descriptive sensitivity only, never independent holdout',
        sensitivity={'low':'whole block with minimum total worker occupancy',
                     'central':'whole block with median total worker occupancy',
                     'high':'whole block with maximum total worker occupancy',
                     'cold_stress':'whole block with maximum first+second active service; no synthetic field inflation'},
        deadline={'status':'calibration_pending','urgent_quantiles':[.5,.9],
                  'urgent_multipliers':[.75,1.,1.5], 'cold_and_warm':'separate scenarios; cold service plus setup once',
                  'normal_multipliers':[.75,1.,1.5], 'normal_formula':'relative deadline=max(0,H-arrival)+multiplier*D_cpu',
                  'H':'last planned arrival minus first planned arrival',
                  'D_cpu':'sum of fixed CPU solo central empirical service demands for the common task sequence',
                  'policy_invariant':True,'report_all':True},
        baselines=['FIFO_CPU','EDF_CPU','fixed_feasible_backend','static_task_backend','adaptive'],
        crn='draw key excludes policy; same scenario/replicate family-rank ticket; pair sampled jointly',
        performance_claim='direction, observed magnitude, bootstrap uncertainty; otherwise inconclusive')


def build_plan(templates,registry,seed=SEED):
    entries=[];manifests={}
    for i in range(5):
        order='AB' if (i+seed%2)%2==0 else 'BA'
        families=FAMILIES[:4].copy();random.Random(f'{seed}/{i}').shuffle(families)
        families+=FAMILIES[4:] if order=='AB' else FAMILIES[4:][::-1]
        for family in families:
            sid=old.uid(PROTOCOL,seed,i,family);pair=family.startswith('resident_')
            entry=dict(session_id=sid,family=family,replicate=i,seed=int(v.sha([PROTOCOL,seed,i])[:8],16),
                       output_root='sessions/'+sid,pair_id=old.uid(PROTOCOL,seed,i,'pair') if pair else None,
                       pair_order=order if pair else None,execution_supported=True)
            m=old.native_manifest(entry,templates)
            v.manifest(m,registry['sessions']+registry['requests'])
            entries.append(entry);manifests[sid]=m
    result=dict(protocol=PROTOCOL,schema_version=1,seed=seed,contract=contract(),
                registry_sha256=v.sha(registry),entries=entries,manifests=manifests)
    return result


def validate_plan(plan,templates,registry):
    import jsonschema
    jsonschema.validate(plan,v.read(SCHEMA))
    if plan!=build_plan(templates,registry,plan['seed']):raise ValueError('frozen plan/manifest altered')
    ids=[e['session_id'] for e in plan['entries']]
    if len(ids)!=30 or len(set(ids))!=30 or set(ids)&set(registry['sessions']):raise ValueError('count/replay')
    all_ids=[]
    for m in plan['manifests'].values():
        all_ids += [m['session_id']]+[r['runtime_id'] for r in m['runtimes']]+[q['request_id'] for q in m['warmup_requests']+m['requests']]
    if len(all_ids)!=len(set(all_ids)):raise ValueError('cross-session identity reuse')
    for i in range(5):
        a,b=pair_manifests(plan,i);v.paired(a,b,consumed=registry['sessions']+registry['requests'])
    return True


def pair_manifests(plan,i):
    def find(f):return plan['manifests'][next(e['session_id'] for e in plan['entries'] if e['replicate']==i and e['family']==f)]
    return find('resident_cpu_serial'),find('resident_corun')


def admit_attempt(plan,sid,attempted):
    if len(attempted)!=len(set(attempted)) or len(attempted)>=30 or sid in attempted:
        raise ValueError('retry/global cap')
    if sid not in plan['manifests']:raise ValueError('unplanned replacement')
    return True


def ingest(root,log,entry,plan,registry):
    m=plan['manifests'][entry['session_id']]
    b=old.make_block(root,v.sha(m),log,registry)
    if b['manifest']!=m:raise ValueError('native manifest does not match frozen plan')
    return b


def approve_blocks(blocks,plan):
    ids=[b['session_id'] for b in blocks]
    if len(ids)!=30 or set(ids)!=set(plan['manifests']) or len(set(ids))!=30:
        raise ValueError('incomplete/partial pair/replayed block')
    byid={b['session_id']:b for b in blocks}
    for sid,b in byid.items():
        if b['manifest']!=plan['manifests'][sid] or b['terminal_outcome']!='succeeded':raise ValueError('failed/altered block')
        # Raw-source validation is mandatory in ingest, this verifies the view again.
        receipt=v.validate_events(b['manifest'],b['events'])
        if len(receipt['samples'])!=len(b['receipt']['samples']):raise ValueError('incomplete joint block')
        for raw,view in zip(receipt['samples'],b['receipt']['samples']):
            if any(view.get(k)!=value for k,value in raw.items()):raise ValueError('cross-session field mixing')
            if view.get('provenance_sha256')!=b['source_provenance_sha256']:raise ValueError('joint provenance')
    for i in range(5):
        a,b=pair_manifests(plan,i);rs=[byid[a['session_id']]['receipt'],byid[b['session_id']]['receipt']]
        rs.sort(key=lambda r:r['session_start_ns']);v.paired(a,b,rs)
    return dict(status='DESCRIPTIVE_DATA_COMPLETE',sessions=30,pairs=5,predictive_approval=False)


def ticket(seed,replicate,scenario='central'):
    """A common random number independent of policy and policy dispatch order."""
    return int(v.sha([PROTOCOL,seed,replicate,scenario])[:16],16)


def select_joint(blocks,seed,replicate,scenario='resample'):
    if not blocks or len({b['session_id'] for b in blocks})!=len(blocks):raise ValueError('empty/duplicate catalog')
    if scenario=='resample':return copy.deepcopy(sorted(blocks,key=lambda b:b['session_id'])[ticket(seed,replicate,scenario)%len(blocks)])
    if scenario not in ('low','central','high','cold_stress'):raise ValueError('unsupported scenario')
    def score(b):
        samples=b['receipt']['samples']
        return sum(s['active_service_ns'] for s in samples if s['runtime_state']['invocation']<=2) if scenario=='cold_stress' else sum(s['worker_occupancy_ns'] for s in samples)
    ranked=sorted(blocks,key=lambda b:(score(b),b['session_id']))
    index=0 if scenario=='low' else (len(ranked)-1)//2 if scenario=='central' else len(ranked)-1
    return copy.deepcopy(ranked[index])


def select_pair(pairs,seed,replicate,scenario='resample'):
    if not pairs or len({p['pair_id'] for p in pairs})!=len(pairs) or any(set(p)!= {'pair_id','A','B'} for p in pairs):
        raise ValueError('partial/duplicate pair pool')
    # One selection returns both native session blocks, never two independent draws.
    proxies=[dict(session_id=p['pair_id'],receipt={'samples':p['A']['receipt']['samples']+p['B']['receipt']['samples']}) for p in pairs]
    selected=select_joint(proxies,seed,replicate,scenario)['session_id']
    return copy.deepcopy(next(p for p in pairs if p['pair_id']==selected))


def paired_diagnostics(cpu,corun,seed=SEED):
    import numpy as np
    if len(cpu)!=5 or len(corun)!=5:raise ValueError('five complete pairs required')
    delta=np.asarray(corun,dtype=float)-np.asarray(cpu,dtype=float)
    if not np.isfinite(delta).all():raise ValueError('invalid paired metric')
    rng=np.random.default_rng(seed);draws=delta[rng.integers(5,size=(2000,5))].mean(axis=1)
    ci=np.quantile(draws,[.025,.975]).tolist()
    return dict(pair_deltas=delta.tolist(),mean_difference=float(delta.mean()),CI95=ci,
                interpretation='inconclusive' if ci[0]<=0<=ci[1] else 'observed direction only; no universal superiority')


def descriptive(values,seed=SEED):
    """Session statistics, LOSO and bootstrap; no width-based acceptance gate."""
    import numpy as np
    if len(values)<2 or any(not x for x in values):raise ValueError('session evidence missing')
    pooled=[x for s in values for x in s]
    medians=[statistics.median(s) for s in values]
    rng=np.random.default_rng(seed)
    draws=np.median(np.asarray(medians)[rng.integers(len(values),size=(2000,len(values)))],axis=1)
    return dict(sessions=len(values),observed_min=min(pooled),observed_median=statistics.median(pooled),observed_max=max(pooled),
                session_median_CI95=np.quantile(draws,[.025,.975]).tolist(),
                loso_session_medians=[statistics.median(medians[:i]+medians[i+1:]) for i in range(len(values))],
                meaning='descriptive bootstrap/LOSO, not independent holdout or population cold P95')


def deadline_scenarios(service_values,setup_values,arrivals,cpu_demands):
    import numpy as np
    if not service_values or not arrivals or len(arrivals)!=len(cpu_demands):raise ValueError('deadline evidence missing')
    if any(x<0 for x in service_values+setup_values+arrivals+cpu_demands):raise ValueError('negative timing')
    h=max(arrivals)-min(arrivals);d=sum(cpu_demands)
    return dict(status='calculated_descriptive_candidates',
        urgent_warm=[float(np.quantile(service_values,q))*m for q in (.5,.9) for m in (.75,1.,1.5)],
        urgent_cold=[float(np.quantile(setup_values,q))*m for q in (.5,.9) for m in (.75,1.,1.5)],
        normal=[[max(0,h-(a-min(arrivals)))+m*d for a in arrivals] for m in (.75,1.,1.5)],
        note='setup_values must be joint cold active+setup once; common CPU reference, never policy-specific')


def dry_run(plan):
    return dict(status='BOUNDED_EMPIRICAL_PLAN_READY',planned_sessions=30,planned_pairs=5,
                device_commands=[],dispatches=0,simulated_completions=0,measurement_executed=False,
                request_count=sum(len(m['requests'])+len(m['warmup_requests']) for m in plan['manifests'].values()))


def code_hashes():
    paths=[Path(__file__),Path(old.__file__),Path(v.__file__),SCHEMA,
           v.SCHEMA,old.SCHEMA.with_name('joint-empirical-session-v1.schema.json')]
    return {str(p.resolve()):v.digest(p) for p in paths}


def generate(previous,smoke,output):
    output.mkdir(parents=True,exist_ok=False)
    old.verify(previous,v.digest(previous/'freeze.json'))
    registry=v.read(previous/'consumed_registry.json')
    sp=v.read(smoke/'smoke_plan_v2/plan.json')
    templates=[v.read(Path(e['manifest'])) for e in sp['entries']]
    gate=v.read(smoke/'host_gate.json')
    pins={**gate['source_hashes'],**gate['apk_sha256']}
    for p,h in pins.items():
        if v.digest(Path(p))!=h:raise ValueError('tested APK/source changed')
    runner=smoke/'smoke_device.py';pins[str(runner)]=v.digest(runner)
    plan=build_plan(templates,registry);validate_plan(plan,templates,registry)
    products={'plan.json':plan,'templates.json':templates,'consumed_registry.json':registry,'no_op.json':dry_run(plan),
              'runner_preview.json':{'python_source':runner_source(runner.read_text(encoding='utf-8'))},
              'execution_sources.json':dict(smoke=str(smoke),previous=str(previous),runner=str(runner),pins=pins,
                  input_sources={name:dict(path=str(Path(e['manifest']).parent/name),sha256=h) for e in sp['entries'] for name,h in e['input_hashes'].items() if name!='manifest.json'})}
    for name,x in products.items():(output/name).write_bytes(v.canonical(x))
    f=dict(protocol='bounded-empirical-freeze-v1',files={name:v.digest(output/name) for name in products},code=code_hashes())
    (output/'freeze.json').write_bytes(v.canonical(f));return v.digest(output/'freeze.json')


def verify(output,expected):
    if v.digest(output/'freeze.json')!=expected:raise ValueError('freeze mutation')
    f=v.read(output/'freeze.json')
    if f['code']!=code_hashes():raise ValueError('code/schema changed')
    for name,h in f['files'].items():
        if Path(name).name!=name or v.digest(output/name)!=h:raise ValueError('artifact mutation')
    sources=v.read(output/'execution_sources.json')
    for p,h in sources['pins'].items():
        if v.digest(Path(p))!=h:raise ValueError('source/APK changed')
    plan=v.read(output/'plan.json');validate_plan(plan,v.read(output/'templates.json'),v.read(output/'consumed_registry.json'))
    return plan


def runner_source(original):
    """Adapt the already smoke-tested runner with exact, audited substitutions.

    Artifact paths retain the old 'smokes' name solely for compatibility. The
    native purpose is instrumentation_calibration, never telemetry_smoke.
    """
    def replace(a,b):
        nonlocal original
        if original.count(a)!=1:raise ValueError('runner template drift: '+a[:60])
        original=original.replace(a,b)
    replace('assert len(plan[\'entries\'])==4', 'assert len(plan[\'entries\'])==30')
    replace("assert m['purpose']=='telemetry_smoke'", "assert m['purpose']=='instrumentation_calibration'")
    replace("consumed=old['consumed_sessions']+old['requests'];traces=list(old['fingerprints'])+[old['diagnostic_fingerprint']]",
            "registry=v.read(ROOT/'consumed_registry.json');consumed=registry['sessions']+registry['requests'];traces=list(registry['traces'])")
    replace('ledger=[];receipts=[]',"assert not (ROOT/'smoke_ledger.json').exists();ledger=[];receipts=[]")
    replace("context=dict(name=entry['name']", "(ROOT/(sid+'.attempted')).write_text('single attempt; no rerun',encoding='utf-8')\n    context=dict(name=entry['name']")
    replace("run(['shell','am','force-stop',PKG]);context['force_stop_confirmed']=True",
            "run(['shell','am','force-stop',PKG]);context['force_stop_confirmed']=True\n            for process in (PKG,PKG+':model_probe'):\n                stopped=run(['shell','pidof',process],allow=(1,));assert not stopped.stdout.strip()\n            context['process_absence_confirmed']=True")
    # Do not continue after an unsuccessful cleanup, even if native validation passed.
    anchor="        (ROOT/'smoke_ledger.json').write_text(json.dumps(ledger,indent=2))"
    replace(anchor,anchor+"\n    if 'cleanup_error' in context:raise RuntimeError(context['cleanup_error'])")
    marker="\na=next(v.read(Path(e['manifest'])) for e in plan['entries'] if e['name']=='resident_cpu_serial')"
    if original.count(marker)!=1:raise ValueError('runner finalizer template drift')
    original=original.split(marker)[0]+"\n(ROOT/'acquisition_result.json').write_text(json.dumps(dict(sessions=len(receipts),receipts=receipts,descriptive=True),indent=2))\n"
    compile(original,'bounded_device_runner.py','exec')
    return original


def execute(bundle,expected,output):
    """Future explicitly invoked acquisition, not called by generate/dry-run/tests."""
    plan=verify(bundle,expected);sources=v.read(bundle/'execution_sources.json')
    # A persistent exclusive claim in the frozen bundle prevents restarting the
    # same 30 UUIDs into another output root after failure or partial completion.
    with (bundle/'execution.claim').open('x',encoding='utf-8') as f:f.write(str(output.resolve()))
    output.mkdir(parents=True,exist_ok=False)
    registry=v.read(bundle/'consumed_registry.json')
    (output/'consumed_registry.json').write_bytes(v.canonical(registry))
    entries=[]
    for entry in plan['entries']:
        sid=entry['session_id'];inputs=output/'inputs'/sid;inputs.mkdir(parents=True)
        m=plan['manifests'][sid]
        required={'anchors.json'}|{i['filename'] for i in m['images']}
        for spec in m['models'].values():required|={spec['model']['filename'],spec['model']['label_filename']}
        for name in sorted(required):
            source=sources['input_sources'][name]
            if v.digest(Path(source['path']))!=source['sha256']:raise ValueError('input mutation')
            shutil.copyfile(source['path'],inputs/name)
        (inputs/'manifest.json').write_bytes(v.canonical(m))
        entries.append(dict(name=entry['family'],session_id=sid,manifest=str((inputs/'manifest.json').resolve()),
                    manifest_sha256=v.digest(inputs/'manifest.json'),input_hashes={p.name:v.digest(p) for p in inputs.iterdir()}))
    acquisition=dict(entries=entries,apk_sha256=next(iter(plan['manifests'].values()))['apk_sha256'],
                     seed=plan['seed'],formal_calibration=False,holdout=False,descriptive_calibration=True)
    (output/'smoke_plan_v2').mkdir();(output/'smoke_plan_v2/plan.json').write_bytes(v.canonical(acquisition))
    gate=v.read(Path(sources['smoke'])/'host_gate.json');gate['plan_sha256']=v.digest(output/'smoke_plan_v2/plan.json')
    (output/'host_gate.json').write_bytes(v.canonical(gate))
    script=runner_source(Path(sources['runner']).read_text(encoding='utf-8'))
    (output/'bounded_device_runner.py').write_text(script,encoding='utf-8')
    p=subprocess.run([sys.executable,str(output/'bounded_device_runner.py')])
    if p.returncode:raise RuntimeError('acquisition incomplete; preserve all files, no device retries')
    blocks=[]
    for entry in plan['entries']:
        root=output/'smokes'/entry['session_id']
        block=ingest(root/'artifacts',(root/'delegate_log.txt').read_text(encoding='utf-8'),entry,plan,registry)
        blocks.append(block)
    result=approve_blocks(blocks,plan)
    (output/'joint_blocks.json').write_bytes(v.canonical(blocks))
    (output/'descriptive_completeness.json').write_bytes(v.canonical(result))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['generate','dry-run','execute'])
    p.add_argument('--previous',type=Path);p.add_argument('--smoke',type=Path)
    p.add_argument('--bundle',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-sha256')
    a=p.parse_args()
    if a.command=='generate':result=generate(a.previous,a.smoke,a.output)
    elif a.command=='dry-run':result=dry_run(verify(a.output,a.expected_sha256))
    else:result=execute(a.bundle,a.expected_sha256,a.output)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
