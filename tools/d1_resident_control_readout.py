"""Fixed-window, descriptive readout for the resident control pair; no fitting."""
import argparse
import json
import math
from pathlib import Path
from tools import d1_resident_control_plan as c
from tools import d1_energy_thermal as energy
from tools import d1_arrival_recorded_replay_analysis as replay


def ap_window(points, lo, hi):
    area=covered=0.;start=end=None
    for (ta,va),(tb,vb) in zip(points,points[1:]):
        a,b=max(ta,lo),min(tb,hi)
        if b<=a or tb-ta>10_000_000_000:continue
        x=va+(vb-va)*(a-ta)/(tb-ta);y=va+(vb-va)*(b-ta)/(tb-ta)
        area+=(x+y)/2*(b-a);covered+=b-a
        if a==lo:start=x
        if b==hi:end=y
    if covered!=hi-lo:return dict(mean_c=None,change_c=None,reason='missing AP bracket/gap')
    return dict(mean_c=area/(hi-lo),start_c=start,end_c=end,change_c=end-start)


def session(folder,manifest,frozen):
    a=folder/'artifacts';boundary=c.p.read(a/'common_boundary.json');origin=boundary['start_ns']
    rows=c.p.read(a/'requests.json');count=c.request_count(manifest)
    if len(rows)!=count or any(r.get('terminal_status')!='succeeded' for r in rows):
        raise ValueError('incomplete planned denominator')
    if c.p.read(a/'cleanup.json')['status']!='completed':raise ValueError('app did not complete')
    events=[json.loads(x) for x in (a/'progress.jsonl').read_text(encoding='utf-8').splitlines()]
    samples=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2)
             for e in events if e.get('kind')=='power_sample']
    thermal=[json.loads(x) for x in (folder/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
    points=[(e['mono_ns'],float(e['AP'])) for e in thermal if e.get('AP') not in ('',None)]
    if any(not math.isfinite(v) for _,v in points) or any(b[0]<=a[0] for a,b in zip(points,points[1:])):
        raise ValueError('invalid AP/time ordering')
    windows={}
    for name,(begin,end) in c.p.read(c.BUNDLE/'execution_contract.json')['fixed_windows_seconds'].items():
        lo,hi=origin+int(begin*1e9),origin+int(end*1e9)
        idle=name!='common'
        occupied=any(r['dispatch_ns']<hi and r['lane_available_ns']>lo for r in rows)
        inside=[s for s in samples if lo<=s['mono_ns']<=hi]
        snapshots=bool(inside) and all(len(s.get('resident_keys',[]))==4 and
                                     (not idle or not s.get('active')) for s in inside)
        valid=snapshots and (not idle or not occupied)
        integrated=energy.integrate(samples,lo,hi,1000)
        j=integrated['full_energy_j'] if valid else None
        windows[name]=dict(start_s=begin,end_s=end,observed_j=j,
            mean_w=j/(end-begin) if j is not None else None,power_samples=len(inside),
            missing_seconds=integrated['missing_s'],idle_required=idle,
            state_eligible=valid,ap=ap_window(points,lo,hi) if valid else {'mean_c':None,'change_c':None})
    segments=replay.observed_segments(rows,origin) if rows else [dict(start_s=0.,end_s=120.,state='idle')]
    powers=frozen['whole_device_power_w']
    mapped=all(replay.state_key(s['state']) in powers for s in segments)
    predicted=sum((s['end_s']-s['start_s'])*powers[replay.state_key(s['state'])] for s in segments) if mapped else None
    actual=windows['common']['observed_j']
    return dict(role=manifest['resident_control_role'],requests=count,windows=windows,
        frozen_diagnostic_120s_j=predicted,signed_diagnostic_error_j=None if predicted is None or actual is None else predicted-actual,
        strict_supported=False,accuracy_pass=None,states=segments)


def readout(plan_file,output):
    plan=c.p.read(plan_file);output=Path(output)
    if output.exists():raise FileExistsError('preserve existing readout')
    if c.p.digest(plan['frozen_model']['path'])!=c.replay.FROZEN_SHA:raise ValueError('freeze changed')
    frozen=c.p.read(plan['frozen_model']['path']);root=Path(plan['output_root']);cases=[]
    for e in plan['entries']:
        folder=root/f"{e['index']:02d}_{e['session_id']}"
        try:
            if c.p.read(folder/'validated.json')['status']!='eligible_descriptive_only':raise ValueError('not eligible')
            cases.append(session(folder,c.p.read(Path(plan_file).parent/e['manifest']),frozen))
        except (OSError,ValueError,KeyError) as error:
            cases.append(dict(role=e['phase'],status='not_evaluable',error=str(error),windows=None))
    changes=[]
    for case in cases:
        w=case.get('windows')
        values=[w[k]['mean_w'] for k in ('pre','late_common')] if w else [None,None]
        changes.append(values[1]-values[0] if None not in values else None)
    result=dict(status='descriptive_only',cases=cases,power_pre_to_late_changes_w=changes,
        difference_of_changes_w=changes[1]-changes[0] if None not in changes else None,
        independent_validation=False,causal_claim=False,model_fit=False,experiment_ready=False)
    output.mkdir(parents=True);c.cal.write_new(output/'summary.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(readout(args.plan,args.output),indent=2))
