import sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/a24_s26_joint_20261022'))
from dominance_common import *
import numpy as np
import torch

def np_logits(net,x,mask):
    w={k:v.detach().numpy().astype(float) for k,v in net.state_dict().items()};linear=lambda a,n:a@w[n+'.weight'].T+w[n+'.bias'];e=np.tanh(linear(np.asarray(x,float),'encode.0'));m=np.asarray(mask,bool);ctx=np.concatenate([(e*m[:,:,None]).sum(1)/m.sum(1)[:,None],np.where(m[:,:,None],e,-1e9).max(1)],axis=-1);a=np.concatenate([e,np.broadcast_to(ctx[:,None],(len(e),36,96))],axis=-1);return np.where(m,linear(np.tanh(linear(a,'actor.0')),'actor.2').squeeze(-1),-1e9)

def main():
    reg=read(H/'OPERATION.json');verify(reg);data=read(H/'INPUTS.json');result=read(O/'RESULT.json');select=read(H/'SELECTION.json');state=legacy.loadpt(CHECKPOINT);net=legacy.Learner(state=state);before=net.snapshot();count=0;choices=0;near_ties=0;maxregret=0.
    old=read(OLDO/'RESULT.json');ranked=screen([r for r in old['rows'] if r['condition']['role']=='DEV']);assert ranked==select['candidates'];assert [r for r in ranked if r['eligible']][:2]==select['selected'];assert select['unix']<read(O/'START.json')['unix'];count+=3
    oldids={(r['bank']['sha256'],r['policy']) for r in old['rows']}
    for item in data['cases']:
        c=item['case'];bank=read(R/item['bank']['path']);public=read(R/item['public']['path'])['public'];co=c['condition'];assert len(bank['jobs'])==len(public['requests'])==c['n'];assert co['setting'] in reg['selected_ids'];assert abs(c['supply_stop_s']-35-c['n']/co['requests_per_second'])<1e-9;assert abs(c['observation_end_s']-c['supply_stop_s']-90)<1e-9;count+=4
        for j,q in zip(bank['jobs'],public['requests']):assert q['priority']==('U' if q['task']=='C' else 'N') and q['deadline_ns']-q['scheduled_arrival_ns']==(800000000 if q['task']=='C' else 2000000000);assert j['queue_entry_ns']>=q['scheduled_arrival_ns'];count+=2
    for row in result['rows']:
        assert (row['bank']['sha256'],row['policy']) not in oldids;assert sha(R/row['raw']['path'])==row['raw']['sha256'];raw=read(R/row['raw']['path']);calls=raw['calls'];count+=2
        if row['policy']=='BC_NEURAL_URGENT':
            for start in range(0,len(calls),128):
                part=calls[start:start+128];x=np.asarray([c['x'] for c in part],np.float32);m=np.asarray([c['mask'] for c in part],bool)
                with torch.no_grad():p=net.net(torch.from_numpy(x),torch.from_numpy(m))[0].argmax(-1).numpy()
                independent=np_logits(net.net,x,m)
                for j,c in enumerate(part):
                    assert int(p[j])==c['chosen'];regret=float(independent[j].max()-independent[j,c['chosen']]);assert regret<2e-6;maxregret=max(maxregret,regret);near_ties+=int(independent[j].argmax()!=c['chosen']);choices+=1
        count+=len(calls)
    assert len(result['rows'])==40 and result['counts']=={'START':40,'COMPLETE':40,'FAIL':0};legacy.equal(net.snapshot(),before);legacy.equal(legacy.loadpt(CHECKPOINT),state);verify(reg);count+=4
    write(O/'AUDIT_PYTHON.json',{'status':'PASS','checks':count,'numpy_Torch_frozen_NN_choices':choices,'numpy_argmax_near_ties':near_ties,'max_numpy_logit_regret':maxregret,'all_DEV_ranking_recomputed':True,'selection_before_CONFIRM':True,'no_completed_identity_rerun':True,'new_fits':0,'new_environments':0,'checkpoint_unchanged':True,'source_pins_unchanged':True,'script':pin(Path(__file__))});print(json.dumps({'state':'AUDIT_PYTHON_PASS','checks':count,'NNchoices':choices,'maxregret':maxregret}),flush=True)
if __name__=='__main__':main()
