"""Saved-only independent NN, TRAIN linkage, fit arithmetic and provenance audit."""
import sys,math,collections,gc
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/a24_s26_matched_bc_20261022'))
from matched_common import *
import numpy as np
import torch

def np_logits(net,x,mask):
    w={k:v.detach().numpy().astype(float) for k,v in net.state_dict().items()};linear=lambda a,n:a@w[n+'.weight'].T+w[n+'.bias'];e=np.tanh(linear(np.asarray(x,float),'encode.0'));m=np.asarray(mask,bool);ctx=np.concatenate([(e*m[:,:,None]).sum(1)/m.sum(1)[:,None],np.where(m[:,:,None],e,-1e9).max(1)],axis=-1);xx=np.concatenate([e,np.broadcast_to(ctx[:,None],(len(e),36,96))],axis=-1);return np.where(m,linear(np.tanh(linear(xx,'actor.0')),'actor.2').squeeze(-1),-1e9)

def main():
    reg=read(H/'OPERATION.json');verify(reg);inputs=read(H/'INPUTS.json');result=read(O/'RESULT.json');assert result['counts']=={'START':105,'COMPLETE':105,'FAIL':0} and len(result['rows'])==102;count=2;choices=0;ties=0;maxregret=0.;mimic={};old=loadpt(CHECKPOINT);states={'OLD':old};nets={'OLD':legacy.Learner(state=old)};records={}
    trainids={i['case']['id'] for i in inputs['training']};evalids={i['case']['id'] for i in inputs['evaluation']};assert not trainids&evalids
    members={s:{(k,r['id']) for k,v in inputs['pool_members'][s].items() for r in v} for s in ['TRAIN','EVAL']};assert not members['TRAIN']&members['EVAL'];count+=2
    for kind in ['training','evaluation']:
        split='TRAIN' if kind=='training' else 'EVAL'
        for item in inputs[kind]:
            c=item['case'];co=c['condition'];bank=read(R/item['bank']['path']);public=read(R/item['public']['path'])['public'];assert len(bank['jobs'])==len(public['requests'])==c['n'];assert co['role']==split and abs(c['supply_stop_s']-35-c['n']/co['requests_per_second'])<1e-9;assert public['initial_ap_c']==c['temperature_c'];count+=3
            for j,q in zip(bank['jobs'],public['requests']):
                assert q['priority']==('U' if q['task']=='C' else 'N') and q['deadline_ns']-q['scheduled_arrival_ns']==(800000000 if q['task']=='C' else 2000000000);assert (q['task']+'_ADMISSION',j['admission']['sample_id']) in members[split]
                for route,r in j['routes'].items():assert (q['task']+'_'+route,r['sample_id']) in members[split]
                count+=4
    datasets=[]
    for stage,fitinfo in enumerate(result['fits'],1):
        state=loadpt(R/fitinfo['checkpoint']['path']);states[str(stage)]=state;nets[str(stage)]=legacy.Learner(state=state);dataset=loadpt(R/fitinfo['dataset']['path']);frames=dataset['frames'];trace=loadpt(R/fitinfo['trace']['path']);assert len(frames)==fitinfo['TRAIN_frames']<=15360 and dataset['split']=='TRAIN' and not dataset['EVAL_used'];assert trace['epochs']==128 and trace['seed']==202610220+stage and trace['network_sha256']==state['network_sha256'];datasets.append(frames);count+=3
        for k in ['updates','episodes','steps']:assert state[k]==old[k];count+=1
        equal(state['network']['critic.0.weight'],old['network']['critic.0.weight']);equal(state['network']['critic.0.bias'],old['network']['critic.0.bias']);equal(state['network']['critic.2.weight'],old['network']['critic.2.weight']);equal(state['network']['critic.2.bias'],old['network']['critic.2.bias']);count+=4
        non=[i for i,f in enumerate(frames) if sum(f['mask'])>1];groups=collections.Counter(frames[i]['group'] for i in non);assert dict(groups)==fitinfo['groups'] and len(non)==fitinfo['nontrivial_frames'];assert fitinfo['new_BC_steps']==math.ceil(len(non)/256)*128;count+=2
        margin=np.zeros((len(frames),36),np.float32);byraw=collections.defaultdict(list)
        for i,f in enumerate(frames):
            assert f['split']=='TRAIN' and f['source_case'] in trainids and f['source_case'] not in evalids;assert f['teacher_mask'].sum()==1 and f['teacher_mask'][f['index']] and f['mask'][f['index']];byraw[f['source_raw']['path']].append((i,f));target=f['index'];best=min(f['scores'][f['mask']])
            for j in np.flatnonzero(f['mask']):
                if j!=target:margin[i,j]=.02*(j-target)/35 if f['scores'][j]-best<=1e-8 else min(.5,max(.001,5*float(f['x'][j,28]-f['x'][target,28])))
            count+=2
        assert np.array_equal(margin,trace['pairwise_margins']);weights=np.array([min(2.,max(.5,len(non)/(len(groups)*groups[f['group']]))) if f['group'] in groups else 0 for f in frames],np.float32);assert np.array_equal(weights,trace['group_weights'].numpy());count+=2
        for rawpath,ff in byraw.items():
            d=read(R/rawpath);assert d['kind'] in ['TRAIN_TEACHER','TRAIN_DAGGER'] and d['case']['id'] in trainids
            for i,f in ff:
                k=f['source_decision_index'];c=d['calls'][k];s=d['result']['decisions'][k]['public_state'];assert B.L.digest(s)==f['source_public_sha256'];assert np.array_equal(np.asarray(c['x'],np.float32),f['x']) and np.array_equal(c['mask'],f['mask']) and c['teacher_index']==f['index'];assert c['post_NN_override']==False;count+=3
            del d;gc.collect()
        good=[]
        for start in range(0,len(frames),256):
            part=frames[start:start+256];x=torch.from_numpy(np.stack([f['x'] for f in part]));m=torch.from_numpy(np.stack([f['mask'] for f in part]))
            with torch.no_grad():pred=nets[str(stage)].net(x,m)[0].argmax(-1).tolist()
            good.extend(j==f['index'] for j,f in zip(pred,part))
        ac=fitinfo['logs'][-1]['accuracy'];assert abs(sum(good)/len(good)-ac['all'])<1e-7 and abs(sum(good[i] for i in non)/len(non)-ac['nontrivial'])<1e-7;count+=2
        for group in ac['per_group']:
            ids=[i for i,f in enumerate(frames) if f['group']==group];assert abs(sum(good[i] for i in ids)/len(ids)-ac['per_group'][group])<1e-7;count+=1
        for k,v in state['network'].items():assert torch.isfinite(v).all();count+=1
    # Both fit datasets must exactly equal saved, bounded TRAIN frame selections in protocol order.
    selected=[]
    for kind in ['TRAIN_TEACHER','TRAIN_DAGGER']:
        for row in [r for r in result['rows'] if r['kind']==kind]:
            fr=loadpt(R/row['frames']['path']);assert len(fr['frames'])<=768 and fr['split']=='TRAIN';selected.extend(fr['frames']);count+=1
        equal(selected,datasets[0 if kind=='TRAIN_TEACHER' else 1]);count+=1
    del datasets,selected;gc.collect()
    for row in result['rows']:
        assert sha(R/row['raw']['path'])==row['raw']['sha256'];raw=read(R/row['raw']['path']);count+=1
        if row['network_sha256'] is not None:
            key='1' if row['kind']=='TRAIN_DAGGER' else '2' if row['policy']=='BC_MATCHED' else 'OLD';net=nets[key];before=net.snapshot();assert row['network_sha256']==states[key]['network_sha256'];calls=raw['calls'];stats=mimic.setdefault(row['condition']['cohort']+'|'+row['kind']+'|'+row['policy'],{'calls':0,'exact_disagreements':0,'cost_incompatible':0,'max_cost_regret':0.})
            for start in range(0,len(calls),128):
                part=calls[start:start+128];x=np.asarray([c['x'] for c in part],np.float32);mask=np.asarray([c['mask'] for c in part],bool)
                with torch.no_grad():pred=net.net(torch.from_numpy(x),torch.from_numpy(mask))[0].argmax(-1).numpy()
                logits=np_logits(net.net,x,mask)
                for j,c in enumerate(part):
                    assert int(pred[j])==c['chosen'];regret=float(logits[j].max()-logits[j,c['chosen']]);assert regret<2e-6;maxregret=max(maxregret,regret);ties+=int(logits[j].argmax()!=c['chosen']);choices+=1;stats['calls']+=1;stats['exact_disagreements']+=int(c['chosen']!=c['teacher_index']);cr=c['teacher_scores'][c['chosen']]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m);stats['cost_incompatible']+=int(cr>1e-8);stats['max_cost_regret']=max(stats['max_cost_regret'],cr)
            equal(net.snapshot(),before);count+=1
        del raw;gc.collect()
    freeze=read(O/'FREEZE.json');events=[json.loads(l) for l in (O/'receipts.jsonl').read_text().splitlines()];first=min(r['unix'] for r in events if r['event']=='START' and r['kind']=='EVAL');assert freeze['unix']<first and freeze['checkpoint']==result['fits'][1]['checkpoint'] and freeze['no_EVAL_selection'];equal(loadpt(CHECKPOINT),old);verify(reg);count+=3
    write(O/'NN_MIMIC_DIAGNOSTICS.json',mimic);write(O/'AUDIT_PYTHON.json',{'status':'PASS','checks':count,'independent_numpy_Torch_choices':choices,'numpy_near_ties':ties,'max_numpy_logit_regret':maxregret,'TRAIN_EVAL_member_split_checked':True,'fit_frame_public_state_binding_checked':True,'margins_weights_steps_critic_PPO_counters_checked':True,'frozen_before_EVAL':True,'checkpoint_unchanged':True,'source_pins_unchanged':True,'new_environments':0,'new_fits':0,'script':pin(Path(__file__))});print(json.dumps({'state':'MATCHED_PYTHON_AUDIT_PASS','checks':count,'NNchoices':choices,'mimic':mimic},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
