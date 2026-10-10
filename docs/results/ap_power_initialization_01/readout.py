"""Direction and energy arithmetic only; no fitted gain replacement or new candidate."""
import argparse
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_ap_power_initialization as m


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);source=m.BUNDLE/'run_v1';m.assets(source)
    fit=m.previous.old.old.read(source/'fit_receipt.json')
    for key,h in fit['model_hashes'].items():
        if m.previous.old.old.sha(source/('candidate_'+key+'.json'))!=h:raise ValueError('frozen gain changed')
    public=m.previous.old.old.read(source/'pre_inputs.json');AP=m.previous.table(source/'AP_errors.csv')
    paths=m.previous.table(source/'AP_paths.csv');stored=m.previous.table(ROOT/'docs/results/preboundary_evidence_01/run_v1/AP_paths.csv')
    legacy={(r['session'],r['t_s']):float(r['predicted_c']) for r in stored if r['variant']=='registered_idle_pre'}
    maximum=max(abs(float(r['predicted_c'])-legacy[(r['session'],r['t_s'])]) for r in paths if r['variant']=='registered_idle_control')
    assert maximum<1e-12
    directions=[];pairs=[];esummary=[];E=m.previous.table(source/'energy_link_errors.csv')
    for p in public:
        key=str(p['gap']) if p['role']=='development' else 'final';model=m.previous.old.old.read(source/('candidate_'+key+'.json'))
        if p['id'].endswith('_C0'):
            x,_,zt,zh,_,norm,_=m.design(p,model['beta_fixed']);dr,dh=-m.solve(x,zt,norm)
            span=p['pre_AP'][-1]['t']-p['pre_AP'][0]['t'];dh_last=dh*np.exp(-span/30.)+zh[-1]
            anchor=p['pre_AP'][-1]['t'];beta=model['beta_fixed']
            def unit(t):
                dt=t-anchor;return dr*(1-np.exp(-beta*dt))+dh_last*m.memory.convolution(beta,30.,dt)
            for phase in ('common85','full_AP'):
                r=next(r for r in AP if r['session']==p['id'] and r['phase']==phase and r['variant']=='registered_idle_control')
                change=float(r['predicted_change_c']);slope=float(unit(float(r['last_sample_s']))-unit(float(r['first_sample_s'])))
                crossing=-change/slope if abs(slope)>1e-15 and -change/slope>0 else None
                directions.append(dict(session=p['id'],role=p['role'],phase=phase,control_predicted_change_c=change,
                    predicted_change_per_unit_gain_c=slope,registered_fitted_gain=model['gain_C_per_J'],
                    positive_gain_at_zero_predicted_change=crossing,
                    registered_rounding_gain_lower=model['constrained_gain_rounding_interval'][0],registered_rounding_gain_upper=model['constrained_gain_rounding_interval'][1],
                    direction_crossing_exceeds_assumed_rounding_upper=crossing>model['constrained_gain_rounding_interval'][1] if crossing is not None else None,
                    no_observed_future_AP_used_in_threshold=True,threshold_not_used_as_gain=True))
        for phase in ('common85','full_AP','post_lane_idle','work_present'):
            use={r['variant']:r for r in AP if r['session']==p['id'] and r['phase']==phase}
            if not use:continue
            a,b=use[m.AP_VARIANTS[0]],use[m.AP_VARIANTS[1]]
            pairs.append(dict(session=p['id'],role=p['role'],gap=p['gap'],phase=phase,
                old_MAE_c=float(a['MAE_c']),new_MAE_c=float(b['MAE_c']),change_MAE_c=float(b['MAE_c'])-float(a['MAE_c']),
                old_max_c=float(a['max_absolute_c']),new_max_c=float(b['max_absolute_c']),
                old_peak_signed_c=float(a['peak_signed_c']),new_peak_signed_c=float(b['peak_signed_c']),
                old_direction_match=a['direction_match'],new_direction_match=b['direction_match']))
    for role in ('development','confirmation'):
        for head in ('original_frozen','zero_offset'):
            for phase in ('reference120','future85','post_lane_idle'):
                for variant in m.AP_VARIANTS:
                    allrows=[r for r in E if r['role']==role and r['head']==head and r['phase']==phase and r['variant']==variant]
                    use=[r for r in allrows if r['absolute_J']]
                    if use:esummary.append(dict(role=role,head=head,phase=phase,variant=variant,planned_sessions=len(allrows),eligible_sessions=len(use),
                        mean_abs_J=float(np.mean([float(r['absolute_J']) for r in use])),maximum_abs_J=max(float(r['absolute_J']) for r in use),
                        is_previous_rejected_energy_relation=True))
    for name,rows in [('C0_direction_gain',directions),('AP_paired_errors',pairs),('energy_link_summary',esummary)]:m.energy.old.scope_api.tail.s.csv_write(out/(name+'.csv'),rows)
    m.previous.old.old.write(out/'receipt.json',dict(status='fixed_family_attribution_complete',new_global_fits=0,
        pre_power_basis_projections=4,new_AP_state_fits=0,control_paths_match_old_max_error_c=maximum,
        contract_sha256=m.previous.old.old.sha(m.BUNDLE/'readout_contract.json'),direction_threshold_not_used_for_prediction=True,
        device_commands=0,default_changed=False,RL_changed=False,strict_support=False,experiment_ready=False))
    print(m.energy.terminal_json([r for r in directions if r['session']=='confirmation_30_C0']))
    print(m.energy.terminal_json([r for r in esummary if r['role']=='confirmation' and r['phase']=='reference120']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
