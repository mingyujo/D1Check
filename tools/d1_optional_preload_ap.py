"""Explicit opt-in AP candidate interface. No simulator/RL defaults are changed."""
import copy
from tools import d1_preload_dynamics_refinement as d


def forecast(preload,segments,query_s,*,initializer):
    if initializer!='free-first-preload-v1':raise ValueError('explicit registered initializer required')
    if d.j.m.sha(d.j.m.MODEL)!=d.j.m.MODEL_SHA:raise ValueError('base model identity')
    model=d.j.m.read(d.j.m.MODEL)
    for s in segments:
        if d.j.h.state_key(s['state']) not in ('resident_idle',)+tuple(d.j.m.base.STATES):
            raise ValueError('unsupported candidate AP state')
    public=dict(preload=copy.deepcopy(preload),segments=copy.deepcopy(segments),query_s=list(query_s))
    initial=d.ap_initial(public['preload'],model)
    values=d.predict_ap(public,model,initial)
    return dict(version='ap-free-first-preload-initial-v1',ap_c=values,query_s=public['query_s'],initial=initial,
                base_model_sha256=d.j.m.MODEL_SHA,input_end_s=initial['input_end_s'],
                posthoc=True,development_gate_passed=False,default=False,strict_support=False,
                accuracy_pass=None,experiment_ready=False)
