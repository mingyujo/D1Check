"""New completion-window reward contracts, independent of base label routine."""
import numpy as np
from run_packing import *
import completion_labels as C
def main():
    op=read(HERE.parent/'minmax_joint_20261018/OPERATION.json');physics=B.Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**op['physics']));state=dict(temperature_c=26.,shared_z=1.);trace=[]
    for i in range(5):
        active=[dict(task='C',route='CPU',stage=1)] if i<2 else [];following,terms=physics.transition(state,active,1.);trace.append(dict(start_ns=(35+i)*10**9,end_ns=(36+i)*10**9,state=dict(state),next_state=following,active=active,**terms));state=following
    result=dict(trace=trace,requests=[dict(available_ns=37*10**9)]);E=sum(t['increment']+t['baseline'] for t in trace[:2]);Q=sum(t['temperature_area']-26 for t in trace);reference=dict(completion_total_J_proxy=E,mean_AP_c=26+Q/5);frames=[dict(time_ns=35_250_000_000),dict(time_ns=36_250_000_000),dict(time_ns=37_250_000_000)];case=dict(drain_stop_s=40.)
    original=C.B.repaired_labels
    def base(result,frames,*unused):
        costs=np.zeros((len(frames),5));costs[-1,2:]=[.2,.3,.4];return costs,dict(cost_sum=costs.sum(0).tolist())
    C.B.repaired_labels=base
    try:
        energy,ea=C.labels(result,frames,case,physics,{},40*10**9,reference,False);joint,ja=C.labels(result,frames,case,physics,{},40*10**9,reference,True)
        assert abs(.5*energy[:,0].sum()-1)<1e-12 and abs(.5*joint[:,0].sum()-1)<1e-12
        assert np.array_equal(energy[:,2:],base(result,frames)[0][:,2:]) and np.array_equal(joint[:,2:],energy[:,2:])
        assert abs(ea['prefix_records'][-1]['completion_energy_prefix_J_proxy']-E)<1e-12 and ea['prefix_records'][-1]['end_ns']==40*10**9
        assert ea['prefix_records'][-1]['heat_excess_prefix_Cs']>ea['prefix_records'][1]['heat_excess_prefix_Cs']
        worse={**reference,'mean_AP_c':26+Q/10};value,a=C.labels(result,frames,case,physics,{},40*10**9,worse,True);assert abs(.5*value[:,0].sum()-2)<1e-12
        refined=[dict(time_ns=t) for t in (35_100_000_000,35_250_000_000,36_100_000_000,36_250_000_000,37_250_000_000)];v,_=C.labels(result,refined,case,physics,{},40*10**9,reference,True);assert abs(v[:,0].sum()-joint[:,0].sum())<1e-12
        try:C.labels(result,frames,case,physics,{},40*10**9,{**reference,'completion_total_J_proxy':0.},True);raise AssertionError('Invalid reference accepted')
        except ValueError:pass
    finally:C.B.repaired_labels=original
    B.G.write_new(HERE/'COMPLETION_CONTRACTS.json',dict(status='PASS',contracts=6,completion_baseline_end_clipped=True,heat_tail_same_H=True,retained_deadline_columns=True,objective_no_compensation=True,refined_decision_telescope=True,positive_reference_required=True,new_environment_START=0,new_optimizer_steps=0));print('COMPLETION_REWARD_CONTRACTS_PASS',flush=True)
if __name__=='__main__':main()
