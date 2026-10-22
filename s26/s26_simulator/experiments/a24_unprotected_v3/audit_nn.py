"""Independent NumPy forward and exact saved on-policy/RNG/Adam arithmetic replay."""
import gzip,hashlib,io,json,msvcrt,os,re,shutil,sys,time
from pathlib import Path
for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
HERE=Path(__file__).resolve().parent
from run import read,save,sha,processes,now

def main(op,out):
    import numpy as np,torch
    from nn_train import Learner,digest
    torch.set_num_threads(1)
    result=read(out/'RESULT.json');selection=read(out/'SELECTION_FROZEN.json');checks=frames_count=update_replays=actor_changes=eval_frames=eval_nonfirst=eval_wait=0;maxlog=maxvalue=0.;started=time.monotonic()
    def load(p):return torch.load(io.BytesIO(gzip.decompress(Path(p).read_bytes())),map_location='cpu',weights_only=False)
    def check(ok,why):
        nonlocal checks
        checks+=1
        if not ok:raise ValueError(why)
    def compare(a,b):
        if torch.is_tensor(a):check(torch.equal(a,b),'Saved tensor mismatch')
        elif isinstance(a,np.ndarray):check(np.array_equal(a,b),'Saved array mismatch')
        elif isinstance(a,dict):
            check(a.keys()==b.keys(),'Saved dict keys');
            for k in a:compare(a[k],b[k])
        elif isinstance(a,(list,tuple)):
            check(len(a)==len(b),'Saved sequence length')
            for x,y in zip(a,b):compare(x,y)
        else:check(a==b,'Saved scalar mismatch '+str(a)+' '+str(b))
    def manual(frame,net):
        nonlocal maxlog,maxvalue,frames_count,eval_frames,eval_nonfirst,eval_wait
        w={k:v.detach().numpy() for k,v in net.state_dict().items()};x=frame['x'];mask=frame['mask'];e=np.tanh(x@w['encode.0.weight'].T+w['encode.0.bias'])
        context=np.r_[(e*mask[:,None]).sum(0)/mask.sum(),np.where(mask[:,None],e,-1e9).max(0)]
        actor=np.tanh(np.concatenate((e,np.tile(context,(27,1))),axis=1)@w['actor.0.weight'].T+w['actor.0.bias'])
        logits=(actor@w['actor.2.weight'].T+w['actor.2.bias']).ravel();logits=np.where(mask,logits,-1e9);lp=logits-np.max(logits);lp-=np.log(np.exp(lp).sum())
        value=np.tanh(context@w['critic.0.weight'].T+w['critic.0.bias'])@w['critic.2.weight'].T+w['critic.2.bias']
        err=abs(float(lp[frame['index']])-frame['old_logp']);verr=float(np.max(abs(value-frame['value'])));maxlog=max(maxlog,err);maxvalue=max(maxvalue,verr)
        check(err<2e-4 and verr<2e-4,'Independent NumPy forward');check(bool(mask[frame['index']]),'Chosen action masked')
        if not frame['collect']:
            check(int(np.argmax(logits))==frame['index'],'Eval independent argmax');eval_frames+=1
            eval_nonfirst+=int(frame['index']!=int(np.flatnonzero(mask)[0]));eval_wait+=int(frame['action']['kind']=='WAIT')
        check(frame['network_sha256']==digest(net),'Frame network provenance');frames_count+=1
    pinfiles=[HERE/'audit_nn.py',HERE/'nn_train.py',HERE/'OPERATION.json',out/'RESULT.json',out/'SELECTION_FROZEN.json']
    save(HERE/'NN_AUDIT_OPERATION.json',dict(utc=now(),pins=[dict(path=str(p),sha256=sha(p)) for p in pinfiles],scope='Saved arithmetic replay only; no simulator invocation, no new training data'))
    train_cases=[c for c in read(HERE/'INPUTS.json')['cases'] if c['phase']=='TRAIN']
    for seed in op['seeds']:
        case_rng=np.random.default_rng(seed)
        for ep in range(1,129):
            label=f'S{seed}_TRAIN_{ep:03d}';before=load(out/f'S{seed}_EP{ep:03d}_before.pt.gz');learner=Learner(seed);learner.restore(before)
            if seed==271081 and ep==6:
                rc=read(out/f'S{seed}_EP{ep:03d}_case_rng.json');check(case_rng.bit_generator.state==rc['before'],'Failed case RNG before');ci=int(case_rng.integers(len(train_cases)));check(train_cases[ci]['id']==rc['selected_input'] and case_rng.bit_generator.state==rc['after'],'Failed case RNG draw')
                partial=load(out/'S271081_TRAIN_006.partial_frames.pt.gz')
                for f in partial:
                    manual(f,learner.net);index,frame=learner.choose(dict(x=f['x'],mask=f['mask'],scores=f['scores']),True);check(index==f['index'] and abs(frame['old_logp']-f['old_logp'])<1e-7,'Failed partial action RNG preserved')
                compare(learner.snapshot(),load(out/'S271081_FAILED_EP006_RNG_ONLY_AFTER.pt.gz'));compare(learner.snapshot(),load(out/'S271081_EP007_before.pt.gz'));continue
            after=load(out/f'S{seed}_EP{ep:03d}_after.pt.gz');data=load(out/(label+'.frames.pt.gz'))
            recorded_case_rng=read(out/f'S{seed}_EP{ep:03d}_case_rng.json');check(case_rng.bit_generator.state==recorded_case_rng['before'],'Case-selection RNG before')
            case_index=int(case_rng.integers(len(train_cases)));check(train_cases[case_index]['id']==recorded_case_rng['selected_input'],'Case-selection exact draw');check(case_rng.bit_generator.state==recorded_case_rng['after'],'Case-selection RNG after')
            for f in data['frames']:
                manual(f,learner.net);index,frame=learner.choose(dict(x=f['x'],mask=f['mask'],scores=f['scores']),True)
                check(index==f['index'],'Sampled action RNG replay');check(abs(frame['old_logp']-f['old_logp'])<1e-7,'Torch logprob replay')
            learner.add(data['frames'],data['costs']);replayed=learner.snapshot();compare(replayed,after)
            if after['updates']>before['updates']:
                update_replays+=1;actor_changes+=int(any(not torch.equal(v,after['network'][k]) for k,v in before['network'].items() if k.startswith('actor.')))
            if ep%16==0:print(json.dumps(dict(status='NN_TRAIN_REPLAY',seed=seed,episode=ep,frames=frames_count,checks=checks)),flush=True)
    nets={}
    for row in result['rows']:
        if row['policy']!='RL' or row['kind']=='TRAIN':continue
        match=re.search(r'DEV_S(\d+)_EP(\d+)_',row['label'])
        if match:seed,ep=map(int,match.groups())
        else:
            seed=int(re.search(r'_S(\d+)$',row['label']).group(1));ep=selection['per_seed'][str(seed)]
        key=(seed,ep)
        if key not in nets:
            l=Learner(seed);l.restore(load(out/f'S{seed}_EP{ep:03d}.pt.gz'));nets[key]=l.net
        data=load(out/(row['label']+'.frames.pt.gz'));raw=read(out/(row['label']+'.raw.json.gz'));decisions=raw['policy_decisions'];check(len(decisions)==len(data['frames']),'NN decision/frame count')
        for frame,decision in zip(data['frames'],decisions):
            check(abs(frame['time_ns']-round(decision['time']*1e9))<=1,'NN decision time')
            for key_action in ('kind','ordinal','route','wait_s'):check(frame['action'].get(key_action)==decision['action'].get(key_action),'NN final action matches environment')
        for f in data['frames']:manual(f,nets[key])
    check(update_replays==191,'Full training update count');check(result['START']==518 and result['combined_START']==528,'Expected new generation')
    audit=dict(status='PASS_INDEPENDENT_NUMPY_NN_AND_EXACT_SAVED_RNG_ADAM_REPLAY',checks=checks,frames=frames_count,replayed_update_arithmetic=update_replays,updates_changing_actor_weights=actor_changes,DEV_and_EVAL_frames=eval_frames,DEV_and_EVAL_actions_different_from_zero_logit_first_legal=eval_nonfirst,DEV_and_EVAL_WAIT_actions=eval_wait,max_numpy_logprob_error=maxlog,max_numpy_critic_error=maxvalue,elapsed_s=time.monotonic()-started,new_environment_instances=0,new_training_data=0,physical_validation=False)
    save(out/'NN_AUDIT.json',audit);print(json.dumps(audit),flush=True)

if __name__=='__main__':
    op=read(HERE/'OPERATION.json');out=Path(op['output']);assert(out/'COMPLETE.json').exists() and not(HERE/'NN_AUDIT_OPERATION.json').exists(),'Audit not eligible/consumed'
    lock=Path(op['shared_mutex']).open('r+b');locked=False
    try:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
        ps=processes();assert len({p['ProcessId'] for p in ps}-{p['ParentProcessId'] for p in ps})<=2
        assert not any(p['ProcessId']!=os.getpid() and any(t in(p.get('CommandLine')or'') for t in('a24_simulator','s26_simulator')) for p in ps)
        assert shutil.disk_usage(HERE).free>=8*1024**3
        main(op,out)
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        lock.close()
