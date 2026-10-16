"""Saved-only independent frozen NN input/mask/action/RNG audit. No environment."""
from pathlib import Path
import gzip,hashlib,io,json,os,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
os.environ['A24_LAB_GUARD_ENTRY']=str(Path(__file__).resolve())
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'reference/model_integration')]
import lab_backend as L
import numpy as np,torch
torch.set_num_threads(1)

def main(opfile):
    op=L.read(opfile)
    for p in op['pins']:L.pin(p)
    G=L.runtime_guard;G.OWN_TOKENS+=('long_scale_20261017','s26-state-aware-atc-','state_recovery_owner')
    reg=L.read(ROOT/'models/registration.json');G.process_guard(Path(__file__).resolve(),reg['known_PS_producer_paths']);L.free_guard([ROOT,'D:/'])
    out=ROOT/'results/LONG_SCALE_REPORT_20261017_01';result=L.read(out/'RESULT.json')
    learn=L.load_module('long_scale_saved_learner',ROOT/'reference/rolling/learner.py');learner=learn.Learner.load_snapshot(L.pin(op['checkpoint']))
    net=learn.network_digest(learner.net);report=[];total=0;checked=0;began=time.monotonic()
    for c in result['cases']:
        for row in c['rows']:
            if row['policy']!='RL':continue
            r=L.read(ROOT/row['source_result_path']);directory=(ROOT/row['source_result_path']).parent
            chain=hashlib.sha256();frames=0;replays=0;largest=0
            for chunk in r['NN']['chunks']:
                p=directory/chunk['file'];L.need(L.sha(p)==chunk['sha256'],'chunk SHA')
                data=torch.load(io.BytesIO(gzip.decompress(p.read_bytes())),weights_only=False,map_location='cpu');L.need(len(data)==chunk['frames'],'chunk frame count')
                for f in data:
                    L.need(learn.input_digest(f)==f['input_sha'],'saved input digest')
                    L.need(f['mask'][f['index']] and f['physical_mask'][f['index']],'chosen action mask')
                    L.need(np.isfinite(f['global_state']).all() and np.isfinite(f['features']).all(),'finite inputs')
                    L.need(torch.equal(f['action_rng_before'],f['action_rng_after']) and not f['collect'],'no sampling/training')
                    # Every frame already replayed during execution. Independently
                    # replay regular17-frame spacing plus both chunk boundaries.
                    if frames%17==0 or f is data[0] or f is data[-1]:
                        replay=learn.replay_frame(learner.net,f);L.need(replay['argmax']==f['index'],'argmax')
                        L.need(abs(replay['logprob']-f['old_logp'])<1e-6 and np.allclose(replay['critic'],f['value'],rtol=1e-5,atol=1e-6),'logprob/critic');replays+=1
                    chain.update((f['input_sha']+':'+str(f['index'])).encode());frames+=1
                largest=max(largest,len(data));del data
            L.need(frames==r['NN']['frames'] and chain.hexdigest()==r['NN']['chain'],'all frame chain')
            report.append(dict(n=c['n'],saved_frames=frames,all_input_mask_RNG='PASS',independent_network_replays=replays,chain=chain.hexdigest()))
            total+=frames;checked+=replays;print('AUDIT',c['n'],frames,'frames',replays,'NN replays',flush=True)
    L.need(learn.network_digest(learner.net)==net,'network unchanged')
    for p in op['pins']:L.pin(p)
    L.write_new(out/'NN_SAVED_AUDIT.json',dict(status='PASS',all_saved_frames=total,independent_network_replays=checked,
        during_execution_network_replays='all saved frames',rows=report,NN_training=0,new_environment_START=0,wall_seconds=time.monotonic()-began))

if __name__=='__main__':main(sys.argv[1])
