"""Replay recorded public decisions; four final native fixture checks, shared cap."""
import argparse,csv,gzip,json,os,subprocess
from datetime import datetime,timezone
from tools import d1_ie_priority_compare_study as s
from tools import d1_ie_response_backfill as m
def raw(run,name):return json.loads(gzip.decompress((run/'items'/(name+'.json.gz')).read_bytes()))
class Budget(s.Budget):
    def __init__(self,run,receipt):self.receipt=receipt;super().__init__(run,'response_final_gate')
    def guard(self,starting=True):
        super().guard(False)
        for name,h in self.receipt['final_source_sha256'].items():assert s.sha(s.ROOT/name)==h
        if starting and (len(self.rows)>=480 or sum(r['phase']==self.phase for r in self.rows)>=4):raise TimeoutError('shared remaining cap')
def verify(run):
    run=run.resolve();pub=s.ROOT/'docs/results/ie_priority_compare_02';old=s.read(run/'response_results.json')
    receipt=dict(utc=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        original_registration_sha256=s.sha(run/'response_registration.json'),
        executed_sources={name:s.sha(pub/'source_versions'/name) for name in ['d1_ie_response_backfill_executed_v1.py','d1_ie_response_backfill_study_executed_v1.py']},
        final_source_sha256={p:s.sha(s.ROOT/p) for p in ['tools/d1_ie_response_backfill.py','tools/d1_ie_response_backfill_study.py','tools/test_d1_ie_response_backfill.py','tools/d1_ie_response_backfill_verify.py']},
        repair='suffix earliest progresses with reserved head start; correction counter uses explicit guard, not shared dispatch reason; learners=0',
        consumed_before=476,final_gate_cap=4,shared_cap=480,clock_reset=False,learning=0,independent_confirmation=0)
    receiptfile=run/'response_repair_registration_v3.json'
    if receiptfile.exists():raise FileExistsError('repair already registered; do not reset budget')
    s.write(receiptfile,receipt)
    frozen,initial=s.p.inputs(s.p.BUNDLE);checked=0;guards=0;rows=[]
    for row in old['rows']:
        item=raw(run,row['identity']);ledger=item['result']['ledger'];by_id={q['id']:q for q in ledger}
        c=m.Controller(frozen,initial['initial']);corrections=0;dispatched=set()
        transitions=item['result']['transitions']
        for d in item['result']['decisions']:
            now=d['now_ns'];ids=[q['id'] for q in ledger if q['arrival_ns']<=now and q['id'] not in dispatched]
            queue=[{k:q[k] for k in ['id','task','priority','arrival_ns','ordinal','deadline_offset_ns']} for i in ids for q in [by_id[i]]]
            lanes={b:dict(request=None,phase='AVAILABLE',since=now,dispatch=None) for b in ('CPU','GPU')}
            for q in ledger:
                if q['id'] not in dispatched:continue
                # Saved transitions round ns; callback times keep float ns.
                events=[e for e in transitions if e['request_id']==q['id'] and e['at_ns']<=round(now)]
                if any(e['event']=='lane_available_ns' for e in events):continue
                labels=dict(execution_start_ns='EXECUTING',output_ready_ns='OUTPUT_READY',persist_complete_ns='PERSISTED',worker_release_ns='WORKER_RELEASED')
                observed=[('ASSIGNED',q['dispatch_ns'])]+[(labels[e['event']],e['at_ns']) for e in events if e['event'] in labels]
                phase,since=observed[-1];lanes[q['backend']]=dict(request={k:q[k] for k in ['id','task','priority','arrival_ns','ordinal','deadline_offset_ns']},phase=phase,since=since,dispatch=q['dispatch_ns'])
            c.observe(now,lanes);changed=c.decide({},queue,lanes,now,{},None,None)
            assert changed['selected']==d['selected'],('decision changed',row['identity'],now)
            if d.get('response_guard'):
                guards+=1;assert changed['response_guard']['allowed']==d['response_guard']['allowed']
                for key in ('baseline','alternative'):
                    assert all(abs(changed['response_guard'][key][i]-v)<1e-9 for i,v in d['response_guard'][key].items())
            corrections+=bool(d.get('selected') and d.get('response_guard',{}).get('allowed'));checked+=1
            if d.get('selected'):dispatched.add(d['selected']['request_id'])
        rows.append(dict(row,GPU_response_corrections=corrections))
    assert guards==1 and sum(r['GPU_response_corrections'] for r in rows)==1
    budget=Budget(run,receipt);owner=run/'owner.lock'
    with owner.open('x',encoding='ascii') as f:f.write(str(os.getpid()))
    try:
        exact=[]
        for i,q in enumerate(budget.reg['fixtures']):
            item=budget.call(f'response_final_gate_{i}',m.Controller(frozen,initial['initial']),q)
            prior=raw(run,f'gate_EDD_{i}')
            exact.append(all(item['result'][k]==prior['result'][k] for k in ('ledger','transitions','metrics')))
        assert all(exact)
    finally:
        if owner.exists() and owner.read_text()==str(os.getpid()):owner.unlink()
    gates=old['gates']
    for gate in gates.values():gate['learners']=0
    result=dict(status='PASS',public_decisions_replayed=checked,guard_projections_exact=guards,final_fixture_exact=exact,
        counter_repair='original reason-based 1584 count was ordinary dispatch count; explicit GPU correction is1',
        original_raw_preserved=True,independent_confirmation=0,new_learning=0,consumption=budget.consumption(),receipt=receipt)
    s.write(run/'response_verification.json',result);s.write(pub/'response_verification.json',result)
    s.write(pub/'response_summary.json',dict(status='development_only',rows=rows,gates=gates,verification=result))
    fields=['condition','identity','GPU_response_corrections','planned','completed','incomplete','urgent_failure','normal_failure','urgent_p95_ms','normal_mean_ms','energy_j','peak_ap_c','native_seconds']
    with (pub/'response_development.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    print(json.dumps(dict(status='PASS',replayed=checked,corrections=1,consumption=budget.consumption())))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--run',required=True,type=s.Path);args=a.parse_args();s.torch.set_num_threads(1);verify(args.run)
