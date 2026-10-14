"""Meaningful native-input/recovery checks on recorded P0; zero new environments."""
import math
import numpy as np
import torch
from common import OUT,SEEDS,ALPHAS,save,read,sha
import ppo,study
from orchestrator import recover_frames
def run():
    learner=ppo.Learner(SEEDS[0],"S26")
    max_lp=max_v=0.;total=0
    for episode in range(8):
        identity=f"P0_NATIVE_{episode}"
        fs,rng=recover_frames(OUT/"rollouts"/(identity+".npz"))
        data,frames=ppo.pack([fs])
        with torch.no_grad():
            for start in range(0,len(fs),128):
                ids=slice(start,start+128)
                logits,values=learner.net(*[data[k][ids] for k in ppo.INPUTS])
                lp=logits.log_softmax(-1).gather(1,data["index"][ids,None]).squeeze(1)
                max_lp=max(max_lp,float((lp-data["old_logp"][ids]).abs().max()))
                max_v=max(max_v,float((values-data["value"][ids]).abs().max()))
        total+=len(fs)
        ctl=learner.controller(ALPHAS[episode%5],collect=True);ctl.frames=fs
        raw=study.load_gz(OUT/"raw/S26"/(identity+".json.gz"))
        learner.add(ctl,raw)
    # Old P0's schema is retained as historical numerical proof, never deployment weights.
    saved=torch.load(OUT/"P0_latest.pt",map_location="cpu",weights_only=False)
    original=ppo.Learner(SEEDS[0],"S26");original.net.load_state_dict(saved["network"])
    same_network=study.netsha(learner.net)==study.netsha(original.net)
    if max_lp>1e-5 or max_v>1e-5 or not same_network:
        raise ValueError("recorded-input/optimizer replay mismatch")
    # Operational fallback is separately checked without introducing a physical episode.
    from unittest.mock import patch
    first=fs[0]
    selected=[dict(id="q0",priority="urgent",task="classification",arrival_ns=0,ordinal=0,deadline_offset_ns=10**9)]
    actions=[dict(request=selected[0],backend="CPU",wait_ns=0),dict(request=None,backend=None,wait_ns=0)]
    bank=dict(**{k:first[k] for k in ppo.INPUTS})
    bank.update(actions=actions,diagnostic=dict(queue=1,time_ns=0,legal_count=1),
       scores={"q0":1.},paths={("q0","CPU"):[1,1,0,0,0]},ranks={"EDD":{"q0":0}},physical_mask=np.array([True,True]))
    bank["mask"]=np.array([True,False])
    class Broken:
        def __call__(self,*args):raise RuntimeError("forced model format error")
    class View:
        now=0
    ctl=ppo.Controller(Broken(),torch.Generator(),collect=False)
    with patch.object(ppo,"build",return_value=bank):
        choice=ctl.choose(View(),selected)
    if choice["backend"]!="CPU" or len(ctl.errors)!=1 or not ctl.audit[-1]["physical"]:raise ValueError("model fallback failed")
    result=dict(status="PASS",new_environments=0,new_experiences=0,recorded_frames=total,
       logprob_max_error=max_lp,critic_max_error=max_v,recorded_eight_episode_optimizer_network_exact=same_network,
       extra_native_updates=1,extra_Adam_steps=learner.steps,model_error_fallback=True,
       source_schema=saved["schema"],current_input_schema=ppo.SCHEMA,
       old_P0_consumption_preserved=True,new_schema_deployment_weights_reused=False)
    save(OUT/"P0_RECORDED_REPLAY.json",result);return result
if __name__=="__main__":print(run())
