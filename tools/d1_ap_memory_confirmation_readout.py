"""Frozen preparation-memory confirmation readout; never calls fitting functions."""
import argparse
import csv
import json
import math
import traceback
from pathlib import Path
from tools import d1_ap_memory_confirmation as plan_module
from tools import d1_ap_preparation_memory as model
from tools import d1_ap_model_completion as scores
from tools import d1_ap_bundle_readout as shared
from tools import d1_ap_transfer_confirmation as transfer
from tools import d1_arrival_recorded_replay_analysis as states
from tools import d1_arrival_energy_analysis as descriptive

p,require=transfer.p,transfer.old.require


def case_from_session(plan_file,plan,entry):
    folder=Path(plan['output_root'])/f"{entry['index']:02d}_{entry['session_id']}"
    art=folder/'artifacts';manifest_file=Path(plan_file).parent/entry['manifest']
    require(p.digest(manifest_file)==entry['manifest_sha256'] and p.read(art/'manifest.json')==p.read(manifest_file),
            'recovered manifest mismatch')
    boundary=p.read(art/'common_boundary.json');origin=boundary['start_ns']
    require(boundary['planned_end_ns']-origin==120_000_000_000,'common window changed')
    rows=p.read(art/'requests.json');manifest=p.read(manifest_file)
    require(len(rows)==24 and {r['request_id'] for r in rows}=={r['request_id'] for r in manifest['requests']},
            'request denominator/identity')
    require(all(r['terminal_status']=='succeeded' and origin<=r['dispatch_ns']<r['lane_available_ns']<origin+120_000_000_000
                for r in rows),'unfinished requests')
    initial=p.read(art/'start_ap.accepted.json')
    require(initial['gate_mode']=='numeric-ap-observe-v2' and initial['common_start_ns']==origin,'AP boundary/mode')
    events=descriptive.read_lines(art/'progress.jsonl')
    baseline=[x['mono_ns'] for x in events if (x.get('phase'),x.get('kind'))==('resident_baseline','phase_start')]
    cooling=[x['mono_ns'] for x in events if (x.get('phase'),x.get('kind'))==('resident_cooling','phase_end')]
    require(len(baseline)==len(cooling)==1 and baseline[0]<origin and cooling[0]>origin+120_000_000_000,
            'baseline/cooling boundary')
    first=min(r['dispatch_ns'] for r in rows);last=max(r['lane_available_ns'] for r in rows)
    thermal=descriptive.read_lines(folder/'thermal.jsonl')
    good=[x for x in thermal if x.get('AP') not in ('',None) and x['thermal_status']=='0']
    pre=[dict(t=(x['mono_ns']-origin)/1e9,ap=float(x['AP']),lo=(x['before_ns']-origin)/1e9,
              hi=(x['after_ns']-origin)/1e9) for x in good if baseline[0]<=x['before_ns']<=x['after_ns']<first]
    post=[x for x in good if first<=x['before_ns']<=x['after_ns']<=cooling[0]]
    ts=[(x['mono_ns']-origin)/1e9 for x in post];end=(cooling[0]-origin)/1e9
    require(len(ts)>=20 and ts[0]-(first-origin)/1e9<=10 and end-ts[-1]<=10 and
            all(0<b-a<=10 for a,b in zip(ts,ts[1:])),'post-load AP coverage')
    observed=[float(x['AP']) for x in post]
    require(all(math.isfinite(x) for x in observed),'nonfinite target AP')
    segments=[*states.observed_segments(rows,origin),dict(start_s=120.,end_s=end,state='idle')]
    return dict(id=entry['phase'],inputs=dict(preload=pre,segments=segments,query_s=ts,initial_ap_c=initial['ap_c']),
                observed_ap_c=observed,first_dispatch_s=(first-origin)/1e9,last_lane_s=(last-origin)/1e9,
                protocol='current signed APK; registered 35/65 second passive interval')


def predict_fixed(case,plan):
    require(p.digest(plan['memory_candidate']['path'])==plan_module.CANDIDATE_SHA,'fixed memory candidate changed')
    candidate=p.read(plan['memory_candidate']['path'])
    return model.predict(case,candidate['fixed_parameters'],candidate['tau_s'],candidate['gamma'])


def report(file,output,*,fixture=False):
    file,output=Path(file),Path(output);plan=p.read(file);root=Path(plan['output_root'])
    for protected in (root,Path(plan['registry']),file.parent):
        require(output.resolve()!=protected.resolve() and protected.resolve() not in output.resolve().parents,
                'protected evidence/plan output')
    require(not output.exists(),'fresh readout output')
    require(plan['experiment_id']==plan_module.EXPERIMENT and plan['source_code']==plan_module.identity(),
            'frozen plan/code differs')
    for key in ('memory_candidate','candidate_freeze','frozen_model','analysis_contract'):
        require(p.digest(plan[key]['path'])==plan[key]['sha256'],'frozen resource differs')
    require(p.digest(root/'memory_candidate_freeze.json')==plan['memory_candidate']['sha256'] and
            p.digest(root/'memory_analysis_contract.json')==plan['analysis_contract']['sha256'],
            'execution freeze differs')
    receipt=p.read(root/'FINAL_RECEIPT.json');contract=p.read(plan['analysis_contract']['path'])
    output.mkdir(parents=True);result=[]
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}"
        attempts=receipt.get('session_attempts',receipt.get('sessions'))
        not_attempted=isinstance(attempts,int) and entry['index']>=attempts and not folder.exists()
        item=dict(role=entry['phase'],status='not_attempted' if not_attempted else 'incomplete',scores=None,
                  independent_sessions=0,accuracy_pass=None)
        if (folder/'validated.json').exists():
            try:
                require(p.read(folder/'validated.json')['status']=='eligible_descriptive_only','session not eligible')
                case=case_from_session(file,plan,entry);predicted,init=predict_fixed(case,plan)
                ts=case['inputs']['query_s'];observed=case['observed_ap_c']
                reference=transfer.candidate.preload_reference([(v['t'],v['ap']) for v in case['inputs']['preload']],
                    p.read(plan['memory_candidate']['path'])['fixed_parameters']['ap_cooling_rate_per_s'])
                original=p.read(plan['frozen_model']['path'])
                old_path=transfer.candidate.predict(case['inputs']['segments'],original,
                    case['inputs']['initial_ap_c'],reference['effective_idle_reference_c'],ts)
                previous=[old_path[round(t,9)] for t in ts]
                table=[dict(elapsed_s=t,observed_ap_c=y,candidate_ap_c=v,existing_preload_ap_c=o,
                            signed_error_c=v-y,phase='post_load_idle' if t>case['last_lane_s'] else 'work_span')
                       for t,y,v,o in zip(ts,observed,predicted,previous)]
                dest=output/entry['phase'];dest.mkdir()
                scores.write_csv(dest/'ap_paths.csv',table)
                scores.write_json(dest/'prediction_inputs.json',dict(case=case['inputs'],initialization=init,
                    first_dispatch_s=case['first_dispatch_s'],last_lane_s=case['last_lane_s'],post_load_ap_used=False))
                direction_table=[dict(r,frozen_ap_c=r['existing_preload_ap_c']) for r in table]
                directions=[shared.direction(direction_table,*window) for window in contract['direction_windows_s']]
                for direction in directions:
                    if 'frozen_change_c' in direction:
                        direction['existing_preload_change_c']=direction.pop('frozen_change_c')
                phases=[]
                for phase in ('work_span','post_load_idle'):
                    rr=[r for r in table if r['phase']==phase]
                    if rr:phases.append(dict(phase=phase,samples=len(rr),**scores.score(
                        [r['observed_ap_c'] for r in rr],[r['candidate_ap_c'] for r in rr])))
                item.update(status='pc_fixture' if fixture else 'evaluated_fixed_candidate',
                    independent_sessions=0 if fixture else 1,scores=scores.score(observed,predicted),
                    existing_preload_scores=scores.score(observed,previous),initialization=init,
                    sample_start_s=ts[0],sample_end_s=ts[-1],samples=len(ts),directions=directions,phase_scores=phases,
                    initial_ap_c=case['inputs']['initial_ap_c'],initial_ap_in_original_range=
                    original['initial_ap_development_range_c'][0]<=case['inputs']['initial_ap_c']<=original['initial_ap_development_range_c'][1])
                # Secondary existing energy/original-AP comparison cannot erase AP evidence.
                try:
                    item['legacy_comparison']=transfer.readout_session(file,plan,entry,dest/'legacy')
                except Exception as error:item['legacy_comparison_error']=dict(error=repr(error),stack=traceback.format_exc())
            except Exception as error:
                item.update(status='analysis_ineligible',error=repr(error),original_stack=traceback.format_exc())
        result.append(item)
    summary=dict(experiment_id=plan['experiment_id'],receipt=receipt,sessions=result,
        consumption=shared.consumption(plan),candidate_sha256=plan['memory_candidate']['sha256'],
        plan_sha256=p.digest(file),new_coefficients=0,post_load_refit=False,
        prediction='offline fixed-parameter reconstruction using only pre-load AP and actual lane schedule',
        evidence='PC existing-session fixture' if fixture else 'prospective fixed candidate; one session per passive preparation interval',
        accuracy_pass=None,strict_support=False,experiment_ready=False,device_commands=0)
    scores.write_json(output/'summary.json',summary)
    return summary


def main():
    q=argparse.ArgumentParser(description=__doc__);q.add_argument('--plan',required=True);q.add_argument('--output',required=True)
    q.add_argument('--pc-fixture',action='store_true');a=q.parse_args()
    result=report(a.plan,a.output,fixture=a.pc_fixture)
    print(json.dumps(dict(statuses=[x['status'] for x in result['sessions']],device_commands=0)))


if __name__=='__main__':main()
