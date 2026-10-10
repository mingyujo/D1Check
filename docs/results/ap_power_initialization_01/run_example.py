"""One actual-schedule AP replay at frozen pre-only gain, no fit/device action."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_ap_power_initialization as m


def example(identity):
    out=m.BUNDLE/'run_v1';m.assets(out);r=m.previous.old.old.read(out/'fit_receipt.json')
    for key,h in r['model_hashes'].items():
        if m.previous.old.old.sha(out/('candidate_'+key+'.json'))!=h:raise ValueError('frozen gain changed')
    p=next(p for p in m.previous.old.old.read(out/'pre_inputs.json') if p['id']==identity)
    c=next(c for c in m.previous.old.old.history() if c['id']==identity)
    key=str(p['gap']) if p['role']=='development' else 'final';model=m.previous.old.old.read(out/('candidate_'+key+'.json'))
    init=m.initialize(p,model);original=m.previous.old.old.read(m.energy.old.analysis.j.m.MODEL)
    ap=m.previous.old.old.read(ROOT/'docs/results/ap_tail_identification_01/run_v2/candidates.json')['LOAD_SLOW']
    q=[float(t) for t in c['q'] if 35<=t<=180];y=m.AP_predict(p,init,original,ap,q,c['actual'],opt_in=True)
    return dict(session=identity,query_s=q,predicted_AP_c=y,initial=init,gain_C_per_J=model['gain_C_per_J'],
        actual_schedule_conditional=True,future_temperature_and_power_inputs=False,posthoc=True,
        default_changed=False,RL_changed=False,strict_support=False,accuracy_pass=None,experiment_ready=False,
        new_global_fits=0,new_local_pre_state_estimates=1,AP_replays=1,device_commands=0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',default='confirmation_30_C0');p.add_argument('--opt-in',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
    if not a.opt_in:p.error('explicit --opt-in required; recorded diagnostic only')
    m.previous.old.old.write(Path(a.output),example(a.session))
