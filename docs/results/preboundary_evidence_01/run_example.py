"""Explicit recorded-history input diagnostic; no current device gate or model fit."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import d1_preboundary_evidence as e


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--opt-in',action='store_true')
    p.add_argument('--session',default='confirmation_180_C0');a=p.parse_args()
    if not a.opt_in:raise ValueError('explicit recorded-initialization diagnostic opt-in required')
    reg=e.current.prior.old.analysis.j.m.read(Path(__file__).with_name('registration.json'))
    data_folder=Path(__file__).with_name('run_v1')
    for name,h in reg['inputs'].items():
        if e.current.prior.old.scope_api.sha(data_folder/name)!=h:raise ValueError('recorded input changed')
    for path,h in reg['sources'].items():
        if e.current.prior.old.scope_api.sha(ROOT/path)!=h:raise ValueError('source/model changed')
    inputs=e.current.prior.old.analysis.j.m.read(data_folder/'expanded_pre.json')
    row=next((r for r in inputs if r['id']==a.session),None)
    if row is None:raise ValueError('recorded history input unavailable;no substitution')
    c=next(r for r in e.current.cases() if r['id']==a.session)
    model=e.current.prior.old.scope_api.read_assets()[2];original=e.current.prior.old.analysis.j.m.read(e.current.prior.old.analysis.j.m.MODEL)
    y,_=e.compare(c,row['expanded_pre'],original,model)
    score=e.current.prior.old.observed.phase_score(c,y,35.,c['actual'][-1]['end_s'])
    result=dict(status='recorded_history_initialization_diagnostic_only',prediction_ap_c=y,query_s=c['q'],
        score_after_prediction=score,observed_initial_AP_c=c['pre'][-1]['ap'],initialization_inputs_latest_s=row['expanded_pre'][-1]['hi'],
        forecast_issue_s=35.,actual_schedule_conditional=True,post_AP_used_to_predict=False,
        energy_prediction_j=None,current_device_gate=False,strict_support=False,accuracy_pass=None,experiment_ready=False,default_changed=False,device_commands=0)
    e.write(Path(a.output),result)
    print(e.current.prior.terminal_json(dict(status=result['status'],AP_MAE_c=score['mae_c'],device_commands=0,coefficients_changed=False)))


if __name__=='__main__':main()
