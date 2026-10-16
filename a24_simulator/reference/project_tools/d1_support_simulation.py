"""지원 한정 유한 배치 simulator. generate/validate/dry-run은 엔진을 호출하지 않는다."""
import argparse
import copy
import itertools
import math
from pathlib import Path

import jsonschema

from tools import d1_simulation_plan as base
from tools import d1_telemetry_v4 as v

VERSION = 'support-constrained-simulation-v1'
SEED = 2026092202
POLICIES = ['FIFO_CPU', 'URGENT_CPU', 'STATIC', 'ALWAYS_CORUN', 'ADAPTIVE_0', 'ADAPTIVE_HALF', 'ADAPTIVE_1']
EPS = {'ADAPTIVE_0': 0, 'ADAPTIVE_HALF': .5, 'ADAPTIVE_1': 1}
SCHEMA = Path(__file__).with_name('schemas')/'support-simulation-v1.schema.json'
SOURCE = Path('C:/Users/LG/Documents/D1Check_Bounded_Empirical_Run/run_20260921_atomic_v1')
FILES = {'plan.json', 'catalog.json', 'audit.json', 'registry.json'}


class OutOfSupport(ValueError):
    pass


def fail(reason):
    raise OutOfSupport('OUT_OF_SUPPORT: '+reason)


def quantile(values, q):
    if not values:
        return None
    values = sorted(values)
    rank = (len(values)-1)*q
    lo = math.floor(rank)
    return values[lo] + (values[math.ceil(rank)]-values[lo])*(rank-lo)


def key(*parts):
    return base.sha([VERSION, SEED, *parts])


def config():
    return dict(version=VERSION, seed=SEED,
        scope='A24/exact-input-APK-model/thermal0/resident/nonpreemptive',
        assumption='warm same-task/backend/state tuples exchangeable within whole session; no order-dependent penalty estimated',
        actions=['CPU_SOLO', 'GPU_SOLO', 'CPU_FIFO', 'CPU_URGENT', 'PAIRED_CORUN'],
        core='12 offset0 arrivals: alternating classification urgent/detection normal, six each',
        policies=POLICIES, adaptive_eps=EPS,
        static='taskwise minimum equal-session mean warm worker occupancy in solo; tie CPU; core requires both CPU',
        adaptive='pre-setup catalog expectation CPU_URGENT vs PAIRED_CORUN; epsilon feasibility then misses,P95,makespan,CPU tie',
        eps_rule='baseline CPU_URGENT; allowed loss=e*max(0,predicted_corun_loss) for makespan,throughput,normal_on_time',
        primary='scenario-wise Pareto on mean per-pair P95,miss,makespan,-throughput,-normal_on_time',
        tie='arrival,input ordinal,request_id; urgent EDF then normal FIFO; no RNG',
        deadline='soft; late success retained; no expiry cancellation; ceil frozen ns candidates',
        memory='original android-low-memory-resident-v1 before_workload gate; preflight rejection latches batch; core admits only',
        precision=dict(method='enumerate all 5 paired atoms; conditional empirical Monte Carlo error exactly zero',
                       replications=5, bootstrap='exact ordered 5^5=3125 pair draws; 95% percentile; no MC',
                       bootstrap_draws=3125, independent_device_pairs=5),
        sensitivity=['low','central','high','LOSO_0','LOSO_1','LOSO_2','LOSO_3','LOSO_4'],
        run_length=12, warmup=6, drain='all 12 terminals; no ongoing arrivals; finite measured durations',
        simulator_clock='integer ns; original dispatch gap + joint output/persist/release tuple; co-run entire trace',
        outcome='frontier and conditional epsilon choice; no universal winner or practical-utility threshold',
        safety='unsupported scenario invalidates run; never count it as fast rejection',
        simulation_execution_requires_separate_approval=True)


def extract(block):
    """원시 구간을 옮기는 입력 변환. 시간 진행/정책 실행/재표집 없음."""
    m, events = block['manifest'], block['events']
    start = v.exactly(events, 'workload_start')['mono_ns']
    end = v.exactly(events, 'workload_end')['mono_ns'] - start
    rows = []
    for i, q in enumerate(m['requests']):
        es = [e for e in events if e['request_id'] == q['request_id']]
        get = lambda name: v.exactly(es, name)['mono_ns'] - start
        spec = m['models'][q['model_key']]
        row = dict(ordinal=i, source_request=q['request_id'], task=spec['model']['task_id'],
                   priority=q['priority'], backend=spec['execution']['backend'], arrival=0,
                   dispatch=get('worker_dispatch'), ready=get('output_ready'),
                   persist=get('persist_complete') if q['priority']=='normal' else None, release=get('worker_release_end'))
        rows.append(row)
    chronological = sorted(rows, key=lambda r:r['dispatch'])
    previous = 0
    for row in chronological:
        row['gap'] = max(0,row['dispatch']-previous)
        previous = row['release']
    return dict(session_id=block['session_id'], rows=rows, end=end,
                tail=end-max(r['release'] for r in rows),
                footprint=block['receipt']['sampled_peak_pss_bytes'],
                setup=[s['setup_ns'] for s in block['receipt']['samples'] if s['runtime_state']['invocation']==1],
                memory=[e['data'] for e in events if e['event']=='memory_admission'],
                fingerprint=block['receipt']['trace_fingerprint'])


def catalog(source, audit):
    blocks = base.read(Path(source)/'simulation_input/joint_blocks.json')
    byid = {b['session_id']: b for b in blocks}
    pairs = []
    for pid, ids in sorted(audit['pairs'].items()):
        arms = {byid[s]['manifest']['paired']['arm']:extract(byid[s]) for s in ids}
        pairs.append(dict(pair_id=pid, **arms))
    solo = {}
    for b in blocks:
        if len(b['manifest']['runtimes']) == 1:
            e = extract(b)
            name = e['rows'][0]['task']+'/'+e['rows'][0]['backend']
            solo.setdefault(name, []).append(e)
    for group in solo.values():
        group.sort(key=lambda x:x['session_id'])
    return dict(pairs=pairs, solo=solo, input_sha256=base.INPUT_SHA)


def validate_catalog(c):
    if set(c) != {'pairs','solo','input_sha256'} or c['input_sha256'] != base.INPUT_SHA:
        fail('catalog identity')
    if len(c['pairs']) != 5 or len({p['pair_id'] for p in c['pairs']}) != 5:
        fail('five complete paired atoms required')
    if set(c['solo']) != {t+'/'+b for t in ('classification','detection') for b in ('CPU','GPU')}:
        fail('solo cells')
    episodes = [e for pair in c['pairs'] for e in (pair['A'],pair['B'])]
    for name, group in c['solo'].items():
        if len(group) != 5:
            fail('five solo sessions per cell')
        episodes.extend(group)
        for e in group:
            if len(e['rows']) != 6 or any(r['task']+'/'+r['backend']!=name or r['priority']!='normal' for r in e['rows']):
                fail('solo workload')
    for pair in c['pairs']:
        if set(pair) != {'pair_id','A','B'}:
            fail('pair structure')
        for arm in ('A','B'):
            rows=pair[arm]['rows']
            if len(rows)!=12:
                fail('pair count')
            for i,r in enumerate(rows):
                expected=('classification','urgent','CPU') if i%2==0 else ('detection','normal','CPU' if arm=='A' else 'GPU')
                if (r['task'],r['priority'],r['backend'])!=expected:
                    fail('pair task/priority/backend')
    if len({e['session_id'] for e in episodes})!=30 or len({e['fingerprint'] for e in episodes})!=30:
        fail('session/fingerprint replay')
    for e in episodes:
        if e['tail']<0 or e['end']!=max(r['release'] for r in e['rows'])+e['tail'] or not e['memory']:
            fail('episode boundaries')
        if len({r['source_request'] for r in e['rows']})!=len(e['rows']):
            fail('request replay')
        for i,r in enumerate(e['rows']):
            if r['ordinal']!=i or r['arrival']!=0:
                fail('order/staggered arrival')
            if any(type(r[k]) is not int for k in ('dispatch','ready','release','gap')):
                fail('integer clock')
            if not 0<=r['dispatch']<=r['ready']<=r['release']<=e['end'] or r['gap']<0:
                fail('joint timing')
            if r['priority']=='normal' and (type(r['persist']) is not int or not r['ready']<=r['persist']<=r['release']):
                fail('normal persistence')
            if r['priority']=='urgent' and r['persist'] is not None:
                fail('fabricated urgent persistence')
        for backend in ('CPU','GPU'):
            ordered=sorted([r for r in e['rows'] if r['backend']==backend],key=lambda r:r['dispatch'])
            if any(a['release']>b['dispatch'] for a,b in zip(ordered,ordered[1:])):
                fail('lane overlap')
        if not admitted(e):
            fail('empirical core contains unmeasured memory rejection')
    return True


def static_mapping(c):
    means = {k:sum(sum(r['release']-r['dispatch'] for r in e['rows'])/6 for e in es)/5
             for k,es in c['solo'].items()}
    mapping = {t:min(('CPU','GPU'),key=lambda b:(means[t+'/'+b],b!='CPU')) for t in ('classification','detection')}
    if set(mapping.values()) != {'CPU'}:
        fail('static mixed layout would require unmeasured serial CPU/GPU context')
    return mapping


def scenarios(source):
    deadlines=base.read(Path(source)/'simulation_input/deadline_scenarios.json')['classification']
    return [dict(id=f'{state}-{u}-{n}', urgent_ns=math.ceil(d),normal_ns=math.ceil(nd[0]),
                 arrivals=[0]*12, tasks=['classification','detection']*6, priorities=['urgent','normal']*6,
                 thermal=0, resident=True, warmup=6, source_state_budget=state)
            for state in ('urgent_warm','urgent_cold','urgent_early')
            for u,d in enumerate(deadlines[state]) for n,nd in enumerate(deadlines['normal'])]


def support(s, action):
    if type(s.get('thermal')) is not int or s['thermal']!=0 or s.get('resident') is not True or s.get('warmup')!=6:
        fail('thermal/residency/state')
    if action not in config()['actions']:
        fail('unknown action/transition')
    if any(type(s.get(k)) is not int or s[k]<=0 for k in ('urgent_ns','normal_ns')):
        fail('deadline')
    n=6 if action in ('CPU_SOLO','GPU_SOLO') else 12
    if s.get('arrivals')!=[0]*n:
        fail('count/staggered overlap/idle')
    if n==12:
        if s.get('tasks')!=['classification','detection']*6 or s.get('priorities')!=['urgent','normal']*6:
            fail('unmeasured mix/priority/order')
    elif s.get('tasks') not in (['classification']*6,['detection']*6) or s.get('priorities')!=['normal']*6:
        fail('solo homogeneous normal only')
    if set(s)-{'id','urgent_ns','normal_ns','arrivals','tasks','priorities','thermal','resident','warmup','source_state_budget'}:
        fail('unknown scenario option')


def admitted(e):
    snapshots=[m for m in e['memory'] if m.get('stage')=='before_workload']
    if len(snapshots)!=1:
        fail('missing/duplicate pre-workload admission')
    for m in snapshots:
        if m['thermal_status']!=0 or m['low_memory'] or not m['avail_bytes']-m['threshold_bytes']>max(m['threshold_bytes'],m['observed_peak_pss_bytes']):
            return False
    return True


def run_action(e, s, action):
    """실행 엔진. 이번에는 synthetic fixture에서만 호출한다."""
    support(s,action)
    expected={'CPU_FIFO':'CPU','CPU_URGENT':'CPU','CPU_SOLO':'CPU','GPU_SOLO':'GPU'}
    if action in expected and any(r['backend']!=expected[action] for r in e['rows']):
        fail('action/backend mismatch')
    if [r['task'] for r in e['rows']]!=s['tasks'] or [r['priority'] for r in e['rows']]!=s['priorities']:
        fail('episode/scenario mismatch')
    if action=='PAIRED_CORUN' and [r['backend'] for r in e['rows']]!=['CPU','GPU']*6:
        fail('unmeasured corun orientation')
    rows=copy.deepcopy(e['rows'])
    for r in rows:
        r['request_id']=key('request',s['id'],r['ordinal'])
        r['source_session']=e['session_id']
    if not admitted(e):
        for r in rows:
            r.update(terminal='rejected',reason='memory_admission',dispatch=None,ready=None,persist=None,release=None)
        return dict(rows=rows,end=0,action=action)
    if action!='PAIRED_CORUN':
        if action=='CPU_URGENT':
            rows.sort(key=lambda r:(r['priority']!='urgent',s['urgent_ns'] if r['priority']=='urgent' else 0,r['ordinal'],r['source_request']))
        now=0
        for r in rows:
            old=r['dispatch']; now+=r['gap']
            r.update(ready=now+r['ready']-old,persist=now+r['persist']-old if r['persist'] is not None else None,
                     release=now+r['release']-old,dispatch=now)
            now=r['release']
        end=now+e['tail']
    else:
        end=e['end']
    for r in rows:
        r.update(terminal='succeeded',reason=None)
    return dict(rows=rows,end=end,action=action)


def validate_result(result,s):
    support(s,result['action'])
    rows=result['rows']
    if len(rows)!=len(s['tasks']) or {r['ordinal'] for r in rows}!=set(range(len(rows))):
        fail('missing/duplicate terminal')
    if len({r['request_id'] for r in rows})!=len(rows):
        fail('request identity')
    for r in rows:
        if r['task']!=s['tasks'][r['ordinal']] or r['priority']!=s['priorities'][r['ordinal']]:
            fail('result binding')
        if r['terminal']=='succeeded':
            if not 0<=r['dispatch']<=r['ready']<=r['release']<=result['end']:
                fail('result clock')
            if r['priority']=='normal' and not r['ready']<=r['persist']<=r['release']:
                fail('result completion')
        elif r['terminal']=='rejected':
            if r['reason']!='memory_admission' or any(r[k] is not None for k in ('dispatch','ready','persist','release')):
                fail('rejected output')
        else:
            fail('unmodeled failure/expiry state')
    for b in ('CPU','GPU'):
        lane=sorted([r for r in rows if r['terminal']=='succeeded' and r['backend']==b],key=lambda r:r['dispatch'])
        if any(x['release']>y['dispatch'] for x,y in zip(lane,lane[1:])): fail('result lane overlap')
    return True


def metrics(result,s):
    validate_result(result,s)
    rows=result['rows']; urgent=[r for r in rows if r['priority']=='urgent'];normal=[r for r in rows if r['priority']=='normal']
    done=[r for r in rows if r['terminal']=='succeeded']
    lat=[r['ready'] for r in urgent if r['terminal']=='succeeded']
    rate=lambda group,boundary,d:sum(r['terminal']=='succeeded' and r[boundary]<=d for r in group)/len(group) if group else None
    return dict(p50=quantile(lat,.5),p95=quantile(lat,.95),p99=quantile(lat,.99),
                miss=1-rate(urgent,'ready',s['urgent_ns']) if urgent else None,
                normal=rate(normal,'persist',s['normal_ns']),completion=len(done)/len(rows),
                makespan=result['end'],throughput=len(done)*1e9/result['end'] if result['end'] else 0,
                waiting_mean=sum(r['dispatch'] for r in done)/len(done) if done else None,
                busy={b:sum(r['release']-r['dispatch'] for r in done if r['backend']==b) for b in ('CPU','GPU')},
                allocation={b:sum(r['backend']==b for r in done)/len(rows) for b in ('CPU','GPU')},
                terminals={t:sum(r['terminal']==t for r in rows) for t in ('succeeded','failed','rejected','expired','cancelled','unfinished')},
                memory_rejection=sum(r['reason']=='memory_admission' for r in rows))


def mean_metrics(ms):
    return {k:sum(m[k] for m in ms)/len(ms) if all(m[k] is not None for m in ms) else None
            for k in ('p50','p95','p99','miss','normal','completion','makespan','throughput')}


def loss(m,ref):
    return [m['makespan']-ref['makespan'],ref['throughput']-m['throughput'],ref['normal']-m['normal']]


def epsilon_choice(pred,epsilon):
    ref=pred['CPU_URGENT'];other=pred['PAIRED_CORUN']
    if any(m['p95'] is None for m in pred.values()):
        fail('no admitted predictive layout')
    bounds=[epsilon*max(0,x) for x in loss(other,ref)]
    feasible=[a for a,m in pred.items() if all(x<=b for x,b in zip(loss(m,ref),bounds))]
    return min(feasible,key=lambda a:(pred[a]['miss'],pred[a]['p95'],pred[a]['makespan'],a!='CPU_URGENT'))


def choose(policy,s,training):
    if policy not in POLICIES or not training:
        fail('policy/training')
    fixed={'FIFO_CPU':'CPU_FIFO','URGENT_CPU':'CPU_URGENT','STATIC':'CPU_FIFO','ALWAYS_CORUN':'PAIRED_CORUN'}
    if policy in fixed:
        return fixed[policy]
    # 학습 catalog의 기대값만 읽는다. 평가 대상 pair ticket/실현 시간을 받지 않는다.
    pred={a:mean_metrics([metrics(run_action(p[arm],s,a),s) for p in training])
          for a,arm in [('CPU_URGENT','A'),('PAIRED_CORUN','B')]}
    return epsilon_choice(pred,EPS[policy])


def frontier(values):
    def vector(m):
        return [m['p95'],m['miss'],m['makespan'],-m['throughput'],-m['normal']]
    valid={k:v for k,v in values.items() if v['p95'] is not None and v['completion']==1}
    def dominates(a,b):
        return all(x<=y for x,y in zip(a,b)) and any(x<y for x,y in zip(a,b))
    return sorted(k for k,m in valid.items() if not any(dominates(vector(n),vector(m)) for j,n in valid.items() if j!=k))


def exact_ci(deltas):
    """작은 paired catalog의 exact bootstrap; 임의 RNG 없음."""
    if not 2<=len(deltas)<=5:
        fail('bootstrap paired count')
    means=[sum(draw)/len(draw) for draw in itertools.product(deltas,repeat=len(deltas))]
    return [quantile(means,.025),quantile(means,.975)]


def evaluate(c,ss):
    """본 결과 생성 API. 별도 승인 실행에서만 사용; 이번 작업의 실제 입력 호출 금지."""
    validate_catalog(c); static_mapping(c)
    output=[]
    ranked=sorted(c['pairs'],key=lambda p:(sum(r['release']-r['dispatch'] for arm in ('A','B') for r in p[arm]['rows']),p['pair_id']))
    variants=[('core',c['pairs'],c['pairs'])]+[(n,[ranked[i]],c['pairs']) for n,i in [('low',0),('central',2),('high',4)]]
    variants += [(f'LOSO_{i}',c['pairs'][:i]+c['pairs'][i+1:],c['pairs'][:i]+c['pairs'][i+1:]) for i in range(5)]
    for s in ss:
        support(s,'CPU_FIFO')
        for name,atoms,training in variants:
            records=[];means={}
            for policy in POLICIES:
                action=choose(policy,s,training)
                scores=[]
                for pair in atoms:
                    e=pair['B' if action=='PAIRED_CORUN' else 'A']
                    result=run_action(e,s,action);m=metrics(result,s);scores.append(m)
                    records.append(dict(policy=policy,pair_id=pair['pair_id'],action=action,metrics=m,requests=result['rows']))
                means[policy]=mean_metrics(scores)
            diffs={}
            for policy in POLICIES:
                for baseline in POLICIES[:4]:
                    for metric in ('p95','miss','normal','completion','makespan','throughput'):
                        deltas=[next(r['metrics'][metric] for r in records if r['policy']==policy and r['pair_id']==p['pair_id'])-
                                next(r['metrics'][metric] for r in records if r['policy']==baseline and r['pair_id']==p['pair_id']) for p in atoms]
                        diffs[f'{policy}/{baseline}/{metric}']=dict(mean=sum(deltas)/len(deltas),CI95=exact_ci(deltas) if name=='core' else None)
            ref=means['URGENT_CPU'];corun=means['ALWAYS_CORUN']
            epsilon_feasible={str(e):[p for p,m in means.items() if all(x<=e*max(0,b) for x,b in zip(loss(m,ref),loss(corun,ref)))] for e in (0,.5,1)}
            output.append(dict(scenario=s['id'],variant=name,records=records,means=means,pareto=frontier(means),paired_differences=diffs,epsilon_feasible=epsilon_feasible))
    return dict(protocol=VERSION,experiment_type='empirical_simulation',results=output,
                interpretation='conditional finite empirical model; no universal winner or user SLA claim')


def plan(c,ss):
    validate_catalog(c)
    if len(ss)!=54 or len({s['id'] for s in ss})!=54:
        fail('54 unique predeclared deadline scenarios required')
    for s in ss: support(s,'CPU_FIFO')
    cfg=config()
    return dict(protocol=VERSION,status='SIMULATION_PLAN_READY',configuration=cfg,configuration_sha256=base.sha(cfg),
                catalog_sha256=base.sha(c),scenarios=ss,static_mapping=static_mapping(c),
                paired_keys=[p['pair_id'] for p in c['pairs']],replications=5,
                crn='all five pair atoms for every policy and deadline; same source tuple identity; no policy RNG consumption',
                seed_derivation='SHA256 canonical [version,seed,purpose,scenario,ordinal]; request IDs share policies/pairs; pair_id separately keys joint atoms; no random draws',
                execution_order=POLICIES,bootstrap_draws=3125,simulation_executed=False)


def code_hashes():
    hashes=base.code_hashes()
    hashes['docs/SUPPORT_SIMULATION_PROTOCOL.md']=base.digest(base.REPO/'docs/SUPPORT_SIMULATION_PROTOCOL.md')
    return hashes


def generate(source,output):
    source=Path(source).resolve(strict=True);output=Path(output).resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        fail('output replay/source overlap')
    audit,registry=base.audit(source)
    c=catalog(source,audit);p=plan(c,scenarios(source))
    jsonschema.validate(p,base.read(SCHEMA))
    output.mkdir(parents=True,exist_ok=False)
    for name,value in {'plan.json':p,'catalog.json':c,'audit.json':audit,'registry.json':registry}.items():
        (output/name).write_bytes(base.canonical(value))
    f=dict(protocol=VERSION,source=str(source),files={n:base.digest(output/n) for n in sorted(FILES)},code=code_hashes())
    (output/'freeze.json').write_bytes(base.canonical(f))
    return dict(status=p['status'],freeze_sha256=base.digest(output/'freeze.json'),simulation_executed=False)


def verify(output,expected):
    output=Path(output)
    if base.digest(output/'freeze.json')!=expected: fail('freeze hash')
    f=base.read(output/'freeze.json')
    if set(f)!={'protocol','source','files','code'} or f['protocol']!=VERSION or set(f['files'])!=FILES or f['code']!=code_hashes(): fail('freeze/code/schema')
    if {x.name for x in output.iterdir()}!=FILES|{'freeze.json'}: fail('extra files')
    for n,h in f['files'].items():
        if base.digest(base.contained(output,n))!=h: fail('input hash')
    audit,registry=base.audit(Path(f['source']))
    c=catalog(Path(f['source']),audit)
    if base.read(output/'audit.json')!=audit or base.read(output/'registry.json')!=registry or base.read(output/'catalog.json')!=c: fail('raw provenance/replay/registry')
    p=base.read(output/'plan.json');jsonschema.validate(p,base.read(SCHEMA))
    if p!=plan(c,scenarios(Path(f['source']))): fail('config/seed/scenario mutation')
    return dict(status='SIMULATION_PLAN_READY',random_samples=0,dispatches=0,simulated_completions=0,result_files=0,device_commands=[])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['generate','validate','dry-run'])
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-sha256')
    args=parser.parse_args()
    result=generate(args.source,args.output) if args.command=='generate' else verify(args.output,args.expected_sha256)
    print(base.canonical(result).decode())


if __name__=='__main__': main()
