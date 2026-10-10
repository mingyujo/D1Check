"""Join stored results only; do not turn favorable identities into a selector."""
import argparse
import csv
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import d1_registered_baseline as m


def table(p):
    with Path(p).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))


def readout(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    source=ROOT/'docs/results/preboundary_evidence_01/run_v1/AP_paths.csv'
    ap=table(source);energy=table(m.BUNDLE/'readout_v1/fixed_head_errors.csv');rows=[]
    for p in m.old.read(m.BUNDLE/'run_v1/pre_inputs.json'):
        scores={}
        for variant in ('existing_short_pre','registered_idle_pre'):
            use=[r for r in ap if r['session']==p['id'] and r['variant']==variant and 35<=float(r['t_s'])<=120]
            if len(use)<2:raise ValueError('AP score window unavailable; not zero')
            error=np.array([float(r['residual_c']) for r in use]);obs=np.array([float(r['observed_c']) for r in use]);pred=np.array([float(r['predicted_c']) for r in use])
            scores[variant]=dict(MAE=float(np.mean(np.abs(error))),max_abs=float(np.max(np.abs(error))),
                peak_signed=float(pred.max()-obs.max()),samples=len(use),first_s=float(use[0]['t_s']),last_s=float(use[-1]['t_s']))
        a,b=scores['existing_short_pre'],scores['registered_idle_pre']
        assert a['samples']==b['samples'] and a['first_s']==b['first_s'] and a['last_s']==b['last_s']
        for head in ('original_frozen','existing_zero_offset'):
            use={r['initializer']:r for r in energy if r['session']==p['id'] and r['head']==head and r['phase']=='reference120'}
            e0,e1=float(use['P50']['absolute_J']),float(use['FULL_CPU']['absolute_J'])
            rows.append(dict(session=p['id'],role=p['role'],gap=p['gap'],energy_head=head,energy_window_s='0..120',AP_window_s='35..120',
                old_energy_abs_J=e0,new_energy_abs_J=e1,new_energy_signed_J=float(use['FULL_CPU']['signed_J']),
                AP_head='fixed_LOAD_SLOW',old_AP_MAE_c=a['MAE'],new_AP_MAE_c=b['MAE'],
                old_AP_max_c=a['max_abs'],new_AP_max_c=b['max_abs'],
                old_AP_peak_signed_c=a['peak_signed'],new_AP_peak_signed_c=b['peak_signed'],
                AP_samples=a['samples'],AP_first_s=a['first_s'],AP_last_s=a['last_s'],
                both_mean_errors_improved=e1<e0-1e-9 and b['MAE']<a['MAE']-1e-12,
                used_to_select_supported_conditions=False,posthoc=True))
    summary=[]
    for role in ('development','confirmation'):
        for head in ('original_frozen','existing_zero_offset'):
            use=[r for r in rows if r['role']==role and r['energy_head']==head]
            summary.append(dict(role=role,energy_head=head,sessions=len(use),
                both_improved_sessions=sum(r['both_mean_errors_improved'] for r in use),
                old_energy_mean_abs_J=float(np.mean([r['old_energy_abs_J'] for r in use])),
                new_energy_mean_abs_J=float(np.mean([r['new_energy_abs_J'] for r in use])),
                old_AP_mean_MAE_c=float(np.mean([r['old_AP_MAE_c'] for r in use])),
                new_AP_mean_MAE_c=float(np.mean([r['new_AP_MAE_c'] for r in use]))))
    for name,data in [('all_sessions',rows),('summary',summary)]:m.old.prior.prior.old.scope_api.tail.s.csv_write(out/(name+'.csv'),data)
    m.old.write(out/'receipt.json',dict(status='existing_result_join_complete',AP_source_sha256=m.old.sha(source),
        contract_sha256=m.old.sha(m.BUNDLE/'joint_readout_contract.json'),new_fits=0,new_AP_replays=0,device_commands=0,
        favorable_ID_selector=False,default_changed=False,RL_changed=False,strict_support=False,experiment_ready=False))
    print(m.old.prior.prior.terminal_json(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();readout(a.output)
