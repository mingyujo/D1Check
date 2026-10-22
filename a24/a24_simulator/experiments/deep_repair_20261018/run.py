"""Finite diagnosis, public-only controls, calibrated PPO and imitation controls."""
import copy,gc,os,subprocess,time
from pathlib import Path
from common import B,HERE,ROOT,np,torch,read,saved,pt,loadpt,Selector
from learner import Learner
from public_controller import PublicController
from resources import wait_resources
from nn_train import digest
ENTRY=Path(__file__).resolve();os.environ['A24_LAB_GUARD_ENTRY']=str(ENTRY)
def equal(a,b):
    if torch.is_tensor(a):assert torch.equal(a,b),'Exact tensor replay'
    elif isinstance(a,np.ndarray):assert np.array_equal(a,b),'Exact array replay'
    elif isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:equal(a[k],b[k])
    elif isinstance(a,(tuple,list)):
        assert len(a)==len(b)
        for u,v in zip(a,b):equal(u,v)
    else:assert a==b,'Exact scalar replay'
def replay(out,rows):
    count=frames=updates=0
    before=loadpt(out/'BC_BEFORE.pt.gz');data=loadpt(out/'BC_DATA.pt.gz');l=Learner(before);l.distill(data['x'],data['mask'],data['teacher']);equal(l.snapshot(),loadpt(out/'BC_AFTER.pt.gz'))
    for row in rows:
        if row['kind']!='TRAIN':continue
        l=Learner(loadpt(out/(row['label']+'.BEFORE.pt.gz')));after=loadpt(out/(row['label']+'.AFTER.pt.gz'));data=loadpt(out/(row['label']+'.frames.pt.gz'))
        for f in data['frames']:
            i,again=l.choose({k:f[k] for k in ('x','mask','scores')},True);assert i==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']);frames+=1
        old=l.updates;l.add(data['frames'],data['costs']);equal(l.snapshot(),after);updates+=l.updates-old;count+=1
    greedy_frames=0;networks={}
    for row in rows:
        if not row['network_sha256'] or row['kind']=='TRAIN':continue
        key=row['network_sha256']
        if key not in networks:
            state=loadpt(out/row['network_file'])
            if row['kind']=='P0':l=B.Learner(state['seed']);l.restore(state)
            else:l=Learner(state)
            networks[key]=l
        l=networks[key];data=loadpt(out/(row['label']+'.frames.pt.gz'))
        for f in data['frames']:
            i,again=l.choose({k:f[k] for k in ('x','mask','scores')},False);assert i==f['index'] and again['old_logp']==f['old_logp'] and np.array_equal(again['value'],f['value']);greedy_frames+=1
    B.G.write_new(out/'STOCHASTIC_REPLAY.json',dict(status='PASS',episodes=count,frames=frames,exact_saved_optimizer_update_replays=updates,BC_epochs=64,BC_exact_optimizer_replay=True,exact_saved_greedy_replay=True,greedy_frames=greedy_frames,new_environment_START=0,new_training_data=0))
def main():
    op=read(HERE/'OPERATION.json');out=ROOT/op['output_dir'];opsha=B.G.sha(HERE/'OPERATION.json')
    assert '--published' in __import__('sys').argv
    for pin in op['sources']+op['input_pins']:B.G.pin(pin)
    assert not out.exists(),'Consumed namespace'
    guard=wait_resources(ENTRY,1536*1024**2,time.monotonic()+1800);B.G.free_guard([ROOT,'D:/'])
    import msvcrt
    lock=(ROOT/'runtime/a24_local_worker.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);begin=time.monotonic();count=0;rows=[]
    try:
        out.mkdir();B.G.write_new(out/'START.json',dict(utc=B.G.now(),operation_sha256=opsha,guard=guard,HEAD=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
        try:
            from diagnostics import run as probes
            probes(out)
            inputs=read(op['inputs']['path']);training=inputs['training'];evaluation=inputs['evaluation'];catalog=read(B.L.pin(B.registration(op)['catalog_pin']));physics=B.Physics(read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),B.Config(**op['physics']));public_nominals=read(ROOT/'experiments/guard_learning_20261018/PUBLIC_NOMINAL_CATALOG.json.gz');references=read(ROOT/'results/GUARD_LEARNING_20261018_01/TRAINING_REFERENCE_ENDPOINTS.json')['endpoints']
            for source in op['evaluation_reference_metrics']:
                for r in read(source['path'])['rows']:
                    if r['policy']=='EDF':references[r['case']]=r['common']['end_ns']
            def getbank(case):
                public,contexts=B.public_input(case,catalog);public['initial_ap_c']=case['temperature_c'];bank=read(op['bank_map'][case['id']]['path'])
                if case['id'].startswith('DENSITY_'):bank={**bank,'nominal_vectors':public_nominals[case['id']]}
                return public,B.BankModel(bank['jobs'],contexts),B.SavedNominal(public,[dict(nominal_vectors=bank['nominal_vectors'])])
            def window(result,end):
                energy=area=0.
                for tr in result['trace']:
                    stop=min(end,tr['end_ns']);dt=(stop-tr['start_ns'])/1e9
                    if dt<=0:continue
                    _,part=physics.transition(tr['state'],tr['active'],dt);energy+=part['increment']+physics.c.baseline*dt;area+=part['temperature_area']
                return dict(total_J_proxy=energy,mean_AP_c=area/(end/1e9-35))
            def simulate(case,policy,kind,label,learner=None,selector_kind=None,continuation='EDF',waitcap=12.,p0=False):
                nonlocal count
                wait_resources(ENTRY,512*1024**2+case['n']*384*1024,begin+op['wall_clock_limit_s']);B.G.free_guard([ROOT,'D:/']);assert count<op['environment_cap'] and time.monotonic()-begin<op['wall_clock_limit_s']
                receipt=dict(event='START',label=label,case=case['id'],policy=policy,kind=kind,utc=B.G.now(),identity=B.L.digest([opsha,label]),start_id=B.L.digest([opsha,label]),durable_START_consumed=True,operation_sha256=opsha);B.G.append(out/'receipts.jsonl',receipt);count+=1;print('START',count,label,flush=True)
                try:
                    public,model,nominal=getbank(case);collect=kind=='TRAIN';neural=learner is not None
                    if p0:actor=B.GuardController(nominal,physics,case,'RL',learner,False,deadline_guard=True)
                    else:actor=PublicController(nominal,physics,case,'RL',learner if neural else Selector(selector_kind),collect,deadline_guard=False,continuation=continuation,neural_wait_cap=waitcap)
                    if collect:pt(out/(label+'.BEFORE.pt.gz'),learner.snapshot())
                    network=digest(learner.net) if neural else None;calls=0
                    def progress(state):
                        nonlocal calls
                        calls+=1
                        if calls%512==0:assert time.monotonic()-begin<op['wall_clock_limit_s'];print('PROGRESS',label,calls,flush=True)
                        return actor(state)
                    result=B.execute(public,model,progress,physics,case['common_potential_key'],receipt);metrics=B.metrics(result,case,physics);NNcalls=[a for a in actor.calls if not a.get('common_coalescing')]
                    if neural:
                        assert len(NNcalls)==len(actor.frames)
                        for call,f in zip(NNcalls,actor.frames):call.update(old_logp=f['old_logp'],critic_value=f['value'].tolist(),collect=collect)
                    raw=out/(label+'.raw.json.gz');saved(raw,dict(result=result,calls=actor.calls,future_actual_work_used=False));costs=audit=None;frames_sha=None
                    if neural:
                        costs,audit=(B.original_rewards.labels(result,actor.frames,case,physics,metrics) if p0 else B.repaired_labels(result,actor.frames,case,physics,metrics,references[case['id']]))
                        framefile=out/(label+'.frames.pt.gz');pt(framefile,dict(frames=actor.frames,costs=costs,reward_audit=audit,collect=collect,network_sha256=network));frames_sha=B.G.sha(framefile)
                        if collect:learner.add(actor.frames,costs);pt(out/(label+'.AFTER.pt.gz'),learner.snapshot())
                    last=max(q['available_ns'] for q in result['requests']) if all(q['available_ns'] is not None for q in result['requests']) else None;completion=window(result,last) if last else None;common=window(result,references[case['id']])
                    row=dict(label=label,case=case['id'],policy=policy,kind=kind,n=case['n'],condition=case['condition'],metrics=metrics,raw_sha256=B.G.sha(raw),frames_sha256=frames_sha,network_sha256=network,reference_end_ns=references[case['id']],reward_audit=audit,network_file=(label+'.BEFORE.pt.gz' if collect else ('P0_INITIAL.pt.gz' if p0 else ('BC_ONLY.FINAL_WARM.pt.gz' if policy=='BC_ONLY' else policy.split('_WAIT48')[0]+'.FINAL_EP032.pt.gz'))) if neural else None,network_temperature=(1. if p0 else learner.temperature) if neural else None,reward_kind='ORIGINAL' if p0 else 'REPAIRED',selector_kind=selector_kind,continuation=continuation,neural_wait_cap=waitcap,finish_ns=last,completion_preview=completion,common_preview=common,selected_NN_WAIT_s=sum(a['action'].get('wait_ns',0)/1e9 for a in NNcalls))
                    B.G.write_new(out/(label+'.json'),row);rows.append(row);B.G.append(out/'receipts.jsonl',{**receipt,'event':'COMPLETE','utc':B.G.now(),'raw_sha256':row['raw_sha256']});print('COMPLETE',label,metrics['on_time'],metrics['urgent_on_time'],'elapsed',round(time.monotonic()-begin,1),flush=True)
                    if p0:
                        expected=read(op['P0_expected'][case['id']]['path'])['result']
                        for key in ('requests','trace','decisions'):assert B.G.canonical(result[key])==B.G.canonical(expected[key]),'Exact original P0 '+key
                    del result,actor;gc.collect();return row
                except BaseException as exc:B.G.append(out/'receipts.jsonl',{**receipt,'event':'FAIL','error':str(exc),'utc':B.G.now()});raise
            initial=loadpt(op['checkpoint']['path']);frozen=B.Learner(op['learner_seed']);frozen.restore(copy.deepcopy(initial));pt(out/'P0_INITIAL.pt.gz',frozen.snapshot())
            for case in evaluation:
                if case['id'] in op['P0_expected']:simulate(case,'P0_ORIGINAL_NN','P0',case['id']+'_P0',frozen,p0=True)
            for case in training:
                for kind in op['public_policies']:simulate(case,kind,'REFERENCE',case['id']+'_'+kind,selector_kind=kind,continuation='ATC' if kind=='LEX_ATC' else 'EDF')
            ref={k:[r for r in rows if r['kind']=='REFERENCE' and r['policy']==k] for k in op['public_policies']};base=ref['BANK_ATC'];eligible=[];selection=[]
            for kind,group in ref.items():
                on=all(all(r['metrics'][m]>=next(b for b in base if b['case']==r['case'])['metrics'][m] for m in ('on_time','urgent_on_time')) for r in group);done=all(r['finish_ns'] is not None and r['finish_ns']<=r['reference_end_ns'] for r in group);energy=sum(r['completion_preview']['total_J_proxy'] for r in group);heat=sum(r['common_preview']['mean_AP_c'] for r in group)/8;be=sum(r['completion_preview']['total_J_proxy'] for r in base);bh=sum(r['common_preview']['mean_AP_c'] for r in base)/8;joint=energy<=be+1e-9 and heat<=bh+1e-9
                record=dict(policy=kind,deadline_nonworse_all8=on,completed_in_fixed_H_all8=done,energy_sum=energy,mean_temperature=heat,joint_nonworse=joint,score=energy/be+(heat-26)/max(.1,bh-26));selection.append(record)
                if on and done and joint:eligible.append(record)
            teacher=min(eligible,key=lambda r:(r['score'],op['public_policies'].index(r['policy'])))['policy'] if eligible else 'BANK_ATC';B.G.write_new(out/'TEACHER_SELECTION.json',dict(teacher=teacher,training_only8=True,evaluation_used=False,all_candidates=selection,fallback='BANK_ATC',already_seen_exploratory_inputs=True))
            x=[];mask=[];target=[];source_labels=[]
            for r in ref[teacher]:
                raw=read(out/(r['label']+'.raw.json.gz'))
                for call in raw['calls']:
                    if call.get('common_coalescing') or sum(call['mask'])<=1:continue
                    x.append(call['x']);mask.append(call['mask']);target.append(call['chosen']);source_labels.append(r['label'])
            dataset=dict(x=np.asarray(x,np.float32),mask=np.asarray(mask,bool),teacher=np.asarray(target,np.int64),source_labels=source_labels);pt(out/'BC_DATA.pt.gz',dataset)
            calibrated=Learner(copy.deepcopy(initial));improved=Learner(copy.deepcopy(initial));pt(out/'BC_BEFORE.pt.gz',improved.snapshot());improved.distill(dataset['x'],dataset['mask'],dataset['teacher']);pt(out/'BC_AFTER.pt.gz',improved.snapshot());bc_only=Learner(improved.snapshot());pt(out/'BC_ONLY.FINAL_WARM.pt.gz',bc_only.snapshot());improved.set_anchor(improved.net.state_dict());arms=dict(CALIBRATED_PPO_OFF=calibrated,BC_PPO_OFF=improved);initials={k:digest(l.net) for k,l in arms.items()}
            for arm,l in arms.items():
                for ep in range(32):simulate(training[ep%8],arm,'TRAIN',arm+f'_TRAIN_{ep+1:03d}',l,continuation='ATC' if arm=='BC_PPO_OFF' and teacher=='LEX_ATC' else 'EDF')
                assert l.episodes==initial['episodes']+32 and l.updates==initial['updates']+16 and not l.pending and digest(l.net)!=initials[arm]
                pt(out/(arm+'.FINAL_EP032.pt.gz'),l.snapshot());B.G.write_new(out/(arm+'.LEARNING.json'),dict(new_episodes=32,new_updates=16,new_Adam_steps=2*(l.steps-initial['steps'])+l.bc_steps,paired_PPO_minibatches=l.steps-initial['steps'],initial_digest=initials[arm],final_digest=digest(l.net),bc_steps=l.bc_steps,logs=l.logs))
            B.G.write_new(out/'SELECTION_FROZEN.json',dict(rule='Fixed final new EP32; BC_ONLY is the fixed pre-PPO warm checkpoint',teacher_from_training_only=teacher,eval_selection=False));evaluators={**arms,'BC_ONLY':bc_only}
            for case in evaluation:
                for kind in op['public_policies']:simulate(case,kind,'RULE_EVAL',case['id']+'_'+kind,selector_kind=kind,continuation='ATC' if kind=='LEX_ATC' else 'EDF')
                for arm,l in evaluators.items():simulate(case,arm,'EVAL',case['id']+'_'+arm,l,continuation='ATC' if arm in ('BC_PPO_OFF','BC_ONLY') and teacher=='LEX_ATC' else 'EDF')
            assert count==308
            maxima={p:max(r['selected_NN_WAIT_s'] for r in rows if r['kind']=='EVAL' and r['policy']==p) for p in arms};selected=max(maxima,key=lambda p:(maxima[p],p=='BC_PPO_OFF'));trigger=maxima[selected]>=9.6;B.G.write_new(out/'WAIT_CAP_TRIGGER.json',dict(trigger=trigger,maxima=maxima,selected_by_WAIT_only=selected,all30_if_triggered=True,threshold_s=9.6,original_cap_s=12,new_cap_s=48))
            if trigger:
                for case in evaluation:simulate(case,selected+'_WAIT48','CAP_EVAL',case['id']+'_'+selected+'_WAIT48',arms[selected],continuation='ATC' if selected=='BC_PPO_OFF' and teacher=='LEX_ATC' else 'EDF',waitcap=48.)
            for pin in op['sources']+op['input_pins']:B.G.pin(pin)
            B.G.write_new(out/'RESULT.json',dict(status='COMPLETED',rows=rows,new_START=count,new_COMPLETE=count,new_FAIL=0,new_training=64,new_updates=32,new_references=32,new_public_evaluations=120,new_evaluations=90,BC_epochs=64,new_physical_fit=0,frozen_bank_restores=0,operation_sha256=opsha));B.G.write_new(out/'COMPLETE.json',dict(utc=B.G.now(),elapsed_s=time.monotonic()-begin,result_sha256=B.G.sha(out/'RESULT.json')))
            replay(out,rows);subprocess.run([op['node_executable'],str(HERE/'audit.cjs')],check=True);subprocess.run([op['node_executable'],str(HERE/'report.cjs')],check=True)
        except BaseException as exc:B.G.write_new(out/('POSTPROCESS_FAILURE.json' if (out/'COMPLETE.json').exists() else 'FAILURE.json'),dict(error=str(exc),utc=B.G.now(),new_START=count,automatic_retry=False));raise
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
