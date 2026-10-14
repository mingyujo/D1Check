"""Explicit conditional observer simulator; fresh boundary, never delay earlier requests."""
import argparse
import copy
import json
from pathlib import Path
from tools import d1_s26_integrated as old
from tools import d1_s26_npu_engine as e
from tools import d1_s26_pair_observer_model as c

SCHEMA='s26-pair-observer-v1'


def validate_bundle(b):
    if b.get('schema')!=SCHEMA or b.get('strict_eligible') is not False or b.get('experiment_ready') is not False:raise ValueError('observer simulator schema')
    if b['service']['schema']!=e.VERSION or b['capabilities']!=dict(classification=['CPU','GPU','NPU'],detection=['CPU'],max_concurrent=2,pairs=['CG_DC','CN_DC']):raise ValueError('service capabilities')
    c.validate(b['cost']);return b


def validate_boundary_requests(requests,mode):
    old.validate_requests(requests)
    if mode=='OBSERVED35' and any(q['arrival_ns']<35_000_000_000 for q in requests):raise ValueError('observed35 requires an already quiet prefix; no request may be delayed/dropped')


class Device(old.IntegratedDevice):
    def __init__(self,bundle,split='confirm',environment_seed=0,npu=True,deterministic=False,initial=None):
        validate_bundle(bundle);e.Device.__init__(self,bundle['service'],split,environment_seed,npu,deterministic)
        init=copy.deepcopy(initial or bundle['cost']['default_initial_assumption']);c.validate_initial(init,bundle['cost']);self.now=int(init['anchor_s']*1e9)
        self.cost=c.CostState(bundle['cost'],init)


def simulate(bundle,requests,controller,split='confirm',environment_seed=0,npu=True,deterministic=False,initial=None):
    validate_boundary_requests(requests,bundle['cost']['mode']);pending=sorted(copy.deepcopy(requests),key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']))
    dev=Device(bundle,split,environment_seed,npu,deterministic,initial);waiting=[];cursor=0
    while dev.now<e.HORIZON:
        dev.advance(dev.now)
        while cursor<len(pending) and pending[cursor]['arrival_ns']<=dev.now:waiting.append(pending[cursor]);cursor+=1
        if waiting:
            jobs=controller.choose(dev,waiting)
            if jobs:
                dev.dispatch(jobs);ids={q['id'] for q,b in jobs};waiting=[q for q in waiting if q['id'] not in ids];continue
        if cursor==len(pending) and not waiting and dev.next_event() is None:break
        future=[e.HORIZON]
        if cursor<len(pending):future.append(pending[cursor]['arrival_ns'])
        if dev.next_event() is not None:future.append(dev.next_event())
        dev.advance(min(t for t in future if t>dev.now))
    service_end=dev.now;dev.advance(e.HORIZON);ledger=[]
    for q in requests:
        r=copy.deepcopy(dev.records.get(q['id'],dict(q,status='unfinished')))
        if r['status']=='running':r['status']='unfinished'
        ledger.append(r)
    metrics=e.metrics(ledger);prefix=copy.deepcopy(dev.current_cost());all_available=not dev.cost.owners
    if all_available:dev.cost.advance(180);cool=dev.current_cost()
    else:cool=None
    complete=metrics['incomplete']==0
    metrics.update(energy_j=prefix['energy_window_j'] if complete else None,peak_ap_c=cool['peak_after35_c']['AP'] if complete and cool else None,mean_ap_c=cool['mean_after35_c']['AP'] if complete and cool else None,
                   cost_model_status='conditional_observer06',strict_eligible=False,experiment_ready=False)
    return dict(schema=SCHEMA,metrics=metrics,ledger=ledger,events=dev.events,service_end_ns=service_end,end_ns=e.HORIZON,environment_seed=environment_seed,npu=npu,
                cost_120=prefix,cooling_180=cool,cost_trace=dev.cost.grid,initialization_mode=bundle['cost']['mode'],initialization_evidence=dev.cost.init['evidence'],policy_cost_learning=False,strict_eligible=False,experiment_ready=False)


def main():
    a=argparse.ArgumentParser();a.add_argument('--model',required=True,type=Path);a.add_argument('--requests',required=True,type=Path);a.add_argument('--out',required=True,type=Path)
    a.add_argument('--policy',choices=('FIFO','EFT','EDD','ATC','FIFO_HOL','PPO'),default='ATC');a.add_argument('--checkpoint',type=Path);a.add_argument('--dependencies',type=Path)
    a.add_argument('--initial',type=Path);a.add_argument('--environment-seed',type=int,default=63012400);a.add_argument('--no-npu',action='store_true');v=a.parse_args()
    if v.out.exists():raise ValueError('existing result never overwritten')
    ctl=old.load_controller(v.policy,v.checkpoint,e.read(v.dependencies)['sources'] if v.dependencies else None);requests=e.read(v.requests);requests=requests if isinstance(requests,list) else requests['requests']
    result=simulate(e.read(v.model),requests,ctl,environment_seed=v.environment_seed,npu=not v.no_npu,initial=e.read(v.initial) if v.initial else None)
    e.write(v.out,result);print(json.dumps(result['metrics'],ensure_ascii=False))


if __name__=='__main__':main()
