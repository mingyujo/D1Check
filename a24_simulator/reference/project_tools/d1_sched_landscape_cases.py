"""Landscape20 hypotheses and policy-neutral copied requests; no environment.

Current neutral/strong copy contrast18. The third level deliberately widens
fast-versus-efficient-route tradeoffs using hypothetical EXECUTING power and
thermal/recent-load costs. All measured cost anchors and source files remain
unchanged. Values below are demonstration assumptions, never phone estimates.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math

PROFILE_ABI='d1-sched-landscape-profile-v1'
CASE_VERSION='d1-sched-landscape-cases-v1'
LEVELS=('current_neutral','current_strong','execution_tradeoff')
DEVICES=('A24','S26')
TASK_MIXES=('balanced','classification_heavy')
ARRIVALS=('steady','bursty')
DEADLINE_MODES=('original','varied')
ARRIVAL_SEEDS=(917400101,917400102)
ORIGINAL_NS=dict(urgent=1_500_000_000,normal=6_000_000_000)
VARIED_NS=dict(urgent=(800_000_000,1_500_000_000,2_500_000_000),
    normal=(3_000_000_000,6_000_000_000,9_000_000_000))
BACKENDS=('CPU','GPU','NPU')
DETECTION_EXECUTION_SCALE=.35


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def keyed(seed,rid,label):
    return int.from_bytes(hashlib.sha256(f'{CASE_VERSION}/{seed}/{rid}/{label}'.encode()).digest()[:8],'big')


def service_means(profile):
    """Training/public nominal means, not confirmation draws or private work."""
    out={}
    for key,ds in profile['service_anchor']['means'].items():
        parts=key.split('|');task,backend=parts[-2:]
        if len(parts)==2 or parts[0]=='CPU_URGENT' or task=='classification':
            out[task+'_'+backend]=list(ds)
    return out


def _shorten_detection(profile,neutral):
    service=profile['service_anchor'];nominal=neutral['service_anchor']
    previous=copy.deepcopy(service)
    if 'contrast_service_transform' in service:
        service['landscape_parent_contrast_service_transform']=service.pop('contrast_service_transform')
    for key,ds in service['means'].items():
        if key.split('|')[-2]!='detection':continue
        ds[1]=nominal['means'][key][1]*DETECTION_EXECUTION_SCALE
    for split,pools in service['pools'].items():
        for key,rows in pools.items():
            if key.split('|')[-2]!='detection':continue
            base_rows=nominal['pools'][split][key]
            if len(base_rows)!=len(rows):raise ValueError('unchanged intact-vector roster')
            for row,base in zip(rows,base_rows):
                row['landscape_parent_durations_ns']=list(row['durations_ns'])
                row['landscape_nominal_durations_ns']=list(base['durations_ns'])
                row['durations_ns'][1]=round(base['durations_ns'][1]*DETECTION_EXECUTION_SCALE)
                row.pop('contrast_execution_scale',None)
                row['landscape_execution_scale_vs_neutral']=DETECTION_EXECUTION_SCALE
                row['landscape_evidence']='hypothetical copied execution interval; not a new measured sample'
    changed_means={key:dict(nominal_phase_means_ns=nominal['means'][key],
        parent_strong_phase_means_ns=previous['means'][key],copied_phase_means_ns=service['means'][key])
        for key in service['means'] if key.split('|')[-2]=='detection'}
    service['landscape_service_transform']=dict(parent_service_sha256=digest(previous),
        nominal_service_sha256=digest(nominal),detection_execution_scale_vs_neutral=DETECTION_EXECUTION_SCALE,
        other_phase_scale=1.,classification='same copied strong anchor',changed_means=changed_means,
        evidence='demonstration assumption; original measurements unchanged',
        reason='max4 slowdown would make a long A24 CPU task backlog dominate every case; .35x dispatch work preserves a chance to finish before120s')


def make_profiles(base_profiles):
    """Return device -> three levels; source is contrast18 profile dictionary."""
    if set(base_profiles)!=set(DEVICES):raise ValueError('separate A24 and S26 profiles')
    result={}
    for device in DEVICES:
        group=base_profiles[device];neutral=group['neutral'];strong=group['strong_coupled']
        for base in (neutral,strong):
            if base['device']!=device or base['abi']!='d1-sched-dynamics-profile-v1':raise ValueError('parent profile ABI')
            if base['hardware_validated'] is not False or base['experiment_ready'] is not False:raise ValueError('no hardware promotion')
        if neutral['cost_anchor']!=strong['cost_anchor']:raise ValueError('same immutable measured cost anchor')
        result[device]={}
        for level in LEVELS:
            parent=neutral if level=='current_neutral' else strong
            profile=copy.deepcopy(parent)
            profile.update(abi=PROFILE_ABI,name=level,active_route_extra_w=dict.fromkeys(BACKENDS,0.))
            profile['landscape']=dict(task='D1-SCHED-LANDSCAPE-20',level=level,
                parent_profile_name=parent['name'],parent_profile_sha256=digest(parent),
                parent_cost_anchor_sha256=digest(parent['cost_anchor']),parent_service_sha256=digest(parent['service_anchor']),
                evidence='hypothesis_only',hardware_validated=False,policy_specific_parameters=False,
                changes_cost_anchor=False,changes_initial_heat_or_baseline=False,
                initial_state='same default boundary supplied to every level; not chosen from policy results')
            if level=='execution_tradeoff':
                _shorten_detection(profile,neutral)
                profile.update(active_route_extra_w=dict(CPU=8.,GPU=1.,NPU=.4),
                    extra_heat_gain_c_per_w=3.,extra_heat_beta_per_s=.05,
                    max_slowdown=4.,recent_slowdown=dict(CPU=2.,GPU=.2,NPU=.08),
                    switch_s_by_backend=dict(CPU=.15),switch_j_by_backend=dict(CPU=.8))
                profile['landscape'].update(
                    active_power_applies_to='actual EXECUTING only; zero during callbacks/reservation/idle',
                    heat_coupling='same hypothetical additionalW drives addedAP, then subsequent execution speed; tau20s',
                    task_switch='CPU task-type change only; other backends use unchanged strong scalar fallback',
                    detection_execution_scale_vs_neutral=DETECTION_EXECUTION_SCALE,
                    classification_service='same strong copied service vectors',
                    purpose='CPU initially fast but active power, recent-load slowdown and task switching cost more; GPU/NPU slower but cheaper; scheduling chooses the tradeoff',
                    initial_values=dict(active_w=dict(CPU=8.,GPU=1.,NPU=.4),gain_c_per_w=3.,beta_per_s=.05,max_slowdown=4.),
                    evidence_note='new power/rates/work scaling are explicitly artificial; not fitted to A24/S26 hardware')
            else:
                if profile['service_anchor']!=parent['service_anchor']:raise AssertionError('unchanged current service copy')
                profile['landscape']['purpose']='unchanged current contrast control; active-route extraW zero'
            if profile['cost_anchor']!=parent['cost_anchor']:raise AssertionError('measured cost anchor modified')
            profile['assumption_note']='Policy-contrast demonstration with shared hypothetical levels; no new measurement, no policy winner assumed, no weights updated.'
            result[device][level]=profile
    return result


def scaled_occupancy(ds,units):
    if len(ds)!=5 or any(not math.isfinite(x) or x<0 for x in ds) or sum(ds)<=0:raise ValueError('public5phase means')
    return sum(ds)+(units-1)*ds[1]


def nominal_capacity(means,requests):
    cpu=0.;accelerators=dict(GPU=0.,NPU=0.)
    for q in requests:
        if q['task']=='detection':cpu+=scaled_occupancy(means['detection_CPU'],q['work_units'])
        else:
            paths=[b for b in accelerators if 'classification_'+b in means]
            if not paths:cpu+=scaled_occupancy(means['classification_CPU'],q['work_units'])
            else:
                b=min(paths,key=lambda b:(scaled_occupancy(means['classification_'+b],q['work_units']),BACKENDS.index(b)))
                accelerators[b]+=scaled_occupancy(means['classification_'+b],q['work_units'])
    return dict(cpu_ns=cpu,accelerator_ns=accelerators,capacity_ns=max(cpu,*accelerators.values()))


def base_case(device,task_mix,arrival_mode,deadline_mode,arrival_seed,nominal_means):
    if device not in DEVICES or task_mix not in TASK_MIXES or arrival_mode not in ARRIVALS or deadline_mode not in DEADLINE_MODES:
        raise ValueError('landscape case factors')
    if arrival_seed not in ARRIVAL_SEEDS:raise ValueError('two frozen landscape arrival seeds')
    c_count=32 if task_mix=='balanced' else 48
    permutation=sorted(range(64),key=lambda i:keyed(arrival_seed,str(i),'task-permutation'))
    c_slots=set(permutation[:c_count]);requests=[]
    for ordinal in range(64):
        rid=f'L20-{arrival_seed}-{task_mix}-{arrival_mode}-{ordinal:03d}'
        task='classification' if ordinal in c_slots else 'detection'
        priority='urgent' if task=='classification' else 'normal'
        units=1+keyed(arrival_seed,rid,'public-work-units')%3
        deadline=ORIGINAL_NS[priority] if deadline_mode=='original' else VARIED_NS[priority][keyed(arrival_seed,rid,'declared-deadline')%3]
        requests.append(dict(id=rid,ordinal=ordinal,task=task,priority=priority,arrival_ns=0,
            deadline_offset_ns=deadline,work_units=units))
    capacity=nominal_capacity(nominal_means,requests)
    target=.7 if arrival_mode=='steady' else 1.1
    # The30s steady floor deliberately preserves a sparse, under-capacity
    # region for faster devices; it is applied before seeing policy results.
    span=min(60.,max(30. if arrival_mode=='steady' else 8.,capacity['capacity_ns']/1e9/target))
    for q in requests:
        if arrival_mode=='steady':
            jitter=(keyed(arrival_seed,q['id'],'arrival-jitter')%1_000_001/1e6-.5)*.2
            position=max(0.,min(span,(q['ordinal']+jitter)*span/63.))
        else:
            position=(q['ordinal']//16)/4.*span
        q['arrival_ns']=round((35.+position)*1e9)
    requests.sort(key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']))
    identity=f'{device}_{task_mix}_{arrival_mode}_{deadline_mode}_{arrival_seed}'
    return dict(version=CASE_VERSION,device=device,task_mix=task_mix,arrival_mode=arrival_mode,
        family=arrival_mode,deadline_mode=deadline_mode,arrival_seed=arrival_seed,split='exploratory',
        identity=identity,requests=requests,request_sha256=digest(requests),activity_span_s=span,
        nominal_public_mean_sha256=digest(nominal_means),nominal_capacity=capacity,
        target_nominal_load=target,effective_nominal_load=capacity['capacity_ns']/1e9/span,
        planned_classification=c_count,planned_detection=64-c_count,
        horizon_ns=120_000_000_000,cooling_end_ns=180_000_000_000,
        assumptions=['task/units/deadline/arrival from independent keyed labels; no outcome-dependent resampling',
            'classification urgent/detection normal existing task-priority mapping',
            'known units1..3 scale execution only; no measured batch efficiency',
            'activity density from current-neutral public nominal accelerator split, identical across levels',
            'steady30s minimum preserves sparse region; burst clusters of16 arrive together',
            'varied U.8/1.5/2.5s and N3/6/9s; original U1.5/N6 failure also reported',
            'all64requests retained; unfinished/null retained; this is hypothetical exploration'])


def make_cases(profile_grid):
    rows=[]
    for device in DEVICES:
        means=service_means(profile_grid[device]['current_neutral'])
        for task_mix in TASK_MIXES:
            for arrival in ARRIVALS:
                for deadline in DEADLINE_MODES:
                    for seed in ARRIVAL_SEEDS:
                        base=base_case(device,task_mix,arrival,deadline,seed,means)
                        for level in LEVELS:
                            case=copy.deepcopy(base);case.update(profile=level,level=level,
                                parent_request_case=base['identity'],identity=base['identity']+'_'+level)
                            rows.append(case)
    validate_cases(rows)
    return rows


def validate_cases(rows):
    if len(rows)!=96 or len({c['identity'] for c in rows})!=96:raise ValueError('32request streams x3levels')
    groups={};deadline_pairs={}
    for c in rows:
        qs=c['requests']
        if len(qs)!=64 or len({q['id'] for q in qs})!=64 or digest(qs)!=c['request_sha256']:raise ValueError('fixed64 roster/hash')
        for q in qs:
            if not 35e9<=q['arrival_ns']<=95e9 or type(q['work_units']) is not int or not 1<=q['work_units']<=3:
                raise ValueError('bounded arrival and known work')
        groups.setdefault(c['parent_request_case'],set()).add(c['request_sha256'])
        key=(c['device'],c['task_mix'],c['arrival_mode'],c['arrival_seed'],c['level'])
        deadline_pairs.setdefault(key,{})[c['deadline_mode']]=qs
    if len(groups)!=32 or any(len(v)!=1 for v in groups.values()):raise ValueError('level changes policy input stream')
    for pair in deadline_pairs.values():
        strip=lambda qs:[{k:v for k,v in q.items() if k!='deadline_offset_ns'} for q in qs]
        if strip(pair['original'])!=strip(pair['varied']):raise ValueError('deadline condition changes arrival/work')
    return True


def build(base_profiles):
    """Pure API: {'profiles':device->level, 'cases':96, 'metadata':...}."""
    before=digest(base_profiles);profiles=make_profiles(base_profiles);cases=make_cases(profiles)
    if digest(base_profiles)!=before:raise AssertionError('parent dictionary mutated')
    return dict(profiles=profiles,cases=cases,metadata=dict(task='D1-SCHED-LANDSCAPE-20',
        profile_abi=PROFILE_ABI,levels=list(LEVELS),arrival_seeds=list(ARRIVAL_SEEDS),
        base_profile_sha256=before,request_streams=32,cases=96,request_bound=64,
        policy_environments_planned=672,new_environment_executed=0,new_learning=0,new_fit=0,
        demonstration_only=True,measured_cost_anchor_changed=False,initial_heat_or_baseline_changed=False,
        policy_specific_input=False,no_winner_assumed=True))
