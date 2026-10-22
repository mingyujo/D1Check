"""Independent Python closed-form activity-energy accounting; no simulation/fit."""
from pathlib import Path
import gzip,json,math
HERE=Path(__file__).resolve().parent
def read(p):
    p=Path(p);b=p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
op=read(HERE/'OPERATION.json');packet=read(HERE.parents[1]/'experiments/multiresource_v1/PACKET.json.gz');model=packet['power']
rows=[json.loads(l) for l in (Path(op['output'])/'rows.jsonl').read_text().splitlines() if l]
checked=0;largest=0;maximum_ratio=0
for row in rows:
    x=read(row['raw_path']);r=x['simulation'];spec=x['spec'];m=x['metrics'];h=m['observed_end_s']
    if spec['kind']=='P0':
        scenario=next(s for s in packet['scenarios'] if s['id']==spec['config']['scenario'])
    else:
        scenario=next(s for s in read(HERE/'INPUTS.json')['inputs'] if s['id']==spec['input_id'])
    b=scenario['context']['initial_context']['targets']['POWER_API']['baseline']['median_api_w']
    power=model['coef'][0]/model['scale'][0]+b*model['coef'][1]/model['scale'][1]
    value=power*h;variation=0
    for k,intervals in enumerate(r['activity']):
        for left,right,weight in intervals:
            def G(u):
                return 0 if u<=0 else u*u if u<.5 else u-.25
            coeff=model['coef'][2+k]/model['scale'][2+k]
            value+=coeff*weight*(G(h-left)-G(h-right)-G(-left)+G(-right))
            variation+=4*weight*abs(coeff)/.5
            for index,tau in enumerate((1,10,60)):
                def primitive(t):
                    if t<=left:return 0
                    if t<=right:return weight*((t-left)+tau*math.expm1(-(t-left)/tau))
                    return weight*((right-left)-tau*(math.exp(-(t-right)/tau)-math.exp(-(t-left)/tau)))
                j=11+index*9+k;coeff=model['coef'][j]/model['scale'][j]
                value+=coeff*(primitive(h)-primitive(0))
                variation+=4*weight*abs(coeff)/tau
    delta=abs(value-m['observed_prefix_API_J']);bound=spec['config']['power_dt_s']**2*variation/8+1e-7
    assert delta<=bound,(row['id'],delta,bound)
    assert abs(m['baseline_API_J']-power*spec['config']['horizon_s'])<1e-8
    if m['total_API_J'] is not None:
        assert abs(m['total_API_J']-m['baseline_API_J']-m['above_baseline_API_J'])<1e-8
    largest=max(largest,delta);maximum_ratio=max(maximum_ratio,delta/bound);checked+=3
result=dict(status='PASS',cases=len(rows),checks=checked,maximum_absolute_J_error=largest,maximum_error_over_rigorous_trapezoid_bound=maximum_ratio,method='Exact pulse convolution antiderivatives; dt^2/8 times total derivative variation bound',new_policy_environments=0,new_fit=0)
(Path(op['output'])/'INDEPENDENT_ENERGY_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
