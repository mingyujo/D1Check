"""Paired case intervals, seed results, ablations and residual heat; no simulations."""
import csv,json,math,gzip
from array import array
import numpy as np
from common import OUT,ALPHAS,SEEDS,save,read,gzsave,digest
import cases

def interval(pairs,seed):
    groups={}
    for ci,e,t in pairs:groups.setdefault(ci,[]).append((e,t))
    note="Descriptive case-cluster resampling within fixed simulator assumptions; learner seeds and repeats are not independent case replicates. No physical-parameter or real-device population interval."
    if len(groups)<2:return dict(energy_CI95=None,AP_CI95=None,independent_case_clusters=len(groups),strict_mean_target_lower_bounds=False,note=note)
    ordered=sorted(groups);sums=np.array([np.sum(groups[k],axis=0) for k in ordered]);ns=np.array([len(groups[k]) for k in ordered])
    rng=np.random.default_rng(seed);indices=rng.integers(0,len(groups),(4000,len(groups)))
    sampled=sums[indices].sum(1)/ns[indices].sum(1)[:,None]
    lo=np.quantile(sampled,.025,axis=0);hi=np.quantile(sampled,.975,axis=0)
    return dict(energy_CI95=[float(lo[0]),float(hi[0])],AP_CI95=[float(lo[1]),float(hi[1])],
       strict_mean_target_lower_bounds=bool(lo[0]>=10 and lo[1]>=.5),independent_case_clusters=len(groups),
       note=note)

def write_table(name,rows):
    save(OUT/(name+".json"),rows)
    with (OUT/(name+".csv")).open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]) if rows else [])
        writer.writeheader();writer.writerows(rows)

def normal_qualifies(m,alpha):
    return (not m["incomplete"] and m.get("energy_180_j") is not None and m.get("mean_ap_c") is not None
            and (not m["normal_planned"] or m["normal_on_time"]>=math.ceil(alpha*m["normal_planned"]-1e-9)))

def policy_label(row,frozen):
    suffix=row["identity"].split(f"_C{row['case_index']}_R{row['index']}_",1)[1]
    for arm in frozen["arms"]:
        if suffix.startswith(arm+"_S"):return arm
    return suffix

def summarize(chosen,baseline,alpha,tail,seed,qualifier=cases.qualifies):
    eligible=[];target=tail_worse=peak_worse=actor_qualified=baseline_qualified=service_worse=incomplete=0
    for row in chosen:
        b=baseline(row);m,bm=row["metrics"],b["metrics"]
        actor_qualified+=qualifier(m,alpha);baseline_qualified+=qualifier(bm,alpha)
        incomplete+=m["incomplete"]>0
        service_worse+=any(m[p+"_on_time"]<bm[p+"_on_time"] for p in ("urgent","normal"))
        effect=cases.goal(m,bm)
        if not effect or not qualifier(m,alpha) or not qualifier(bm,alpha):continue
        eligible.append((row["case_index"],effect["energy_reduction_pct"],effect["mean_AP_reduction_c"]))
        target+=effect["joint_target"]
        tail_worse+=tail[row["identity"]]>tail[b["identity"]]+1e-9
        peak_worse+=m["peak_ap_c"]>bm["peak_ap_c"]+1e-9
    return dict(total=len(chosen),policy_eligible=actor_qualified,baseline_eligible=baseline_qualified,
        common_eligible=len(eligible),policy_incomplete_pairs=incomplete,service_worse_pairs=service_worse,
        energy_reduction_pct_mean=float(np.mean([x[1] for x in eligible])) if eligible else None,
        mean_AP_reduction_c=float(np.mean([x[2] for x in eligible])) if eligible else None,
        joint_target_pairs=target,tail_AP180_worse_pairs=tail_worse,peak_AP_worse_pairs=peak_worse,
        **interval(eligible,seed))

def run():
    frozen=read(OUT/"FINAL_FREEZE.json")
    rows=[json.loads(s) for s in (OUT/"rows.jsonl").read_text(encoding="utf-8").splitlines()]
    final=[r for r in rows if r["split"]=="FINAL"];byid={r["identity"]:r for r in final}
    # One raw read per row. Retain scalar tails and compact timing arrays, not full raw traces.
    tail={};timings={};banks={}
    for row in final:
        with gzip.open(row["raw_path"],"rt",encoding="utf-8") as stream:raw=json.load(stream)
        tail[row["identity"]]=raw["cooling_180"]["ap_c"] if raw["cooling_180"] else math.nan
        name=policy_label(row,frozen);key=(row["device"],name)
        for item in raw["decisions"]:
            group=timings.setdefault(key,{k:array("d") for k in ("atc_us","build_us","nn_us","total_decision_us")})
            for k in group:
                if k in item:group[k].append(item[k])
            qbucket=min((1,8,32,64,128,512),key=lambda b:abs(b-item["queue"]))
            bank=banks.setdefault((row["device"],name,qbucket),dict(count=0,ATC_EDD_same=0,optional_wait=0,multiple_actions=0))
            bank["count"]+=1;bank["ATC_EDD_same"]+=item["atc_edd_order_same"]
            bank["optional_wait"]+=item.get("wait_ns",0)>0;bank["multiple_actions"]+=item["legal_count"]>1
    timing_rows=[]
    for (d,name),groups in timings.items():
        for component,values in groups.items():
            if values:
                values=np.frombuffer(values,dtype=np.float64)
                timing_rows.append(dict(device=d,policy=name,component=component,n=len(values),mean_us=float(values.mean()),
                    P95_us=float(np.quantile(values,.95)),max_us=float(values.max()),phone_inference_measurement=False))
    save(OUT/"TIMINGS_PC.json",timing_rows)
    save(OUT/"CANDIDATE_DIAGNOSTICS.json",[dict(device=d,policy=n,queue_bucket=q,**v) for (d,n,q),v in banks.items()])
    del timings
    result=[];seed_results=[];normal_results=[];ablation=[]
    for d in ("A24","S26"):
        for layer in frozen["layers"]:
            for arm in frozen["arms"]:
                for alpha in ALPHAS:
                    chosen=[r for r in final if r["device"]==d and r["layer"]==layer and r["alpha"] is not None
                            and abs(r["alpha"]-alpha)<1e-6 and f"_{arm}_S" in r["identity"]]
                    for baseline_name in frozen["baselines"]:
                        baseline=lambda r:byid[f"FINAL_{d}_{layer}_C{r['case_index']}_R{r['index']}_{baseline_name}"]
                        key=[d,layer,arm,alpha,baseline_name]
                        head=dict(device=d,layer=layer,evidence_grade=frozen["evidence_grades"][layer],arm=arm,alpha=alpha,baseline=baseline_name)
                        pooled=summarize(chosen,baseline,alpha,tail,int(digest(key)[:8],16))
                        result.append(dict(**head,**pooled))
                        for learner_seed in SEEDS:
                            subset=[r for r in chosen if f"_S{learner_seed}_A" in r["identity"]]
                            seed_results.append(dict(**head,learner_seed=learner_seed,
                                **summarize(subset,baseline,alpha,tail,int(digest(key+[learner_seed])[:8],16))))
                        normal_results.append(dict(**head,service_contract="normal only; urgent retained without a threshold; complete work required",
                            absent_normal_pairs=sum(r["metrics"]["normal_planned"]==0 for r in chosen),
                            **summarize(chosen,baseline,alpha,tail,int(digest(key+["normal"])[:8],16),normal_qualifies)))
                    if arm=="ATC_WAIT":
                        for other in ("NONDELAY","EDD_WAIT","DIRECT_WAIT"):
                            def comparator(row):
                                suffix=row["identity"].split("_ATC_WAIT_",1)[1]
                                return byid[f"FINAL_{d}_{layer}_C{row['case_index']}_R{row['index']}_{other}_{suffix}"]
                            ablation.append(dict(device=d,layer=layer,evidence_grade=frozen["evidence_grades"][layer],
                                arm=arm,alpha=alpha,baseline_arm=other,exposure=frozen["B"],
                                checkpoint_protocol="Equal total exposure and DEV selection opportunities; selected episode counts may differ",
                                **summarize(chosen,comparator,alpha,tail,int(digest([d,layer,alpha,other])[:8],16))))
    write_table("ALL_ARMS_CONFIDENCE",result)
    write_table("ALL_ARMS_SEED_SUMMARY",seed_results)
    write_table("NORMAL_ONLY_AUXILIARY",normal_results)
    write_table("ABLATION_SUMMARY",ablation)
    write_table("CHECKPOINT_EXPOSURE",frozen["models"])
    # Model changes are separate from the within-model policy effect.
    model_pairs=[]
    for row in final:
        if row["layer"]!="M1_coupled":continue
        original=byid[row["identity"].replace("_M1_coupled_","_M0_frozen35_")]
        m,b=row["metrics"],original["metrics"]
        model_pairs.append(dict(device=row["device"],identity=row["identity"],reference_identity=original["identity"],
            alpha=row["alpha"],case_index=row["case_index"],replicate=row["index"],policy=policy_label(row,frozen),
            label="M0 to M1 model change with the same fixed scheduler; not a policy benefit",
            energy_change_j=m["energy_180_j"]-b["energy_180_j"] if m["energy_180_j"] is not None and b["energy_180_j"] is not None else None,
            mean_AP_change_c=m["mean_ap_c"]-b["mean_ap_c"] if m["mean_ap_c"] is not None and b["mean_ap_c"] is not None else None,
            incomplete_M0=b["incomplete"],incomplete_M1=m["incomplete"]))
    gzsave(OUT/"MODEL_CHANGE_PAIRS.json.gz",model_pairs)
    return result

if __name__=="__main__":run()
