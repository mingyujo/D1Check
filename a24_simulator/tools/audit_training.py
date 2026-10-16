"""Saved tensor/optimizer replay, no environment samples or parameter adoption."""
from pathlib import Path
import sys,json,hashlib
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'reference/rolling'))
import learner as learn
import numpy as np,torch
torch.set_num_threads(1)
def main():
    checks=frames=updates=0
    for i in range(1,65):
        root=P/'runtime/training_v2'
        before=learn.Learner.load_snapshot(root/('TRAIN%03d.before.pt'%i))
        exp=torch.load(root/('TRAIN%03d.experience.pt'%i),map_location='cpu',weights_only=False)
        after=torch.load(root/('TRAIN%03d.after.pt'%i),map_location='cpu',weights_only=False)
        for f in exp['frames']:
            r=learn.replay_frame(before.net,f)
            assert abs(r['logprob']-f['old_logp'])<1e-6
            assert np.allclose(r['critic'],f['value'],rtol=1e-5,atol=1e-6)
            assert f['mask'][f['index']] and f['physical_mask'][f['index']]
            assert f['network_sha256']==learn.network_digest(before.net)
            checks+=4;frames+=1
        counts={'U':sum(q['priority']=='U' for q in json.loads((root/('TRAIN%03d.summary.json'%i)).read_text())['requests']),
                'N':sum(q['priority']=='N' for q in json.loads((root/('TRAIN%03d.summary.json'%i)).read_text())['requests'])}
        before.add_episode(exp['frames'],exp['costs'],.95,counts)
        assert learn.network_digest(before.net)==after['network_sha256']
        assert before.steps==after['steps'] and before.updates==after['updates']
        assert torch.equal(before.action_rng.get_state(),after['action_rng'])
        assert torch.equal(before.shuffle_rng.get_state(),after['shuffle_rng'])
        checks+=4;updates+=int(i%8==0)
    result={'status':'PASS_SAVED_INPUT_MASK_LOGPROB_CRITIC_AND_EXACT_ADAM_RNG_REPLAY','checks':checks,'frames':frames,
            'episodes':64,'optimizer_update_replays':updates,'new_environment_START':0,'adopted_new_networks':0,
            'physical_goal_pass':False,'measured_J':None}
    (P/'results/TRAINING_REPLAY_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':main()
