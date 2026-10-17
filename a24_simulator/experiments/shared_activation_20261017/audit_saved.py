"""Independent interval-intersection/union verification of the saved new costs.

Does not import the new cost implementation or start an environment. Uses direct
per-owner work, CPU/GPU interval intersections and merged idle gaps instead of
the evaluator's exclusive-state scan.
"""
from pathlib import Path
import gzip
import json
import math
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'reference/model_integration'))
import runtime_guard as G
G.OWN_TOKENS+=('shared_activation_20261017','choice_opportunities_20261017','rl_cost_20261017','state_recovery_owner')


def read(path):
    b=path.read_bytes()
    return json.loads(gzip.decompress(b) if path.suffix=='.gz' else b)


def intersection(a,b,lo,hi):
    return max(0.,min(a['end_s'],b['end_s'],hi)-max(a['start_s'],b['start_s'],lo))


def direct(owners,lo,hi,solo,discount,scale,tau):
    H=discount*scale
    work=sum(solo[('classification' if r['task']=='C' else 'detection')+'_'+r['route']]*
        max(0.,min(hi,r['end_s'])-max(lo,r['start_s'])) for r in owners)
    cpu=[r for r in owners if r['route']=='CPU'];gpu=[r for r in owners if r['route']=='GPU']
    known=unknown=0.
    for a in cpu:
        for b in gpu:
            overlap=intersection(a,b,lo,hi)
            if a['task']=='D' and b['task']=='C':known+=overlap
            else:unknown+=overlap
    busy=[]
    for r in sorted((r for r in owners if r['start_s']<hi),key=lambda r:r['start_s']):
        a,b=r['start_s'],min(hi,r['end_s'])
        if busy and a<=busy[-1][1]:busy[-1][1]=max(busy[-1][1],b)
        else:busy.append([a,b])
    tail_seconds=0.
    if tau:
        for i,(_,end) in enumerate(busy):
            a=max(lo,end);b=min(hi,busy[i+1][0] if i+1<len(busy) else hi)
            if b>a:
                tail_seconds+=tau*(math.exp(-(a-end)/tau)-math.exp(-(b-end)/tau))
    known_credit=-discount*known;unknown_credit=-H*unknown;tail=H*tail_seconds
    return dict(additive_route_J_proxy=work,identified_pair_credit_J_proxy=known_credit,
        hypothesized_pair_credit_J_proxy=unknown_credit,hypothesized_idle_tail_J_proxy=tail,
        known_pair_overlap_s=known,transferred_pair_overlap_s=unknown,
        increment_J_proxy=work+known_credit+unknown_credit+tail)


def run():
    op_path=Path(__file__).parent/'OPERATION.json';op=read(op_path);out=ROOT/op['output_dir']
    G.require((out/'COMPLETE.json').is_file() and not (out/'AUDIT.json').exists(),'Requires completed unaudited output')
    reg=read(ROOT/'models/registration.json')
    guard=G.process_guard(Path(__file__).resolve(),reg['known_PS_producer_paths']);G.free_guard([ROOT,'D:/'])
    checks=0;worst=0.
    def close(actual,expected):
        nonlocal checks,worst
        error=abs(actual-expected);worst=max(worst,error);checks+=1
        G.require(error<1e-7,'Independent arithmetic mismatch: '+str((actual,expected)))
    pins=[*op['source_pins'],*op['input_pins']]
    pins += [p for row in op['schedules'] for p in (row['raw'],row['summary'])]
    for p in pins:
        G.require(G.sha(ROOT/p['path'])==p['sha256'] and (ROOT/p['path']).stat().st_size==p['bytes'],'Source drift')
        checks+=1
    model=read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')
    powers=dict(zip(model['supported_states'],model['coefficients_W_proxy']))
    pair=powers.pop('classification_GPU+detection_CPU');powers['detection_GPU']=.6013808404579677
    discount=powers['classification_GPU']+powers['detection_CPU']-pair
    data=read(out/'SCHEDULES.json');comp=read(out/'COMPARISON.json');terminal=read(out/'COMPLETE.json')
    G.require(data['scenarios']==op['scenarios'] and len(data['rows'])==72,'Scenario denominator')
    G.require(len({r['id'] for r in data['rows']})==72,'Unique schedules')
    by_id={r['id']:r for r in data['rows']}
    for s in op['schedules']:
        row=by_id[s['id']];owners=read(ROOT/s['raw']['path'])['summary']['gantt']
        saved=read(ROOT/s['summary']['path'])
        G.require(row['raw_sha256']==s['raw']['sha256']==saved['raw_sha256'],'Bound raw')
        for i,param in enumerate(op['scenarios']):
            cost=row['scenario_costs'][i];lo,hi=s['window']
            expected=direct(owners,lo,hi,powers,discount,param['shared_scale'],param['idle_decay_s'])
            for key,value in expected.items():close(cost[key],value)
            close(cost['total_J_proxy'],expected['increment_J_proxy']+(hi-lo)*model['reference_baseline_W_proxy'])
            last=max(r['end_s'] for r in owners)
            entire=direct(owners,0,last,powers,discount,param['shared_scale'],param['idle_decay_s'])
            close(cost['full_episode_increment_J_proxy'],entire['increment_J_proxy']+discount*param['shared_scale']*param['idle_decay_s'])
            close(cost['shared_scale'],param['shared_scale']);close(cost['idle_decay_s'],param['idle_decay_s'])
        for key in ('on_time','urgent_on_time','mean_AP_c'):close(row[key],saved['metrics'][key])
    for scenario,sensitivity in enumerate(comp['sensitivity']):
        G.require(sensitivity['parameters']==op['scenarios'][scenario],'Scenario label')
        for group in sensitivity['policy_means']:
            rows=[r for r in data['rows'] if r['collection']==group['collection'] and r['policy']==group['policy']]
            close(group['requests'],sum(r['n'] for r in rows))
            for key in ('total_J_proxy','increment_J_proxy','full_episode_increment_J_proxy','additive_route_J_proxy',
                        'identified_pair_credit_J_proxy','hypothesized_pair_credit_J_proxy','hypothesized_idle_tail_J_proxy'):
                close(group[key],sum(r['scenario_costs'][scenario][key] for r in rows)/len(rows))
        for c in sensitivity['comparisons']:
            collection='CHOICE_V2' if c['a']=='COALESCED_COST' else 'FRESH12'
            aa={r['case']:r for r in data['rows'] if r['collection']==collection and r['policy']==c['a']}
            bb={r['case']:r for r in data['rows'] if r['collection']==collection and r['policy']==c['b']}
            for pair in c['per_condition']:
                for key in c['mean_delta']:
                    close(pair[key],aa[pair['case']]['scenario_costs'][scenario][key]-bb[pair['case']]['scenario_costs'][scenario][key])
            for key,value in c['mean_delta'].items():close(value,sum(p[key] for p in c['per_condition'])/len(c['per_condition']))
    for p in terminal['result_pins']:
        G.require(G.sha(out/p['path'])==p['sha256'] and (out/p['path']).stat().st_size==p['bytes'],'Saved result changed')
        checks+=1
    G.require(terminal['new_environment_START']==terminal['new_fit']==terminal['NN_updates']==0,'No hidden rollout/fit')
    G.write_new(out/'AUDIT.json',dict(status='PASS_INDEPENDENT_INTERVAL_UNION_AND_INTERSECTION',
        utc=G.now(),checks=checks,max_absolute_arithmetic_error=worst,guard=guard,
        operation_sha256=G.sha(op_path),schedule_count=72,scenario_count=16,
        new_environment_START=0,new_fit=0,NN_updates=0,physical_validation=False,measured_J=None))
    print(json.dumps(dict(status='PASS',checks=checks,max_absolute_error=worst)))


if __name__=='__main__':run()
