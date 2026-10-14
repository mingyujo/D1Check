"""Policy-independent synthetic workloads and cryptographically disjoint splits."""
import random,math
from common import digest,ALPHAS
SPECS=(
 ("steady64_low",64,.50,1,.4),
 ("steady64_mid",64,.50,1,.7),
 ("steady64_edge",64,.50,1,.95),
 ("burst64",64,.50,8,.9),
 ("phased128",128,.50,8,.9),
 ("burst128",128,.50,16,.9),
 ("class128",128,.75,8,.9),
 ("detect128",128,.25,8,.9),
 ("class256",256,.75,16,1.1),
 ("mixed256",256,.50,16,1.3),
 ("single_class252",252,1.,1,.9),
 ("class_burst256",256,1.,8,.9),
)
def environment_seed(split,index):
    return int(digest(["RATR37-V2-ENV",split,index])[:12],16)%(2**31-1)
def arrival_seed(split,index):
    return int(digest(["RATR37-V2-ARRIVAL",split,index])[:12],16)%(2**31-1)
def means(profile):
    m=profile["service_anchor"]
    if "service" in m:m=m["service"]
    out={}
    for k,ds in m["means"].items():
        task,b=k.split("|")[-2:];out.setdefault(task+"_"+b,[]).append(ds)
    return {k:[sum(row[i] for row in rows)/len(rows) for i in range(5)] for k,rows in out.items()}
def requests(profile,case_index,split,index):
    name,n,ratio,batch,load=SPECS[case_index]
    seed=arrival_seed(split,index);rng=random.Random(seed)
    nc=round(n*ratio);tasks=["classification"]*nc+["detection"]*(n-nc);rng.shuffle(tasks)
    ms=means(profile);capacity=max(nc*sum(ms["classification_GPU"]),(n-nc)*sum(ms["detection_CPU"]))
    interval=capacity/n/load
    if name=="single_class252":interval=333_200_000.
    if name=="class_burst256":interval=250_000_000.
    caps={"urgent":2.2e9,"normal":5e9} if profile["device"]=="A24" else {"urgent":.8e9,"normal":2e9}
    qs=[]
    for i,task in enumerate(tasks):
        group=i//batch
        # All rules get the identical arrival jitters; do not condition on policy outcomes.
        jitter=.005 if name=="single_class252" else .02
        off=group*batch*interval*(1+rng.uniform(-jitter,jitter))
        if name=="phased128":off=group*batch*interval+(.15*group*batch*interval if group>=8 else 0)
        priority="urgent" if task=="classification" else "normal"
        arrival=35_000_000_000+round(max(0,off))
        if not 0<=arrival<120e9:raise ValueError("registered arrival outside120s")
        qs.append(dict(id=f"RATR37V2_{split}_{seed}_{i}",ordinal=i,task=task,priority=priority,
                       arrival_ns=arrival,deadline_offset_ns=int(caps[priority]),work_units=1))
    return qs
def qualifies(m,alpha):
    if m["incomplete"] or m.get("energy_180_j") is None or m.get("mean_ap_c") is None:return False
    for pr in ("urgent","normal"):
        n=m[pr+"_planned"]
        if n and m[pr+"_on_time"]<math.ceil(alpha*n-1e-9):return False
    return True
def goal(m,b):
    if not m.get("energy_180_j") or not b.get("energy_180_j") or m.get("mean_ap_c") is None or b.get("mean_ap_c") is None:return None
    energy=(b["energy_180_j"]-m["energy_180_j"])/b["energy_180_j"]
    ap=b["mean_ap_c"]-m["mean_ap_c"]
    return dict(energy_reduction_pct=energy*100,mean_AP_reduction_c=ap,
                joint_target=energy>=.10 and ap>=.5,
                service_not_worse=all(m[p+"_on_time"]>=b[p+"_on_time"] for p in ("urgent","normal")))
