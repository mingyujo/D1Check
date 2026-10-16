"""Explicit fresh four-route PPO, predetermined DEV selection and saved EVAL.

Never auto-resume. Every environment consumes START before sampling. The model
is frozen; learning changes policy weights only. No remote/device operations.
"""
from pathlib import Path
import copy,gzip,json,os,sys,hashlib,subprocess
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'src'))
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())
import lab_backend as L
import numpy as np,torch
torch.set_num_threads(1)
ENTRY=Path(__file__).resolve()
def save(p,x):L.write_new(p,x)
def consume(label,body):
    L.runtime_guard.process_guard(ENTRY)
    L.free_guard([P])
    ledger=P/'runtime/receipts.jsonl';used=sum(json.loads(s)['event']=='START' for s in ledger.read_text().splitlines()) if ledger.exists() else 0
    if used>=256:raise RuntimeError('Shared child allocation exhausted')
    identity=L.digest(['FOUR_ROUTE_PPO_V2',label,OP_SHA])
    if ledger.exists() and identity in ledger.read_text():raise RuntimeError('Consumed identity; no automatic retry')
    start={'event':'START','identity':identity,'label':label,'operation_sha256':OP_SHA,'utc':L.now(),'new_environment':1}
    L.append(ledger,start)
    try:
        out=body(start);save(P/'runtime/training'/(label+'.summary.json'),out['summary'])
        with gzip.open(P/'runtime/training'/(label+'.json.gz'),'wt',encoding='utf-8') as f:f.write(L.canonical(out['prediction']))
        L.append(ledger,{**start,'event':'PREPARED','summary_sha256':L.digest(out['summary'])})
        L.append(ledger,{**start,'event':'COMPLETE'});return out
    except BaseException as e:
        L.append(ledger,{**start,'event':'FAIL','error':str(e),'automatic_retry':False});raise
def score(rows):
    short=[]
    for r in rows:
        for v in r['by_priority'].values():
            if v['planned']:short.append(max(0,.95-v['on_time']/v['planned']))
    return [sum(r['metrics']['response_missing'] for r in rows),sum(short)/len(short),
            sum(r['J_proxy'] for r in rows)/len(rows),sum(r['AP_mean_c'] for r in rows)/len(rows)]
def main():
    global OP_SHA
    op=L.read(P/'models/TRAINING_OPERATION.json');OP_SHA=L.sha(P/'models/TRAINING_OPERATION.json')
    for pin in op['source_pins']:L.pin(pin)
    L.runtime_guard.process_guard(ENTRY);L.free_guard([P])
    if (P/'runtime/training').exists():raise RuntimeError('Training namespace exists: preserve and audit, never rerun')
    (P/'runtime/training').mkdir(parents=True)
    import msvcrt
    lock=Path(op['shared_worker_lock']).open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        reg=L.read(P/'models/registration.json');model,thermal,profile=L.initialize(reg)
        catalog=L.read(L.pin(reg['catalog_pin']))
        learn=L.load_module('fresh_a24_learner',P/'reference/rolling/learner.py')
        learner=learn.Learner(20261028,'JOINT_ATC_RL',learn.Settings(episodes_per_update=8))
        BasePolicy=L.RLPolicy
        class TrainingPolicy(BasePolicy):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs)
                self.controller=learner.controller(.95,.5,True);self.collect=True
                self.network_sha=learn.network_digest(learner.net)
        init_sha=learn.network_digest(learner.net);snapshots={}
        plan=op['cases'];train=plan['train'];dev=plan['dev'];evals=plan['eval']
        for episode,c in enumerate(train,1):
            value=L.validate_input(c['input'],catalog['profiles'])
            value['rl_seed']=46201  # constructor reference only; fresh learner owns every action
            pub,contexts=L.prepare_public(value,catalog['templates'],catalog['profiles']);m=L.Model(model,contexts)
            holder={}
            def body(start):
                L.RLPolicy=TrainingPolicy
                try:r,actor=L.policy_result('ROLLING_ATC_RL',pub,m,thermal,profile,value,start,reg)
                finally:L.RLPolicy=BasePolicy
                r['summary']['RL_status']='FRESH_FOUR_ROUTE_PPO_STOCHASTIC_TRAIN_COLLECTION'
                for f in actor.controller.frames:
                    replay=learn.replay_frame(learner.net,f)
                    if abs(replay['logprob']-f['old_logp'])>1e-6:raise ValueError('Stochastic logprob replay mismatch')
                costs=np.zeros((len(actor.controller.frames),5),dtype=np.float64)
                s=r['summary'];inc=sum(s['energy']['increment_terms_J'].values())
                ts=np.asarray(r['AP']['t_s']);ap=np.asarray(r['AP']['ap_c'])
                heat=float(np.trapezoid(np.maximum(ap-pub['initial_ap_c'],0),ts))
                fail=[(v['planned']-v['on_time'])/v['planned'] if v['planned'] else 0 for v in s['by_priority'].values()]
                costs[-1]=[inc/100,heat/1000,*fail,s['metrics']['response_missing']/s['metrics']['planned']]
                # Exact experiences and pre-update CP are saved before Adam.
                torch.save({'frames':actor.controller.frames,'costs':costs},P/'runtime/training'/('TRAIN%03d.experience.pt'%episode))
                learner.save_snapshot(P/'runtime/training'/('TRAIN%03d.before.pt'%episode))
                meta=learner.add_episode(actor.controller.frames,costs,.95,{p:v['planned'] for p,v in s['by_priority'].items()})
                learner.save_snapshot(P/'runtime/training'/('TRAIN%03d.after.pt'%episode))
                holder['meta']=meta;return r
            consume('TRAIN%03d'%episode,body)
            if episode in (16,32,64):
                cp=P/'models'/('PPO_FOUR_ROUTE_EP%03d.pt'%episode);learner.save_snapshot(cp)
                snapshots[episode]={'path':str(cp),'sha256':L.sha(cp),'bytes':cp.stat().st_size}
            if episode%8==0:print('TRAIN',episode,'Adam',learner.steps,flush=True)
        # No selection by the final evaluation grid. These DEV seeds are separate.
        rankings=[]
        for ep,cp in snapshots.items():
            dr=copy.deepcopy(reg);dr['checkpoints']['20261028']=cp;dr['four_route_retrained']=True;rows=[]
            for i,c in enumerate(dev):
                v=copy.deepcopy(c['input']);v['rl_seed']=20261028
                pub,contexts=L.prepare_public(v,catalog['templates'],catalog['profiles']);m=L.Model(model,contexts)
                def body(start):
                    r,actor=L.policy_result('ROLLING_ATC_RL',pub,m,thermal,profile,v,start,dr)
                    L.audit_result(r,actor);return r
                rows.append(consume('DEV_EP%03d_%02d'%(ep,i),body)['summary'])
            rankings.append({'episode':ep,'checkpoint':cp,'score':score(rows),'rows':rows})
        selected=min(rankings,key=lambda x:(x['score'],x['episode']))
        reg['checkpoints']['20261028']=selected['checkpoint'];reg['four_route_retrained']=True
        # Every generated runtime registration uses an explicit final code freeze.
        reg['source_pins']=op['source_pins'];reg['RL_selection']='DEV_ONLY_LEXICOGRAPHIC_INCOMPLETE_SERVICE_SHORTFALL_THEN_J_AP'
        (P/'models/registration.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        training={'status':'FOUR_ROUTE_PPO_TRAINED_DEV_SELECTED_NOT_DEVICE_VALIDATED','operation_sha256':OP_SHA,
            'episodes':64,'updates':learner.updates,'adam_steps':learner.steps,'initial_network_sha256':init_sha,
            'final_network_sha256':learn.network_digest(learner.net),'actor_changed':init_sha!=learn.network_digest(learner.net),
            'rankings':rankings,'selected':selected['checkpoint'],'selected_episode':selected['episode'],
            'new_device_measurements':0,'fresh_confirmation':False,'energy_J_measured':None,'physical_goal_pass':False}
        save(P/'models/TRAINING_RESULT.json',training)
        # Final evaluation is never used to change the selected checkpoint.
        allrows=[]
        for i,c in enumerate(evals):
            value=copy.deepcopy(c['input']);value['rl_seed']=20261028
            pub,contexts=L.prepare_public(value,catalog['templates'],catalog['profiles']);m=L.Model(model,contexts);rows=[]
            for policy in L.POLICIES:
                def body(start):
                    r,a=L.policy_result(policy,pub,m,thermal,profile,value,start,reg);L.audit_result(r,a);return r
                rows.append(consume('EVAL_%02d_%s'%(i,policy),body)['summary'])
            from diagnostics import schedule_groups
            allrows.append({'label':c['label'],'input':value,'rows':rows,'schedule_equivalence':schedule_groups(rows)})
            print('EVAL',i+1,len(evals),flush=True)
        save(P/'results/FOUR_ROUTE_V2_EVAL.json',{'cases':allrows,'same_fixed_model':True,'heldout_simulation_seeds_not_independent_device_data':True,'model_accuracy_validated':False})
        for pin in op['source_pins']:L.pin(pin)
        save(P/'models/TRAINING_COMPLETE.json',{'status':'COMPLETE_SOFTWARE_TRAIN_DEV_EVAL','source_sha256':OP_SHA,'START':64+len(dev)*3+len(evals)*7,'FAIL':0,'selected_episode':selected['episode'],'new_reservation':0})
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
