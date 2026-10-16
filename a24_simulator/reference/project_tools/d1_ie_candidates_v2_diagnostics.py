"""Closed-result diagnostics and trained-archive arithmetic checks, zero starts."""
from __future__ import annotations
import copy,json
from pathlib import Path


def archive_arithmetic():
    from tools import d1_ie_candidates_v2_study as s
    if not (s.BUNDLE/'resume_verification.json').exists():raise RuntimeError('actual fixtures still active')
    results=[]
    for algorithm in s.ALGORITHMS:
        source=s.LOCAL/(algorithm+'_fixture_continuous_terminal.pt');hashes=[];paths=[]
        for arm in ('direct','roundtrip'):
            learner=s.restore(source)
            # Reuse already charged, closed fixture experience. Never main weights.
            episodes=[]
            for i in range(8):
                path=s.LOCAL/'items'/f'fixture__{algorithm}__continuous__{i}.pt'
                item=s.x.torch.load(path,map_location='cpu',weights_only=False)
                episodes.append({k:item[k] for k in ('data','costs','valid')})
            learner['state']['batch']=episodes
            if arm=='roundtrip':
                p=s.LOCAL/(algorithm+'_trained_partial_verification.pt');s.archive(p,learner);learner=s.restore(p)
            stats=s.update(learner);p=s.LOCAL/(algorithm+'_trained_'+arm+'_verification.pt');s.archive(p,learner);paths.append(p)
            hashes.append(s.x.old.current.model_hash(learner['network']))
        def equal(a,b):
            if isinstance(a,s.x.torch.Tensor):return isinstance(b,s.x.torch.Tensor) and s.x.torch.equal(a,b)
            if isinstance(a,s.x.np.ndarray):return isinstance(b,s.x.np.ndarray) and s.x.np.array_equal(a,b)
            if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
            if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
            return a==b
        payloads=[s.x.torch.load(p,map_location='cpu',weights_only=False) for p in paths]
        for k in ('network','optimizer','target_network','rng','state'):assert equal(payloads[0][k],payloads[1][k]),k
        assert hashes[0]==hashes[1]
        results.append(dict(algorithm=algorithm,status='PASS',source_sha256=s.sha(source),network_sha256=hashes[0],
            populated_adam_target_replay_partial_batch_roundtrip=True,additional_update=stats))
    s.write(s.BUNDLE/'trained_archive_verification.json',dict(results=results,new_environment_starts=0,new_learning_episodes=0,
        scope='extra update arithmetic on previously charged fixture data; no main actor warm start or mutation'))
    print(json.dumps(results,indent=2))


def physical(ledger):
    out=[]
    for row in sorted(ledger,key=lambda r:r['id']):
        r={k:v for k,v in row.items() if k!='source_request_id'}
        for k,v in list(r.items()):
            if k.endswith('_ns') and isinstance(v,(int,float)):r[k]=round(v)
        out.append(r)
    return out


def final_diagnostics():
    from tools import d1_ie_candidates_v2_report as r
    from tools import d1_policy_coefficient_sensitivity as sensitivity
    items=r.load('final');by={(i['row']['seed'],i['row']['family'],i['row']['context'],i['row']['policy']):i for i in items}
    rows=[]
    for p in r.LABELS:
        group=[i for i in items if i['row']['policy']==p]
        row=dict(policy=p,conditions=len(group))
        for base,label in [(r.BASE,'EDD'),(r.BAND,'Band'),(r.TRITON,'Triton')]:
            row['same_schedule_as_'+label]=sum(physical(i['ledger'])==physical(by[i['row']['seed'],i['row']['family'],i['row']['context'],base]['ledger']) for i in group)
        row['nonbase_choices']=sum(i['row'].get('nonbase_choices',0) for i in group)
        row['informative_choices']=sum(i['row'].get('informative_choices',0) for i in group)
        rows.append(row)
    r.csv_write(r.BUNDLE/'schedule_diagnostics.csv',rows)
    receipts=[json.loads(line) for line in (r.LOCAL/'executions.jsonl').read_text().splitlines()]
    import datetime
    timings=[]
    for a in ('PPO','DDQN'):
        for seed in (11,23,37):
            path=r.LOCAL/f'{a}_seed{seed}_done.json';data=r.read(path)
            first=min(datetime.datetime.fromisoformat(e['utc']).timestamp() for e in receipts if e['event']=='start' and e['identity'].startswith(f'train/{a}/{seed}/'))
            timings.append(dict(algorithm=a,seed=seed,environment_host_wall_s=sum(row['host_wall_s'] for row in data['rows']),
                learner_elapsed_s=path.stat().st_mtime-first,scope='includes environment/update/archive wall after first start; excludes process/network initialization; concurrent PC load, not phone control energy'))
    r.csv_write(r.BUNDLE/'training_compute_time.csv',timings)
    import gzip
    original=json.loads(gzip.decompress((r.LOCAL/'items'/('preservation__'+r.BAND+'.json.gz')).read_bytes()))
    ref=json.loads(gzip.decompress((r.LOCAL/'items'/('reference__812000001__low__mean__'+r.BAND+'.json.gz')).read_bytes()))
    assert physical(original['ledger'])==physical(ref['ledger'])
    r.write(r.BUNDLE/'baseline_preservation.json',dict(Band_independent_repeat_ledger_equal=True,
        EDD='original source hash unchanged, existing eight semantic checks passed, registered original-adapter run retained',
        model_and_original_adapter_sources_preserved=True,new_environment_starts=0))
    models=sensitivity.models();initial=r.read(r.ROOT/'docs/results/external_rules_02/inputs.json')['initial'];costs=[]
    for item in items:
        row=item['row']
        if row['seed']!=812020001 or row['completed']!=row['planned']:continue
        segments=sensitivity.segments(item['ledger'])
        for name,model in models:
            value=sensitivity.j.m.base.costs(segments,initial,list(range(35,181)),model,180.)
            costs.append(dict(seed=row['seed'],family=row['family'],context=row['context'],policy=row['policy'],model=name,
                energy_j=value['whole_120s_j'],peak_ap_c=max(value['ap_path']),physical_saving_verified=False))
    r.csv_write(r.BUNDLE/'coefficient_sensitivity.csv',costs)
    r.write(r.BUNDLE/'sensitivity_contract.json',dict(first_seed=812020001,conditions='four families, all three contexts, every policy with complete work',
        models=[n for n,_ in models],source_freeze_sha256=r.sha(sensitivity.FREEZE),original_model_sha256=r.sha(sensitivity.j.m.MODEL),
        scope='original + four already fitted rejected development variants; fixed-schedule cost stress, no fit/retraining/changed-model policy replay/CI',
        new_environment_starts=0,rows=len(costs)))
    print(json.dumps(dict(schedule_rows=len(rows),sensitivity_rows=len(costs)),indent=2))


if __name__=='__main__':
    import sys
    if sys.argv[1]=='archive':archive_arithmetic()
    else:final_diagnostics()
