"""Both frozen NNs on exactly the same saved new-rule states; no environment/fit."""
import sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/a24_s26_matched_bc_20261022'))
from matched_common import *
import numpy as np
import torch

def main():
    result=read(O/'RESULT.json');old=loadpt(CHECKPOINT);new=loadpt(R/result['fits'][1]['checkpoint']['path']);nets={'OLD':legacy.Learner(state=old),'RETRAINED':legacy.Learner(state=new)};out={};checks=0
    for cohort in ['PRIMARY','SMALL','STRESS']:
        rr=[r for r in result['rows'] if r['kind']=='EVAL' and r['condition']['cohort']==cohort and r['policy']=='BC_GUARD_FROZEN'];counts={k:{'states':0,'nontrivial':0,'exact_errors':0,'nontrivial_errors':0,'cost_incompatible':0,'max_cost_regret':0.} for k in nets};changed=0;pins=[]
        for r in rr:
            d=read(R/r['raw']['path']);calls=d['calls'];pins.append(r['raw'])
            for start in range(0,len(calls),128):
                cc=calls[start:start+128];x=torch.from_numpy(np.asarray([c['x'] for c in cc],np.float32));mask=torch.from_numpy(np.asarray([c['mask'] for c in cc],bool));pred={}
                with torch.no_grad():
                    for k,net in nets.items():pred[k]=net.net(x,mask)[0].argmax(-1).tolist()
                for i,c in enumerate(cc):
                    assert pred['OLD'][i]==c['chosen'];changed+=int(pred['OLD'][i]!=pred['RETRAINED'][i]);checks+=1
                    for k in nets:
                        idx=pred[k][i];s=counts[k];error=idx!=c['teacher_index'];non=sum(c['mask'])>1;regret=c['teacher_scores'][idx]-min(v for v,m in zip(c['teacher_scores'],c['mask']) if m);s['states']+=1;s['nontrivial']+=int(non);s['exact_errors']+=int(error);s['nontrivial_errors']+=int(error and non);s['cost_incompatible']+=int(regret>1e-8);s['max_cost_regret']=max(s['max_cost_regret'],regret)
        out[cohort]={'fixed_state_source_policy':'BC_GUARD_FROZEN','source_raws':pins,'counts':counts,'NN_action_changes':changed,'not_new_rollout':True,'no_model_selection':True}
    for k,state in [('OLD',old),('RETRAINED',new)]:equal(nets[k].snapshot(),state);checks+=1
    write(O/'FIXED_STATE_COMPARISON.json',{'status':'PASS','checks':checks,'cohorts':out,'new_environments':0,'new_fits':0,'script':pin(Path(__file__))});print(json.dumps({'state':'FIXED_STATE_COMPARE_PASS','checks':checks,'cohorts':{k:v['counts'] for k,v in out.items()}},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
