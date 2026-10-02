"""Common-cutoff AP background contrast. No fitting, no device commands."""
import argparse
import math
import traceback
from pathlib import Path
from tools import d1_ap_background_contrast as plan_module
from tools import d1_ap_preparation_memory as model
from tools import d1_ap_model_completion as common
from tools import d1_ap_bundle_readout as shared
from tools import d1_resident_control_readout as control
from tools import d1_arrival_recorded_replay_analysis as states
from tools import d1_arrival_energy_analysis as logs

p,require=plan_module.p,plan_module.old.require


def case_from_session(plan_file,plan,entry):
    folder=Path(plan['output_root'])/f"{entry['index']:02d}_{entry['session_id']}";art=folder/'artifacts'
    manifest_file=Path(plan_file).parent/entry['manifest'];manifest=p.read(manifest_file)
    require(p.digest(manifest_file)==entry['manifest_sha256'] and p.read(art/'manifest.json')==manifest,'recovered manifest mismatch')
    require(p.read(art/'cleanup.json')['status']=='completed','app cleanup not completed')
    boundary=p.read(art/'common_boundary.json');origin=boundary['start_ns'];rows=p.read(art/'requests.json')
    require(boundary['planned_end_ns']-origin==120_000_000_000,'common window changed')
    count=plan_module.memory.base.control.request_count(manifest)
    require(count==entry['requests']==len(rows) and {r['request_id'] for r in rows}=={r['request_id'] for r in manifest['requests']},'request denominator')
    require(all(r['terminal_status']=='succeeded' and origin<=r['dispatch_ns']<r['lane_available_ns']<origin+120_000_000_000 for r in rows),'unfinished work')
    approval=p.read(art/'start_ap.accepted.json')
    require(approval['gate_mode']=='numeric-ap-observe-v2' and approval['common_start_ns']==origin,'AP start boundary')
    events=logs.read_lines(art/'progress.jsonl')
    baseline=[e['mono_ns'] for e in events if (e.get('phase'),e.get('kind'))==('resident_baseline','phase_start')]
    cooling=[e['mono_ns'] for e in events if (e.get('phase'),e.get('kind'))==('resident_cooling','phase_end')]
    require(len(baseline)==len(cooling)==1 and baseline[0]<origin and cooling[0]>origin+120_000_000_000,'phase boundary')
    cutoff=origin+35_000_000_000
    require(all(r['dispatch_ns']>=cutoff for r in rows),'work before fixed initialization cutoff')
    thermal=logs.read_lines(folder/'thermal.jsonl')
    good=[e for e in thermal if e.get('AP') not in ('',None) and e.get('thermal_status')=='0']
    require(all(math.isfinite(float(e['AP'])) and e['before_ns']<=e['mono_ns']<=e['after_ns'] for e in good),'invalid numeric AP/bracket')
    require(all(a['mono_ns']<b['mono_ns'] for a,b in zip(good,good[1:])),'unordered AP')
    pre=[dict(t=(e['mono_ns']-origin)/1e9,ap=float(e['AP']),lo=(e['before_ns']-origin)/1e9,hi=(e['after_ns']-origin)/1e9)
         for e in good if baseline[0]<=e['before_ns']<=e['after_ns']<cutoff]
    post=[e for e in good if cutoff<=e['before_ns']<=e['after_ns']<=cooling[0]]
    ts=[(e['mono_ns']-origin)/1e9 for e in post];end=(cooling[0]-origin)/1e9
    require(len(ts)>=20 and ts[0]-35<=10 and end-ts[-1]<=10 and all(0<b-a<=10 for a,b in zip(ts,ts[1:])),'AP target coverage')
    segments=states.observed_segments(rows,origin) if rows else [dict(start_s=0.,end_s=120.,state='idle')]
    segments.append(dict(start_s=120.,end_s=end,state='idle'))
    return dict(id=entry['phase'],condition=entry['condition'],requests=count,
        inputs=dict(preload=pre,query_s=ts,segments=segments),observed_ap_c=[float(e['AP']) for e in post],
        first_dispatch_s=min((r['dispatch_ns']-origin)/1e9 for r in rows) if rows else None,
        last_lane_s=max((r['lane_available_ns']-origin)/1e9 for r in rows) if rows else None,
        common_start_ap_c=approval['ap_c'])


def predict_fixed(case,plan):
    binding=plan['memory_candidate']
    require(p.digest(binding['path'])==plan_module.memory.CANDIDATE_SHA,'frozen candidate changed')
    candidate=p.read(binding['path']);params=candidate['fixed_parameters'];x=case['inputs']
    queries=x['query_s'];pre=x['preload'];cursor=0.
    require(queries and pre and all(math.isfinite(t) for t in queries) and queries[0]>=35 and
        all(0<b-a<=10 for a,b in zip(queries,queries[1:])) and all(v['hi']<35 for v in pre),'fixed cutoff/query boundary')
    for s in x['segments']:
        require(math.isfinite(s['start_s']) and math.isfinite(s['end_s']) and abs(s['start_s']-cursor)<=1e-6 and s['end_s']>=cursor,'schedule coverage')
        require(states.state_key(s['state']) in params['ap_slope_at_30_c_per_s'],'unsupported state')
        require(s['state']=='idle' or s['start_s']>=35,'load before cutoff')
        cursor=s['end_s']
    require(queries[-1]<=cursor,'query after schedule')
    init=model.initialize(pre,params['ap_cooling_rate_per_s'],candidate['tau_s'])
    require(0<=init['anchor_s']<35,'initial anchor boundary')
    values=model._propagate(x['segments'],queries,params['ap_slope_at_30_c_per_s'],
        params['ap_cooling_rate_per_s'],candidate['tau_s'],candidate['gamma'],init)
    return values,init


def delta(ts,ys,start,end):
    a=common.interpolate(ts,ys,start);b=common.interpolate(ts,ys,end)
    return None if a is None or b is None else b-a


def describe(case,values,init,contract):
    ts=case['inputs']['query_s'];obs=case['observed_ap_c']
    require(len(ts)==len(obs)==len(values) and all(math.isfinite(v) for v in obs),'missing targets')
    windows=[]
    for start,end in contract['fixed_direction_windows_s']:
        windows.append(dict(axis='common_origin',start_s=start,end_s=end,
            observed_change_c=delta(ts,obs,start,end),predicted_change_c=delta(ts,values,start,end)))
    if case['last_lane_s'] is not None:
        for start,end in contract['load_relative_windows_s']:
            lo,hi=case['last_lane_s']+start,case['last_lane_s']+end
            windows.append(dict(axis='since_actual_last_lane',start_s=start,end_s=end,
                observed_change_c=delta(ts,obs,lo,hi),predicted_change_c=delta(ts,values,lo,hi)))
    phase_rows=[]
    for phase in ('before_work','work_span','post_work_idle','no_work'):
        selected=[]
        for t,y,v in zip(ts,obs,values):
            actual='no_work' if case['last_lane_s'] is None else ('before_work' if t<case['first_dispatch_s'] else
                'work_span' if t<=case['last_lane_s'] else 'post_work_idle')
            if actual==phase:selected.append((y,v))
        if selected:phase_rows.append(dict(phase=phase,samples=len(selected),**common.score(*zip(*selected))))
    return dict(role=case['id'],condition=case['condition'],status='evaluated_fixed_candidate',requests=case['requests'],
        first_s=ts[0],last_s=ts[-1],samples=len(ts),initialization=init,scores=common.score(obs,values),
        windows=windows,phase_scores=phase_rows,first_dispatch_s=case['first_dispatch_s'],last_lane_s=case['last_lane_s'],
        observed_peak_first_s=ts[obs.index(max(obs))],predicted_peak_first_s=ts[values.index(max(values))],
        peak_timing='first maximum on recorded target samples; no sub-sample maximum claim',
        common_start_ap_c=case['common_start_ap_c'],accuracy_pass=None,strict_support=False)


def contrasts(results,contract):
    complete=len(results)==6 and all(r.get('status')=='evaluated_fixed_candidate' for r in results)
    out=[]
    for start,end in contract['fixed_direction_windows_s']:
        grouped={c:[] for c in ('C','L35','L65')}
        for r in results:
            w=next((w for w in r.get('windows',[]) if w['axis']=='common_origin' and (w['start_s'],w['end_s'])==(start,end)),None)
            if w:grouped[r['condition']].append(w['observed_change_c'])
        valid=complete and all(len(v)==2 and None not in v for v in grouped.values())
        means={c:sum(v)/2 if valid else None for c,v in grouped.items()}
        out.append(dict(start_s=start,end_s=end,complete_six_arms=complete,condition_repeats=grouped,
            L35_minus_C=None if not valid else means['L35']-means['C'],
            L65_minus_C=None if not valid else means['L65']-means['C'],
            L65_minus_L35=None if not valid else means['L65']-means['L35'],
            interpretation='arithmetic AP-change contrast; not causal subtraction, CI or accuracy PASS'))
    return out


def report(file,output,*,fixture=False):
    file,output=Path(file),Path(output);plan=p.read(file);root=Path(plan['output_root'])
    for protected in (root,Path(plan['registry']),file.parent):
        require(output.resolve()!=protected.resolve() and protected.resolve() not in output.resolve().parents,'protected evidence output')
    require(not output.exists(),'fresh PC readout required')
    require(plan['experiment_id']==plan_module.EXPERIMENT and plan['source_code']==plan_module.identity(),'frozen code differs')
    for key in ('memory_candidate','candidate_freeze','frozen_model','analysis_contract'):
        require(p.digest(plan[key]['path'])==plan[key]['sha256'],'frozen resource differs')
    require(p.digest(root/'memory_candidate_freeze.json')==plan['memory_candidate']['sha256'] and
        p.digest(root/'memory_analysis_contract.json')==plan['analysis_contract']['sha256'],'execution freeze differs')
    contract=p.read(plan['analysis_contract']['path']);receipt=p.read(root/'FINAL_RECEIPT.json')
    output.mkdir(parents=True);results=[];paths=[]
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}"
        r=dict(role=entry['phase'],condition=entry['condition'],status='not_evaluable',scores=None)
        try:
            require(p.read(folder/'validated.json')['status']=='eligible_descriptive_only','session not eligible')
            case=case_from_session(file,plan,entry);values,init=predict_fixed(case,plan)
            r=describe(case,values,init,contract)
            limits=p.read(plan['frozen_model']['path'])['initial_ap_development_range_c']
            r['original_start_ap_in_development_range']=limits[0]<=case['common_start_ap_c']<=limits[1]
            r['short_transition_strict_supported']=False
            common.write_json(output/(entry['phase']+'_inputs.json'),case)
            for t,y,v in zip(case['inputs']['query_s'],case['observed_ap_c'],values):
                paths.append(dict(role=entry['phase'],condition=entry['condition'],common_s=t,
                    since_last_lane_s=None if case['last_lane_s'] is None else t-case['last_lane_s'],
                    observed_c=y,predicted_c=v,residual_c=v-y,
                    observed_delta_c=y-init['anchor_ap_c'],predicted_delta_c=v-init['anchor_ap_c']))
            try:
                r['energy_and_states']=control.session(folder,p.read(file.parent/entry['manifest']),p.read(plan['frozen_model']['path']))
            except Exception as error:r['energy_error']=dict(error=repr(error),stack=traceback.format_exc())
        except Exception as error:r.update(status='not_evaluable',error=repr(error),original_stack=traceback.format_exc())
        results.append(r)
    result=dict(experiment_id=plan['experiment_id'],evidence='PC archived fixture' if fixture else 'prospective background/timing contrast',
        receipt=receipt,plan_sha256=p.digest(file),sessions=results,contrasts=contrasts(results,contract),
        consumption=shared.consumption(plan),new_fit=0,post_load_ap_used_as_input=False,
        independent_confirmation_of_new_model=0,accuracy_pass=None,strict_support=False,experiment_ready=False,device_commands=0)
    common.write_json(output/'summary.json',result)
    common.write_json(output/'inventory.json',[dict(path=f.relative_to(root).as_posix(),bytes=f.stat().st_size,sha256=p.digest(f)) for f in sorted(root.rglob('*')) if f.is_file()])
    if paths:
        common.write_csv(output/'paths.csv',paths)
        try:plot(output,paths,results,fixture)
        except Exception as error:common.write_json(output/'plot_error.json',dict(error=repr(error),stack=traceback.format_exc()))
    return result


def plot(output,paths,results,fixture):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(6,2,figsize=(12,16),constrained_layout=True)
    for i,r in enumerate(results):
        pp=[p for p in paths if p['role']==r['role']]
        for ax in axes[i]:ax.set_title(r['role']);ax.set_xlabel('Common-origin seconds');ax.grid(alpha=.2)
        if not pp:
            for ax in axes[i]:ax.text(.1,.5,'Not evaluable; no zero fill',transform=ax.transAxes)
            continue
        ts=[p['common_s'] for p in pp]
        axes[i,0].plot(ts,[p['observed_c'] for p in pp],label='Observed')
        axes[i,0].plot(ts,[p['predicted_c'] for p in pp],label='Fixed memory');axes[i,0].set_ylabel('AP C');axes[i,0].legend()
        axes[i,1].plot(ts,[p['residual_c'] for p in pp]);axes[i,1].axhline(0,color='gray');axes[i,1].set_ylabel('Predicted - observed C')
        if r.get('last_lane_s') is not None:
            for ax in axes[i]:ax.axvspan(r['first_dispatch_s'],r['last_lane_s'],color='gray',alpha=.15)
    fig.suptitle('PC archived fixture; NOT new data' if fixture else 'Fixed-candidate background/timing contrast; no accuracy PASS')
    fig.savefig(output/'paths.png',dpi=120);plt.close(fig)


if __name__=='__main__':
    q=argparse.ArgumentParser(description=__doc__);q.add_argument('--plan',required=True);q.add_argument('--output',required=True)
    q.add_argument('--pc-fixture',action='store_true');a=q.parse_args();r=report(a.plan,a.output,fixture=a.pc_fixture)
    print([s['status'] for s in r['sessions']])
