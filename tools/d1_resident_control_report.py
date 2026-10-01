"""Post-run report; preserves incomplete load evidence, never resumes a plan."""
import argparse
import csv
import json
from pathlib import Path
from tools import d1_resident_control_plan as c
from tools import d1_resident_control_readout as readout
from tools import d1_energy_thermal as energy
from tools.d1_arrival_recorded_replay_analysis import state_key


def diagnostic_cumulative_j(states, powers_w, end_s):
    """Frozen whole-device power on actual lanes; gaps never become zero power."""
    if not 0 <= end_s <= 120:
        return None
    cursor = total = 0.
    for segment in states:
        if cursor >= end_s:
            break
        start, stop = segment['start_s'], min(segment['end_s'], end_s)
        if abs(start-cursor) > 1e-8 or stop <= start:
            return None
        watts = powers_w.get(state_key(segment['state']))
        if watts is None:
            return None
        total += (stop-start)*watts
        cursor = stop
    return total if abs(cursor-end_s) < 1e-8 else None


def report(plan_file, output):
    plan=c.p.read(plan_file);root=Path(plan['output_root']);output=Path(output)
    result=readout.readout(plan_file,output)
    for case in result['cases']:
        if case.get('status')=='not_evaluable':case['error']='No validated session; common window/cooling incomplete'
    receipt=c.p.read(root/'FINAL_RECEIPT.json')
    frozen_powers=c.p.read(plan['frozen_model']['path'])['whole_device_power_w']
    frozen_idle_w=frozen_powers['resident_idle']
    completed=receipt.get('completed_sessions',receipt.get('sessions',0))
    attempted=receipt.get('session_attempts',len(list(root.glob('*/attempt.json'))))
    result.update(status=receipt['status'],completed_sessions=completed,
        session_attempts=attempted,elapsed_seconds=receipt['elapsed_seconds'],
        adb_commands=len(list((root/'host_commands').glob('[0-9]*'))),
        failure=None if receipt['status']=='completed_descriptive_only' else
            'Stopped; inspect original receipt and bounded command results. No retry.',
        plan_sha256=c.p.digest(plan_file),apk_sha256=plan['apk_sha256'],budget=plan['budget'])
    paths=[];lanes=[];evidence={};sessions=[]
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}"
        a=folder/('artifacts' if (folder/'validated.json').exists() else 'failure_prefix')
        kinds=('runtime_start','runtime_return','warmup_start','warmup_return','request_start',
               'output_ready','persist_complete','worker_release','lane_available')
        if not (a/'progress.jsonl').exists():
            no_launch=not (folder/'launch_attempt.json').exists() and not folder.exists()
            sessions.append(dict(role=entry['phase'],confirmed_counts=None,
                status='not_attempted' if no_launch else 'unknown',
                app_cleanup='not_applicable_no_launch' if no_launch else 'unconfirmed',
                host_cleanup='not_applicable_no_launch' if no_launch else 'unconfirmed'))
            continue
        events=[json.loads(line) for line in (a/'progress.jsonl').read_text(encoding='utf-8').splitlines()]
        origin=next((e['scheduled_origin_ns'] for e in events if e['kind']=='common_start'),None)
        if origin is None:
            sessions.append(dict(role=entry['phase'],confirmed_counts={k:sum(e['kind']==k for e in events) for k in kinds},
                                 app_cleanup='unconfirmed',host_cleanup='unconfirmed',common_start_observed=False))
            continue
        powers=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2)
                for e in events if e['kind']=='power_sample']
        thermals=[json.loads(line) for line in (folder/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
        role=entry['phase'];samples=[]
        for e in powers:
            t=(e['mono_ns']-origin)/1e9
            if not 0<=t<=180:continue
            row=dict(role=role,kind='power',time_s=t,power_w=energy.discharge_w(e,1000),ap_c=None,
                cumulative_observed_j=None,cumulative_frozen_j=None)
            if t<=120:
                row['cumulative_observed_j']=energy.integrate(powers,origin,e['mono_ns'],1000)['full_energy_j']
                row['cumulative_frozen_j']=diagnostic_cumulative_j(
                    result['cases'][entry['index']].get('states',[]),frozen_powers,t)
            samples.append(row)
        case=result['cases'][entry['index']]
        common=(case.get('windows') or {}).get('common',{})
        if common.get('observed_j') is not None:
            # Integration boundaries are not fabricated sensor samples.
            for t in (0.,120.):
                samples.append(dict(role=role,kind='energy_boundary',time_s=t,power_w=None,ap_c=None,
                    cumulative_observed_j=0. if t==0 else common['observed_j'],
                    cumulative_frozen_j=diagnostic_cumulative_j(case.get('states',[]),frozen_powers,t)))
        for e in thermals:
            t=(e['mono_ns']-origin)/1e9
            if 0<=t<=180 and e.get('AP') not in ('',None):
                samples.append(dict(role=role,kind='AP',time_s=t,power_w=None,ap_c=float(e['AP']),
                    cumulative_observed_j=None,cumulative_frozen_j=None))
        paths.extend(samples)
        manifest=c.p.read(folder/'input_manifest.json')
        # The generic lane mapper carries queue defaults; use this run's provenance.
        for segment in case.get('states',[]):
            segment.update(scenario=manifest['scenario'],seed=manifest['source_seed'],
                           realized=manifest['source_realized_interference'],policy=manifest['policy'])
        starts=[e for e in events if e['kind']=='dispatch'];releases={e['id']:e for e in events if e['kind']=='lane_available'}
        for e in starts:
            q=next(q for q in manifest['requests'] if q['request_id']==e['id'])
            end=releases.get(e['id'])
            lanes.append(dict(ordinal=q['ordinal'],task=q['task_id'],backend=q['recorded_backend'],
                start_s=(e['dispatch_ns']-origin)/1e9,end_s=None if end is None else (end['mono_ns']-origin)/1e9))
        sessions.append(dict(role=role,confirmed_counts={kind:sum(e['kind']==kind for e in events) for kind in
            ('runtime_start','runtime_return','warmup_start','warmup_return','request_start','output_ready','persist_complete','worker_release','lane_available')},
            recovered_power_end_s=max((e['mono_ns']-origin)/1e9 for e in powers),
            app_cleanup=c.p.read(a/'cleanup.json')['status'] if (a/'cleanup.json').exists() else 'unconfirmed',
            host_cleanup=c.p.read(next((f for f in (folder/'host_cleanup.json',folder/'failure_host_cleanup.json')
                                       if f.exists())))['status']))
        approval=c.p.read(folder/'start_ap_gate'/'host_approval.json')
        sessions[-1]['host_start_ap_c']=float(approval['sample']['AP'])
        sessions[-1]['host_initial_ap_in_development_range']=approval['initial_ap_in_frozen_development_range']
        sessions[-1]['ap_read_bracket_s']=(approval['sample']['after_ns']-approval['sample']['before_ns'])/1e9
        for name in ('manifest.json','progress.jsonl','cleanup.json','requests.json','common_boundary.json'):
            if (a/name).exists():evidence[role+'/'+name]=c.p.digest(a/name)
        evidence[role+'/thermal.jsonl']=c.p.digest(folder/'thermal.jsonl')
    result['sessions']=sessions;result['source_sha256']=evidence
    result['missing_not_zero']=True
    result['installation']=(dict((k,receipt['installation'].get(k)) for k in
        ('status','apk_transfer_attempts','install_attempts','elapsed_seconds','installed_sha256'))
        if receipt.get('installation') else None)
    commands=[c.p.read(p) for p in sorted((root/'host_commands').glob('*/client/result.json'))]
    result['observed_consumption']=dict(
        installed_host_pulls=sum('pull' in d['command'] for d in commands),
        staging_files=sum('push' in d['command'] and not d['command'][-1].endswith('.apk') for d in commands),
        sessions_attempted=attempted,sessions_completed=completed,
        runtime_starts=sum(s['confirmed_counts']['runtime_start'] for s in sessions if s['confirmed_counts'] is not None),
        warmup_starts=sum(s['confirmed_counts']['warmup_start'] for s in sessions if s['confirmed_counts'] is not None),
        work_starts=sum(s['confirmed_counts']['request_start'] for s in sessions if s['confirmed_counts'] is not None),
        explicit_starts=sum(s['confirmed_counts']['warmup_start']+s['confirmed_counts']['request_start'] for s in sessions if s['confirmed_counts'] is not None),
        meaning='confirmed durable event counts only; absent records are not actual zero')
    for name,rows in [('paths.csv',paths),('partial_load_lanes.csv',lanes)]:
        with (output/name).open('w',encoding='utf-8',newline='') as f:
            fields=list(rows[0]) if rows else (['role','kind','time_s','power_w','ap_c','cumulative_observed_j','cumulative_frozen_j']
                if name=='paths.csv' else ['ordinal','task','backend','start_s','end_s'])
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    if not paths:return result
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(12,7))
    for role,label in zip(c.ROLES,('C no load','L registered load')):
        rows=[r for r in paths if r['role']==role]
        power=[r for r in rows if r['kind']=='power']
        ap=[r for r in rows if r['kind']=='AP']
        axes[0,0].plot([r['time_s'] for r in power],[r['power_w'] for r in power],label=label)
        axes[0,1].plot([r['time_s'] for r in ap],[r['ap_c'] for r in ap],label=label)
        j=sorted((r for r in rows if r['time_s']<=120 and r['kind'] in ('power','energy_boundary')),
                 key=lambda r:r['time_s'])
        # None is NaN, so incomplete coverage remains a break in the plotted path.
        def values(key):return [float('nan') if r[key] is None else r[key] for r in j]
        axes[1,0].plot([r['time_s'] for r in j],values('cumulative_observed_j'),label=label+' observed')
        axes[1,0].plot([r['time_s'] for r in j],values('cumulative_frozen_j'),ls='--',label=label+' frozen diagnostic')
        residual=[float('nan') if r['cumulative_observed_j'] is None or r['cumulative_frozen_j'] is None
                  else r['cumulative_frozen_j']-r['cumulative_observed_j'] for r in j]
        axes[1,1].plot([r['time_s'] for r in j],residual,label=label)
    for ax in axes.flat:
        for lo,hi in ((5,30),(90,120),(150,180)):
            ax.axvspan(lo,hi,color='gray',alpha=.08)
    for lo,hi in [(s['start_s'],s['end_s']) for s in result['cases'][1].get('states',[]) if s['state']!='idle']:
        axes[0,0].axvspan(lo,hi,color='red',alpha=.1)
        axes[0,1].axvspan(lo,hi,color='red',alpha=.1)
    axes[0,0].axhline(frozen_idle_w,color='orange',label='Frozen resident idle W (diagnostic)')
    axes[0,0].set_title('Observed power; red = actual L occupancy');axes[0,0].set_ylabel('Whole device W')
    axes[0,1].set_ylabel('AP Celsius');axes[0,1].set_title('Observed AP only; window eligibility in summary')
    axes[1,0].set_ylabel('Cumulative J');axes[1,0].set_title('Fixed 0-120 s; frozen = extrapolation diagnostic')
    axes[1,1].set_ylabel('Predicted - observed J');axes[1,1].set_title('Cumulative energy residual; no accuracy PASS')
    axes[1,1].axhline(0,color='black',lw=.5)
    for ax in axes.flat:ax.set_xlabel('Seconds from actual common origin');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle(result['status']+': no causal attribution, no fit, current raw=mA conditional')
    fig.tight_layout();fig.savefig(output/'observed.png',dpi=160);fig.savefig(output/'observed.svg');plt.close(fig)
    svg=output/'observed.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(report(a.plan,a.output),indent=2))
