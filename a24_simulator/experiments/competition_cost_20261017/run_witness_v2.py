"""Eight preregistered input witnesses, frozen EP024, no training/retry."""
from pathlib import Path
import argparse, copy, gzip, json, os, sys
ROOT=Path(__file__).resolve().parents[2]
ENTRY=Path(__file__).resolve()
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'experiments/edf_cpu_first_20261016'),
              str(ROOT/'experiments/protected48_v2_20261016')]
os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
import lab_backend as L
import interactive_kernel as kernel
from policy import installed, metrics
from protected_policy import ProtectedPolicy
import torch
torch.set_num_threads(1)
L.runtime_guard.OWN_TOKENS+=('competition_cost_20261017','protected48_v2_20261016',
                            's26-state-aware-atc-','state_recovery_owner','s26-integrated-model-')

def main(path):
    op=L.read(path); sha=L.sha(path); reg=L.read(ROOT/'models/registration.json')
    L.need(op['schema']=='A24-competition-witness-operation-v2','Schema')
    for p in op['source_pins']+op['input_pins']:L.pin(p)
    known=reg['known_PS_producer_paths']+op['known_PS_producer_paths']
    L.runtime_guard.process_guard(ENTRY,known);L.free_guard([ROOT,'D:/',reg['worker_lock_path']])
    out=ROOT/op['output_dir']; ledger=ROOT/'runtime/receipts.jsonl'
    events=[json.loads(s) for s in ledger.read_text().splitlines() if s]
    L.need(sum(e['event']=='START' for e in events)==op['expected_child_START_before'],'Budget prefix')
    L.need(L.sha(ledger)==op['ledger_prefix']['sha256'],'Ledger byte prefix')
    L.need(op['new_environment_cap']==8 and op['expected_child_START_before']+8<=reg['environment_cap'],'Budget')
    L.need(not out.exists(),'Consumed target: no automatic retry')
    import msvcrt
    lock=Path(reg['worker_lock_path']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    n=0
    try:
        out.mkdir(parents=True,exist_ok=False)
        L.write_new(out/'START.json',dict(operation_sha256=sha,utc=L.now(),guard=L.runtime_guard.process_guard(ENTRY,known)))
        try:
            base,thermal,profile=L.initialize(reg)
            catalog=L.read(L.pin(reg['catalog_pin']))
            learn=L.load_module('competition_frozen_learner',ROOT/'reference/rolling/learner.py')
            cp=op['checkpoint'];frozen=learn.Learner.load_snapshot(L.pin(cp))
            network=learn.network_digest(frozen.net)
            rr=copy.deepcopy(reg);rr['checkpoints']['20261028']=cp
            rr['adapter_contract_sha256']=L.sha(ROOT/'experiments/protected48_v2_20261016/protected_policy.py')
            cases=[]
            for case in op['cases']:
                rows=[]
                for policy in ('EDF_CPU_FIRST','ROLLING_ATC_RL_PROTECTED48'):
                    L.runtime_guard.process_guard(ENTRY,known);L.free_guard([ROOT,'D:/'])
                    used=sum(json.loads(s)['event']=='START' for s in ledger.read_text().splitlines() if s)
                    L.need(used==op['expected_child_START_before']+n and n<8,'Consumption frontier')
                    value=L.validate_input(copy.deepcopy(case['input']),catalog['profiles'])
                    public,contexts=L.prepare_public(value,catalog['templates'],catalog['profiles'])
                    model=L.Model(base,contexts)
                    label='CASE_%02d_%s'%(case['index'],policy)
                    identity=L.digest(['A24_COMPETITION_WITNESS_V2',label,sha])
                    L.need(not any(e.get('identity')==identity for e in events),'Consumed identity')
                    start=dict(event='START',identity=identity,start_id=identity,operation_sha256=sha,
                               utc=L.now(),label=label,policy=policy,input_sha256=L.digest(value),new_environment=1,
                               durable_START_consumed=True,registration_sha256=sha)
                    L.append(ledger,start);L.append(out/'receipts.jsonl',start);n+=1
                    try:
                        if policy=='EDF_CPU_FIRST':
                            with installed(kernel,L):result,actor=L.policy_result(policy,public,model,thermal,profile,value,start,reg)
                        else:
                            original=L.RLPolicy
                            def factory(*args,**kwargs):return ProtectedPolicy(model,public,thermal,profile,frozen,learn,False,False)
                            L.RLPolicy=factory
                            try:result,actor=L.policy_result('ROLLING_ATC_RL',public,model,thermal,profile,value,start,rr)
                            finally:L.RLPolicy=original
                            result['summary'].update(policy=policy,label=policy,protection_decisions=actor.bank_audits)
                        audit=L.audit_result(result,actor)
                        L.need(learn.network_digest(frozen.net)==network,'Frozen actor mutated')
                        raw=out/(label+'.raw.json.gz')
                        if actor:
                            frame=out/(label+'.frames.pt');torch.save(actor.controller.frames,frame)
                            result['summary']['saved_frames']={'path':str(frame),'sha256':L.sha(frame)}
                        with gzip.open(raw,'xt',encoding='utf-8') as f:f.write(L.canonical(result))
                        L.write_new(out/(label+'.summary.json'),result['summary'])
                        prep={**start,'event':'PREPARED','raw_sha256':L.sha(raw),'summary_sha256':L.sha(out/(label+'.summary.json')),'audit':audit}
                        L.append(ledger,prep);L.append(out/'receipts.jsonl',prep)
                        terminal={**prep,'event':'COMPLETE','utc':L.now()}
                        L.append(ledger,terminal);L.append(out/'receipts.jsonl',terminal)
                        rows.append(result['summary']);print(label,'COMPLETE',n,'/8',flush=True)
                    except BaseException as e:
                        fail={**start,'event':'FAIL','utc':L.now(),'error':str(e),'retry':False}
                        L.append(ledger,fail);L.append(out/'receipts.jsonl',fail);raise
                lo=min(r['arrival_s'] for r in value['requests']);hi=min(180,max(r['arrival_s'] for r in value['requests'])+15)
                cases.append(dict(index=case['index'],input=case['input'],condition=case['condition'],label=case['label'],
                                  common_work_window_s=[lo,hi],rows=rows,metrics=[metrics(r,lo,hi) for r in rows]))
            result=dict(schema='A24-competition-witness-v1',operation_sha256=sha,cases=cases,
                        budget=dict(new_START=n,child_START=op['expected_child_START_before']+n,
                                    parent_START=105,shared_START=105+op['expected_child_START_before']+n,shared_cap=512),
                        model_fit=0,NN_training=0,measured_J=None,device_confirmation=False,
                        interpretation='Preregistered input witnesses only; not full-grid superiority evaluation')
            L.write_new(out/'RESULT.json',result)
            for p in op['source_pins']+op['input_pins']:L.pin(p)
            L.need(L.sha(path)==sha and n==8,'Completion boundary')
            L.write_new(out/'COMPLETE.json',dict(result_sha256=L.sha(out/'RESULT.json'),budget=result['budget'],utc=L.now()))
        except BaseException as e:
            L.write_new(out/'FAILURE.json',dict(error=str(e),utc=L.now(),retry=False));raise
    finally:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);main(p.parse_args().operation)
