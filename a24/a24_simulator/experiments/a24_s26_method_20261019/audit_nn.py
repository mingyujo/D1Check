"""Saved-only independent Float64 NN audit and all-condition report."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,gzip,hashlib,time,msvcrt,shutil,datetime
from pathlib import Path
import psutil
H=Path(__file__).resolve().parent;A=H.parents[1];R=A.parent;O=A/'results/A24_S26_METHOD_20261019_01'
def read(p):
    b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    result=read(O/'RESULT.json');assert result['COMPLETE']==240 and read(O/'AUDIT.json')['status']=='PASS'
    assert not (O/'POST_START.json').exists(),'Consumed saved audit identity'
    lock=(A/'runtime/a24_local_worker.lock').open('r+b');locked=False;deadline=time.monotonic()+3600
    while True:
        if not locked:
            try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            except OSError:pass
        processes=[p.info for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in ('python.exe','python3.exe')]
        if locked and len(processes)<=3 and psutil.virtual_memory().available>=512*1048576:break
        assert time.monotonic()<deadline;time.sleep(5)
    try:
        save('POST_START.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256=sha(H/'audit_nn.py'),new_environment=0,new_training=0))
        sys.path.insert(0,str(A/'experiments/public_transfer_20261018'))
        from common_transfer import np,loadpt
        frames=0;maxregret=0.;tied=0;rewardchecks=0;rewarderror=0.;expected={x['label']:x for x in read(O/'EXPECTED_TRAIN_REWARDS.json')}
        def linear(x,net,name):return x@net[name+'.weight'].T+net[name+'.bias']
        for row in result['rows']:
            if row['network_file'] is None:continue
            snap=loadpt(O/row['network_file']);assert snap['network_sha256']==row['network_sha256'];net={k:v.detach().numpy().astype(np.float64) for k,v in snap['network'].items()};calls=read(O/(row['label']+'.raw.json.gz'))['calls']
            if row['kind']=='TRAIN':
                saved=loadpt(O/(row['label']+'.FRAMES.pt.gz'));cost=np.asarray(expected[row['label']]['costs']);assert saved['cost'].shape==cost.shape;error=float(np.max(np.abs(saved['cost']-cost)));rewarderror=max(rewarderror,error);assert error<5e-7;rewardchecks+=int(cost.size)
            for start in range(0,len(calls),128):
                cs=calls[start:start+128];x=np.asarray([q['x'] for q in cs],np.float64);mask=np.asarray([q['mask'] for q in cs],bool);e=np.tanh(linear(x,net,'encode.0'));mean=(e*mask[:,:,None]).sum(1)/mask.sum(1)[:,None];maximum=np.where(mask[:,:,None],e,-1e9).max(1);ctx=np.concatenate([mean,maximum],-1);cxt=np.broadcast_to(ctx[:,None,:],(len(cs),36,96));logits=linear(np.tanh(linear(np.concatenate([e,cxt],-1),net,'actor.0')),net,'actor.2').squeeze(-1);logits=np.where(mask,logits,-1e9)
                for j,q in enumerate(cs):
                    assert mask[j,q['chosen']] and q['actions'][q['chosen']]==q['action']
                    if row['kind']!='TRAIN':
                        regret=float(logits[j].max()-logits[j,q['chosen']]);maxregret=max(maxregret,regret);assert regret<2e-6,(row['label'],regret);tied+=int(int(logits[j].argmax())!=q['chosen'])
                    frames+=1
            print('SAVED_NN',row['label'],frames,flush=True)
        save('NN_AUDIT.json',dict(status='PASS',frames=frames,max_Float64_argmax_regret=maxregret,Float32_rounding_ties=tied,independent_reward_scalar_checks=rewardchecks,max_independent_reward_error=rewarderror,TRAIN_actions='Original Torch RNG/Adam exact replay in REPLAY.json; Float64 checks legal selected action only',new_environment=0))
        print('S26_METHOD_SAVED_NN_COMPLETE',frames,flush=True)
    finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
if __name__=='__main__':main()
