"""Exhaustive public-state equivalence check; not a new physical simulation."""
import types,random,math
from common import OUT,read,save
import candidates,study
def run():
    text=(OUT/"source_generations/P0_ORIGINAL/candidates.py").read_text(encoding="utf-8")
    old=types.ModuleType("legacy_priority_p0");exec(compile(text,"P0_ORIGINAL/candidates.py","exec"),old.__dict__)
    tested=0
    for device in ("A24","S26"):
        profile=study.profile(device,"M1_coupled");model=profile["service_anchor"]
        if "service" in model:model=model["service"]
        for occupied in (None,("classification","CPU"),("detection","CPU"),("classification","GPU"),("classification","NPU")):
            if occupied and occupied[1]=="NPU" and device=="A24":continue
            for factor in (1.,1.1,1.3333333333):
                for case in range(20):
                    rng=random.Random(case);waiting=[]
                    for i in range(12):
                        task="classification" if rng.random()<.6 else "detection"
                        waiting.append(dict(id=f"q{i}",ordinal=i,task=task,priority="urgent" if task=="classification" else "normal",
                            arrival_ns=35_000_000_000+i*10_000_000,deadline_offset_ns=int(2.2e9 if task=="classification" else 5e9),work_units=1))
                    class View:
                        now=50_000_000_000;wait_used=0;last_release={b:0 for b in candidates.BACKENDS}
                        def routes(self,q):
                            return ("CPU",) if q["task"]=="detection" else candidates.BACKENDS if device=="S26" else ("CPU","GPU")
                        def estimate(self,q,b):
                            if device=="A24":key=q["task"]+"|"+b
                            else:
                                context="B2_PARALLEL" if b=="GPU" or q["task"]=="detection" and occupied==("classification","GPU") else "NPU_PARALLEL" if b=="NPU" or q["task"]=="detection" and occupied==("classification","NPU") else "CPU_URGENT"
                                key=context+"|"+q["task"]+"|"+b
                            ds=list(model["means"][key]);ds[1]*=factor;return ds
                        def public(self):
                            lanes={b:None for b in candidates.BACKENDS}
                            if occupied:
                                t,b=occupied;q=dict(id="owner",task=t,priority="urgent" if t=="classification" else "normal",
                                    arrival_ns=0,ordinal=0,deadline_offset_ns=6_000_000_000)
                                lanes[b]=dict(request=q,phase="EXECUTING",dispatch=self.now-10_000_000,estimate_ns=self.estimate(q,b))
                            return dict(now_ns=self.now,lanes=lanes,npu_enabled=device=="S26",device=device,ap_c=33.,reference_ap_c=31.,power_w=1.,
                                thermal_observation_age_s=0.,power_observation_age_s=0.,observed_history=[],recent_activity={b:0. for b in candidates.BACKENDS})
                        def feasible(self,q,b):
                            if occupied and occupied[1]==b:return False
                            labels={occupied,(q["task"],b)} if occupied else {(q["task"],b)}
                            return len(labels)==1 or labels in [{("classification","GPU"),("detection","CPU")},{("classification","NPU"),("detection","CPU")}]
                        def local_proxy(self,q,b,ds):return sum(ds)/1e9,1.
                    bank=candidates.build(View(),waiting,"FULL",False)
                    for name in ("SPT","WSPT"):
                        if candidates.Rule(name).index(bank)!=old.Rule(name).index(bank):raise ValueError("old priority differs: "+str((device,occupied,factor,case,name)))
                        tested+=1
    result=dict(status="PASS",public_state_rule_checks=tested,new_environments=0,
        scope="unit1, classification urgent/detection normal, supported routes, common observed rate; registered case family",
        SPT_WSPT_pre_and_post_choices_equal=True,LST_needs_new144_controls=True)
    save(OUT/"PRIORITY_EQUIVALENCE.json",result);return result
if __name__=="__main__":print(run())
