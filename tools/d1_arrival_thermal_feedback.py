"""Assumption-only online energy/AP policy for the existing arrival event engine.

The whole-device state coefficients are not A24 measurements. The policy sees
only arrived tickets, observable lane phases, frozen medians, and current AP.
"""
from __future__ import annotations

import math

from tools import d1_energy_thermal as thermal

POLICY = 'THERMAL_ENERGY_PC_V1'
VERSION = 'arrival-thermal-energy-explore-v1'
TASKS = ('classification', 'detection')
BACKENDS = ('CPU', 'GPU')
SINGLES = tuple(f'{task}:{backend}' for task in TASKS for backend in BACKENDS)
PAIRS = tuple('+'.join(sorted((f'{TASKS[0]}:{a}', f'{TASKS[1]}:{b}')))
              for a in BACKENDS for b in BACKENDS) + (
              'classification:CPU+classification:GPU',
              'detection:CPU+detection:GPU')
STATES = ('idle', *SINGLES, *PAIRS)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(model):
    require(model.get('version') == VERSION and model.get('evidence') == 'explicit_assumptions',
            'unsupported thermal model/version')
    require(model.get('device') == 'A24' and model.get('model') == 'efficientnet_lite0+efficientdet_lite0',
            'device/model support')
    require(math.isfinite(model['initial_ap_c']) and math.isfinite(model['ap_limit_c'])
            and math.isfinite(model['tau_s']) and model['tau_s'] > 0, 'AP inputs')
    require(0 < model['max_wait_ns'] <= 2_000_000_000 and 0 < model['wait_step_ns'] <= model['max_wait_ns'],
            'bounded wait')
    for mode in ('predicted', 'realized'):
        branch = model[mode]
        for key in ('power_w', 'ap_equilibrium_c'):
            require(set(branch[key]) == set(STATES), f'unsupported {mode} state coverage')
            require(all(isinstance(v, (int,float)) and math.isfinite(v) for v in branch[key].values()),
                    f'invalid {mode} {key}')
        require(all(v >= 0 for v in branch['power_w'].values()), 'negative whole-device power')
    return model


def state_for(lanes):
    active=[]
    for backend in BACKENDS:
        lane=lanes[backend]
        if lane is None:
            continue
        request=lane.get('request') if 'request' in lane else lane['ticket']
        if request is not None:
            active.append(f"{request['task']}:{backend}")
    state='+'.join(sorted(active)) or 'idle'
    require(state in STATES, f'unsupported joint state: {state}')
    return state


def state_from_ledger(label):
    if label == 'idle':
        return 'idle'
    state='+'.join(sorted(':'.join(member.split(':')[:2]) for member in label.split('+')))
    require(state in STATES, f'unsupported ledger state: {state}')
    return state


def seconds_above(start, equilibrium, tau, duration, limit):
    """Exact time above a user-specified research AP limit for one monotone step."""
    end=thermal.transition(start,equilibrium,tau,duration)
    if start == limit:
        return duration if end > limit else 0.
    if start > limit and end > limit:
        return duration
    if start <= limit and end <= limit:
        return 0.
    ratio=(limit-equilibrium)/(start-equilibrium)
    require(0 < ratio < 1, 'AP crossing outside transition')
    crossing=-tau*math.log(ratio)
    return crossing if start > limit else duration-crossing


def profile(model, which='realized'):
    validate(model)
    branch=model[which]
    return dict(version=thermal.VERSION,device=model['device'],model=model['model'],
                sensors=['AP'],evidence='explicit_assumptions',unit_status='unmeasured_stress_W',
                source=model.get('id'),states={state:dict(power_w=branch['power_w'][state],
                    thermal={'AP':dict(equilibrium_c=branch['ap_equilibrium_c'][state],
                                       tau_s=model['tau_s'])}) for state in STATES})


def account_result(result, model, horizon_ns):
    """Use the established common-window energy/thermal accountant."""
    require(horizon_ns == 120_000_000_000, 'fixed common window')
    segments=[dict(start_s=s['start_s'],end_s=s['end_s'],state=state_from_ledger(s['state']))
              for s in thermal.ledger_segments(result,horizon_ns)]
    done=sum(r['status']=='succeeded' for r in result['ledger'])
    accounting=thermal.account(segments,profile(model),device=model['device'],model=model['model'],
                               mode='assumption_exploration',initial_temperature={'AP':model['initial_ap_c']},
                               planned=len(result['ledger']),completed=done)
    temperature=model['initial_ap_c'];over=0.
    for s in segments:
        state=s['state'];duration=s['end_s']-s['start_s'];equilibrium=model['realized']['ap_equilibrium_c'][state]
        over+=seconds_above(temperature,equilibrium,model['tau_s'],duration,model['ap_limit_c'])
        temperature=thermal.transition(temperature,equilibrium,model['tau_s'],duration)
    require(math.isclose(temperature,accounting['temperature']['AP'],abs_tol=1e-7),
            'online/offline temperature mismatch')
    return dict(energy_j=accounting['energy_j'],ap_final_c=accounting['temperature']['AP'],
                ap_peak_c=accounting['peak_temperature']['AP'],
                ap_exceed_s=over,common_window_s=accounting['common_window_s'],
                evidence='PC schedule with unmeasured whole-device power and AP transition assumptions')


def predict_intervals(now, request, backend, lanes, config, settings, model, current_ap, wait_ns, horizon_ns):
    """Predict one arrived head ticket on a COMMON horizon for every action."""
    other='GPU' if backend=='CPU' else 'CPU'
    lane=lanes[other]
    other_task=None;other_remaining=0.
    if lane['request'] is not None:
        other_task=lane['request']['task']
        cell=config['cells'][f'{other_task}_{other}_{lane["request"]["priority"]}']
        other_remaining=cell['joint']['dispatch_to_lane_ns']['median_ns']*settings['estimate_factor']-(now-lane['dispatch'])
        if other_remaining <= 0:
            return None  # UNKNOWN_OVERRUN is not zero residual.
    cell=config['cells'][f"{request['task']}_{backend}_{request['priority']}"]
    overhead=settings['decision_ns']+settings['record_ns']+settings['dispatch_ns']
    start=overhead+wait_ns
    occupancy=cell['joint']['dispatch_to_lane_ns']['median_ns']*settings['estimate_factor']
    response=cell['joint']['dispatch_to_response_ns']['median_ns']*settings['estimate_factor']
    if other_task is not None and start < other_remaining:
        # Explicit approximation: the same frozen factor affects expected occupancy/response.
        occupancy*=settings['predicted_interference']
        response*=settings['predicted_interference']
    end=start+occupancy
    require(end <= horizon_ns and start+response <= horizon_ns, 'common prediction horizon too short')
    cuts=sorted({0.,float(horizon_ns),float(start),float(end),float(other_remaining)})
    power=model['predicted']['power_w'];equilibria=model['predicted']['ap_equilibrium_c']
    temp=current_ap;peak=temp;energy=0.
    for a,b in zip(cuts,cuts[1:]):
        if b<=a:continue
        mid=(a+b)/2
        members=[]
        if other_task is not None and mid<other_remaining:members.append(f'{other_task}:{other}')
        if start<=mid<end:members.append(f"{request['task']}:{backend}")
        state='+'.join(sorted(members)) or 'idle'
        if state not in power:
            return None
        dt=(b-a)/1e9
        energy+=power[state]*dt
        temp=thermal.transition(temp,equilibria[state],model['tau_s'],dt)
        peak=max(peak,temp)
    deadline=request['arrival_ns']+request['deadline_offset_ns']
    completion=now+start+response
    return dict(request_id=request['id'],backend=backend,wait_ns=wait_ns,
                predicted_response_ns=completion,predicted_energy_j=energy,
                predicted_ap_peak_c=peak,deadline_miss=completion>deadline,
                ap_violation=peak>model['ap_limit_c'],
                lateness_ns=max(0.,completion-deadline),
                ap_over_c=max(0.,peak-model['ap_limit_c']),
                prediction_horizon_ns=horizon_ns)


def choose(config, queue, lanes, now, settings, model, current_ap):
    validate(model)
    require(settings['mode']=='explore', 'unsupported strict thermal policy without measured costs')
    aging=settings['aging_ns']
    ordered=sorted(queue,key=lambda q:(0 if now-q['arrival_ns']>=aging else 1 if q['priority']=='urgent' else 2,
        q['arrival_ns'] if now-q['arrival_ns']>=aging else q['arrival_ns']+q['deadline_offset_ns'],q['ordinal'],q['id']))
    result=dict(now_ns=now,queue=ordered,lanes=lanes,current_ap_c=current_ap,
                candidates=[],selected=None,reason='empty' if not queue else 'busy_lanes')
    if not ordered:return result
    head=ordered[0]
    free=[b for b in BACKENDS if lanes[b]['request'] is None]
    step=model['wait_step_ns']
    if not free:
        # The real lane_available event, not a point estimate, wakes the engine.
        result.update(reason='busy_lanes')
        return result
    elapsed=now-head['arrival_ns']
    deadline=head['arrival_ns']+head['deadline_offset_ns']
    voluntary_wait=(elapsed<model['max_wait_ns'] and now<deadline)
    wait=min(step,model['max_wait_ns']-elapsed) if voluntary_wait else 0
    overhead=settings['decision_ns']+settings['record_ns']+settings['dispatch_ns']
    all_cells=[config['cells'][f"{head['task']}_{b}_{head['priority']}"] for b in BACKENDS]
    max_duration=max(max(c['joint']['dispatch_to_lane_ns']['median_ns'],
                         c['joint']['dispatch_to_response_ns']['median_ns']) for c in all_cells)
    max_other=max((config['cells'][f"{lanes[b]['request']['task']}_{b}_{lanes[b]['request']['priority']}"]
                   ['joint']['dispatch_to_lane_ns']['median_ns']*settings['estimate_factor']-(now-lanes[b]['dispatch'])
                   for b in BACKENDS if lanes[b]['request'] is not None),default=0.)
    horizon=max(8_000_000_000.,overhead+wait+max_duration*settings['estimate_factor']*
                max(1.,settings['predicted_interference']),max_other)
    require(horizon<=30_000_000_000, 'prediction horizon unsupported')
    for backend in free:
        for delay in (0.,float(wait)) if wait>0 else (0.,):
            item=predict_intervals(now,head,backend,lanes,config,settings,model,current_ap,delay,horizon)
            if item is not None:result['candidates'].append(item)
    if not result['candidates']:
        if elapsed>=model['max_wait_ns']:
            # Unknown residual is not zero. Preserve the unsupported forecast,
            # then dispatch the fastest standalone estimate to prevent starvation.
            winner=min(free,key=lambda b:(config['cells'][f"{head['task']}_{b}_{head['priority']}"]
                  ['joint']['dispatch_to_response_ns']['median_ns'],b!='CPU'))
            result.update(reason='fallback_unknown_overrun_unquantified_pair_cost',
                          selected=dict(request_id=head['id'],backend=winner),
                          prediction_unsupported='unknown busy-lane residual')
            return result
        result.update(reason='unknown_overrun_wait',wait_until_ns=now+step)
        return result
    candidates=result['candidates']
    feasible=[c for c in candidates if not c['deadline_miss'] and not c['ap_violation']]
    if feasible:
        winner=min(feasible,key=lambda c:(c['predicted_energy_j'],c['wait_ns']>0,c['backend']!='CPU'))
        reason='minimum_common_horizon_energy' if winner['wait_ns']==0 else 'wait_for_lower_predicted_energy_or_ap'
    else:
        # Never voluntarily wait when all actions are already predicted ineligible.
        immediate=[c for c in candidates if c['wait_ns']==0]
        winner=min(immediate,key=lambda c:(c['lateness_ns'],c['ap_over_c'],c['predicted_energy_j'],c['backend']!='CPU'))
        reason='fallback_predicted_deadline_or_ap_violation'
    result['chosen_prediction']=winner
    if winner['wait_ns']:
        result.update(reason=reason,wait_until_ns=now+winner['wait_ns'])
    else:
        result.update(reason=reason,selected=dict(request_id=head['id'],backend=winner['backend']))
    return result
