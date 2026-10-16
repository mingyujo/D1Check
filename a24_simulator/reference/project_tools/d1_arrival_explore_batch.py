"""Finite PC development -> freeze -> separate scenario evaluation; no device calls."""
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path
import statistics
import time
from tools import d1_arrival_explore as engine
from tools import d1_arrival_plan as io


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('preserve output: '+str(path))
    path.write_text(json.dumps(value,indent=2,sort_keys=True),encoding='utf-8')


def workload(name, phase):
    n=24 if phase=='evaluation' else 20
    interval={'low':1200,'queue':200,'burst':80,'urgent_heavy':200,'classification_mix':200,'reverse':200}[name]
    rows=[]
    for i in range(n):
        urgent=i%(2 if name=='urgent_heavy' else 4)==1
        task='classification' if urgent else 'detection'
        if name=='classification_mix':task='classification' if i%4!=0 else 'detection'
        if name=='reverse':task='detection' if urgent else 'classification'
        arrival=i*interval+(i//6*1000 if name=='burst' else 0)
        rows.append(dict(id=f'{phase}/{name}/{i}',task=task,priority='urgent' if urgent else 'normal',
            ordinal=i,arrival_ns=arrival*1_000_000,deadline_offset_ns=(1500 if urgent else 6000)*1_000_000))
    return rows


def defaults(mode):
    return dict(mode=mode,decision_ns=100_000,record_ns=100_000,dispatch_ns=100_000,
        aging_ns=4_000_000_000,interference=1.5,predicted_interference=1.5,estimate_factor=1.,
        load_prepare_factor=1.,load_callback_factor=1.,static_parallel=False,
        static_map=dict(classification='CPU',detection='CPU'))


def scenarios():
    rows=[]
    for name in ('low','queue','burst','urgent_heavy','classification_mix','reverse'):
        rows.append(dict(id=name,workload=name,changes={}))
    for factor in (1.,2.):rows.append(dict(id=f'queue_interference_{factor}',workload='queue',changes=dict(interference=factor)))
    for factor in (.75,1.25):rows.append(dict(id=f'queue_estimate_{factor}',workload='queue',changes=dict(estimate_factor=factor)))
    rows.append(dict(id='queue_load_x2',workload='queue',changes=dict(load_prepare_factor=2.,load_callback_factor=2.)))
    rows.append(dict(id='queue_hostcost_x10',workload='queue',changes=dict(decision_ns=1_000_000,record_ns=1_000_000,dispatch_ns=1_000_000)))
    return rows


def run(bundle,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);bundle=Path(bundle)
    config=io.read(bundle/'estimates.json');vectors=io.read(bundle/'realizations.json')
    receipt=io.read(bundle/'receipt.json')
    for f in ('estimates.json','realizations.json'):
        if io.digest(bundle/f)!=receipt['files'][f]:raise ValueError('source bundle hash')
    start=time.monotonic()
    contract=dict(version=engine.VERSION,development_seed=[101,102,103],evaluation_seed=[201,202,203,204,205],
        scenarios=scenarios(),development_workloads=['low','queue','burst'],
        policies=list(engine.POLICIES)+['P_NO_PAIR_COST_PC'],
        b2_rule='all 4 task maps x serial/parallel (strict serial only); complete and per-scenario mean normal response <= CPU_URGENT and normal timely >= CPU_URGENT; then mean urgent miss, urgent P95, normal mean, makespan, canonical candidate ID',
        margins='zero relative developmental normal loss is a PC selection convention, not project noninferiority/success threshold',
        P='fixed assumed pair factor 1.5; no search/tuning; ablation factor1 equals B3; no-parallel ablation',
        scope='post-unblinding exploratory model; separate scenario evaluation conditional on same small calibration bundle',
        limitations=['not independent device prediction','queue/order transfer assumed','new priorities mix assumed','success-only realizations; failures not estimated','no thermal/energy model'],
        source_hashes={f:io.digest(bundle/f) for f in ('estimates.json','realizations.json')},
        code_hashes={str(Path(f).name):io.digest(f) for f in (__file__,engine.__file__)},
        horizon_ns=120_000_000_000,maximum_runs=1200,wall_cap_seconds=600,experiment_ready=False)
    write(output/'contract_before_development.json',contract)
    def sim(name,phase,policy,s,seed):
        if time.monotonic()-start>600:raise TimeoutError('PC batch wall cap')
        return engine.simulate(config,vectors,workload(name,phase),policy=policy,settings=s,seed=seed)
    selections={};dev=[]
    for mode in ('strict','explore'):
        references={}
        for name in contract['development_workloads']:
            references[name]=[sim(name,'development','CPU_URGENT',defaults(mode),seed)['metrics'] for seed in contract['development_seed']]
        candidates=[]
        for cc,dd,parallel in itertools.product(('CPU','GPU'),('CPU','GPU'),(False,True)):
            if mode=='strict' and parallel:continue
            s=defaults(mode);s.update(static_map=dict(classification=cc,detection=dd),static_parallel=parallel)
            ident=f'{cc}_{dd}_{"parallel" if parallel else "serial"}'
            rows=[];eligible=True
            for name in contract['development_workloads']:
                ms=[sim(name,'development','B2_PC',s,seed)['metrics'] for seed in contract['development_seed']]
                mean=lambda group,key:statistics.mean(m[key] for m in group)
                eligible &= all(m['completion']==1 for m in ms) and mean(ms,'normal_mean_ms')<=mean(references[name],'normal_mean_ms')+1e-9 and mean(ms,'normal_timely')>=mean(references[name],'normal_timely')-1e-12
                rows+=ms
            score=[statistics.mean(m[k] for m in rows) for k in ('urgent_deadline_violation','urgent_p95_ms','normal_mean_ms','makespan_s')]
            entry=dict(mode=mode,candidate=ident,eligible=eligible,score=score,settings=s);dev.append(entry)
            if eligible:candidates.append(entry)
        if not candidates:raise ValueError('no feasible static candidate; do not relax constraint')
        selections[mode]=min(candidates,key=lambda x:(x['score'],x['candidate']))
    write(output/'development_selection.json',dev)
    freeze=dict(contract_sha256=io.digest(output/'contract_before_development.json'),B2=selections,
        policy_parameters={m:defaults(m) for m in ('strict','explore')},evaluation_data_seen=False,
        independent_device_validation=False)
    write(output/'freeze_before_evaluation.json',freeze)
    rows=[];example=None;run_count=0
    for mode in ('strict','explore'):
        for scenario in scenarios():
            for seed in contract['evaluation_seed']:
                for policy in contract['policies']:
                    s=defaults(mode);s.update(scenario['changes'])
                    s.update({k:selections[mode]['settings'][k] for k in ('static_map','static_parallel')})
                    actual=policy
                    if policy=='P_NO_PAIR_COST_PC':actual='P_PAIR_COST_PC';s['predicted_interference']=1.
                    result=sim(scenario['workload'],'evaluation',actual,s,seed);run_count+=1
                    row=dict(mode=mode,scenario=scenario['id'],seed=seed,policy=policy,**result['metrics']);rows.append(row)
                    # Prespecified: queue/default/lowest evaluation seed, all policies, not best session.
                    if mode=='explore' and scenario['id']=='queue' and seed==201:
                        write(output/'representative'/f'{policy}.json',result)
    fields=list(rows[0]);output.mkdir(exist_ok=True)
    with (output/'metrics.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    summaries=[];effects=[]
    for mode in ('strict','explore'):
        for scenario in scenarios():
            for policy in contract['policies']:
                group=[r for r in rows if (r['mode'],r['scenario'],r['policy'])==(mode,scenario['id'],policy)]
                summary=dict(mode=mode,scenario=scenario['id'],policy=policy,simulation_replicates=5)
                for k in ('urgent_p95_ms','normal_mean_ms','makespan_s','throughput','completion','urgent_deadline_violation','normal_timely'):
                    values=[r[k] for r in group];summary[k]=statistics.mean(values);summary[k+'_min']=min(values);summary[k+'_max']=max(values)
                summaries.append(summary)
            for seed in contract['evaluation_seed']:
                pair={r['policy']:r for r in rows if (r['mode'],r['scenario'],r['seed'])==(mode,scenario['id'],seed)}
                for comparator in ('B3_SOLO_EFT_PC','B2_PC','CPU_URGENT'):
                    effects.append(dict(mode=mode,scenario=scenario['id'],seed=seed,comparator=comparator,
                        urgent_relative_pct=100*(pair['P_PAIR_COST_PC']['urgent_p95_ms']/pair[comparator]['urgent_p95_ms']-1),
                        normal_relative_pct=100*(pair['P_PAIR_COST_PC']['normal_mean_ms']/pair[comparator]['normal_mean_ms']-1)))
    for name,data in (('summary.csv',summaries),('paired_effects.csv',effects)):
        with (output/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    plot(output,summaries,effects)
    write(output/'receipt.json',dict(status='completed',evaluation_runs=run_count,development_runs=126,
        evaluation_requests=run_count*24,device_sessions=0,wall_seconds=time.monotonic()-start,
        frozen_sha256=io.digest(output/'freeze_before_evaluation.json'),experiment_ready=False,
        artifacts={str(f.relative_to(output)):io.digest(f) for f in output.rglob('*') if f.is_file()}))
    return dict(output=str(output),evaluation_runs=run_count,B2={m:v['candidate'] for m,v in selections.items()})


def plot(out,summaries,effects):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names=['CPU_URGENT','FIXED_SPLIT','B2_PC','B3_SOLO_EFT_PC','P_PAIR_COST_PC','P_NO_PARALLEL_PC']
    fig,axes=plt.subplots(1,3,figsize=(16,5))
    for ax,key,label in zip(axes,('urgent_p95_ms','normal_mean_ms','throughput'),('Urgent nearest-rank P95 (ms)','Normal mean response (ms)','Throughput (requests/s)')):
        rows=[next(r for r in summaries if r['mode']=='explore' and r['scenario']=='queue' and r['policy']==p) for p in names]
        vals=[r[key] for r in rows];err=[[r[key]-r[key+'_min'] for r in rows],[r[key+'_max']-r[key] for r in rows]]
        ax.bar(range(len(rows)),vals,yerr=err,capsize=3);ax.set_xticks(range(len(rows)),names,rotation=65,ha='right');ax.set_ylabel(label)
    fig.suptitle('Exploratory queue model; mean and range of 5 keyed-vector replicates\n24 requests/replicate; interference assumption 1.5; not device confidence intervals')
    fig.tight_layout()
    for ext in ('png','svg'):fig.savefig(out/f'policy_comparison.{ext}',dpi=150)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,5));ids=[x['id'] for x in scenarios()]
    for key,label in (('urgent_relative_pct','Urgent P95'),('normal_relative_pct','Normal mean')):
        groups=[[r[key] for r in effects if r['mode']=='explore' and r['scenario']==s and r['comparator']=='B3_SOLO_EFT_PC'] for s in ids]
        means=[statistics.mean(g) for g in groups]
        ax.errorbar(range(len(ids)),means,yerr=[[a-min(g) for a,g in zip(means,groups)],[max(g)-a for a,g in zip(means,groups)]],label=label,marker='o',capsize=3)
    ax.axhline(0,color='black',lw=.8);ax.set_xticks(range(len(ids)),ids,rotation=45,ha='right');ax.set_ylabel('(P / B3 - 1) %, lower is better');ax.legend()
    ax.set_title('Scenario sensitivity: mean/range across 5 paired model replicates, not a CI')
    fig.tight_layout()
    for ext in ('png','svg'):fig.savefig(out/f'sensitivity.{ext}',dpi=150)
    plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(14,8),sharex=True)
    for ax,p in zip(axes,('CPU_URGENT','B3_SOLO_EFT_PC','P_PAIR_COST_PC')):
        data=io.read(out/'representative'/f'{p}.json')
        for row in data['ledger']:
            y=0 if row['backend']=='CPU' else 1
            for a,b,color in (('arrival_ns','dispatch_ns','lightgray'),('dispatch_ns','execution_start_ns','gold'),('execution_start_ns','output_ready_ns','steelblue'),('output_ready_ns','lane_available_ns','salmon')):
                waiting=a=='arrival_ns'
                ax.broken_barh([(row[a]/1e9,(row[b]-row[a])/1e9)],
                    (y-.38,.10) if waiting else (y-.20,.40),facecolors=color,zorder=0 if waiting else 2)
            ax.plot(row['arrival_ns']/1e9,y-.33,'k|',markersize=5,zorder=3)
        ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(p);ax.grid(axis='x',alpha=.2)
    axes[-1].set_xlabel('Seconds since first scheduled arrival; gray wait / gold prepare / blue S->O / red O->lane')
    fig.suptitle('Prespecified representative: queue, seed201, 24 requests; model trace, not GPU kernel timeline')
    fig.tight_layout()
    for ext in ('png','svg'):fig.savefig(out/f'gantt.{ext}',dpi=150)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.bundle,a.output),indent=2))

if __name__=='__main__':main()
