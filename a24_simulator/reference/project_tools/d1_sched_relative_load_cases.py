"""Pure S26 relative-arrival-load matching; preserve landscape20 sources.

Only arrival timestamps change. The target is the corresponding A24 public
nominal load, not the realized hot-device utilization. Original TTLs, work,
request IDs, dynamics, outcome RNG and policy weights must remain unchanged.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math

VERSION='d1-sched-relative-load-cases-v1'
ANCHOR_NS=35_000_000_000
HORIZON_NS=120_000_000_000
PAIR_FIELDS=('task_mix','family','deadline_mode','arrival_seed','profile')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def pair_key(case):
    return tuple(case[key] for key in PAIR_FIELDS)


def validate_roster(case):
    requests=case['requests']
    if len(requests)!=64 or len({q['id'] for q in requests})!=64:
        raise ValueError('unchanged64-request bound')
    if digest(requests)!=case['request_sha256']:raise ValueError('source request SHA')
    for q in requests:
        if type(q['arrival_ns']) is not int or not 0<=q['arrival_ns']<HORIZON_NS:
            raise ValueError('arrival must be integer ns within120s')
        if type(q['work_units']) is not int or not 1<=q['work_units']<=3 or q['deadline_offset_ns']<=0:
            raise ValueError('known work or original relative deadline')
    if requests!=sorted(requests,key=lambda q:(q['arrival_ns'],q['ordinal'],q['id'])):
        raise ValueError('stable input order')


def build(old_cases):
    """Return after_cases96/new_cases/transformations96/metadata without IO."""
    if len(old_cases)!=96 or len({c['identity'] for c in old_cases})!=96:
        raise ValueError('landscape20 original96cases required')
    original_sha=digest(old_cases)
    index={}
    for original in old_cases:
        validate_roster(original)
        key=(original['device'],pair_key(original))
        if key in index:raise ValueError('duplicate device/correspondence key')
        index[key]=original
    if sum(c['device']=='A24' for c in old_cases)!=48 or sum(c['device']=='S26' for c in old_cases)!=48:
        raise ValueError('48original conditions per device')
    after=[];new=[];transformations=[]
    for original in old_cases:
        key=pair_key(original)
        reference=index.get(('A24',key))
        if reference is None:raise ValueError('missing A24 correspondence')
        target=float(reference['effective_nominal_load'])
        old_span=float(original['activity_span_s']);old_load=float(original['effective_nominal_load'])
        capacity_s=float(original['nominal_capacity']['capacity_ns'])/1e9
        if not all(math.isfinite(x) and x>0 for x in (target,old_span,old_load,capacity_s)):
            raise ValueError('finite positive nominal quantities')
        if not math.isclose(old_load,capacity_s/old_span,rel_tol=1e-12,abs_tol=1e-12):
            raise ValueError('source nominal load arithmetic')
        computed_span=capacity_s/target
        changed=original['device']=='S26' and not math.isclose(computed_span,old_span,rel_tol=1e-12,abs_tol=1e-10)
        new_span=computed_span if changed else old_span
        lineage=dict(before_identity=original['identity'],after_identity=original['identity']+('_RELLOAD21' if changed else ''),
            device=original['device'],task_mix=original['task_mix'],family=original['family'],
            deadline_mode=original['deadline_mode'],arrival_seed=original['arrival_seed'],profile=original['profile'],
            reference_A24_identity=reference['identity'],before_request_sha256=original['request_sha256'],
            old_span_s=old_span,old_effective_nominal_load=old_load,target_A24_effective_nominal_load=target,
            new_span_s=new_span,new_effective_nominal_load=capacity_s/new_span,
            ratio=new_span/old_span,changed_arrival=changed,reuse_old_environment=not changed,
            matching_scope='current-neutral public nominal capacity only; actual thermal/parallel utilization not equalized')
        case=copy.deepcopy(original)
        if changed:
            by_id={q['id']:q for q in original['requests']}
            for q in case['requests']:
                q['arrival_ns']=ANCHOR_NS+round((q['arrival_ns']-ANCHOR_NS)*new_span/old_span)
                before=by_id[q['id']]
                if {k:v for k,v in q.items() if k!='arrival_ns'}!={k:v for k,v in before.items() if k!='arrival_ns'}:
                    raise AssertionError('changed a nonarrival request field')
            case['requests'].sort(key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']))
            case.update(identity=lineage['after_identity'],activity_span_s=new_span,
                effective_nominal_load=capacity_s/new_span,target_nominal_load=target,
                request_sha256=digest(case['requests']),relative_load_lineage=copy.deepcopy(lineage),
                original_landscape_case_identity=original['identity'],relative_load_version=VERSION)
            case['assumptions']=list(original.get('assumptions',[]))+[
                'S26 arrival offsets from35s rescaled to matching A24 nominal load; no new work or policy parameters',
                'original relative TTL unchanged; absolute deadline follows the shifted arrival',
                'same original environment seed and per-request latent draw keys; no fresh random resampling',
                'remove steady30s/burst8s floors only when nominal target requires it; no outcome-driven retuning']
            lineage['after_request_sha256']=case['request_sha256']
            case['relative_load_lineage']['after_request_sha256']=case['request_sha256']
            validate_roster(case)
            new.append(case)
        else:
            if case!=original:raise AssertionError('unchanged case must remain exactly reusable')
            lineage['after_request_sha256']=original['request_sha256']
        after.append(case);transformations.append(lineage)
    if digest(old_cases)!=original_sha:raise AssertionError('source cases mutated')
    if len({c['identity'] for c in after})!=96:raise AssertionError('after-case identity collision')
    # Every profile receives the same changed stream, and original/varied only
    # differ in their pre-existing TTLs. No profile-specific arrival tuning.
    groups={};deadline_pairs={}
    for case in after:
        key=(case['device'],case['task_mix'],case['family'],case['deadline_mode'],case['arrival_seed'])
        groups.setdefault(key,set()).add(case['request_sha256'])
        ddlkey=(case['device'],case['task_mix'],case['family'],case['arrival_seed'],case['profile'])
        deadline_pairs.setdefault(ddlkey,{})[case['deadline_mode']]=case['requests']
    if any(len(v)!=1 for v in groups.values()):raise AssertionError('profile-dependent transformed requests')
    for pair in deadline_pairs.values():
        strip=lambda rows:[{k:v for k,v in q.items() if k!='deadline_offset_ns'} for q in rows]
        if strip(pair['original'])!=strip(pair['varied']):raise AssertionError('TTL condition changed work/arrival')
    changed_by_seed={str(seed):sum(c['arrival_seed']==seed for c in new) for seed in sorted({c['arrival_seed'] for c in old_cases})}
    return dict(after_cases=after,new_cases=new,transformations=transformations,
        metadata=dict(task='D1-SCHED-RELLOAD-21',version=VERSION,source_cases_sha256=original_sha,
            after_cases=96,changed_cases=len(new),unchanged_cases=96-len(new),A24_cases_reused=48,
            changed_cases_by_seed=changed_by_seed,new_environments_planned=len(new)*7,
            reused_environments_planned=(96-len(new))*7,after_logical_role_views=96*7,
            before_environments_reused=96*7,new_environment_executed=0,new_learning=0,new_fit=0,
            profiles_changed=False,weights_changed=False,latent_outcome_rng_changed=False,
            matching_scope='A24 current-neutral nominal accelerator-capacity target; not equal actual hot-device load',
            absolute_deadline='newarrival + unchanged original TTL; original1.5/6 failure separately retained'))
