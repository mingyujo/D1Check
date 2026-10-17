"""Pure adversarial RR tests. No model, simulator, NN or environment imports."""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from rr_policy import RoundRobin, installed

def run():
    checks = []
    def ok(x, name):
        if not x: raise AssertionError(name)
        checks.append(name)
    def q(i, task='C', arrival=1):
        return dict(request_id=str(i), task=task, scheduled_arrival_ns=arrival,
                    queue_entry_ns=arrival, ordinal=i, deadline_ns=100-i)
    def state(rows, owners=()): return dict(now_ns=10, queue=rows, owners=list(owners))
    rr = RoundRobin(); s = state([q(1,'D'),q(2,'C')]); old = copy.deepcopy(s)
    ok(rr(s)['request_id']=='2','initial C turn, independent of deadline')
    ok(rr(s)['request_id']=='1','next D turn')
    ok(s==old,'public state not modified')
    rr=RoundRobin(); ok(rr(state([q(9,'D')]))['request_id']=='9','empty C skipped')
    ok(rr.turn=='C','turn follows actually dispatched class')
    ok(rr(state([]))=={'kind':'RESOURCE_WAIT'} and rr.turn=='C','empty queue preserves turn')
    busy=[dict(route='CPU'),dict(route='GPU')]
    ok(rr(state([q(1)],busy))=={'kind':'RESOURCE_WAIT'} and rr.turn=='C','busy preserves turn')
    ok(rr(state([q(1)],[dict(route='CPU')]))['route']=='GPU','free GPU for C')
    ok(RoundRobin()(state([q(1,'D')]))['route']=='CPU','both free CPU first for D')
    ok(RoundRobin()(state([q(9,'C',2),q(3,'C',1)]))['request_id']=='3','FIFO within class')
    ok(RoundRobin()(state([q(9),q(3)]))['request_id']=='3','ordinal tie break')
    for label,s in [('future',state([q(1,arrival=11)])),('duplicate',state([q(1),q(1)])),
                    ('unknown task',state([q(1,'X')])),('duplicate owner',state([q(1)],[dict(route='CPU')]*2))]:
        try: RoundRobin()(s)
        except ValueError: checks.append(label+' rejected')
        else: raise AssertionError(label)
    sentinel=lambda *args: {'kind':'ORIGINAL'}
    kernel=SimpleNamespace(_rule_action=sentinel,POLICIES=('OLD',)); trace=[]
    with installed(kernel,trace):
        action=kernel._rule_action('RR_CPU_FIRST',state([q(1)]),None,None,None,None)
        ok(action['request_id']=='1' and len(trace)==1,'hook logs actual dispatch')
        ok(kernel._rule_action('OLD',None,None,None,None,None)['kind']=='ORIGINAL','other policies unchanged')
    ok(kernel._rule_action is sentinel and kernel.POLICIES==('OLD',),'hook restores')
    ok('torch' not in sys.modules and 'lab_backend' not in sys.modules,'no NN/model import')
    return {'status':'PASS','groups':len(checks),'tests':checks,'environment_START':0,'NN_execution':0}

if __name__=='__main__':
    target=Path(sys.argv[1])
    with target.open('x',encoding='utf-8') as f: json.dump(run(),f,ensure_ascii=False,indent=2)
