"""Local queued-request deadline veto for PAIR_COALESCE; PC-only opt-in.
Not a future-arrival or worst-case service guarantee. Existing policies unchanged.
"""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import statistics
from tools import d1_scheduler_conditions as s
from tools import d1_request_ppo as rl
p=s.p
ID='PAIR_QUEUED_SERVICE_GUARD_V1'
EID='g1.2_c0.75_b8'
SOURCE=p.ROOT/'docs/results/supervised_selector_01/run_v1/local_ledgers.jsonl'


def forecast(fc,queue,active,decision,now):
    rid=decision.get('chosen_request_id') or decision.get('head_request_id')
    if decision.get('selected'):rid=decision['selected']['request_id']
    q=next(q for q in queue if q['id']==rid)
    b=decision['chosen_backend'];delay=decision.get('chosen_explicit_delay_s',0.)
    first=fc.place(q,b,now+delay,active);jobs=copy.deepcopy(active)+[first]
    for other in queue:
        if other['id']==rid:continue
        jobs.append(min((fc.place(other,b,first['start'],jobs) for b in p.backends(other)),
                        key=lambda j:(j['response'],j['backend']!='CPU')))
    return {j['id']:max(0.,j['response']-j['deadline']) for j in jobs if not j['already_responded']}


def worsens(proposed,reference):
    if set(proposed)!=set(reference):raise ValueError('forecast request mismatch')
    return [rid for rid in proposed if proposed[rid]>reference[rid]+1e-9]


class Controller(s.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial,'PAIR_COALESCE_V1')
        self.guard_records=[]

    def __call__(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        proposed=super().__call__(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        if not queue or 'chosen_backend' not in proposed:return proposed
        ref=p.Controller.__call__(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        now=now_ns/1e9;active=self.long.active_jobs(lanes,now)
        if active is None or 'chosen_backend' not in ref:return ref
        ordered=s.a.order(queue,now_ns,settings)
        cp=forecast(self.long,ordered,active,proposed,now);cr=forecast(self.long,ordered,active,ref,now)
        ids=worsens(cp,cr)
        self.guard_records.append(dict(now_ns=now_ns,veto=bool(ids),worsened_ids=ids,
            proposal=proposed,reference=ref,proposed_lateness_s=cp,reference_lateness_s=cr))
        if ids:return dict(ref,reason='queued_deadline_veto_to_EFT',guard_veto=True)
        return dict(proposed,guard_veto=False)


def simulate(frozen,initial,tickets,scenario,policy):
    if policy!=ID:return s.simulate(frozen,initial,tickets,scenario,policy)
    c=Controller(frozen,initial)
    vectors=dict(cells={k:[dict(source_request_id='fixed_'+scenario,durations_ns=v) for _ in range(4)]
                       for k,v in p.profile(frozen,scenario).items()})
    # Engine legal action namespace stays original; provider implements opt-in guard.
    rr=s.a.old.engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,tickets,
        policy='PAIR_COALESCE_V1',settings=rl.settings(),seed=201,decision_provider=c)
    row,extra=rl.outcome(rr,initial,frozen)
    return row,rr,c,extra


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),Path(s.__file__),Path(p.__file__),SOURCE,p.BUNDLE/'model.json',p.BUNDLE/'initial_inputs.json']
    hashes={str(x.relative_to(p.ROOT)):p.digest(x) for x in paths}
    spec=dict(id=ID,utc=datetime.now(timezone.utc).isoformat(),base_head='e884882b88d6146b78c740437e0b002a27b09377',
        envelope=EID,reproduction_seeds=[123001,123002],fresh_seeds=[124001,124002],
        scenarios=s.a.old.SCENARIOS,policies=['EFT_REFERENCE','PAIR_COALESCE_V1',ID],
        runs=36,max_wall_s=300,rule='per arrived request predicted lateness under long_context may not increase vs current EFT choice; EFT continuation',
        scope='one known failed envelope; fresh seeds not unseen workload/device validation',no_fit=True,device_commands=0,experiment_ready=False)
    p.write(out/'contract_before_run.json',dict(spec=spec,hashes=hashes))
    source={}
    with SOURCE.open(encoding='utf8') as f:
        for line in f:
            d=json.loads(line);r=d['meta']
            if r['envelope']==EID and r['policy'] in ('EFT_REFERENCE','PAIR_COALESCE_V1'):
                source[int(r['seed']),r['scenario'],r['policy']]=d
    decomposition=[]
    for seed in spec['reproduction_seeds']:
        for sc in spec['scenarios']:
            a=source[seed,sc,'PAIR_COALESCE_V1'];b=source[seed,sc,'EFT_REFERENCE']
            for x,y in zip(a['ledger'],b['ledger']):
                assert x['id']==y['id']
                decomposition.append(dict(seed=seed,scenario=sc,ordinal=x['ordinal'],task=x['task'],
                    arrival_s=x['arrival_ns']/1e9,backend=x['backend'],eft_backend=y['backend'],
                    deadline_ms=x['deadline_offset_ns']/1e6,response_ms=x['response_ns']/1e6,eft_response_ms=y['response_ns']/1e6,
                    wait_ms=(x['dispatch_ns']-x['arrival_ns'])/1e6,eft_wait_ms=(y['dispatch_ns']-y['arrival_ns'])/1e6,
                    own_response_ms=(x['response_ns']-x['dispatch_ns']+x['arrival_ns'])/1e6,
                    eft_own_response_ms=(y['response_ns']-y['dispatch_ns']+y['arrival_ns'])/1e6,
                    lane_hold_ms=(x['lane_available_ns']-x['dispatch_ns'])/1e6,
                    response_delta_ms=(x['response_ns']-y['response_ns'])/1e6,
                    missed=x['response_ns']>x['deadline_offset_ns'],eft_missed=y['response_ns']>y['deadline_offset_ns']))
    s.save_rows(out/'original_request_decomposition.csv',decomposition)
    import time
    began=time.monotonic();rows=[];reproduced=0
    frozen,case=p.inputs(p.BUNDLE);initial=case['initial'];e=next(e for e in s.envelopes() if e['id']==EID)
    with (out/'local_records.jsonl').open('w',encoding='utf8') as f:
        for stage,seeds in [('reproduction',spec['reproduction_seeds']),('fresh',spec['fresh_seeds'])]:
            for seed in seeds:
                for sc in spec['scenarios']:
                    for pol in spec['policies']:
                        if time.monotonic()-began>300:raise TimeoutError('bounded PC study')
                        row,rr,c,_=simulate(frozen,initial,s.workload(e,seed),sc,pol)
                        if stage=='reproduction' and pol!=ID:
                            original=source[seed,sc,pol]
                            assert rr['ledger']==original['ledger'],'original ledger mismatch'
                            reproduced+=1
                        row={k:v for k,v in row.items() if not isinstance(v,(dict,list))}
                        guards=getattr(c,'guard_records',[])
                        row.update(stage=stage,seed=seed,scenario=sc,policy=pol,vetoes=sum(x['veto'] for x in guards))
                        rows.append(row)
                        f.write(json.dumps(dict(meta=row,ledger=rr['ledger'],decisions=rr['decisions'],guard=guards))+'\n')
    s.save_rows(out/'results.csv',rows)
    assert hashes=={str(x.relative_to(p.ROOT)):p.digest(x) for x in paths}
    summary=dict(spec=spec,reproduced_ledgers=reproduced,runs=len(rows),elapsed_s=time.monotonic()-began,
        original_missed_requests=sum(r['missed'] for r in decomposition),hashes_unchanged=True,device_commands=0)
    p.write(out/'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();run(args.output)
