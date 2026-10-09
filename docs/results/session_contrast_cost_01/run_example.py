"""Explicit, unadopted transfer candidate example; no fit/simulator/device calls."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import d1_session_contrast_cost as api


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--opt-in',action='store_true')
    p.add_argument('--window',choices=('registered600','matched'),default='registered600');a=p.parse_args()
    case=api.prior.old.analysis.j.m.read(ROOT/'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')[1]
    context=api.prior.old.analysis.j.m.read(api.prior.BUNDLE/'recorded_contexts.json')[case['id']]
    lo,hi=(35.,635.) if a.window=='registered600' else (max(35.,case['q'][0],case['power_t'][0]),min(case['q'][-1],case['power_t'][-1]))
    indices=[i for i,t in enumerate(case['q']) if lo<=t<=hi]
    result=api.forecast(dict(case,q=[case['q'][i] for i in indices]),context,Path(__file__).with_name('run_v1'),opt_in=a.opt_in,lo_s=lo,hi_s=hi)
    if result['status']=='diagnostic_energy_AP_only':
        observed=api.prior.old.observed.measured_energy(case,lo,hi)['full_energy_j']
        result.update(observed_j=observed,signed_J=result['energy_prediction_j']-observed if observed is not None else None,
            AP_MAE_c=sum(abs(y-case['ap'][i]) for y,i in zip(result['prediction_ap_c'],indices))/len(indices),
            targets_used_only_after_prediction=True,adopted=False,primary_recommended_bundle='energy_ap_zero_offset_01_with_fixed_LOAD_SLOW')
    api.prior.write(Path(a.output),result)
    print(api.prior.terminal_json({k:result.get(k) for k in ('status','selected_heads','signed_J','AP_MAE_c','strict_support','accuracy_pass')}))


if __name__=='__main__':main()
