"""Policy-neutral V17 arrival/work grid, keyed independently of physical RNG.

Units scale execution only. Device-normalized active windows are synthetic
capacity stress conditions, not claims about a measured mobile use case.
"""
from __future__ import annotations
import hashlib
import json

VERSION='d1-scheduling-dynamics-cases-v17'
FAMILIES=('low','steady','burst','mixed')
DEADLINE_MODES=('original','declared')
SPLIT_SEEDS=dict(train=tuple(range(917100100,917100228)),
    dev=(917200101,917200102), final=(917300101,917300102))
ORIGINAL_NS=dict(urgent=1_500_000_000,normal=6_000_000_000)
DECLARED_NS=dict(urgent=(800_000_000,1_500_000_000,2_500_000_000),
    normal=(3_000_000_000,6_000_000_000,9_000_000_000))
LOAD_TARGETS=dict(low=.2,steady=.7,burst=.9,mixed=1.05)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def keyed(seed,rid,label):
    return int.from_bytes(hashlib.sha256(f'{VERSION}/{seed}/{rid}/{label}'.encode()).digest()[:8],'big')


def scaled_mean(ds,units):
    if len(ds)!=5 or min(ds)<0 or sum(ds)<=0:
        raise ValueError('fivephase public means')
    return sum(ds)+(units-1)*ds[1]


def reference_demand(service_means,requests):
    # A fixed policy-neutral split uses the fastest nominal accelerator for C
    # and CPU for D; occupancy includes the actualAVAILABLE tail.
    cpu=0.;accelerators={b:0. for b in ('GPU','NPU')}
    for q in requests:
        if q['task']=='detection':
            cpu+=scaled_mean(service_means['detection_CPU'],q['work_units'])
        else:
            routes=[b for b in accelerators if 'classification_'+b in service_means]
            if not routes:
                cpu+=scaled_mean(service_means['classification_CPU'],q['work_units'])
            else:
                b=min(routes,key=lambda b:(scaled_mean(service_means['classification_'+b],q['work_units']),b))
                accelerators[b]+=scaled_mean(service_means['classification_'+b],q['work_units'])
    return dict(cpu_ns=cpu,accelerator_ns=accelerators,capacity_ns=max(cpu,*accelerators.values()))


def make_case(device,split,arrival_seed,family,deadline_mode,service_means):
    if device not in ('A24','S26') or split not in SPLIT_SEEDS or family not in FAMILIES or deadline_mode not in DEADLINE_MODES:
        raise ValueError('unregistered case factor')
    if arrival_seed not in SPLIT_SEEDS[split]:
        raise ValueError('arrival split leakage')
    n=32 if family=='low' else 64
    requests=[]
    # Balanced task roster is permuted with arrival RNG. Deadline and units use
    # different keyed labels; no outcome-dependent tuning or resampling.
    tasks=sorted(range(n),key=lambda j:keyed(arrival_seed,str(j),'task-permutation'))
    classification=set(tasks[:n//2])
    for i in range(n):
        rid=f'{family}-{arrival_seed}-{i:03d}'
        task='classification' if i in classification else 'detection'
        priority='urgent' if task=='classification' else 'normal'
        units=1+(keyed(arrival_seed,rid,'known-work-units')%3) if family=='mixed' else 1
        deadline=ORIGINAL_NS[priority] if deadline_mode=='original' else DECLARED_NS[priority][keyed(arrival_seed,rid,'declared-deadline')%3]
        requests.append(dict(id=rid,ordinal=i,task=task,priority=priority,arrival_ns=0,
            deadline_offset_ns=deadline,work_units=units))
    demand=reference_demand(service_means,requests)
    minimum=15. if family=='low' else 4.
    span=min(70.,max(minimum,demand['capacity_ns']/1e9/LOAD_TARGETS[family]))
    for i,q in enumerate(requests):
        if family=='burst':
            cluster=i//16
            local=(keyed(arrival_seed,q['id'],'burst-arrival')%1_000_001)/1e6
            position=(cluster/4.+local*.04)*span
        elif family=='mixed':
            # Paired short/long work arrives at the same publicly known burst
            # boundaries; units assignment is independent of boundary index.
            cluster=i//8
            local=(keyed(arrival_seed,q['id'],'mixed-arrival')%1_000_001)/1e6
            position=(cluster/8.+local*.04)*span
        else:
            jitter=((keyed(arrival_seed,q['id'],'smooth-arrival')%1_000_001)/1e6-.5)*.35
            position=max(0.,min(span,(i+jitter)*span/max(n-1,1)))
        q['arrival_ns']=round((35.+position)*1e9)
    requests.sort(key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']))
    if len(requests)>64 or min(q['arrival_ns'] for q in requests)<35e9 or max(q['arrival_ns'] for q in requests)>105e9:
        raise AssertionError('bounded input window')
    return dict(version=VERSION,device=device,split=split,arrival_seed=arrival_seed,family=family,
        deadline_mode=deadline_mode,requests=requests,request_sha256=digest(requests),
        public_service_mean_sha256=digest(service_means),activity_span_s=span,
        reference_demand=demand,target_nominal_load=LOAD_TARGETS[family],
        assumptions=['device-normalized synthetic activity window; no measured arrival claim',
            'classification urgent/detection normal existing task-priority mapping',
            'work_units 1..3 scales execution only; no fitted batching efficiency',
            'units/deadline/arrival independent keyed labels; no favorable correlation search'],
        horizon_ns=120_000_000_000,cooling_end_ns=180_000_000_000)


def grid(device,split,service_means,seeds=None):
    return [make_case(device,split,seed,family,deadline_mode,service_means)
        for seed in (SPLIT_SEEDS[split] if seeds is None else seeds)
        for family in FAMILIES for deadline_mode in DEADLINE_MODES]
