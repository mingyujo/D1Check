"""Posthoc idle history readout from preserved sessions. No device or fitting path."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_energy_thermal as energy
from tools import d1_preload_power_candidate as candidate
from tools.d1_resident_control_readout import ap_window

ORIGIN = candidate.ORIGIN
ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT/'docs/results/resident_history_01'


def export(source_root, output):
    """Add AP and the complete C/L pair to the already shared four-session samples."""
    if Path(output).exists():
        raise FileExistsError('fresh input only')
    root = Path(source_root)
    old_file = ROOT/'docs/results/resident_power_candidate_01/inputs.json'
    old = p.read(old_file)
    if old['frozen_sha256'] != candidate.FROZEN_SHA:
        raise ValueError('freeze identity mismatch')
    cases = old['cases']
    sources = {'previous_portable_bundle':p.digest(old_file)}
    for case, (_, run, prefix) in zip(cases, candidate.SPECS):
        folders = list((root/run).glob(prefix+'*'))
        if len(folders) != 1:
            raise ValueError('one exact session required')
        folder = folders[0]
        for key, sha in old['source_hashes'].items():
            name, filename = key.split('/')
            if name != case['case']:
                continue
            base = root/run if filename == 'FINAL_RECEIPT.json' else (
                folder if filename in ('validated.json','before_session_battery.txt','thermal.jsonl')
                else folder/'artifacts')
            if p.digest(base/filename) != sha:
                raise ValueError('original source changed: '+key)
            sources[key] = sha
        origin = p.read(folder/'artifacts/common_boundary.json')['start_ns']
        case['source_context']['apk_sha256'] = p.read(folder/'artifacts/manifest.json')['apk_sha256']
        case['ap_samples'] = relative_ap(folder/'thermal.jsonl', origin)
        case['work_requests'] = 24
        case['protocol_group'] = 'previous_four_loaded_sessions'
    pair_plan = root/'energy_ap_resident_control_plan_v3/collection_plan.json'
    plan = p.read(pair_plan)
    pair_summary_file = ROOT/'docs/results/resident_control_design_01/run03/summary.json'
    pair = p.read(pair_summary_file)
    if p.digest(pair_plan) != pair['plan_sha256'] or pair['completed_sessions'] != 2:
        raise ValueError('pair plan/completion mismatch')
    run = root/'energy_ap_resident_control_run_v3'
    if p.read(run/'FINAL_RECEIPT.json')['status'] != 'completed_descriptive_only':
        raise ValueError('pair not completed')
    sources['pair_plan'] = p.digest(pair_plan)
    sources['pair_shared_summary'] = p.digest(pair_summary_file)
    for entry, result in zip(plan['entries'], pair['cases']):
        folder = run/f"{entry['index']:02d}_{entry['session_id']}"
        role = entry['phase']
        for key, sha in pair['source_sha256'].items():
            source_role, filename = key.split('/')
            if source_role != role:
                continue
            base = folder if filename == 'thermal.jsonl' else folder/'artifacts'
            if p.digest(base/filename) != sha:
                raise ValueError('pair source changed: '+key)
            sources['pair/'+key] = sha
        a = folder/'artifacts'
        origin = p.read(a/'common_boundary.json')['start_ns']
        requests = p.read(a/'requests.json')
        if len(requests) != entry['requests'] or any(r['terminal_status'] != 'succeeded' for r in requests):
            raise ValueError('pair denominator incomplete')
        events = [json.loads(x) for x in (a/'progress.jsonl').read_text(encoding='utf-8').splitlines()]
        baseline = next(x['mono_ns'] for x in events if x['kind']=='phase_start' and x['phase']=='resident_baseline')
        samples = []
        for x in events:
            if x['kind'] != 'power_sample' or x['snapshot_start_ns'] < baseline:
                continue
            samples.append(dict(relative_ns=(x['snapshot_start_ns']+x['sensor_read_end_ns'])//2-origin,
                read_start_ns=x['snapshot_start_ns']-origin,read_end_ns=x['sensor_read_end_ns']-origin,
                current_raw=x['current_raw'],current_valid=x['current_valid'],voltage_mV=x['voltage_mV'],
                plugged=x['plugged'],active_count=len(x['active']),resident_keys=x['resident_keys'],phase=x['phase']))
        # Recorded app completion and resident snapshots support cooling idle;
        # no extension is used for a partial or failed session.
        battery = (folder/'before_session_battery.txt').read_text(encoding='utf-8')
        import re
        value = lambda key:int(re.search(r'(?m)^\s*'+key+r':\s*(\d+)\s*$',battery).group(1))
        cases.append(dict(case='control03_'+('C' if entry['index']==0 else 'L')+'_seen',
            source_context=dict(initial_ap_c=pair['sessions'][entry['index']]['host_start_ap_c'],
                battery_percent=value('level'),bat_c=value('temperature')/10,scenario='burst',
                apk_sha256=plan['apk_sha256'],
                observation_protocol='numeric-ap-observe-v2',whole_observed_j=result['windows']['common']['observed_j']),
            protocol_group='resident_control03_same_pair_fixed_C_then_L',work_requests=entry['requests'],
            baseline_start_ns=baseline-origin,samples=samples,states=result['states'],
            ap_samples=relative_ap(folder/'thermal.jsonl',origin)))
    frozen_file = root/'energy_ap_state_run_v5/development_freeze.json'
    if p.digest(frozen_file) != candidate.FROZEN_SHA:
        raise ValueError('original frozen file changed')
    bundle = dict(version='resident-history-portable-v1',cases=cases,original_power_w=old['original_power_w'],
        frozen_sha256=candidate.FROZEN_SHA,source_hashes=sources)
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(bundle,indent=2)+'\n',encoding='utf-8')
    return bundle


def relative_ap(path, origin):
    result = []
    for x in map(json.loads,Path(path).read_text(encoding='utf-8').splitlines()):
        if x.get('AP') in ('',None):
            continue
        value = float(x['AP'])
        if not math.isfinite(value):
            raise ValueError('invalid AP, not zero-filled')
        result.append(dict(relative_ns=x['mono_ns']-origin,ap_c=value,
            read_bracket_ns=x.get('after_ns',x['mono_ns'])-x.get('before_ns',x['mono_ns'])))
    return result


def validate_states(states):
    cursor = 0.
    for s in states:
        if not all(math.isfinite(s[k]) for k in ('start_s','end_s')) or abs(s['start_s']-cursor)>1e-8 or s['end_s']<=cursor:
            raise ValueError('state gap/overlap/nonfinite')
        cursor=s['end_s']
    if abs(cursor-120)>1e-8:
        raise ValueError('exact complete 120s state map required')


def window(case, lo, hi, idle_required=True):
    """Fixed endpoints; bracket missing or mixed idle is never a smaller replacement window."""
    validate_states(case['states'])
    samples = [dict(x,mono_ns=ORIGIN+x['relative_ns']) for x in case['samples']]
    samples = energy.canonical_samples(samples)[0]
    lo_ns,hi_ns=ORIGIN+round(lo*1e9),ORIGIN+round(hi*1e9)
    integrated=energy.integrate(samples,lo_ns,hi_ns,1000,2.5)
    inside=[x for x in samples if lo_ns<=x['mono_ns']<=hi_ns]
    touched=[(a,b) for a,b in zip(samples,samples[1:]) if min(b['mono_ns'],hi_ns)>max(a['mono_ns'],lo_ns)]
    brackets=[x for pair in touched for x in pair]
    keys={'classification_CPU','classification_GPU','detection_CPU','detection_GPU'}
    residents=bool(inside) and all(set(x['resident_keys'])==keys for x in brackets)
    occupied=any(s['state']!='idle' and s['start_s']<hi and s['end_s']>lo for s in case['states'])
    snapshot_idle=all(x['active_count']==0 for x in brackets)
    # Trapezoids touching an idle window must not import an active sensor endpoint
    # or hide a short request between their two samples.
    bracket_mixed=any(s['state']!='idle' and s['start_s']<(b['mono_ns']-ORIGIN)/1e9 and
        s['end_s']>(a['mono_ns']-ORIGIN)/1e9 for a,b in touched for s in case['states'])
    eligible=residents and (not idle_required or (not occupied and snapshot_idle and not bracket_mixed))
    actual=integrated['full_energy_j'] if eligible else None
    points=[(ORIGIN+x['relative_ns'],x['ap_c']) for x in case['ap_samples']]
    if any(b[0]<=a[0] for a,b in zip(points,points[1:])):
        raise ValueError('AP time ordering')
    ap=ap_window(points,lo_ns,hi_ns) if eligible else {'mean_c':None,'change_c':None,'reason':'not resident idle'}
    return dict(start_s=lo,end_s=hi,observed_j=actual,mean_w=None if actual is None else actual/(hi-lo),
        power_samples=len(inside),missing_s=integrated['missing_s'],resident_eligible=residents,
        state_eligible=eligible,idle_required=idle_required,ap_mean_c=ap.get('mean_c'),
        ap_start_c=ap.get('start_c'),ap_end_c=ap.get('end_c'),ap_change_c=ap.get('change_c'),
        ap_reason=ap.get('reason'),reason=None if eligible and actual is not None else
            ('mixed_or_nonresident' if not eligible else 'power_bracket_or_gap_missing'))


def analyze(bundle_file, contract_file, output):
    if Path(output).exists():
        raise FileExistsError('preserve prior analysis')
    bundle,contract=p.read(bundle_file),p.read(contract_file)
    expected={'pre':[5,30],'late_common':[90,120],'late_cooling':[150,180],'common':[0,120]}
    if contract['fixed_windows_seconds']!=expected or contract['bins_seconds']!=10 or contract['new_candidate_count']!=0 or \
        contract['bin_extent_seconds']!=[0,180] or contract['max_power_gap_s']!=2.5 or contract['max_ap_gap_s']!=10:
        raise ValueError('no adaptive window/candidate search')
    if bundle['frozen_sha256']!=candidate.FROZEN_SHA or len(bundle['cases'])!=6:
        raise ValueError('six exact preserved sessions required')
    prefix_contract=p.read(ROOT/'docs/results/resident_power_candidate_01/contract.json')
    fixed=[];bins=[];scores=[];metadata=[]
    for case in bundle['cases']:
        windows={}
        for name,(lo,hi) in expected.items():
            windows[name]=window(case,lo,hi,name!='common')
            fixed.append(dict(case=case['case'],window=name,**windows[name]))
        a,b=windows['pre']['mean_w'],windows['late_common']['mean_w']
        metadata.append(dict(case=case['case'],work_requests=case['work_requests'],
            context=case['source_context'],protocol_group=case['protocol_group'],
            pre_to_late_w=None if a is None or b is None else b-a,
            load_end_s=max((s['end_s'] for s in case['states'] if s['state']!='idle'),default=None)))
        for lo in range(0,180,10):
            bins.append(dict(case=case['case'],**window(case,lo,lo+10)))
        if case['work_requests']:
            info,rows,_=candidate.evaluate_case(case,prefix_contract,bundle['original_power_w'])
            scores.extend(rows)
            metadata[-1]['existing_candidate_prefix']=info
        else:
            metadata[-1]['existing_candidate_prefix']=None
    # Historical scores are reused as identity checks, not rerun policy batches.
    previous=ROOT/'docs/results/resident_power_candidate_01/readout/scores.csv'
    old=list(csv.DictReader(previous.open(encoding='utf-8')))
    for row in old:
        match=next(x for x in scores if x['case']==row['case'] and x['phase']==row['phase'])
        for key in ('observed_j','original_j','candidate_j','original_error_j','candidate_error_j'):
            if not math.isclose(match[key],float(row[key]),rel_tol=0,abs_tol=1e-8):
                raise ValueError('previous candidate arithmetic changed')
    c,l=[next(x for x in metadata if x['case']==name) for name in ('control03_C_seen','control03_L_seen')]
    loaded=[x for x in scores if x['phase']=='future_total']
    changed=[x for x in metadata if x['pre_to_late_w'] is not None]
    bin_summary=[]
    for case in metadata:
        points=[r for r in bins if r['case']==case['case']]
        valid=[r['mean_w'] for r in points if r['mean_w'] is not None]
        steps=[b['mean_w']-a['mean_w'] for a,b in zip(points,points[1:])
               if a['mean_w'] is not None and b['mean_w'] is not None]
        bin_summary.append(dict(case=case['case'],eligible_bins=len(valid),
            mixed_or_missing_bins=len(points)-len(valid),min_mean_w=min(valid) if valid else None,
            max_mean_w=max(valid) if valid else None,adjacent_increases=sum(x>0 for x in steps),
            adjacent_decreases=sum(x<0 for x in steps),meaning='descriptive correlated bins; not independent sessions or prediction bounds'))
    result=dict(id=contract['id'],cases=metadata,case_count=6,control_sessions=1,loaded_sessions=5,
        pair_difference_of_changes_w=l['pre_to_late_w']-c['pre_to_late_w'],
        fixed_pre_late_increases=sum(x['pre_to_late_w']>0 for x in changed),
        fixed_pre_late_decreases=sum(x['pre_to_late_w']<0 for x in changed),
        fixed_pre_late_ineligible=len(metadata)-len(changed),
        existing_candidate_improved=sum(abs(x['candidate_error_j'])<abs(x['original_error_j']) for x in loaded),
        existing_candidate_worsened=sum(abs(x['candidate_error_j'])>abs(x['original_error_j']) for x in loaded),
        history_coefficients_identified=False,new_fitted_parameters=0,new_candidate_count=0,
        causal_attribution=False,independent_validation=False,policy_rank=None,accuracy_pass=None,
        strict_support=False,experiment_ready=False,device_commands=0,
        simulation_scope=dict(recorded_idle_accounting='supported_only_on_exact_observed_windows',
            frozen_equation='conditional_extrapolation_diagnostic_only_on_these_six_sessions',
            preload_offset_candidate='not_adopted_2_improved_3_worsened',
            transferable_time_or_history_power_law='not_identified',
            dynamic_energy_policy_rank=None,ap_candidate='unchanged_separate_evidence',
            schedule_response='no_new_validation_in_this_analysis'),
        identifiability_limit='One control, unmatched initial background/thermal history, fixed order, all outcomes seen; time/temperature/load-history effects not separately identified.',
        frozen_sha256=candidate.FROZEN_SHA,bundle_sha256=p.digest(bundle_file),contract_sha256=p.digest(contract_file),
        analysis_code_sha256=p.digest(__file__),existing_prefix_contract_sha256=p.digest(ROOT/'docs/results/resident_power_candidate_01/contract.json'))
    output=Path(output);output.mkdir(parents=True)
    for name,data in [('fixed_windows.csv',fixed),('idle_bins.csv',bins),('idle_bin_summary.csv',bin_summary),('existing_candidate_scores.csv',scores)]:
        with (output/name).open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    plot(bins,metadata,bundle['original_power_w']['resident_idle'],output)
    return result


def plot(rows,metadata,frozen_w,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,2,figsize=(12,10))
    for ax,case in zip(axes.flat,metadata):
        bins=[r for r in rows if r['case']==case['case']]
        ax.plot([(r['start_s']+r['end_s'])/2 for r in bins],
            [float('nan') if r['mean_w'] is None else r['mean_w'] for r in bins],marker='o',label='10s resident-idle mean W')
        ax.axhline(frozen_w,ls='--',color='gray',label='Original frozen idle W')
        for r in bins:
            if r['reason'] is not None:
                ax.axvspan(r['start_s'],r['end_s'],alpha=.12,color='red' if not r['state_eligible'] else 'gray')
        ax.set_title(case['case']+'; initial AP '+str(case['context']['initial_ap_c'])+' C')
        ax.set_ylabel('Whole-device W; raw=mA conditional');ax.set_xlabel('Common-origin seconds')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Six previously seen sessions: descriptive idle time/history\nRed = mixed/nonidle; gray = missing bracket; no causal fit or policy ranking')
    fig.tight_layout()
    for ext in ('png','svg'):
        file=output/('idle_history.'+ext);fig.savefig(file,dpi=150)
        if ext=='svg':file.write_text('\n'.join(x.rstrip() for x in file.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)


def main():
    q=argparse.ArgumentParser(description=__doc__);s=q.add_subparsers(dest='action',required=True)
    ex=s.add_parser('export');ex.add_argument('--source-root',required=True);ex.add_argument('--output',required=True)
    an=s.add_parser('analyze');an.add_argument('--bundle',required=True);an.add_argument('--contract',required=True);an.add_argument('--output',required=True)
    a=q.parse_args()
    if a.action=='export':print('Exported cases:',len(export(a.source_root,a.output)['cases']))
    else:print(json.dumps(analyze(a.bundle,a.contract,a.output),indent=2))


if __name__=='__main__':main()
