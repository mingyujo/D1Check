"""Independent saved-only Float64 verification of frozen large PPO."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import sys,json,gzip,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent;A=H.parents[1];O=A/'results/A24_DURATION_040_20261019_01'
sys.path.insert(0,str(A/'experiments/public_transfer_20261018'))
from common_transfer import np,loadpt
def read(p):return json.loads(gzip.decompress(Path(p).read_bytes()) if str(p).endswith('.gz') else Path(p).read_bytes())
def main():
    rows=read(O/'RESULT.json')['rows'];op=read(H/'OPERATION.json');snap=loadpt(op['checkpoint']['path']);net={k:v.detach().numpy().astype(np.float64) for k,v in snap['network'].items()};frames=0;regretmax=0.;ties=0
    def linear(x,n):return x@net[n+'.weight'].T+net[n+'.bias']
    for row in rows:
        if row['policy']!='OLD_PPO' or row.get('status')=='FAIL':continue
        assert row['network_sha256']==snap['network_sha256'];calls=read(O/(row['label']+'.raw.json.gz'))['calls']
        for start in range(0,len(calls),128):
            cs=calls[start:start+128];x=np.asarray([q['x'] for q in cs],np.float64);mask=np.asarray([q['mask'] for q in cs],bool);e=np.tanh(linear(x,'encode.0'));mean=(e*mask[:,:,None]).sum(1)/mask.sum(1)[:,None];maximum=np.where(mask[:,:,None],e,-1e9).max(1);ctx=np.concatenate([mean,maximum],-1);logits=linear(np.tanh(linear(np.concatenate([e,np.broadcast_to(ctx[:,None,:],(len(cs),36,96))],-1),'actor.0')),'actor.2').squeeze(-1);logits=np.where(mask,logits,-1e9)
            for j,q in enumerate(cs):
                assert mask[j,q['chosen']] and q['actions'][q['chosen']]==q['action'];regret=float(logits[j].max()-logits[j,q['chosen']]);regretmax=max(regretmax,regret);assert regret<2e-6,(row['label'],regret);ties+=int(int(logits[j].argmax())!=q['chosen']);frames+=1
        print('DURATION_SAVED_NN',row['label'],frames,flush=True)
    with (O/'NN_AUDIT.json').open('x',encoding='utf-8') as f:json.dump(dict(status='PASS',frames=frames,max_Float64_argmax_regret=regretmax,Float32_rounding_ties=ties,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),producer_exact_Torch_replay=read(O/'REPLAY.json'),new_environment=0),f,indent=2)
if __name__=='__main__':main()
