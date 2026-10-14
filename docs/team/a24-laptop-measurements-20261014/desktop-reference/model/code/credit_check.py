"""Tests causal credit at same-time events/startup and not-yet-due requests."""
import numpy as np
from common import OUT,save,H180
import ppo
def run():
    class C:
        errors=[];alpha=.95;frames=[]
    ctl=C()
    ctl.frames=[dict(time_ns=t,value=np.zeros(5,np.float32),learn_actor=True,heat=.5) for t in (10,20)]
    raw=dict(ledger=[dict(id="r",priority="urgent",arrival_ns=0,deadline_offset_ns=20,response_ns=25,status="succeeded")],
      cost_120={"reference_ap_c":0.},nominal_resident_w=0.,
      cost_samples=[dict(time_ns=0,energy_j=0.,ap_area=0.),dict(time_ns=15,energy_j=1.,ap_area=0.),
       dict(time_ns=20,energy_j=2.,ap_area=0.),dict(time_ns=20,energy_j=4.,ap_area=0.,reason="dispatch",decision_index=1),
       dict(time_ns=30,energy_j=5.,ap_area=0.),dict(time_ns=H180,energy_j=5.,ap_area=0.)])
    frames,meta=ppo.labels(ctl,raw,ppo.Settings(),"DENSE")
    if not np.allclose([f["cost"][0] for f in frames],[.1,.15],atol=1e-7):raise ValueError("interval/startup causal credit")
    if [float(f["cost"][2]) for f in frames]!=[1.,0.]:raise ValueError("expired-deadline charged to post-event action")
    raw["ledger"][0].update(arrival_ns=119_000_000_000,deadline_offset_ns=2_000_000_000,status="unfinished")
    raw["ledger"][0].pop("response_ns")
    _,meta2=ppo.labels(ctl,raw,ppo.Settings(),"DENSE")
    if meta2["total_cost"][2]!=0 or meta2["total_cost"][4]!=1:raise ValueError("not-yet-due versus incomplete")
    result=dict(status="PASS",new_environments=0,new_experiences=0,interval_credit_precedes_event=True,
        startup_credit_current_action=True,deadline_event_precedes_new_choice=True,unfinished_separate_from_not_due=True)
    save(OUT/"CAUSAL_CREDIT_CHECK.json",result);return result
if __name__=="__main__":print(run())
