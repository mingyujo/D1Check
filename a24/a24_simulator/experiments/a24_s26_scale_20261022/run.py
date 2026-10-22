import copy,gc,msvcrt,traceback
from scale_common import *
from scoring import metrics,evaluate_setting,ranking

def receipt(event,label,**kw):
    row={'event':event,'label':label,'kind':'EVAL','unix':time.time(),'start_id':hashlib.sha256((OPSHA+'|'+label).encode()).hexdigest(),'durable_START_consumed':True,**kw}
    with (O/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
    return row

def episode(item,mode,state,risk,batch):
    case=item['case'];label=case['id']+'__'+mode;rec=receipt('START',label);start=time.monotonic();last=[None];actor=None;print('ENV_START',label,case['n'],flush=True)
    try:
        bank=read(R/item['bank']['path']);public=read(R/item['public']['path'])['public'];ph=P.physics();nom=P.Nominal(bank['nominal_vectors']);model=B.BankModel(bank['jobs'],{q['request_id']:public for q in public['requests']});net=legacy.Learner(state=state) if mode=='BC_NEURAL_URGENT' else None;before=net.snapshot() if net else None
        actor=DynamicPolicy(nom,ph,mode) if mode.endswith('_DYN') else Policy(nom,ph,case,net,False,risk=risk);notice=[start]
        def guarded(s):
            last[0]=s;t=time.monotonic();assert t-start<1200 and t-batch<10800 and len(actor.calls)<=max(1024,20*case['n'])
            if t-notice[0]>=30:resources();print('ENV_PROGRESS',label,len(actor.calls),round(s['now_ns']/1e9-35,2),len(s['queue']),flush=True);notice[0]=t
            return actor(s)
        result=C.engine.run(public,model,guarded,ph,case['common_potential_key'],rec);m=metrics(result,case)
        if net:legacy.equal(before,net.snapshot())
        raw=O/(label+'.raw.json.gz');save(raw,{'result':result,'calls':actor.calls,'case':case,'source':item,'policy':mode,'network_sha256':NETWORK if net else None,'profile':{'id':'ORIGINAL','CPU':3,'GPU':1,'beta':.25},'metrics':m,'new_training':0,'new_fit':0});row={'label':label,'case':case['id'],'condition':case['condition'],'policy':mode,'status':'COMPLETE','raw':pin(raw),'bank':item['bank'],'metrics':m,'elapsed_s':time.monotonic()-start};write(O/(label+'.json'),row);receipt('COMPLETE',label,raw=row['raw']);print('ENV_COMPLETE',label,round(row['elapsed_s'],2),m['service']['ALL']['on'],m['service']['U']['on'],flush=True);del actor,result,net,bank;gc.collect();return row
    except BaseException as e:
        raw=O/(label+'.FAILED.json.gz');save(raw,{'case':case,'last_public_state':last[0],'calls':actor.calls if actor else [],'error':repr(e),'traceback':traceback.format_exc(),'partial_not_complete':True});row={'label':label,'case':case['id'],'condition':case['condition'],'policy':mode,'status':'FAIL','raw':pin(raw),'error':repr(e),'automatic_retry':False};write(O/(label+'.json'),row);receipt('FAIL',label,error=repr(e));print('ENV_FAIL',label,repr(e),flush=True);return row

def main():
    global OPSHA
    assert not O.exists(),'Consumed identity';reg=read(H/'OPERATION.json');verify(reg);OPSHA=sha(H/'OPERATION.json');lock=(A/'runtime/a24_local_worker.lock').open('r+b');owned=False;begun=time.monotonic()
    try:
        for attempt in range(31):
            try:resources(True);lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True;break
            except (AssertionError,OSError) as e:
                if attempt==30:write(V/f'WAIT_EXPIRED_{int(time.time())}.json',{'science_START':0,'reason':repr(e)});return
                print('RESOURCE_WAIT',str(e) or 'shared byte lock',round(time.monotonic()-begun),flush=True);time.sleep(20)
        O.mkdir();write(O/'START.json',{'unix':time.time(),'resources':resources(True),'operation_sha256':OPSHA,'HEAD':reg['HEAD'],'dirty':True,'max_eval':120});data=read(H/'INPUTS.json');state=legacy.loadpt(CHECKPOINT);assert state['network_sha256']==NETWORK;risk=read(A/'results/A24_NN_URGENT_TIE_20261021_01/RISK_CALIBRATION.json')['task_margin_s'];rows=[];batch=time.monotonic()
        for item in data['cases']:
            if item['case']['condition']['role']!='DEV':continue
            for mode in MODES:rows.append(episode(item,mode,state,risk,batch))
        candidates=[]
        for setting in data['settings']:
            rr=[r for r in rows if r['condition']['setting']==setting['id']];score=evaluate_setting(rr) if len(rr)==10 and all(r['status']=='COMPLETE' for r in rr) else None;candidates.append({'setting':setting,'score':score,'rank':list(ranking(setting,score)) if score else None})
        valid=[r for r in candidates if r['score'] is not None];assert valid,'No valid DEV candidate';chosen=min(valid,key=lambda r:ranking(r['setting'],r['score']));write(O/'DEV_SELECTION.json',{'candidates':candidates,'selected':chosen,'confirmation_read_for_choice':False,'unix':time.time()});print('DEV_SELECTED',json.dumps(chosen),flush=True)
        for item in data['cases']:
            condition=item['case']['condition']
            if condition['role']=='CONF' and condition['setting']==chosen['setting']['id']:
                for mode in MODES:rows.append(episode(item,mode,state,risk,batch))
        verify(reg);legacy.equal(legacy.loadpt(CHECKPOINT),state);events=[json.loads(l) for l in (O/'receipts.jsonl').read_text().splitlines()];counts={k:sum(e['event']==k for e in events) for k in ['START','COMPLETE','FAIL']};assert counts['START']<=120 and counts['START']==counts['COMPLETE']+counts['FAIL'];write(O/'RESULT.json',{'state':'FINITE_TERMINAL','rows':rows,'counts':counts,'selected':chosen['setting'],'new_TRAIN':0,'new_fit':0,'new_measurement':0,'old_results_rerun':0,'elapsed_s':time.monotonic()-batch,'adopted':False});print('BATCH_COMPLETE',counts,flush=True)
    except BaseException as e:
        write((O if O.exists() else V)/f'FAILURE_{int(time.time())}.json',{'error':repr(e),'traceback':traceback.format_exc(),'automatic_retry':False});raise
    finally:
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
        if owned:write(V/f'LOCK_RELEASED_{int(time.time())}.json',{'owned_lock_returned':True})
if __name__=='__main__':main()
