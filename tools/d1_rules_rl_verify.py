"""Verify preserved state, complete service denominators and selected raw costs.

This verifier never calls the simulator or performs optimization. Every actual
new ledger is checked for service/count consistency; J/AP are independently
recomputed for the preregistered first test seed, all families/contexts/models.
"""
import collections
import json
from pathlib import Path
from tools import d1_rules_rl_common as c
from tools import d1_rl_amount_campaign as a
from tools import d1_rules_rl_evaluation as e


def run(folder=c.OUTPUT):
    a.v.q.prev.seed_all(0)
    folder=Path(folder);spec=c.read(folder/'final_comparison_freeze.json');state=c.read(folder/'evaluation/state.json')
    if state['status']!='completed':raise ValueError('final comparison incomplete; do not certify complete results')
    events=[json.loads(x) for x in (folder/'consumption.jsonl').read_text(encoding='utf8').splitlines()]
    starts=[x for x in events if x['event']=='start'];finishes={x['started_serial']:x for x in events if x['event']=='finish'}
    identities={f'{v}_{s}' for v,s in a.IDENTITIES}
    formal=[x for x in starts if x.get('training_identity') in identities]
    keys=[(x['training_identity'],x['update'],tuple(x['case'])) for x in formal]
    if len(keys)!=49152 or len(set(keys))!=49152:raise ValueError('formal training/recovery accounting mismatch')
    if any(x['serial'] not in finishes for x in starts):raise ValueError('unresolved execution remains; no false completion')
    milestones=c.read(folder/'rl/freeze_before_test.json')['milestones'];checked=0
    for record in milestones:
        path=folder/'rl'/record['terminal_file']
        if c.digest(path)!=record['terminal_sha256']:raise ValueError('terminal archive changed')
        payload=a.v.torch.load(path,map_location='cpu',weights_only=False)
        if payload['update']!=record['update'] or payload['update']*8!=record['episodes']:raise ValueError('archive progress')
        if len(payload['training_records'])!=payload['update'] or len(payload['validation_records'])!=1+payload['update']//32:
            raise ValueError('committed learning/validation curve incomplete')
        if set(payload['rng'])!={'python','numpy','torch'} or not payload['optimizer']['state']:raise ValueError('exact state missing')
        if any(not {'step','exp_avg','exp_avg_sq'}<=set(x) for x in payload['optimizer']['state'].values()):raise ValueError('Adam state incomplete')
        if payload['optimizer']['param_groups'][0]['lr']!=.0003:raise ValueError('learning rate changed')
        for kind,source in [('latest','network'),('best','best_actor')]:
            actor=c.read(folder/'rl'/record[kind+'_actor'])
            net=a.v.q.ActorCritic();net.load_state_dict(payload[source])
            if actor['sha256']!=a.v.q.prev.model_hash(net):raise ValueError('latest/best conflated')
        checked+=1
    if checked!=24:raise ValueError('all four common points required')
    policies=[p for p in spec['baselines']]+spec['recombination']+[p['policy'] for p in spec['policies']]
    expected=[(case,policy) for case in spec['test'] for policy in policies]
    if state['cursor']!=len(expected) or len(expected)!=10560:raise ValueError('logical evaluation denominator')
    hashes={};variant_by_hash={}
    for p in spec['policies']:
        previous=variant_by_hash.setdefault(p['model_sha256'],p['variant'])
        if previous!=p['variant']:raise ValueError('cross-variant cache alias')
        if c.digest(folder/p['file'])!=p['file_sha256']:raise ValueError('actor drift')
    frozen,case=a.v.q.p.inputs(a.v.q.p.BUNDLE);initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
    raw_ledgers=0;requests=0;cost_checks=0;max_J=max_peak=max_area=0.;rows=[]
    for i,(test_case,policy) in enumerate(expected):
        path=folder/'evaluation/items'/f'{i:06d}.json.gz';item=e.read_gzip(path)
        if item['case']!=test_case or item['policy']!=policy:raise ValueError('case/policy order or identity')
        row=item['row'];seed,family,context=test_case
        planned=len(a.v.q.old.workload(family,seed))
        if row['planned']!=planned or row['completed']>planned:raise ValueError('planned denominator')
        rows.append(row)
        ledger=item['ledger']
        if ledger is None:continue
        raw_ledgers+=1;requests+=len(ledger)
        tickets=a.v.q.old.workload(family,seed)
        if len(ledger)!=planned or {r['id'] for r in ledger}!={q['id'] for q in tickets}:raise ValueError('missing/duplicate request')
        completed=sum(r['status']=='succeeded' for r in ledger)
        if completed!=row['completed']:raise ValueError('completion count')
        for priority in ('urgent','normal'):
            rs=[r for r in ledger if r['priority']==priority]
            failures=sum(r['status']!='succeeded' or 'response_ns' not in r or r['response_ns']>r['deadline_offset_ns'] for r in rs)
            if len(rs)!=row[priority+'_n'] or failures!=row[priority+'_service_failure']:raise ValueError('service numerator')
        full=all(r.get('lane_available_ns',float('inf'))<=120e9 for r in ledger)
        if full!=row['equal_work']:raise ValueError('lane release boundary')
        if seed==610720001:
            reconstructed,extra=a.v.q.prev.outcome(dict(ledger=ledger,metrics=dict(urgent_p95_ms=row['urgent_p95_ms'],normal_mean_ms=row['normal_mean_ms'])),initial,frozen)
            errors=[abs(reconstructed[k]-row[k]) for k in ('energy_j','peak_ap_c','thermal_degree_seconds')]
            max_J=max(max_J,errors[0]);max_peak=max(max_peak,errors[1]);max_area=max(max_area,errors[2]);cost_checks+=1
            if any(value>1e-8 for value in errors):raise ValueError('raw J/AP accounting differs')
    for row in rows:
        if row.get('reuse_source')=='original_v2_test.csv':continue
        # Content-addressed cache is cohort-bound; every alias has a canonical
        # retained ledger at the identical case/model/variant, validated above.
        if row.get('reuse_source') and 'evaluation/cache/' in row['reuse_source']:
            source=e.read_gzip(folder/row['reuse_source'])
            if (source['case']!=[row['trace_seed'],row['family'],row['context']] or
                source['row'].get('variant')!=row.get('variant') or
                any(source['row'][k]!=row[k] for k in ('planned','completed','energy_j','peak_ap_c','thermal_degree_seconds'))):
                raise ValueError('cache alias mismatch')
    purpose=collections.Counter((x['category'],x['purpose']) for x in starts)
    budgets=c.Budget(folder)
    if budgets.counts['rl']>80000 or budgets.counts['recombination']>4000:raise ValueError('environment cap exceeded')
    if any(budgets.training[k]>8192 for k in identities):raise ValueError('learner cap exceeded')
    protected=c.verify_protected(folder)
    users=c.read(folder/'protected_user_files.json')
    if any(c.digest(c.ROOT/path)!=sha for path,sha in users.items()):raise ValueError('user file changed')
    result=dict(status='PASSED',verified_utc=c.utc(),base_head='9e1975bfd4cb96587e7cfb5b18b85f5409ff0b83',
        working_tree='related code/docs/results uncommitted; user files preserved',command='python -B -m tools.d1_rules_rl_verify',
        terminal_archives=checked,logical_rows=len(rows),actual_new_raw_ledgers=raw_ledgers,raw_requests_checked=requests,
        cost_recalculations=cost_checks,max_abs_J_difference=max_J,max_abs_peak_difference=max_peak,max_abs_area_difference=max_area,
        first_seed_cost_scope='all available actual ledgers, all families/contexts/unique models; other costs use source immutability plus service checks',
        actual_environment_runs=budgets.counts,formal_training_episodes=len(formal),formal_replayed_environment_runs=0,
        purpose_counts=[dict(category=k[0],purpose=k[1],executions=v) for k,v in purpose.items()],
        protected_original_files=protected,protected_user_files=len(users),device_commands=0,experiment_ready=False,
        new_environment_runs_for_verification=0,new_training_for_verification=0,
        sources={Path(__file__).relative_to(c.ROOT).as_posix():c.digest(__file__)})
    c.atomic(folder/'final_integrity_verification.json',result);return result


if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
