"""M6 development-calibrated causal residual-heat boundary, no future samples."""
import copy
import math
import numpy as np
from tools import d1_s26_pair_observer_model as parent

VERSION='s26-m6-causal-slope-boundary-v1'

def apply_rule(initial, past_slopes, rule):
    result=copy.deepcopy(initial)
    for sensor in ('AP','SKIN'):
        setting=rule[sensor]
        if setting.get('mode')=='development_equilibrium':
            reference=setting['reference_c']
            if not math.isfinite(reference) or not 15<=reference<=45 or setting['beta_per_s'] not in (.03,.06,.12,.25):
                raise ValueError('M6 frozen equilibrium parameters')
            result['reference_c'][sensor]=reference
            continue
        if not math.isfinite(past_slopes[sensor]) or not 0<=setting['gain']<=3 or setting['beta_per_s'] not in (.03,.06,.12,.25):
            raise ValueError('M6 causal boundary parameters')
        delta=float(np.clip(setting['gain']*past_slopes[sensor]/setting['beta_per_s'],-8,8))
        result['reference_c'][sensor]=result['initial_c'][sensor]+delta
    result['evidence']='completed_past_measurements_M6_development_boundary_rule'
    return result

def from_observations(power,thermal,rule):
    # The caller supplies read-completed times, not future interpolation endpoints.
    initial=parent.causal_boundary(power,thermal,0,'START0')
    slopes={}
    for sensor in ('AP','SKIN'):
        rows=np.asarray([r for r in thermal[sensor] if -20<=r[0]<=0],float)
        if len(rows)<3 or np.ptp(rows[:,0])<5:raise ValueError('M6 past thermal coverage')
        slopes[sensor]=float(np.polyfit(rows[:,0],rows[:,1],1)[0])
    return apply_rule(initial,slopes,rule)
