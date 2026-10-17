"""Saved-only stochastic actor + exact PPO/Adam/RNG replay. No environments."""
import argparse,copy,gzip,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
import torch
torch.set_num_threads(1)
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/RL_COST_20261017_01'
RUN=OUT
sys.path.insert(0,str(Path(__file__).resolve().parent))
from snapshots import load_snapshot,load_torch
checks=0
def need(ok,label):
    global checks
    if not ok:raise ValueError(label)
    checks+=1
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def eq(a,b,key='snapshot'):
    if isinstance(a,torch.Tensor):need(isinstance(b,torch.Tensor) and torch.equal(a,b),key)
    elif isinstance(a,np.ndarray):need(isinstance(b,np.ndarray) and np.array_equal(a,b),key)
    elif isinstance(a,dict):
        need(a.keys()==b.keys(),key+' keys')
        for k in a:eq(a[k],b[k],key+'.'+str(k))
    elif isinstance(a,(tuple,list)):
        need(type(a)==type(b) and len(a)==len(b),key+' len')
        for i,(x,y) in enumerate(zip(a,b)):eq(x,y,key+'.'+str(i))
    else:need(a==b,key)
def main():
    guard=load('protected48_audit_guard',ROOT/'reference/model_integration/runtime_guard.py')
    guard.OWN_TOKENS+=('rr_20261017','rl_cost_20261017','s26-multiresource-','s26-integrated-model-')
    reg=read(ROOT/'models/registration.json');guard.process_guard(Path(__file__).resolve(),reg['known_PS_producer_paths']);guard.free_guard([ROOT,'D:/'])
    need(not (OUT/'NN_AUDIT.json').exists(),'Audit never overwrite/retry')
    result=read(OUT/'RESULT.json');terminal=read(OUT/'COMPLETE.json');need(terminal['result_sha256']==sha(OUT/'RESULT.json'),'Complete SHA')
    learn=load('protected48_audit_learner',ROOT/'reference/rolling/learner.py')
    frames_total=0;update_episodes=[];actor_changed=0
    for i in range(1,97):
        label='TRAIN_%03d'%i;m=read(OUT/(label+'.learning.json'))
        for key in ('before','after','experience'):need(sha(m[key]['path'])==m[key]['sha256'],'Exact '+label+key)
        learner=load_snapshot(learn,m['before']['path'])
        exp=load_torch(m['experience']['path'])
        for f in exp['frames']:
            rp=learn.replay_frame(learner.net,f)
            need(abs(rp['logprob']-f['old_logp'])<1e-6,'Stochastic logprob replay')
            need(np.allclose(rp['critic'],f['value'],rtol=1e-5,atol=1e-6),'Stochastic critic replay')
            need(f['collect'] and f['mask'][f['index']] and f['physical_mask'][f['index']],'Stochastic legal mask')
            eq(learner.action_rng.get_state(),f['action_rng_before'],'Action RNG chain')
            with torch.no_grad():
                residual,_=learner.net(*learn.tensors(f));logits=(residual+torch.from_numpy(f['prior_logits'])[None,:]).masked_fill(~torch.from_numpy(f['mask'])[None,:],-1e9)
                idx=int(torch.multinomial(logits.softmax(-1)[0],1,generator=learner.action_rng))
            need(idx==f['index'],'Exact stochastic action')
            eq(learner.action_rng.get_state(),f['action_rng_after'],'Post action RNG');frames_total+=1
        learner.add_episode(exp['frames'],exp['costs'],exp['alpha'],exp['role_counts'])
        expected=load_torch(m['after']['path'])
        eq(learner.snapshot(),expected,'After '+label)
        need(learn.network_digest(learner.net)==m['after_network'],'Network digest')
        if m['before_network']!=m['after_network']:actor_changed+=1;update_episodes.append(i)
        # Reward aggregate proof is independent of PPO relabel/update replay.
        need(exp['costs'].shape==(len(exp['frames']),5),'Cost dimensions')
        need(np.allclose(exp['costs'].sum(0),exp['proof']['total_cost'],atol=1e-10),'Dense reward telescope')
        print(label,'SAVED_REPLAY_PASS',flush=True)
    selected=result['selected']['checkpoint']['path'];eval_count=0
    for p in sorted(RUN.glob('*.frames.pt.gz')):
        if p.name.startswith('TRAIN_'):continue
        label=p.name[:-len('.frames.pt.gz')]
        if label.startswith('DEV_EP'):checkpoint=OUT/('PPO_COST_EP'+label[6:9]+'.pt.gz')
        elif label.endswith('_ROLLING_ATC_RL'):checkpoint=ROOT/'models/PPO_FOUR_ROUTE_EP032.pt'
        else:checkpoint=selected
        learner=load_snapshot(learn,checkpoint)
        for f in load_torch(p):
            rp=learn.replay_frame(learner.net,f)
            need(rp['argmax']==f['index'],'Eval deterministic argmax '+label)
            need(abs(rp['logprob']-f['old_logp'])<1e-6,'Eval logprob')
            need(np.allclose(rp['critic'],f['value'],rtol=1e-5,atol=1e-6),'Eval critic')
            need(not f['collect'] and f['mask'][f['index']] and f['physical_mask'][f['index']],'Eval legal mask')
            eq(f['action_rng_before'],f['action_rng_after'],'Eval RNG unused');eval_count+=1
    need(actor_changed>0 and result['updates']==12,'Real network updates12')
    terminal_snapshot=load_torch(OUT/'PPO_COST_EP096.pt.gz')
    need(terminal_snapshot['network_sha256']==read(OUT/'TRAIN_096.learning.json')['after_network'],'Training terminal network')
    report=dict(status='PASS_EXACT_SAVED_ACTOR_ADAM_ACTION_SHUFFLE_RNG_UPDATE_REPLAY',checks=checks,
        training_episodes=96,training_frames=frames_total,eval_frames=eval_count,network_change_episodes=update_episodes,
        updates=result['updates'],optimizer_steps=result['Adam_steps'],new_environment=0,actual_new_NN_training=0,
        saved_optimizer_replay_only=True,source_sha256=sha(__file__),result_sha256=sha(OUT/'RESULT.json'),
        measured_J=None,physical_goal_validated=False,utc=guard.now())
    guard.write_new(OUT/'NN_AUDIT.json',report);print(json.dumps(report),flush=True)
if __name__=='__main__':main()
