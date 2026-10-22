"""Six objective-preserving deadline timing contracts; no native episodes."""
from pathlib import Path
import sys,numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'packing_rl_20261018'))
from run_packing import B,read,pt,loadpt,equal,Learner,ROOT
import event_labels as E
def main():
    requests=[dict(request_id='late-U',priority='U',scheduled_arrival_ns=35*10**9,deadline_ns=40*10**9,response_ns=50*10**9),dict(request_id='ontime-N',priority='N',scheduled_arrival_ns=35*10**9,deadline_ns=44*10**9,response_ns=42*10**9),dict(request_id='missing-U',priority='U',scheduled_arrival_ns=35*10**9,deadline_ns=41*10**9,response_ns=None)]
    endpoints=[39,41,51,60];frames=[dict(time_ns=t*10**9) for t in (35,39,41,51)];case=dict(n=3,drain_stop_s=60.)
    def completion(result,frames,case,*rest):
        ends=[f['time_ns'] for f in frames[1:]]+[60*10**9];costs=np.zeros((len(frames),5));costs[-1,0]=.8;costs[-1,4]=.3
        times=[f['time_ns'] for f in frames]
        for q in result['requests']:
            if q['response_ns'] is None or q['response_ns']>60*10**9:continue
            terminal=E.deadline_prefix([q],60*10**9,case['n'],60*10**9);i=max(0,min(len(frames)-1,int(np.searchsorted(times,q['response_ns'],side='right'))-1));costs[i,2:4]+=terminal
        return costs,dict(prefix_records=[dict(end_ns=t) for t in ends],cost_sum=costs.sum(0).tolist())
    previous=E.completion;E.completion=completion
    try:
        result=dict(requests=requests);original,_=completion(result,frames,case);shifted,audit=E.labels(result,frames,case,None,None,60*10**9,{},False)
        assert np.max(abs(original.sum(0)-shifted.sum(0)))<1e-12 and np.array_equal(original[:,[0,1,4]],shifted[:,[0,1,4]])
        assert shifted[1,2]>0 and original[1,2]==0,'Irreversible miss charged before delayed completion'
        for t,v in zip([x*10**9 for x in endpoints],E.sweep(requests,[x*10**9 for x in endpoints],3,60*10**9)):assert np.max(abs(v-E.deadline_prefix(requests,t,3,60*10**9)))<1e-12
        refined=[dict(time_ns=t*10**9) for t in (35,38,39,40,41,45,50,51)];fine,_=E.labels(result,refined,case,None,None,60*10**9,{},False);assert np.max(abs(fine.sum(0)-shifted.sum(0)))<1e-12
        for response in (40*10**9,40*10**9+1,40*10**9+2,61*10**9,None):
            q={**requests[0],'response_ns':response};end=[40*10**9,40*10**9+1,40*10**9+2,60*10**9]
            for t,v in zip(end,E.sweep([q],end,1,60*10**9)):assert np.max(abs(v-E.deadline_prefix([q],t,1,60*10**9)))<1e-10
    finally:E.completion=previous
    # The same original BC warm / two Adam / RNG is the only starting point.
    warm=ROOT/'results/PACKING_RL_20261018_01/PACKING_BC_ONLY.FINAL_WARM.pt.gz'
    if warm.exists():
        state=loadpt(warm);equal(state,Learner(state).snapshot());equal(state,loadpt(ROOT/'results/PACKING_RL_20261018_01/PACKING_ENERGY_TRAIN_001.BEFORE.pt.gz'))
    B.G.write_new(HERE/'CONTRACTS.json',dict(status='PASS',contracts=6,episode_objective_equal=True,energy_heat_unfinished_unchanged=True,deadline_signal_before_completion=True,fast_sweep_equals_naive=True,refined_decision_invariant=True,missing_drain_and_ns_boundaries=True,parent_warm_two_Adam_RNG_exact=warm.exists(),new_environment_START=0,new_optimizer_steps=0));print('DEADLINE_EVENT_CONTRACTS_PASS',flush=True)
if __name__=='__main__':main()
