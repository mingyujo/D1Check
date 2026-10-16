"""Pure rule/identity/trace fixtures. No simulation environment or NN."""
from pathlib import Path
import ast,copy,hashlib,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'src'),str(ROOT/'experiments/edf_cpu_first_20261016')]
from rules import installed,select_fifo,SPEC
from policy import select as select_edf
from shared_exact import L
K=L.load_module('pure_rules_kernel',ROOT/'experiments/long_scale_20261017/kernel_long.py')
def main(opfile,outfile):
    op=L.read(opfile)
    for p in op['pins']:L.pin(p)
    tests=[]
    for p in HERE.glob('*.py'):compile(p.read_bytes(),str(p),'exec');ast.parse(p.read_bytes())
    tests.append('all sources AST/compile')
    old=ast.parse((ROOT/'experiments/long_scale_20261017/run_scale_v4.py').read_bytes());new=ast.parse((HERE/'shared_exact.py').read_bytes())
    for name in ('public_input','metrics','save_binary'):
        a=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name);b=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==name)
        assert ast.dump(a)==ast.dump(b);tests.append('exact shared '+name)
    def q(rid,ordinal,arrival,due,priority='N'):
        return dict(request_id=rid,ordinal=ordinal,task='C',priority=priority,scheduled_arrival_ns=arrival,queue_entry_ns=arrival,deadline_ns=due)
    a=q('a',0,0,20_000_000_000);b=q('b',1,1,10_000_000_000,'U');state=dict(now_ns=100,queue=[b,a],owners=[])
    assert select_fifo(state)['request_id']=='a';tests.append('FIFO arrival; ignores tighter deadline')
    assert select_edf(state)['request_id']=='b';tests.append('EDF absolute deadline; priority not separate multiplier')
    assert select_fifo(state)['route']=='CPU';tests.append('FIFO both idle CPU-first')
    owned={**state,'owners':[dict(route='CPU',request_id='own',task='D',dispatch_ns=0)]}
    assert select_fifo(owned)['route']=='GPU';tests.append('FIFO free GPU for either task')
    assert select_fifo({**owned,'owners':owned['owners']+[dict(route='GPU')]})['kind']=='RESOURCE_WAIT';tests.append('no third owner')
    assert select_fifo({**state,'queue':[]})['kind']=='RESOURCE_WAIT';tests.append('empty queue')
    try:select_fifo({**state,'queue':[q('future',0,101,1000)]});raise AssertionError('future accepted')
    except ValueError:tests.append('future queue rejected')
    tied={**state,'queue':[q('z',4,0,1000),q('x',3,0,1000)]}
    assert select_fifo(tied)['request_id']=='x';tests.append('ordinal tie break')
    rows={v['request_id']:{**v,'context':{'rid':v['request_id']}} for v in state['queue']}
    class Model:
        def nominal(self,context,task,route,**kw):return dict(occupancy_ns=1_000_000_000,response_ns=900_000_000)
    model=Model();original=K._rule_action;expected=original('ATC',state,rows,model,'READY_QUEUE',None,True);before=copy.deepcopy(state);trace=[]
    with installed(K,trace):
        actual=K._rule_action('ROLLING_ATC',state,rows,model,'READY_QUEUE',None,True)
        assert actual==expected and actual['request_id']=='b';tests.append('ATC delegates same native score/action')
        assert len(trace)==1 and len(trace[0]['nominal_calls'])==4;tests.append('trace captures native calls once')
        assert K._rule_action('FIFO_CPU_FIRST',state,rows,model,'READY_QUEUE',None,True)==select_fifo(state);tests.append('FIFO hook')
    assert K._rule_action==original and state==before;tests.append('hooks restore; state immutable')
    assert not SPEC['shared_execution']['multi_step_lookahead_optimization'];tests.append('rolling vs lookahead contract')
    assert 'torch' not in sys.modules;tests.append('no NN module imported/executed')
    L.write_new(outfile,dict(status='PASS',tests=tests,groups=len(tests),environment_START=0,NN_execution=0,operation_sha256=L.sha(opfile)))
    print(json.dumps(dict(status='PASS',groups=len(tests),environment_START=0,NN_execution=0)))
if __name__=='__main__':main(*sys.argv[1:])
