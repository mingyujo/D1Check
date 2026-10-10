"""Analytic pre-training loss at a diagnostic threshold, not a gain fit/selection."""
import argparse
import sys
from pathlib import Path
import math
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_ap_power_initialization as m


def run(output):
    path=Path(output)
    if path.exists():raise ValueError('new output only')
    source=m.BUNDLE/'run_v1';m.assets(source);rows=[]
    for row in m.previous.table(m.BUNDLE/'readout_v1/C0_direction_gain.csv'):
        value=row['positive_gain_at_zero_predicted_change']
        if not value:continue
        key=row['session'].split('_')[1] if row['role']=='development' else 'final'
        model=m.previous.old.old.read(source/('candidate_'+key+'.json'));g=float(value)
        loss=model['weighted_pre_residual_RMSE_c']**2+model['residual_power_information']*((g-model['unconstrained_gain_C_per_J'])**2-(model['gain_C_per_J']-model['unconstrained_gain_C_per_J'])**2)
        if loss<0:raise ValueError('invalid quadratic residual attribution')
        rows.append(dict(session=row['session'],phase=row['phase'],direction_threshold_gain=g,
            registered_gain=model['gain_C_per_J'],registered_development_pre_RMSE_c=model['weighted_pre_residual_RMSE_c'],
            hypothetical_profiled_pre_RMSE_at_threshold_c=math.sqrt(loss),new_fits=0,
            threshold_not_used_for_forecast=True,posthoc_arithmetic=True))
    m.energy.old.scope_api.tail.s.csv_write(path,rows)
    print(m.energy.terminal_json([r for r in rows if r['session']=='confirmation_30_C0']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
