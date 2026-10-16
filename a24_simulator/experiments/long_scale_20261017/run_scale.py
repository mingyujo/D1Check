"""Registered extended-horizon counterfactuals. Frozen policies, no training."""
from pathlib import Path
import copy,gc,gzip,hashlib,io,json,math,os,sys,time
ROOT=Path(__file__).resolve().parents[2];ENTRY=Path(__file__).resolve()
sys.path[:0]=[str(ENTRY.parent),str(ROOT/'src'),str(ROOT/'experiments/edf_cpu_first_20261016'),
              str(ROOT/'experiments/protected48_v2_20261016'),str(ROOT/'experiments/competition_cost_20261017')]
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
import lab_backend as L,interactive_kernel as Original
from policy import installed,window_heat
import protected_policy as P0Policy
import protected_policy_long as Policy
from fast_thermal import FastThermal
import state_cost as Cost
from relative_drain import exclusive
import numpy as np,torch
torch.set_num_threads(1)
G=L.runtime_guard
G.OWN_TOKENS+=('long_scale_20261017','competition_cost_20261017','s26-state-aware-atc-','state_recovery_owner')
K=L.load_module('registered_long_kernel',ENTRY.with_name('kernel_long.py'))
Bridge=L.load_module('registered_long_bridge',ENTRY.with_name('bridge_long.py'))
Policy.bridge=Bridge
NS=1_000_000_000

def save_binary(p,b):
    with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())

def public_input(case,catalog):
    value=case['input'];base=copy.deepcopy(value);base['requests']=base['requests'][:48]
    public,contexts=L.prepare_public(base,catalog['templates'],catalog['profiles'])
    prototypes={r['ordinal']:r for r in public['requests']}
    sources={r['bank']:contexts[r['request_id']] for r in public['requests']}
    rows=[];newcontexts={}
    for q in value['requests']:
        row=copy.deepcopy(prototypes[q['ordinal']%48])
        row.update(request_id='user-'+str(q['ordinal']).zfill(5),ordinal=q['ordinal'],
                   scheduled_arrival_ns=round(q['arrival_s']*NS),deadline_ns=round(q['deadline_s']*NS),group=q['ordinal']//8)
        rows.append(row);newcontexts[row['request_id']]=sources[row['bank']]
    lookup={q['request_id']:q for q in rows}
    for s in sources.values():s['_requests_by_id']=lookup
    public.update(requests=rows,service_stop_ns=round(case['service_stop_s']*NS),
                  drain_stop_ns=round(case['drain_stop_s']*NS),observation_end_ns=round(case['observation_end_s']*NS))
    public['public_base_sha256']=L.digest(value);public['public_scenario_sha256']=L.digest(value)
    return public,newcontexts

class Actor:
    def __init__(self,model,public,thermal,profile,learner,learn,fast,folder,label,validate):
        fields=('session_id','device','source_family','source_generation','protocol','cohort_id','compatibility',
                'initial_ap_c','initial_ap_time_s','initial_ap_hi_s','observations','forecast_origin_s','ambient_c','service_stop_ns')
        minimal={k:public[k] for k in fields if k in public}
        cls=Policy.ProtectedPolicy if fast else P0Policy.ProtectedPolicy
        self.actor=cls(model,minimal,thermal,profile,learner,learn,False,False)
        self.original=L.thermal_model.predict;self.fast=FastThermal(L.thermal_model,self.original,minimal,thermal) if fast else None
        self.folder,self.label,self.learn=folder,label,learn;self.chunk=0;self.frames=0;self.chain=hashlib.sha256()
        self.validate=validate;self.chunks=[];self.max_AP_error=0.;self.started=time.monotonic()
        self.stats=dict(calls=0,dispatch=0,multiple_candidates=0,WAIT=0,two_free=0)
    def __call__(self,state):
        if self.fast:
            def predictor(*a,**kw):
                value=self.fast.predict(*a,**kw)
                if self.validate:
                    old=self.original(*a,**kw);err=abs(old['ap_c'][0]-value['ap_c'][0]);self.max_AP_error=max(self.max_AP_error,err)
                    L.need(err<1e-8 and np.allclose(old['local_coefficients'],value['local_coefficients'],rtol=0,atol=1e-12),'Streaming AP equivalence')
                return value
            L.thermal_model.predict=predictor
        try:a=self.actor(state)
        finally:L.thermal_model.predict=self.original
        b=self.actor.bank_audits.pop();f=self.actor.controller.frames[-1]
        rp=self.learn.replay_frame(self.actor.learner.net,f)
        L.need(rp['argmax']==f['index'] and abs(rp['logprob']-f['old_logp'])<1e-6 and np.allclose(rp['critic'],f['value'],rtol=1e-5,atol=1e-6),'Frozen saved NN replay')
        L.need(np.array_equal(f['mask'],b['mask']) and f['physical_mask'][f['index']] and f['mask'][f['index']],'Legal action')
        L.need(torch.equal(f['action_rng_before'],f['action_rng_after']) and not f['collect'],'No NN update/RNG draw')
        self.chain.update((f['input_sha']+':'+str(f['index'])).encode());self.frames+=1;self.stats['calls']+=1
        if a['kind']=='DISPATCH':
            self.stats['dispatch']+=1;self.stats['two_free']+=len(state['owners'])==0
            self.stats['multiple_candidates']+=len({i//3 for i,v in enumerate(b['mask'][:72]) if v})>1
        self.stats['WAIT']+=a['kind']=='WAIT'
        if len(self.actor.controller.frames)>=256:self.flush()
        return a
    def flush(self):
        if not self.actor.controller.frames:return
        name=self.label+'.frames.%04d.pt.gz'%self.chunk;buf=io.BytesIO()
        torch.save(self.actor.controller.frames,buf);save_binary(self.folder/name,gzip.compress(buf.getvalue(),compresslevel=1,mtime=0))
        self.chunks.append(dict(file=name,sha256=L.sha(self.folder/name),frames=len(self.actor.controller.frames)))
        self.actor.controller.frames.clear();self.actor.controller.decisions.clear();self.chunk+=1
        if self.frames%2048==0:print('PROGRESS',self.label,self.frames,'actor calls',round(time.monotonic()-self.started,1),'seconds',flush=True)

def metrics(summary,prediction,case,costmodel):
    lo,hi=case['work_window'];observed=summary['requests'];answered=[r for r in observed if r['response_ns'] is not None]
    latency=sorted((r['response_ns']-r['scheduled_arrival_ns'])/NS for r in answered)
    heat=window_heat(summary,lo,hi)
    cost=Cost.observe(exclusive(summary['gantt'],0.,case['observation_end_s']),lo,hi,costmodel)
    result=dict(**heat,**cost,planned=len(observed),responded=len(answered),
        on_time=sum(r['response_ns']<=r['deadline_ns'] for r in answered),
        urgent_planned=sum(r['priority']=='U' for r in observed),urgent_on_time=sum(r['priority']=='U' and r['response_ns'] is not None and r['response_ns']<=r['deadline_ns'] for r in observed),
        incomplete=len(observed)-sum(r['available_ns'] is not None for r in observed),
        AVAILABLE_by_window_end=sum(r['available_ns'] is not None and r['available_ns']/NS<=hi for r in observed),
        response_missing=len(observed)-len(answered),P95_completed_response_s=latency[max(0,math.ceil(.95*len(latency))-1)] if latency else None,
        tardiness_lower_bound_s=sum(max(0,r['response_ns']-r['deadline_ns'])/NS for r in answered),
        overlap_s=prediction['metrics']['overlap_ns']/NS,window_s=[lo,hi],duration_s=hi-lo,
        baseline_share_percent=100*cost['baseline_J_proxy']/cost['total_J_proxy'],
        residual_AP_at_plus180_c=summary['AP']['ap_c'][-1],
        route_counts={t+'_'+r:sum(q['task']==t and q['route']==r for q in observed) for t in ('C','D') for r in ('CPU','GPU')})
    return result

def main(path):
    op=L.read(path);sha=L.sha(path);reg=L.read(ROOT/'models/registration.json')
    L.need(op['schema']=='A24-long-scale-operation-v1','Schema')
    for p in op['pins']:L.pin(p)
    G.process_guard(ENTRY,reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/',reg['worker_lock_path']])
    out=ROOT/op['output_dir'];L.need(not out.exists(),'Consumed operation; no automatic restart')
    import msvcrt
    lock=Path(reg['worker_lock_path']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    count=0
    try:
        out.mkdir(parents=True,exist_ok=False);L.write_new(out/'START.json',dict(operation_sha256=sha,utc=L.now(),actual_process=G.process_guard(ENTRY,reg['known_PS_producer_paths'])))
        try:
            base,thermal,profile=L.initialize(reg);catalog=L.read(L.pin(reg['catalog_pin']))
            learn=L.load_module('long_scale_learner',ROOT/'reference/rolling/learner.py');learner=learn.Learner.load_snapshot(L.pin(op['checkpoint']))
            network=learn.network_digest(learner.net);costmodel=L.read(L.pin(op['cost_model']))
            design=L.read(L.pin(op['inputs']));results=[]
            def simulate(case,policy,label,fast,validate=False):
                nonlocal count
                G.process_guard(ENTRY,reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/'])
                L.need(count<op['environment_cap'],'New reservation exhausted')
                public,contexts=public_input(case,catalog);model=L.Model(base,contexts)
                identity=L.digest([sha,label]);start=dict(event='START',identity=identity,start_id=identity,
                     durable_START_consumed=True,registration_sha256=sha,operation_sha256=sha,label=label,
                     new_environment=1,utc=L.now(),n=case['n'],policy=policy,input_sha256=L.digest(case['input']))
                old=L.read(L.pin(op['budget']))
                global_starts=sum(sum(json.loads(s).get('event')=='START' for s in Path(l['path']).read_text(encoding='utf-8-sig').splitlines() if s) for l in old['global_ledgers'])
                L.need(global_starts+count<137712,'Global START cap')
                L.append(out/'receipts.jsonl',start);count+=1;print('START',label,case['n'],'requests',flush=True)
                try:
                    k=K if fast else Original;actor=Actor(model,public,thermal,profile,learner,learn,fast,out,label,validate) if policy=='RL' else None
                    began=time.monotonic()
                    with installed(k,L):
                        pred=k.simulate_protocol(public,model,'FROZEN_RL_REPLAY' if actor else 'EDF_CPU_FIRST',execution_guard=start,
                            scenario_key=design['common_potential_key'],admission_protocol='SERIAL',redispatch_mode='ZERO_EXPLICIT_BASELINE',
                            zero_baseline_id='COMMON_UNIDENTIFIED_CONTROLLER_IDEAL_ZERO',pair_scope='READY_QUEUE',frozen_policy=actor,
                            frozen_policy_binding=dict(replay_only=True,checkpoint_sha256=op['checkpoint']['sha256'],input_contract_sha256=L.sha(ENTRY.with_name('protected_policy_long.py'))) if actor else None,
                            decision_cap=max(8192,case['n']*64),concurrency_mode='DATA_DERIVED_PROGRESS',unidentified_overlap='SERIAL_INDEPENDENT')
                    if actor:actor.flush()
                    activity=L.generated_activity(public,pred);end=case['observation_end_s'];times=sorted(set([0.,35.,case['work_window'][1],end]+[float(i) for i in range(math.ceil(end))]))
                    ap=L.thermal_model.predict(thermal,activity,times=times,allow_extrapolation=True)
                    L.need(ap['status']=='CONDITIONAL_AP_PREDICTION','Final AP response')
                    summary=dict(policy=policy,requests=pred['requests'],gantt=activity['owner_intervals'],AP=dict(t_s=ap['t_s'],ap_c=ap['ap_c']))
                    audit=L.audit_result({'prediction':pred,'summary':{'measured_J':None}},None)
                    m=metrics(summary,pred,case,costmodel)
                    raw=out/(label+'.raw.json.gz');save_binary(raw,gzip.compress(L.canonical(dict(prediction=pred,summary=summary)).encode(),compresslevel=1,mtime=0))
                    nn=dict(frames=actor.frames,chain=actor.chain.hexdigest(),chunks=actor.chunks,stats=actor.stats,max_AP_stream_error=actor.max_AP_error) if actor else None
                    result=dict(label=label,n=case['n'],policy=policy,metrics=m,NN=nn,audit=audit,AP_flags=ap['extrapolation_flags'],
                                extended_duration_beyond_current_M8_210s=end>210,wall_seconds=time.monotonic()-began,raw_sha256=L.sha(raw),
                                measured_J=None,physical_goal_verified=False,trained_on_this_long_horizon=False)
                    L.need(learn.network_digest(learner.net)==network,'Frozen network changed')
                    L.write_new(out/(label+'.json'),result)
                    for event in ('PREPARED','COMPLETE'):L.append(out/'receipts.jsonl',{**start,'event':event,'result_sha256':L.sha(out/(label+'.json')),'raw_sha256':result['raw_sha256'],'utc':L.now()})
                    print('COMPLETE',label,'baseline%',round(m['baseline_share_percent'],3),'on_time',m['on_time'],'/',case['n'],'wall',round(result['wall_seconds'],2),flush=True)
                    return result,summary
                except BaseException as e:
                    L.append(out/'receipts.jsonl',{**start,'event':'FAIL','error':str(e),'utc':L.now(),'automatic_retry':False});raise
            p0=copy.deepcopy(design['cases'][0]);p0.update(service_stop_s=180.,drain_stop_s=210.,observation_end_s=210.)
            equivalence=[]
            for policy in ('EDF','RL'):
                old,oldsummary=simulate(p0,policy,'P0_ORIGINAL_'+policy,False)
                new,newsummary=simulate(p0,policy,'P0_EXTENDED_'+policy,True,True)
                L.need(L.digest(oldsummary['requests'])==L.digest(newsummary['requests']),'P0 exact request clocks')
                L.need(np.allclose(oldsummary['AP']['ap_c'],newsummary['AP']['ap_c'],rtol=0,atol=1e-10),'P0 exact AP trace')
                if policy=='RL':L.need(old['NN']['chain']==new['NN']['chain'],'P0 NN input/action equivalence')
                equivalence.append(dict(policy=policy,request_clocks_exact=True,AP_exact=True,NN_input_actions_exact=policy=='RL'))
                del oldsummary,newsummary;gc.collect()
            L.write_new(out/'P0_EQUIVALENCE.json',dict(status='PASS',cases=equivalence))
            for case in design['cases']:
                rows=[]
                for policy in ('EDF','RL'):
                    row,summary=simulate(case,policy,'N%05d_%s'%(case['n'],policy),True)
                    rows.append(row);del summary;gc.collect()
                results.append(dict(n=case['n'],window_s=case['work_window'],input_sha256=L.digest(case['input']),rows=rows))
                L.write_new(out/('PROGRESS_N%05d.json'%case['n']),dict(completed_levels=len(results),total_levels=len(design['cases']),START=count,latest=rows,utc=L.now()))
            for p in op['pins']:L.pin(p)
            L.write_new(out/'RESULT.json',dict(schema='A24-long-scale-results-v1',cases=results,operation_sha256=sha,
                START=count,COMPLETE=count,FAIL=0,new_global_reservation=24,old_shared511_unchanged=True,
                P0_equivalence=equivalence,maximum_requests=design['counts'][-1],NN_training=0,model_fitting=0,
                measured_J=None,independent_device_confirmation=False,source_HEAD=op['source_HEAD'],
                interpretation='Single fixed48-request cycle repeated; fixed EP024 with extended public horizon. Long heat/energy are extrapolations, no thermal feedback added.'))
            L.write_new(out/'COMPLETE.json',dict(result_sha256=L.sha(out/'RESULT.json'),START=count,utc=L.now()))
        except BaseException as e:
            L.write_new(out/'FAILURE.json',dict(error=str(e),utc=L.now(),automatic_retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':main(sys.argv[1])
