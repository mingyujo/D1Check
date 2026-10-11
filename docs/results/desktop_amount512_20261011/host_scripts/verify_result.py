"""Read-only full audit of completed desktop task; no environment starts."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE/'bundle/D1Check-desktop-cpu-20261011'
DEST = ROOT/'output/desktop_joint_amount_amount512_desktop_20261011_a'
sys.path.insert(0, str(ROOT))
from tools import d1_joint_amount_cli as cli
x = cli.x

def main():
    start = time.perf_counter()
    reg = cli.check_task(DEST)
    completion = x.read(DEST/'completion.json')
    assert completion['status']=='completed'
    assert not (DEST/'owner.lock').exists()
    clock = x.read(DEST/'clock.json')
    assert clock['running_since'] is None
    assert 0 < clock['consumed_active_seconds'] < reg['active_seconds']-reg['reserve_seconds']
    manifest = x.read(ROOT/'bundle_manifest.json')
    for e in manifest['files']:
        p = ROOT/e['path']
        assert p.stat().st_size==e['bytes'] and x.sha(p)==e['sha256'],e['path']
    starts, finishes = {}, {}
    for line in (DEST/'executions.jsonl').read_text().splitlines():
        e = json.loads(line)
        d = finishes if e.get('event') else starts
        assert e['number'] not in d
        d[e['number']] = e
    assert len(starts)==len(finishes)==2200
    assert set(starts)==set(range(1,2201))==set(finishes)
    assert len({e['identity'] for e in starts.values()})==2200
    phases = collections.Counter(e['phase'] for e in starts.values())
    assert dict(phases)==dict(reference=448,train=1344,confirmation=336,development=72)
    assert sum(e['learning'] for e in starts.values())==1344
    pause = x.read(BASE/'pause_verification.json')
    assert starts[474]['identity']==pause['next_actual_learning_identity']
    assert clock['consumed_active_seconds']>pause['clock']['consumed_active_seconds']
    assert x.sha(DEST/'registration.json')==pause['registration_sha256']
    totals = collections.Counter()
    request_ids, decision_count, callback_count = 0, 0, 0
    for number,e in starts.items():
        f = finishes[number]
        assert f['status']==f['event']=='completed'
        for key in ('number','identity','phase','case','learning'):
            assert e[key]==f[key]
        path = DEST/'items'/(e['identity']+'.json.gz')
        assert x.sha(path)==f['sha256'], e['identity']
        raw = json.loads(gzip.decompress(path.read_bytes()))
        ledger = raw['result']['ledger']
        x.old.x.previous.audit(raw['result'],e['case']['tickets'])
        assert len(ledger)==raw['row']['planned']==len(e['case']['tickets'])
        assert raw['row']['completed']==sum(q['status']=='succeeded' for q in ledger)
        assert raw['row']['incomplete']==len(ledger)-raw['row']['completed']
        for priority,key in (('urgent','urgent_failure'),('normal','normal_failure')):
            assert raw['row'][key]==sum(q['priority']==priority and ('response_ns' not in q or q.get('late_success',True)) for q in ledger)
        assert raw['row']['urgent_p95_ms']==raw['result']['metrics']['urgent_p95_ms']
        totals['planned']+=raw['row']['planned']
        totals['completed']+=raw['row']['completed']
        totals['incomplete']+=raw['row']['incomplete']
        for s in raw['snapshots']:
            assert s['mask'][s['chosen']]
            assert all(not a or b for a,b in zip(s['mask'],s['physical_mask']))
        decision_count+=len(raw['snapshots'])
        callback_count+=len(raw['callback_seconds'])
    payload = x.r.torch.load(DEST/'session_latest.pt',map_location='cpu',weights_only=False)
    learners,cursor,consumption = cli.session.restore(payload)
    assert cursor==dict(case=448,next_seed=0)
    assert consumption['native_starts']==1792 and consumption['learning_starts']==1344
    states = []
    for seed in x.SEEDS:
        p = x.r.torch.load(DEST/'checkpoints'/f'seed{seed}_ep512.pt',map_location='cpu',weights_only=False)
        parent = x.r.torch.load(ROOT/reg['parent_checkpoints'][str(seed)]['path'],map_location='cpu',weights_only=False)
        assert p['accepted_episodes']==512 and len(p['pending_episodes'])==0
        assert p['update_count']==64 and p['optimizer_steps']>parent['optimizer_steps']
        assert not p['failed_updates']
        assert p['dependencies']==parent['dependencies']
        assert p['settings']==parent['settings'] and p['schema_id']==parent['schema_id']
        assert len(p['optimizer']['state'])==len(parent['optimizer']['state'])==14
        adam_steps=[int(v['step']) for v in p['optimizer']['state'].values()]
        assert max(adam_steps)==p['optimizer_steps'] and min(adam_steps)>96
        for name in ('network','optimizer',*cli.session.FIELDS):
            assert cli.session.digest(p[name])==cli.session.digest(payload['learners'][str(seed)][name]),(seed,name)
        actor_changed = any(not x.r.torch.equal(v,parent['network'][k]) for k,v in p['network'].items() if k.startswith('actor'))
        assert actor_changed
        states.append(dict(seed=seed,episodes=p['accepted_episodes'],updates=p['update_count'],optimizer_steps=p['optimizer_steps'],pending_episodes=len(p['pending_episodes']),adam_states=len(p['optimizer']['state']),actor_changed=True,sha256=x.sha(DEST/'checkpoints'/f'seed{seed}_ep512.pt'),original_sha256=reg['parent_checkpoints'][str(seed)]['sha256']))
    rows = completion['rows']
    confirmed = [q for q in rows if q['scope']=='confirmation']
    assert len(confirmed)==336
    policies = {q['policy'] for q in confirmed}
    assert len(policies)==7 and len({(q['condition'],q['policy']) for q in confirmed})==336
    assert len([q for q in rows if q['scope']=='development'])==72
    for condition in range(48):
        same = [q for q in confirmed if q['condition']==condition]
        assert len({(q['arrival_seed'],q['family'],q['context'],q['planned']) for q in same})==1
    final = [dict(q,policy='Rule') if q['policy']=='CostList' else q for q in confirmed]
    gates = {f'PPO{s}_512':x.old.gate_rows(final,f'PPO{s}_512',48) for s in x.SEEDS}
    assert gates==completion['gates']
    assert not reg['experiment_ready'] and not reg['automatic_adoption'] and not reg['strict_changed']
    assert completion['consumption']==cli.Budget(DEST).used()
    smoke = x.read(ROOT/'output/desktop_package_smoke_20261011_v1/completion.json')
    assert smoke['new_native']==3 and smoke['new_learning']==0 and smoke['completed']==smoke['planned']==72 and smoke['failed']==0
    receipt = dict(status='PASS_full_ledger_checkpoint_source_budget_and_common48',task=reg['task'],new_native=2200,new_learning=1344,failed_native=0,phases=dict(phases),totals=dict(totals),states=states,clock=clock,shared_session_sha256=x.sha(DEST/'session_latest.pt'),session_cursor=cursor,session_consumption_at_last_training_boundary=consumption,final_consumption=completion['consumption'],manifest96_unchanged=True,all_items_sha256_verified=True,all_request_ledgers_audited=True,all_selected_actions_allowed=True,snapshots_verified=decision_count,callbacks_recorded=callback_count,common_confirmation_conditions=48,policies=sorted(policies),gates_recomputed=True,real_safe_stop_resume_verified=True,next_learning_identity_after_resume=starts[474]['identity'],pause_verification=pause,automatic_adoption=False,experiment_ready=False,strict_changed=False,device_commands=0,new_physical_measurements=0,verification_seconds=time.perf_counter()-start)
    (BASE/'final_verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
