"""Blind-input forecast API: fixed service, no measured future targets or schedule."""
import copy
import math
from tools import d1_simulation_model_v2 as v2
from tools import d1_simulation_model_v3 as model
from tools import d1_simulation_model_v3_thermal as thermal
from tools import d1_simulation_model_v3_energy as energy

ALLOWED={'id','role','source_group','pre','pre_w','initial_power_late_w','history','q'}


def forecast(public,requests,policy,candidate,original,shape_role='confirmation'):
    if set(public)-ALLOWED:raise ValueError('unregistered public fields: measured future or schedule is forbidden')
    if candidate['version']!=model.VERSION or candidate['original_model']['sha256']!=v2.prior.MODEL_SHA:
        raise ValueError('candidate/original identity')
    if policy not in ('CPU_URGENT_ONLINE_V1','B2_PARALLEL_ONLINE_V1'):raise ValueError('unverified policy context')
    if any(r['hi']>=35 for r in public['pre']):raise ValueError('future initial AP')
    history=public.get('history',[])
    if history and history[-1]['end_s']>0:raise ValueError('history overlaps future target schedule')
    q=public['q']
    if not q or any(not math.isfinite(t) or t<35 for t in q) or any(b<=a for a,b in zip(q,q[1:])):
        raise ValueError('evaluation query grid')
    initial=dict(preload=copy.deepcopy(public['pre']),preload_power_w=public['pre_w'])
    legacy,segments=v2.prior.base.forecast(initial,copy.deepcopy(requests),policy,original,planning_input_role=shape_role)
    end=max(180.,q[-1]);segments=copy.deepcopy(segments)
    if segments[-1]['end_s']<end:segments.append(dict(start_s=segments[-1]['end_s'],end_s=end,state='idle'))
    scoped=dict(copy.deepcopy(public),actual=segments)
    values,state=thermal.predict(scoped,candidate['thermal'],original)
    safe={k:scoped[k] for k in ('pre_w','initial_power_late_w','actual') if k in scoped}
    old=v2.prior.base.costs(segments,initial,q,original,end)
    return dict(version=model.VERSION,scope='planned manifest -> frozen original service -> corrected costs; future targets absent',
        legacy=legacy,segments=segments,query_s=list(q),predicted_AP_c=values,
        predicted_J120=energy.predict(safe,candidate['energy'],120.),
        original_AP_c=old['ap_path'],original_J120=old['whole_120s_j'],initial=state,
        inputs=copy.deepcopy(public),model_fit_at_prediction=False,experiment_ready=False)
