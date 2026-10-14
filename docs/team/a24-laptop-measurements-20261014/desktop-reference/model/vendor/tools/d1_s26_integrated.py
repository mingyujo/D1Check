"""Executable S26 <=120s service + current-event costs, fixed policies/PPO."""
import argparse
import copy
import json
from pathlib import Path
from tools import d1_s26_npu_engine as e
from tools import d1_s26_npu_policy as p
from tools import d1_s26_integrated_cost as c

SCHEMA='s26-integrated-simulator-v1'


def validate_bundle(bundle):
    if bundle.get('schema')!=SCHEMA or bundle.get('strict_eligible') is not False or bundle.get('experiment_ready') is not False:raise ValueError('integrated ABI/eligibility')
    if bundle['service']['schema']!=e.VERSION or bundle['capabilities']['max_concurrent']!=2:raise ValueError('service/capability ABI')
    if bundle['capabilities']['classification']!=['CPU','GPU','NPU'] or bundle['capabilities']['detection']!=['CPU']:raise ValueError('unsupported capabilities')
    c.validate(bundle['cost']);return bundle


class IntegratedDevice(e.Device):
    def __init__(self,bundle,split='confirm',environment_seed=0,npu=True,deterministic=False,initial=None):
        validate_bundle(bundle);super().__init__(bundle['service'],split,environment_seed,npu,deterministic)
        initial=copy.deepcopy(initial or bundle['cost']['default_initial_assumption'])
        self.cost=c.CostState(bundle['cost'],initial['baseline_w'],initial['reference_c'],initial['initial_c'])

    def dispatch(self,jobs):
        self.cost.advance(self.now/1e9);super().dispatch(jobs)
        for q,b in jobs:self.cost.dispatch(q['id'],q['task'],b)

    def advance(self,to):
        if to<self.now or to>e.HORIZON:raise ValueError('service clock <=120s')
        # Future event times belong to the environment. Policies never receive them.
        while self._events and self._events[0][0]<=to:
            at=self._events[0][0];self.cost.advance(at/1e9);before=len(self.events);super().advance(at)
            for ev in self.events[before:]:
                if ev['phase']=='AVAILABLE':self.cost.available(ev['id'],ev['backend'])
        self.cost.advance(to/1e9);super().advance(to)

    def current_cost(self):return self.cost.snapshot()


def validate_requests(requests):
    if not requests or len(requests)>1200 or len({q.get('id') for q in requests})!=len(requests):raise ValueError('empty/duplicate/oversize request roster')
    for q in requests:
        if set(q)!=e.REQUEST_FIELDS or not isinstance(q['id'],str) or not q['id']:raise ValueError('request ABI/id')
        if any(not isinstance(q[k],int) or isinstance(q[k],bool) for k in ('ordinal','arrival_ns','deadline_offset_ns')):raise ValueError('integer ns/ordinal required')
        if not 0<=q['arrival_ns']<e.HORIZON or q['ordinal']<0 or q['priority'] not in ('urgent','normal'):raise ValueError('arrival/priority range')
        cap=1_500_000_000 if q['priority']=='urgent' else 6_000_000_000
        if not 0<q['deadline_offset_ns']<=cap:raise ValueError('deadline exceeds existing service cap')
        e.routes(q)


def simulate(bundle,requests,controller,split='confirm',environment_seed=0,npu=True,deterministic=False,initial=None):
    validate_requests(requests)
    pending=sorted(copy.deepcopy(requests),key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']))
    dev=IntegratedDevice(bundle,split,environment_seed,npu,deterministic,initial);waiting=[];cursor=0
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
    metrics=e.metrics(ledger);prefix=copy.deepcopy(dev.current_cost());trace120=copy.deepcopy(dev.cost.grid)
    # No invented future completion/idle cooling when an owner remains at cutoff.
    all_available=not dev.cost.owners
    if all_available:
        dev.cost.advance(180);cool=dev.current_cost()
    else:cool=None
    complete=metrics['incomplete']==0
    metrics.update(energy_j=prefix['energy_window_j'] if complete else None,
                   peak_ap_c=cool['peak_after35_c']['AP'] if complete and cool else None,
                   mean_ap_c=cool['mean_after35_c']['AP'] if complete and cool else None,
                   cost_model_status='exploratory',strict_eligible=False,experiment_ready=False)
    return dict(schema=SCHEMA,metrics=metrics,ledger=ledger,events=dev.events,service_end_ns=service_end,end_ns=e.HORIZON,
       split=split,environment_seed=environment_seed,npu=npu,cost_120=prefix,cooling_180=cool,cost_trace=dev.cost.grid,
       prefix_trace120=trace120,cooling_status='provided; all lanes AVAILABLE at120' if all_available else 'UNAVAILABLE; unfinished owner at120',
       quality=bundle['quality'],implementation_complete=bundle.get('implementation_complete',False),
       policy_cost_learning=False,strict_eligible=False)


def load_controller(role,checkpoint=None,dependencies=None):
    if role in ('FIFO','EFT','EDD','ATC','FIFO_HOL'):return p.Controller(role)
    if role!='PPO' or checkpoint is None or dependencies is None:raise ValueError('PPO requires explicit192/64 service checkpoint and dependency contract')
    from tools import d1_s26_npu_ppo as rl
    net=rl.Learner.load(Path(checkpoint),dependencies).network
    return p.Controller(network=net,deterministic=True,collect=False)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--model',required=True,type=Path);ap.add_argument('--requests',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--policy',choices=('FIFO','EFT','EDD','ATC','FIFO_HOL','PPO'),default='ATC');ap.add_argument('--checkpoint',type=Path);ap.add_argument('--dependencies',type=Path)
    ap.add_argument('--split',choices=('train','dev','confirm'),default='confirm');ap.add_argument('--environment-seed',type=int,default=6301201);ap.add_argument('--no-npu',action='store_true');ap.add_argument('--mean-service',action='store_true');ap.add_argument('--initial',type=Path)
    a=ap.parse_args();bundle=e.read(a.model);data=e.read(a.requests);requests=data if isinstance(data,list) else data['requests']
    ctl=load_controller(a.policy,a.checkpoint,e.read(a.dependencies)['sources'] if a.dependencies else None)
    result=simulate(bundle,requests,ctl,a.split,a.environment_seed,not a.no_npu,a.mean_service,e.read(a.initial) if a.initial else None)
    e.write(a.out,result);print(json.dumps(result['metrics'],ensure_ascii=False))


if __name__=='__main__':main()
