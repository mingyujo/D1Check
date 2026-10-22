import copy,gc,msvcrt,traceback,math
from matched_common import *
from a24_nn_urgent_tie_20261021.policy import Policy as OldPolicy
from a24_s26_matched_bc_20261022.policy import Policy as GuardPolicy
from a24_s26_matched_bc_20261022.train import fit
from a24_s26_scale_20261022.scoring import metrics

STARTS=0
def receipt(event,label,kind,**kw):
    global STARTS
    if event=='START':STARTS+=1;assert STARTS<=105
    r={'event':event,'label':label,'kind':kind,'unix':time.time(),'start_id':hashlib.sha256((OPSHA+'|'+kind+'|'+label).encode()).hexdigest(),'durable_START_consumed':True,**kw}
    with (O/'receipts.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(r,allow_nan=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
    return r
def select_frames(frames):
    def take(seq,n):
        if len(seq)<=n:return seq
        if n<=0:return []
        if n==1:return seq[:1]
        return [seq[round(i*(len(seq)-1)/(n-1))] for i in range(n)]
    if len(frames)<=TRAIN_MAX_FRAMES:return list(range(len(frames)))
    rare=[i for i,f in enumerate(frames) if f.get('guard_fired') or f.get('chosen_differs_teacher')];chosen=set(take(rare,384));chosen.update(take([i for i in range(len(frames)) if i not in chosen],TRAIN_MAX_FRAMES-len(chosen)));return sorted(chosen)

def episode(item,mode,kind,state,risk,batch):
    case=item['case'];label=case['id']+'__'+kind+'__'+mode;rec=receipt('START',label,kind);start=time.monotonic();last=[None];actor=None;collect=kind in ['TRAIN_TEACHER','TRAIN_DAGGER'];guarded_mode=mode in ['TEACHER_GUARD','BC_GUARD_FROZEN','BC_MATCHED'];print('ENV_START',kind,case['condition']['cohort'],mode,case['n'],case['condition']['mix'],flush=True)
    try:
        resources();bank=read(R/item['bank']['path']);public=read(R/item['public']['path'])['public'];ph=P.physics();nom=P.Nominal(bank['nominal_vectors']);model=B.BankModel(bank['jobs'],{q['request_id']:public for q in public['requests']});net=legacy.Learner(state=state) if state is not None else None;before=net.snapshot() if net else None
        actor=DynamicPolicy(nom,ph,mode) if mode.endswith('_DYN') else (GuardPolicy if guarded_mode else OldPolicy)(nom,ph,case,net,collect,risk=risk);notice=[start]
        def guarded(s):
            last[0]=s;t=time.monotonic();assert t-start<1200 and t-batch<14400 and len(actor.calls)<=max(1024,20*case['n'])
            if t-notice[0]>=30:resources();print('ENV_PROGRESS',kind,mode,len(actor.calls),round(s['now_ns']/1e9-35,2),len(s['queue']),flush=True);notice[0]=t
            return actor(s)
        result=C.engine.run(public,model,guarded,ph,case['common_potential_key'],rec);m=metrics(result,case)
        if net:equal(before,net.snapshot())
        raw=O/(label+'.raw.json.gz');save(raw,{'result':result,'calls':actor.calls,'case':case,'source':item,'policy':mode,'kind':kind,'network_sha256':state['network_sha256'] if state is not None else None,'profile':{'id':'ORIGINAL','CPU':3,'GPU':1,'beta':.25},'metrics':m,'risk':risk,'deadline_wait_guard':guarded_mode,'new_physical_fit':0});row={'label':label,'case':case['id'],'condition':case['condition'],'kind':kind,'policy':mode,'status':'COMPLETE','raw':pin(raw),'bank':item['bank'],'public':item['public'],'metrics':m,'network_sha256':state['network_sha256'] if state is not None else None,'elapsed_s':time.monotonic()-start};selected=[]
        if collect:
            indices=select_frames(actor.frames);selected=[actor.frames[i] for i in indices]
            for f in selected:f['source_raw']=row['raw']
            fp=O/(label+'.FRAMES.pt.gz');pt(fp,{'frames':selected,'indices':indices,'available_frames':len(actor.frames),'split':'TRAIN'});row['frames']=pin(fp)
        write(O/(label+'.json'),row);receipt('COMPLETE',label,kind,raw=row['raw']);print('ENV_COMPLETE',kind,mode,round(row['elapsed_s'],2),'on',m['service']['ALL']['on'],'/',case['n'],'U',m['service']['U']['on'],flush=True);del actor,result,net,bank;gc.collect();return row,selected
    except BaseException as e:
        raw=O/(label+'.FAILED.json.gz');save(raw,{'case':case,'last_public_state':last[0],'calls':actor.calls if actor else [],'error':repr(e),'traceback':traceback.format_exc(),'partial_not_complete':True});row={'label':label,'case':case['id'],'condition':case['condition'],'kind':kind,'policy':mode,'status':'FAIL','raw':pin(raw),'error':repr(e),'automatic_retry':False};write(O/(label+'.json'),row);receipt('FAIL',label,kind,error=repr(e));print('ENV_FAIL',label,repr(e),flush=True);return row,[]

def calibrate(rows):
    label='MATCHED_TRAIN_RESIDUAL_Q90';rec=receipt('START',label,'CALIBRATION')
    try:
        values={t:[] for t in ['C','D']};samples=[]
        for row in rows:
            assert row['kind']=='TRAIN_CAL' and row['status']=='COMPLETE';d=read(R/row['raw']['path']);qs={q['request_id']:q for q in d['result']['requests']}
            for call in d['calls']:
                if call['action']['kind']!='DISPATCH':continue
                q=qs[call['action']['request_id']]
                if q['response_ns'] is None:continue
                predicted=call['forecasts'][call['chosen']]['responses_s'].get(q['request_id'])
                if predicted is None:continue
                residual=q['response_ns']/1e9-predicted;values[q['task']].append(residual);samples.append({'case':row['case'],'raw_sha256':row['raw']['sha256'],'request_id':q['request_id'],'task':q['task'],'predicted_s':predicted,'response_s':q['response_ns']/1e9,'residual_s':residual,'split':'TRAIN'})
        margins={}
        for task,v in values.items():assert len(v)>=20;margins[task]=max(0.,sorted(v)[math.ceil(.9*len(v))-1])
        write(O/'RISK_CALIBRATION.json',{'task_margin_s':margins,'quantile':.9,'method':'nearest-rank positive actual-minus-own-dispatch forecast; all matched TRAIN C/D responses','samples':samples,'counts':{k:len(v) for k,v in values.items()},'EVAL_used':False,'new_physical_fit':0});receipt('COMPLETE',label,'CALIBRATION',artifact=pin(O/'RISK_CALIBRATION.json'));print('CALIBRATION_COMPLETE',margins,flush=True);return margins
    except BaseException as e:receipt('FAIL',label,'CALIBRATION',error=repr(e));raise
def fit_stage(initial,frames,stage):
    label='MATCHED_BC_STAGE'+str(stage);rec=receipt('START',label,'BC_FIT');dp=O/(label+'.DATA.pt.gz');pt(dp,{'frames':frames,'split':'TRAIN','EVAL_used':False})
    try:
        resources();state,trace=fit(initial,frames,rec,stage);cp=O/(label+'.pt.gz');tp=O/(label+'.TRACE.pt.gz');pt(cp,state);pt(tp,trace);info={k:v for k,v in trace.items() if k not in ['optimizer','shuffle_rng','group_weights','pairwise_margins']};info.update(checkpoint=pin(cp),trace=pin(tp),dataset=pin(dp));write(O/(label+'.json'),info);receipt('COMPLETE',label,'BC_FIT',checkpoint=info['checkpoint']);return state,info
    except BaseException as e:write(O/(label+'.FAILURE.json'),{'error':repr(e),'traceback':traceback.format_exc()});receipt('FAIL',label,'BC_FIT',error=repr(e));raise

def main():
    global OPSHA
    assert not O.exists(),'Consumed experiment identity';reg=read(H/'OPERATION.json');verify(reg);OPSHA=sha(H/'OPERATION.json');lock=(A/'runtime/a24_local_worker.lock').open('r+b');owned=False;wait=time.monotonic();rows=[];fits=[];batch=None
    try:
        for attempt in range(31):
            try:resources(True);lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True;break
            except (AssertionError,OSError) as e:
                if attempt==30:write(V/f'WAIT_EXPIRED_{int(time.time())}.json',{'science_START':0,'reason':repr(e)});return
                print('RESOURCE_WAIT',repr(e),round(time.monotonic()-wait),flush=True);time.sleep(20)
        O.mkdir();batch=time.monotonic();write(O/'START.json',{'unix':time.time(),'resources':resources(True),'operation_sha256':OPSHA,'HEAD':reg['HEAD'],'dirty':True,'max_START':105});inputs=read(H/'INPUTS.json');old=loadpt(CHECKPOINT);oldrisk=read(OLD_RISK)['task_margin_s']
        for item in inputs['training']:
            row,_=episode(item,'TEACHER_OLD','TRAIN_CAL',None,oldrisk,batch);rows.append(row);assert row['status']=='COMPLETE'
        risk=calibrate(rows);frames=[]
        for item in inputs['training']:
            row,ff=episode(item,'TEACHER_GUARD','TRAIN_TEACHER',None,risk,batch);rows.append(row);assert row['status']=='COMPLETE';frames.extend(ff)
        stage1,info=fit_stage(old,frames,1);fits.append(info)
        for item in inputs['training']:
            row,ff=episode(item,'BC_MATCHED','TRAIN_DAGGER',stage1,risk,batch);rows.append(row);assert row['status']=='COMPLETE';frames.extend(ff)
        final,info=fit_stage(stage1,frames,2);fits.append(info);frames.clear();gc.collect();write(O/'FREEZE.json',{'unix':time.time(),'checkpoint':fits[-1]['checkpoint'],'network_sha256':final['network_sha256'],'fit_stage':2,'EVAL_episodes_started':0,'no_EVAL_selection':True,'risk':pin(O/'RISK_CALIBRATION.json')})
        for item in inputs['evaluation']:
            for mode in MODES:
                state=old if mode in ['BC_OLD','BC_GUARD_FROZEN'] else final if mode=='BC_MATCHED' else None;currentrisk=oldrisk if mode in ['TEACHER_OLD','BC_OLD'] else risk;row,_=episode(item,mode,'EVAL',state,currentrisk,batch);rows.append(row)
        verify(reg);equal(loadpt(CHECKPOINT),old);equal(loadpt(R/fits[-1]['checkpoint']['path']),final);events=[json.loads(l) for l in (O/'receipts.jsonl').read_text().splitlines()];counts={k:sum(e['event']==k for e in events) for k in ['START','COMPLETE','FAIL']};assert counts['START']<=105 and counts['START']==counts['COMPLETE']+counts['FAIL'];write(O/'RESULT.json',{'state':'FINITE_TERMINAL','rows':rows,'fits':fits,'counts':counts,'new_environments':len(rows),'new_residual_calibration':1,'new_NN_fits':2,'new_physical_fit':0,'new_measurements':0,'new_PPO':0,'old_completed_rerun':0,'elapsed_s':time.monotonic()-batch,'adopted':False});print('BATCH_COMPLETE',counts,flush=True)
    except BaseException as e:
        if O.exists():write(O/f'BATCH_FAILURE_{int(time.time())}.json',{'error':repr(e),'traceback':traceback.format_exc(),'rows':rows,'fits':fits,'science_START':STARTS,'automatic_retry':False})
        else:write(V/f'PRESTART_FAILURE_{int(time.time())}.json',{'error':repr(e),'traceback':traceback.format_exc(),'science_START':0})
        raise
    finally:
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
        if owned:write(V/f'LOCK_RELEASED_{int(time.time())}.json',{'owned_lock_returned':True})
if __name__=='__main__':main()
