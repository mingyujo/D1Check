"""Replay saved public selectors with the exact original NumPy source; no NN."""
import gc,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'deep_repair_20261018'))
from common import B,ROOT,read,np,selector
from resources import inspect

def main():
    guard=inspect(Path(__file__),1024**3);B.G.free_guard([ROOT,'D:/'])
    out=ROOT/'results/DEEP_REPAIR_20261018_01';op=read(HERE/'OPERATION.json')
    for p in op['sources']:B.G.pin(p)
    result=read(out/'RESULT.json');frames=episodes=0;rows=[]
    for row in result['rows']:
        if not row['selector_kind']:continue
        raw=out/(row['label']+'.raw.json.gz');assert B.G.sha(raw)==row['raw_sha256']
        calls=read(raw)['calls'];n=0
        for call in calls:
            if call.get('common_coalescing'):continue
            bank=dict(x=np.asarray(call['x'],np.float32),mask=np.asarray(call['mask'],bool),scores=np.asarray(call['forecast_scores'],np.float32))
            assert selector(bank,row['selector_kind'])==call['chosen'],('Original selector replay',row['label'],call['time_ns'])
            n+=1
        frames+=n;episodes+=1;rows.append(dict(label=row['label'],frames=n,raw_sha256=row['raw_sha256']))
        del calls;gc.collect()
        if episodes%16==0:print('PUBLIC_SELECTOR_REPLAY',episodes,frames,flush=True)
    assert episodes==152
    B.G.write_new(out/'PUBLIC_SELECTOR_REPLAY.json',dict(status='PASS',NumPy_version=np.__version__,public_episodes=episodes,exact_original_public_choices=frames,records=rows,guard=guard,new_environment_START=0,new_NN_forward=0,new_optimizer_steps=0,new_training_data=0))
    print('ORIGINAL_NUMPY_PUBLIC_REPLAY_PASS',episodes,frames,flush=True)
if __name__=='__main__':main()
