"""One frozen recorded-baseline diagnostic example; no refit or device access."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_registered_baseline as m


def example(identity):
    out=m.BUNDLE/'run_v1';m.assets(out);receipt=m.old.read(out/'fit_receipt.json')
    for key,h in receipt['model_hashes'].items():
        if m.old.sha(out/('candidate_'+key+'.json'))!=h:raise ValueError('candidate changed')
    p=next(p for p in m.old.read(out/'pre_inputs.json') if p['id']==identity)
    key=str(p['gap']) if p['role']=='development' else 'final';model=m.old.read(out/('candidate_'+key+'.json'))
    fixed,_=m.old.prior.prior.read_candidate(m.old.prior.prior.BUNDLE/'run_v1')
    return dict(session=identity,power_head='existing_zero_offset',
        initializer='FULL_CPU',reference120_J=m.predict(p,model,fixed,0,120,opt_in=True),
        future85_J=m.predict(p,model,fixed,35,120,opt_in=True),window_s=[0,120],hypothetical_issue_s=35,
        actual_schedule_conditional=True,offline_recorded_only=True,online_export_available=False,
        accuracy_pass=None,default_changed=False,RL_changed=False,AP=None,strict_support=False,
        experiment_ready=False,global_fits=0,device_commands=0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',default='confirmation_30_C0');p.add_argument('--opt-in',action='store_true');p.add_argument('--output',required=True);a=p.parse_args()
    if not a.opt_in:p.error('--opt-in required; recorded diagnostic only')
    m.old.write(Path(a.output),example(a.session))
