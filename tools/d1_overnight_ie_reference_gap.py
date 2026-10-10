"""Frozen R1/Flex on the already consumed PPO confirmation: posthoc only.

Only96 new native evaluations. All10 existing controls/actors are SHA-bound
reused results. No learner, weight, policy, encoder, deadline, model or original
verdict changes. Static first-dispatch divergence is an explanatory audit,
not a new online feature, independent validation or causal effect estimate.
"""
import argparse,copy,csv,gzip,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_overnight_ie_run as native
from tools import d1_overnight_ie_policy as conservative
from tools import d1_overnight_ie_flex_policy as flex
from tools import d1_overnight_rl_amount as parent

ROOT=native.ROOT;LOCAL=ROOT/'output/overnight_ie_reference_gap_20261011_v1';PUBLIC=ROOT/'docs/results/overnight_reference_gap_20261011'
TASK='POSTHOC-L0-BAND-REFERENCE-GAP-01';NEW_ROLES=('R1','Flex')
ALL_ROLES=('Band','Triton','L0','Rule','PPO11_512','PPO23_512','PPO37_512','NoWait11','NoWait23','NoWait37','R1','Flex')
read=native.read;sha=native.sha;serial=native.serial;_write=native.write
IDS=dict(native.IDS,Flex=flex.FLEX)

def write(path,value):
    for attempt in range(20):
        try:return _write(path,value)
        except PermissionError:
            if attempt==19:raise
            time.sleep(.05)

def sources():
    files={Path(m.__file__).resolve() for n,m in sys.modules.copy().items() if n.startswith('tools.') and getattr(m,'__file__',None)}
    files.add(ROOT/'tools/d1_overnight_ie_reference_gap.py')
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files) if p.suffix=='.py' and p.is_relative_to(ROOT)}

def register():
    if LOCAL.exists():raise FileExistsError('closed/consumed task cannot reset')
    done=read(parent.LOCAL/'completion.json');oldreg=read(parent.LOCAL/'registration.json');data=read(parent.LOCAL/'inputs.json')
    if done['status']!='completed' or (parent.LOCAL/'owner.lock').exists():raise ValueError('complete original RL results required')
    if done['consumption']['native_starts']!=2688 or done['consumption']['learning_starts']!=1440:raise ValueError('original consumed lineage differs')
    controls=[q for q in done['rows'] if q['scope'] in ('confirmation','no_wait')]
    if len(controls)!=480 or {(q['condition'],q['policy']) for q in controls}!={(j,r) for j in range(48) for r in ALL_ROLES if r not in NEW_ROLES}:raise ValueError('original completed controls missing/duplicate')
    cases=data['confirmation'];assert len(cases)==48
    raw_sha={q['identity']:sha(parent.LOCAL/'items'/(q['identity']+'.json.gz')) for q in controls}
    reg=dict(task=TASK,registered_utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        authorization='root approved fixed R1/Flex same-consumed-confirmation diagnosis after 3PPO512 failed; no fresh success test',
        parent_task=parent.TASK,parent_completion_sha256=sha(parent.LOCAL/'completion.json'),parent_inputs_sha256=sha(parent.LOCAL/'inputs.json'),
        original_RL_native=2688,original_RL_learning=1440,original_RL_native_cap=3072,native_cap=128,learning_cap=0,expected_native=96,phase_caps=dict(diagnosis=96),
        active_seconds=1800,save_reserve_seconds=300,original_RL_execution_deadline_utc=datetime.fromtimestamp(datetime.fromisoformat(oldreg['registered_utc']).timestamp()+10200,timezone.utc).isoformat(),
        reused_controls=480,reused_raw_sha256=raw_sha,source_sha256=sources(),inputs_sha256=flex.r.c.digest(cases),new_policy_ids=dict(R1=conservative.R1,Flex=flex.FLEX),
        frozen_model_sha256=sha(flex.r.h.MODEL),model_upstream_sha256=flex.r.h.UPSTREAM_SHA,service_energy_sha256=flex.r.h.p.MODEL_SHA,initial_sha256=flex.r.h.p.INITIAL_SHA,
        common_settings=oldreg['common_settings'],realization_seed=201,realization_source_label='same_overnight_ plus context, same original deterministic4vectors',
        output_meaning='posthoc same-data transport of existing fixed policies; no tuning, seed replacement or independent confirmation',
        hypothesis='L0 learning reference has45 normal misses vs Band42; do unchanged initial-cooling guard or P95-flex narrow that gap on identical traces?',
        original_verdicts_preserved=True,baseline_is_Band_comparator_not_app_default=True,policy_fallback_and_reference='unchanged L0',
        final_KPI_gate_unchanged=True,first_divergence='earliest different same-time dispatch set; only preceding public arrivals/phase events for queue/lane reconstruction; original full encoder snapshot retained',
        device_commands=0,model_fit_calls=0,new_learning=0,new_hyperparameters=0,new_policy_versions=0,experiment_ready=False,automatic_adoption=False)
    LOCAL.mkdir();write(LOCAL/'registration.json',reg);write(LOCAL/'inputs.json',dict(cases=cases,controls=controls));write(PUBLIC/'execution_contract.json',reg)
    write(PUBLIC/'cases.json',cases);write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='registered',consumption=dict(native_starts=0,learning_starts=0),next_action='first low condition included in96 then fixed same-data diagnosis'))
    return reg

def check():
    reg=read(LOCAL/'registration.json')
    for name,digest in reg['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('registered source changed '+name)
    if sha(parent.LOCAL/'completion.json')!=reg['parent_completion_sha256'] or sha(parent.LOCAL/'inputs.json')!=reg['parent_inputs_sha256']:raise ValueError('consumed source changed')
    if flex.r.c.digest(read(LOCAL/'inputs.json')['cases'])!=reg['inputs_sha256'] or sha(flex.r.h.MODEL)!=reg['frozen_model_sha256']:raise ValueError('input/model changed')
    return reg

def agent(role):
    f,i,_=flex.r.h.load()
    return conservative.Controller(f,i['initial'],conservative.R1) if role=='R1' else flex.Controller(f,i['initial'])

native.LOCAL=LOCAL;native.PUBLIC=PUBLIC;native.check=check;native.write=write;native.agent=agent

class Budget(native.Budget):
    def __init__(self):
        super().__init__();self.deadline=min(datetime.fromisoformat(self.reg['registered_utc']).timestamp()+1500,datetime.fromisoformat(self.reg['original_RL_execution_deadline_utc']).timestamp())
    def used(self):return dict(native_starts=len(self.rows),native_cap=128,new_learning=0,failed=sum(v['status']=='failed' for v in self.rows),device_commands=0,model_fit_calls=0,parent_RL_plus_diagnosis=2688+len(self.rows),parent_RL_plus_diagnosis_cap=3072)
    def call(self,identity,phase,case,role):
        check()
        if len(self.rows)>=128 or 2688+len(self.rows)>=3072:raise TimeoutError('task/parent cap')
        # Preserve the parent vector metadata as well as its costs. The shim
        # affects only this process's top-level native invocation and restores
        # the same engine function even on failure; no engine source is edited.
        engine=flex.r.h.prior.external.old.engine;original=engine.simulate
        def same_source_labels(config,vectors,tickets,*args,**kwargs):
            vectors=copy.deepcopy(vectors)
            for cell in vectors['cells'].values():
                for vector in cell:vector['source_request_id']='same_overnight_'+case['context']
            return original(config,vectors,tickets,*args,**kwargs)
        engine.simulate=same_source_labels
        try:return super().call(identity,phase,case,role)
        finally:engine.simulate=original

def row(raw,case,role):return dict(scope='posthoc_confirmation_reuse',identity=f'diagnosis_{role}_{case["condition"]:02d}',condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],policy=role,policy_id=IDS[role],**raw['row'])

def read_raw(identity,new=False):
    path=(LOCAL if new else parent.LOCAL)/'items'/(identity+'.json.gz')
    expected=read(LOCAL/'registration.json')['reused_raw_sha256'].get(identity)
    if expected and sha(path)!=expected:raise ValueError('reused artifact changed '+identity)
    return json.loads(gzip.decompress(path.read_bytes()))

def dispatches(raw):
    groups={}
    for q in raw['result']['ledger']:
        if 'dispatch_ns' in q:groups.setdefault(q['dispatch_ns'],[]).append((q['id'],q['backend']))
    return {k:sorted(v) for k,v in groups.items()}

def public_before(case,raw,now):
    owners={'CPU':None,'GPU':None};phases={b:'AVAILABLE' for b in owners};assigned=set()
    events=[(q['dispatch_ns'],0,q['backend'],q['id'],'ASSIGNED') for q in raw['result']['ledger'] if q.get('dispatch_ns',1e99)<now]
    names=dict(execution_start_ns='EXECUTING',output_ready_ns='OUTPUT_READY',persist_complete_ns='PERSISTED',worker_release_ns='WORKER_RELEASED',lane_available_ns='AVAILABLE')
    events.extend((q['at_ns'],1,q['backend'],q['request_id'],names[q['event']]) for q in raw['result']['transitions'] if q['at_ns']<=now)
    for at,kind,backend,rid,phase in sorted(events):
        if kind==0:owners[backend]=rid;phases[backend]=phase;assigned.add(rid)
        elif owners[backend]==rid:phases[backend]=phase;owners[backend]=None if phase=='AVAILABLE' else rid
    queue=[q for q in case['tickets'] if q['arrival_ns']<=now and q['id'] not in assigned]
    return dict(now_ns=now,queue=queue,owners=owners,phases=phases,source='only actual dispatches before now and public phase callbacks<=now; no remaining duration or later arrival input')

def first_difference(case,left,right):
    aa,bb=dispatches(left),dispatches(right);when=next((t for t in sorted(set(aa)|set(bb)) if aa.get(t,[])!=bb.get(t,[])),None)
    if when is None:return dict(condition=case['condition'],same_dispatch_schedule=True)
    state=public_before(case,left,when);ss=[s for s in left['snapshots'] if abs(s['now_ns']-when)<=1]
    result=dict(condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],same_dispatch_schedule=False,first_difference_ns=when,L0_jobs=aa.get(when,[]),Band_jobs=bb.get(when,[]),public_state=state,snapshot_found=bool(ss),candidate_matches=[])
    if not ss:return dict(result,classification='no encoded L0 snapshot at first different dispatch timestamp; no inferred mask cause')
    snap=ss[0];result['encoder_snapshot']={k:snap[k] for k in ('state','candidates','physical_mask','mask','actions','admissions','chosen','schema_id','window_ids','risk')}
    target=bb.get(when,[])
    for index,action in enumerate(snap['actions']):
        jobs=sorted((j['request_id'],j['backend']) for j in action.get('jobs',[]))
        match=jobs==target if target else action['kind']=='resource_wait' and any(state['owners'].values())
        if match:result['candidate_matches'].append(dict(slot=index,kind=action['kind'],physical=snap['physical_mask'][index],prediction_admitted=snap['mask'][index],reason=snap['admissions'][index],forecasts=snap['forecasts'][index]))
    result['classification']='not in recorded bank' if not result['candidate_matches'] else ('physical masked' if not any(q['physical'] for q in result['candidate_matches']) else 'prediction masked' if not any(q['prediction_admitted'] for q in result['candidate_matches']) else 'in bank and permitted, selector chooses differently')
    return result

def late_gap(case,left,right):
    aa={q['id']:q for q in left['result']['ledger']};bb={q['id']:q for q in right['result']['ledger']};out=[]
    for rid,q in aa.items():
        ref=bb[rid]
        if q['priority']=='normal' and q['late_success'] and not ref['late_success']:
            out.append(dict(condition=case['condition'],arrival_seed=case['seed'],family=case['family'],context=case['context'],request_id=rid,arrival_ns=q['arrival_ns'],deadline_ns=q['arrival_ns']+q['deadline_offset_ns'],L0_response_ms=q['response_ns']/1e6,Band_response_ms=ref['response_ns']/1e6,L0_dispatch_ns=q['dispatch_ns'],Band_dispatch_ns=ref['dispatch_ns'],both_backend_CPU=q['backend']==ref['backend']=='CPU'))
    return out

def inspect():
    data=read(LOCAL/'inputs.json');by={(q['condition'],q['policy']):q for q in data['controls']};differences=[];late=[];routing=[]
    for case in data['cases']:
        left=read_raw(by[case['condition'],'L0']['identity']);right=read_raw(by[case['condition'],'Band']['identity']);differences.append(first_difference(case,left,right));late.extend(late_gap(case,left,right))
        for role in ('L0','Band','Rule','PPO11_512','PPO23_512','PPO37_512','NoWait11','NoWait23','NoWait37'):
            raw=read_raw(by[case['condition'],role]['identity']);ledger=raw['result']['ledger'];snapshots=raw['snapshots']
            routing.append(dict(condition=case['condition'],family=case['family'],context=case['context'],policy=role,classification_CPU=sum(q['task']=='classification' and q.get('backend')=='CPU' for q in ledger),classification_GPU=sum(q['task']=='classification' and q.get('backend')=='GPU' for q in ledger),selected_cool_wait=sum(s['actions'][s['chosen']]['kind']=='cool_wait' for s in snapshots),selected_resource_wait=sum(s['actions'][s['chosen']]['kind']=='resource_wait' for s in snapshots),normal_failure=raw['row']['normal_failure'],energy_j=raw['row']['energy_j'],peak_ap_c=raw['row']['peak_ap_c']))
    write(LOCAL/'first_divergence.json',differences);write(PUBLIC/'first_divergence.json',differences);write(PUBLIC/'late_request_gap.json',late);write(PUBLIC/'routing_wait_counts.json',routing)
    return dict(first_divergence_cases=sum(not q['same_dispatch_schedule'] for q in differences),L0_late_Band_on_time=len(late),native_starts=0,learning_starts=0,model_projection_calls=0)

def run():
    b=Budget();data=read(LOCAL/'inputs.json');rows=[dict(q,reused_native_starts=0,meaning='original completed same-condition row; not new validation') for q in data['controls']];lock=LOCAL/'owner.lock'
    with lock.open('x',encoding='utf-8') as f:f.write(str(os.getpid()))
    try:
        for case in data['cases']:
            for role in NEW_ROLES:
                raw=b.call(f'diagnosis_{role}_{case["condition"]:02d}','diagnosis',case,role);rows.append(row(raw,case,role));write(LOCAL/'rows_partial.json',rows)
            print(json.dumps(dict(condition=case['condition'],consumption=b.used())),flush=True)
        gates={role:native.verdict(rows,role,48) for role in NEW_ROLES};write(LOCAL/'comparison_rows.json',rows);write(PUBLIC/'comparison.json',rows);write(PUBLIC/'descriptive_original_gate.json',gates)
        diagnostic=inspect();write(LOCAL/'completion.json',dict(task=TASK,status='completed',consumption=b.used(),rows=rows,diagnostic=diagnostic,original_verdicts_changed=False,automatic_adoption=False))
        write(LOCAL/'WORKING_STATE.json',dict(task=TASK,phase='completed',consumption=b.used(),next_action='posthoc explanation and final expert review; no new policy adoption'));write(PUBLIC/'consumption.json',b.used());return dict(consumption=b.used(),diagnostic=diagnostic,gates={k:v['promising'] for k,v in gates.items()})
    finally:lock.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','check','run','inspect'));a=p.parse_args();print(json.dumps(serial(globals()[a.command]()),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
