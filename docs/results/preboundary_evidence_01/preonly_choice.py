"""One fixed pre-only initialization choice; never selects on post-load errors."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools import d1_preboundary_evidence as e


def run():
    out=Path(__file__).with_name('run_v1')
    registration=e.current.prior.old.analysis.j.m.read(Path(__file__).with_name('preonly_choice_registration.json'))
    for path,h in registration['sources'].items():
        if e.current.prior.old.scope_api.sha(ROOT/path)!=h:raise ValueError('registered source changed')
    if (out/'preonly_choice_receipt.json').exists():raise ValueError('choice already evaluated')
    memory=e.current.prior.old.analysis.j.m.memory
    original=e.current.prior.old.analysis.j.m.read(e.current.prior.old.analysis.j.m.MODEL)
    model=e.current.prior.old.scope_api.read_assets()[2]
    lookup={c['id']:c for c in e.current.cases()};data=e.current.prior.old.analysis.j.m.read(out/'expanded_pre.json')
    rows=[];paths=[]
    for d in data:
        c=lookup[d['id']];errors={};held=d['expanded_pre'][-1]
        for name,pre in [('existing_short_pre',c['pre']),('registered_idle_pre',d['expanded_pre'])]:
            train=pre[:-1]
            if train[-1]['hi']>held['lo']:raise ValueError('validation AP already read before input cutoff')
            init=memory.initialize(train,original['ap']['beta'],30.)
            pred=memory.advance(init['anchor_ap_c'],init['h_last_c_per_s'],0.,init['reference_c'],original['ap']['beta'],30.,0.,held['t']-init['anchor_s'])[0]
            errors[name]=abs(pred-held['ap'])
        chosen='registered_idle_pre' if errors['registered_idle_pre']<errors['existing_short_pre']-1e-12 else 'existing_short_pre'
        # Re-estimate the permitted initial state with all pre observations after choosing.
        pre=d['expanded_pre'] if chosen=='registered_idle_pre' else c['pre']
        y,_=e.compare(c,pre,original,model)
        score=e.current.prior.old.observed.phase_score(c,y,35.,c['actual'][-1]['end_s'])
        rows.append(dict(session=c['id'],role=c['role'],gap=c['gap'],chosen=chosen,**score,
            short_pre_validation_abs_c=errors['existing_short_pre'],full_pre_validation_abs_c=errors['registered_idle_pre'],
            selection_inputs_end_s=held['hi'],issue_s=35.,post_AP_used_for_choice=False))
        paths.extend(dict(session=c['id'],t_s=t,observed_c=obs,predicted_c=pred,residual_c=pred-obs) for t,obs,pred in zip(c['q'],c['ap'],y))
    e.current.prior.old.scope_api.tail.s.csv_write(out/'preonly_choice.csv',rows)
    e.current.prior.old.scope_api.tail.s.csv_write(out/'preonly_choice_paths.csv',paths)
    e.write(out/'preonly_choice_receipt.json',dict(method='one last pre-AP validation sample;choose by pre-only error then refit local state with permitted pre;short on numerical tie',
        global_coefficients_changed=False,post_AP_choice=False,local_state_estimates=36,AP_replays=12,
        accuracy_pass=None,default_changed=False,device_commands=0))
    print(e.current.prior.terminal_json(rows))


if __name__=='__main__':run()
