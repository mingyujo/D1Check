"""Ten preregistered matched information/candidate interventions."""
import gc,os,subprocess,time
from factors import *
from page_resources import wait_resources
ENTRY=Path(__file__).resolve();os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)

def main():
    op=read(HERE/'OPERATION.json');opsha=B.G.sha(HERE/'OPERATION.json');out=ROOT/op['output_dir'];assert '--published' in sys.argv
    assert subprocess.check_output(['git','show','HEAD:'+str((HERE/'OPERATION.json').relative_to(ROOT.parent)).replace('\\','/')])==(HERE/'OPERATION.json').read_bytes()
    assert not out.exists(),'Consumed operation'
    for p in op['sources']+op['input_pins']:B.G.pin(p)
    guard=wait_resources(ENTRY,1536*1024**2,time.monotonic()+1800);B.G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/a24_local_worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);begin=time.monotonic();rows=[];count=0
    try:
        out.mkdir();B.G.write_new(out/'START.json',dict(utc=B.G.now(),operation_sha256=opsha,guard=guard,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
        try:
            case=next(c for c in read(op['inputs']['path'])['evaluation'] if c['id']==op['target_case']);public,model,jobs,nominal,physics,preferred,protected=setup(op,case)
            prior=read(op['reused_complete']['raw']['path']);oldrow=read(op['reused_complete']['row']['path']);assert B.G.sha(op['reused_complete']['raw']['path'])==oldrow['raw_sha256']
            B.save_binary(out/(oldrow['label']+'.raw.json.gz'),Path(op['reused_complete']['raw']['path']).read_bytes());oldrow={**oldrow,'kind':'REUSED','source_stage':'WITNESS_GAP_FACTORIAL_V2_20261018_01'};B.G.write_new(out/(oldrow['label']+'.json'),oldrow);rows.append(oldrow)
            replay=make(oldrow['factors'],jobs,physics,nominal,preferred,protected)
            for decision in prior['result']['decisions']:assert replay(decision['public_state'])==decision['action']
            reused_checks=len(prior['result']['decisions']);del prior,replay;gc.collect()
            B.G.write_new(out/'GRADIENT_PROBES.json',dict(records=[],new_NN_forward=0));selector_checks=reused_checks
            for spec in op['interventions']:
                wait_resources(ENTRY,1024**3,begin+op['wall_clock_limit_s']);B.G.free_guard([ROOT,'D:/']);assert count<op['environment_cap'] and time.monotonic()-begin<op['wall_clock_limit_s']
                label=case['id']+'_'+spec['label'];actor=make(spec,jobs,physics,nominal,preferred,protected)
                receipt=dict(start_id=B.L.digest([opsha,label]),event='START',label=label,case=case['id'],policy=spec['label'],kind='FACTOR',utc=B.G.now(),identity=B.L.digest([opsha,label]),operation_sha256=opsha,durable_START_consumed=True)
                B.G.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,label,flush=True)
                try:
                    r=B.execute(public,model,actor,physics,case['common_potential_key'],receipt);m=B.metrics(r,case,physics)
                    file=out/(label+'.raw.json.gz');saved(file,dict(result=r,calls=actor.calls,information_factors=spec,public_only=not any(spec[k] for k in ('work_actual','protected_hindsight','lp_preferred'))))
                    row=dict(label=label,case=case['id'],policy=spec['label'],kind='FACTOR',condition=case['condition'],n=case['n'],metrics=m,raw_sha256=B.G.sha(file),network_sha256=None,selector_kind=None,reward_kind='ORIGINAL',reference_end_ns=op['common_end_ns'],factors=spec)
                    B.G.write_new(out/(label+'.json'),row);rows.append(row)
                    replay=make(spec,jobs,physics,nominal,preferred,protected)
                    for d in r['decisions']:assert replay(d['public_state'])==d['action'];selector_checks+=1
                    if spec['label'] in ('W1_H1_L1','W1_H1_L0'):
                        expected=read(op['exact_P0'][spec['label']]['path'])['result']
                        for key in ('requests','trace','decisions'):assert B.G.canonical(r[key])==B.G.canonical(expected[key]),'Exact original P0 '+key
                        del expected
                    B.G.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':B.G.now(),'raw_sha256':row['raw_sha256']});print('COMPLETE',label,m['on_time'],m['urgent_on_time'],flush=True)
                    del r,actor,replay;gc.collect()
                except BaseException as exc:B.G.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','error':str(exc),'automatic_retry':False});raise
            assert count==9
            for p in op['sources']+op['input_pins']:B.G.pin(p)
            B.G.write_new(out/'SELECTOR_REPLAY.json',dict(status='PASS',decisions=selector_checks,new_environment_START=0))
            B.G.write_new(out/'RESULT.json',dict(status='COMPLETED',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,new_training=0,new_physical_fit=0,new_LP_solves=0,reused_complete=1,operation_sha256=opsha));B.G.write_new(out/'COMPLETE.json',dict(utc=B.G.now(),elapsed_s=time.monotonic()-begin,result_sha256=B.G.sha(out/'RESULT.json')))
            subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True);subprocess.run([op['node_executable'],str(HERE/'report.cjs')],check=True)
        except BaseException as exc:B.G.write_new(out/('POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'),dict(utc=B.G.now(),error=str(exc),new_START=count,automatic_retry=False));raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
