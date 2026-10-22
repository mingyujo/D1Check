import sys,math,csv,copy,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/a24_s26_scale_20261022'))
from scale_common import *
from scoring import evaluate_setting,ranking
import numpy as np
import torch

def np_logits(net,x,mask):
    w={k:v.detach().numpy().astype(float) for k,v in net.state_dict().items()};linear=lambda a,n:a@w[n+'.weight'].T+w[n+'.bias'];e=np.tanh(linear(np.asarray(x,float),'encode.0'));m=np.asarray(mask,bool);ctx=np.concatenate([(e*m[:,:,None]).sum(1)/m.sum(1)[:,None],np.where(m[:,:,None],e,-1e9).max(1)],axis=-1);a=np.concatenate([e,np.broadcast_to(ctx[:,None],(len(e),36,96))],axis=-1);return np.where(m,linear(np.tanh(linear(a,'actor.0')),'actor.2').squeeze(-1),-1e9)

def main():
    reg=read(H/'OPERATION.json');verify(reg);data=read(H/'INPUTS.json');result=read(O/'RESULT.json');select=read(O/'DEV_SELECTION.json');state=legacy.loadpt(CHECKPOINT);net=legacy.Learner(state=state);before=net.snapshot();count=0;choices=0;near_ties=0;maxregret=0.;bindings=[];protos={};deviations=[]
    for item in data['cases']:
        c=item['case'];bank=read(R/item['bank']['path']);public=read(R/item['public']['path'])['public'];cond=c['condition'];n=c['n'];burst=cond['burst'];rate=cond['requests_per_second'];assert n==len(bank['jobs'])==len(public['requests']);assert sum(q['task']=='C' for q in bank['jobs'])==n*cond['mix'];count+=2
        assert abs(c['supply_stop_s']-35-n/rate)<1e-9 and abs(c['service_stop_s']-c['supply_stop_s']-45)<1e-9 and abs(c['censor_s']-c['supply_stop_s']-60)<1e-9 and abs(c['observation_end_s']-c['supply_stop_s']-90)<1e-9;count+=4
        for q,j in zip(public['requests'],bank['jobs']):
            assert q['scheduled_arrival_ns']==round((35+(j['ordinal']//burst)*burst/rate)*1e9);assert q['deadline_ns']-q['scheduled_arrival_ns']==(800000000 if q['task']=='C' else 2000000000);assert q['priority']==('U' if q['task']=='C' else 'N');assert j['queue_entry_ns']>=q['scheduled_arrival_ns'];count+=4
            key=(cond['role'],cond['draw'],cond['mix'],j['ordinal'],j['task']);v=(j['admission']['sample_id'],tuple((r,v['sample_id'],tuple(v['stages_ns'])) for r,v in j['routes'].items()))
            if key in protos:assert protos[key]==v
            protos[key]=v
    # In the scaled burst templates task rotation depends on burst group. Thus only
    # same task/ordinal shares latent vectors across bursts; within-setting policies match exactly.
    example={}
    for item in data['cases']:
        c=item['case'];co=c['condition']
        if co['role']=='DEV' and co['n']==256 and co['mix']==.5 and co['nominal_load']==.25:example[co['burst']]=[q['task'] for q in read(R/item['bank']['path'])['jobs']]
    diff=[i for i,(a,b) in enumerate(zip(example[4],example[8])) if a!=b]
    write(O/'INPUT_PAIRING_NOTE.json',{'same_setting_policies_exact':True,'same_role_draw_mix_ordinal_task_latents_exact':True,'burst_changes_task_rotation_positions':True,'example_N256_C50_B4_vs_B8_changed_task_ordinals':len(diff),'example_first_changed_ordinals':diff[:20],'protocol_qualification':'Task mixture totals are fixed; task rotation depends on burst grouping, so cross-burst comparison also changes task order. This is a scale-scenario search, not an isolated causal effect of burst size. N/load comparisons at fixed burst share exact prefix.','new_environment':0})
    for row in result['rows']:
        if row['status']!='COMPLETE':continue
        raw=read(R/row['raw']['path']);assert sha(R/row['raw']['path'])==row['raw']['sha256'];calls=raw['calls']
        if row['policy']=='BC_NEURAL_URGENT':
            for start in range(0,len(calls),128):
                part=calls[start:start+128];x=np.asarray([c['x'] for c in part],np.float32);m=np.asarray([c['mask'] for c in part],bool)
                with torch.no_grad():p=net.net(torch.from_numpy(x),torch.from_numpy(m))[0].argmax(-1).numpy()
                independent=np_logits(net.net,x,m)
                for j,c in enumerate(part):
                    assert int(p[j])==c['chosen'];regret=float(independent[j].max()-independent[j,c['chosen']]);assert regret<2e-6;maxregret=max(maxregret,regret);near_ties+=int(independent[j].argmax()!=c['chosen']);choices+=1
        count+=len(calls)
    recomputed=[]
    for st in data['settings']:
        rr=[r for r in result['rows'] if r['condition']['role']=='DEV' and r['condition']['setting']==st['id']];s=evaluate_setting(rr);prior=next(r for r in select['candidates'] if r['setting']==st);assert s==prior['score'];recomputed.append((st,s));count+=1
    winner=min(recomputed,key=lambda v:ranking(*v));assert winner[0]==select['selected']['setting']==result['selected'];confirm=[r for r in result['rows'] if r['condition']['role']=='CONF'];assert len(confirm)==20 and all(r['condition']['setting']==winner[0]['id'] for r in confirm);count+=2
    events=[json.loads(l) for l in (O/'receipts.jsonl').read_text().splitlines()];firstconf=min(e['unix'] for e in events if e['event']=='START' and '_CONF_' in e['label']);assert select['unix']<firstconf and not select['confirmation_read_for_choice'];legacy.equal(net.snapshot(),before);legacy.equal(legacy.loadpt(CHECKPOINT),state);verify(reg);count+=4
    write(O/'AUDIT_PYTHON.json',{'status':'PASS','checks':count,'numpy_Torch_frozen_NN_choices':choices,'numpy_argmax_near_ties':near_ties,'max_numpy_logit_regret':maxregret,'all_DEV_ranking_recomputed':True,'selection_before_CONFIRM':True,'input_pairing_qualification_recorded':True,'new_fits':0,'new_environments':0,'checkpoint_unchanged':True,'source_pins_unchanged':True,'script':pin(Path(__file__))});print(json.dumps({'state':'AUDIT_PYTHON_PASS','checks':count,'NNchoices':choices,'maxregret':maxregret}),flush=True)
if __name__=='__main__':main()
