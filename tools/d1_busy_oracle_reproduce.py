"""Recompute the sealed finite spaces from shared data, zero engine executions."""
import contextlib,io,json,time
from tools import d1_busy_schedule_oracle as x
from tools import d1_busy_oracle_check as audit

def reproduce():
    with contextlib.redirect_stdout(io.StringIO()):audit.check()
    data=audit.read(audit.BUNDLE/'inputs.json');frozen,_=x.p.inputs(x.p.BUNDLE);model=x.micro.PulseModel(frozen,data['initial']);counts=[];began=time.monotonic()
    for i,case in enumerate(data['cases']):
        certificate=audit.read(audit.BUNDLE/f'case_{i:02d}.json');saved=certificate['oracle']
        # Explicit saved domains include BOTH native reference starts. No new
        # engine or raw historical output is needed merely to certify this space.
        domain_calendar=[[dict(request_id=identifier,backend='CPU',start_ns=v) for identifier,domain in zip(case['variable_ids'],saved['domains_ns']) for v in domain]]
        refs=[certificate['baselines'][k] for k in ('BAND_HEFT_WHOLE_REQUEST_ADAPT_V1','TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1')]
        answer=x.enumerate_calendars(case,x.p.profile(frozen,case['context']),model,refs,domain_calendar,deadline=began+60)
        assert answer['domains_ns']==saved['domains_ns'] and answer['counts']==saved['counts']
        for role,w in answer['witnesses'].items():
            old=saved['witnesses'][role];assert (w is None)==(old is None)
            if w is None:continue
            for k in ('energy_j','peak_ap_c','urgent_p95_ms','normal_mean_ms'):assert abs(w[k]-old[k])<1e-8
            assert w['calendar']==old['calendar']
        counts.append(answer['counts'])
    result=dict(status='PASS',conditions=4,raw_calendars=sum(c['raw'] for c in counts),visited_calendars=sum(c['visited'] for c in counts),joint_gain=sum(c['joint_gain'] for c in counts),
        scope='recomputed exact declared finite certificates from shared domains/model; not a new original-engine comparison or independent data',new_environment_starts=0,new_learning_starts=0,device_commands=0,wall_s=time.monotonic()-began)
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':reproduce()
