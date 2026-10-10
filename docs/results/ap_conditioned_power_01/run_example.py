"""Recorded CPU/AP conditional cost example. No oracle or measurement input."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_ap_conditioned_power as m


def example(identity):
    out=m.BUNDLE/'run_v1';m.assets(out);receipt=m.old.old.read(out/'fit_receipt.json')
    for key,h in receipt['model_hashes'].items():
        if m.old.old.sha(out/('candidate_'+key+'.json'))!=h:raise ValueError('candidate changed')
    public=next(p for p in m.public_cases(out) if p['id']==identity)
    key=str(public['gap']) if public['role']=='development' else 'final';model=m.old.old.read(out/('candidate_CPU_AP_'+key+'.json'))
    original=m.old.old.read(m.old.old.prior.prior.old.analysis.j.m.MODEL);power=dict(idle_bias_w=0.,increments=original['energy_increment_w'])
    return dict(session=identity,predicted_reference120_J=m.prediction(public,model,power,0,120,opt_in=True),
        predicted_future85_J=m.prediction(public,model,power,35,120,opt_in=True),power_head='original_frozen',
        forecast='CPU_AP_unadopted',window_s=[0,120],actual_schedule_conditional=True,
        future_measured_AP_used=False,oracle_available_in_prediction=False,live_feature_delivery_implemented=False,
        default_changed=False,RL_changed=False,strict_support=False,accuracy_pass=None,experiment_ready=False,
        new_fits=0,new_AP_initializations=0,device_commands=0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',default='confirmation_180_C0');p.add_argument('--opt-in',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
    if not a.opt_in:p.error('explicit --opt-in required; unadopted recorded diagnostic only')
    m.old.old.write(Path(a.output),example(a.session))
