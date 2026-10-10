"""One read-only recorded diagnostic example, no fitting or device interaction."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_cpu_prebaseline as m


def example(identity):
    out=m.BUNDLE/'run_v1';reg=m.read(out/'registration.json')
    amendment=m.read(m.BUNDLE/'source_amendment.json')
    for p,h in reg['sources'].items():
        actual=m.sha(ROOT/p)
        if actual==h:continue
        a=amendment['files'].get(p)
        if not a or a['original_sha256']!=h or a['corrected_sha256']!=actual or m.sha(ROOT/a['original_snapshot'])!=h:
            raise ValueError('source hash mismatch '+p)
    for p,h in reg['input_hashes'].items():
        if m.sha(out/p)!=h:raise ValueError('input hash mismatch '+p)
    receipt=m.read(out/'fit_receipt.json')
    for key,h in receipt['model_hashes'].items():
        if m.sha(out/('candidate_'+key+'.json'))!=h:raise ValueError('candidate changed')
    public=next(r for r in m.read(out/'pre_inputs.json') if r['id']==identity)
    model=m.read(out/('candidate_'+(str(public['gap']) if public['role']=='development' else 'final')+'.json'))
    fixed,_=m.prior.prior.read_candidate(m.prior.prior.BUNDLE/'run_v1')
    return dict(session=identity,predicted_J=m.predict(public,model,fixed,0,120,opt_in=True),
                window_s=[0,120],future_only_window_s=[35,120],
                actual_schedule_conditional=True,event_time_causal=True,live_export_available=False,
                model='unadopted_CPU_prebaseline',AP=None,default_changed=False,strict_support=False,
                accuracy_pass=None,experiment_ready=False,device_commands=0,global_fits=0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--opt-in',action='store_true');p.add_argument('--session',default='confirmation_180_C0');p.add_argument('--output',required=True);a=p.parse_args()
    if not a.opt_in:p.error('explicit --opt-in required; unadopted offline diagnostic only')
    m.write(Path(a.output),example(a.session))
