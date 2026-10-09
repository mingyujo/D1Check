"""Use the separate guarded cost API on a stored case. No phone/fit/RL execution."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import d1_energy_ap_zero_offset as api


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--opt-in',action='store_true')
    p.add_argument('--profile',choices=('C0_LONG','LOAD_A_LONG'),default='LOAD_A_LONG')
    p.add_argument('--window',choices=('registered600','matched'),default='registered600');a=p.parse_args()
    case=next(c for c in api.old.analysis.j.m.read(ROOT/'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz') if c['policy']==a.profile)
    context=api.old.analysis.j.m.read(Path(__file__).with_name('recorded_contexts.json'))[case['id']]
    lo,hi=(35.,635.) if a.window=='registered600' else (max(35.,case['q'][0],case['power_t'][0]),min(case['q'][-1],case['power_t'][-1]))
    indices=[i for i,t in enumerate(case['q']) if lo<=t<=hi]
    query_case=dict(case,q=[case['q'][i] for i in indices])
    result=api.forecast(query_case,context,Path(__file__).with_name('run_v1'),opt_in=a.opt_in,lo_s=lo,hi_s=hi)
    if result['status']=='diagnostic_energy_AP_only':
        # Targets only enter after the prediction has returned.
        observed=api.old.observed.measured_energy(case,lo,hi)['full_energy_j']
        result.update(recorded_example=True,energy_observed_j=observed,
            energy_signed_error_j=result['energy_prediction_j']-observed if observed is not None else None,
            AP_MAE_c=sum(abs(y-case['ap'][i]) for y,i in zip(result['prediction_ap_c'],indices))/len(indices),
            target_used_only_after_prediction=True,energy_evidence='posthoc_seen_long_not_new_confirmation',
            AP_evidence='fixed_candidate_previously_confirmed_on_this_recording')
    api.write(Path(a.output),result)
    print(api.terminal_json({key:result[key] for key in ('status','energy_prediction_j','strict_support','accuracy_pass')}))


if __name__=='__main__':main()
