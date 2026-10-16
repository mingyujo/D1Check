"""Matched late requests and first observed wait, from stored evidence only."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import torch


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def item(run,identity):return json.loads(gzip.decompress((run/'items'/(identity+'.json.gz')).read_bytes()))


def diagnose(run,out):
    run,out=Path(run),Path(out);out.mkdir(parents=True,exist_ok=True);rows=[];exact=[];deltas=[]
    for stage in ('main_development','confirmation'):
        data=read(run/(stage+'_results.json'))['rows'];bases={r['condition']:r for r in data if r['policy']=='L0'}
        for r in data:
            if r['policy']!='tailPPO':continue
            b=bases[r['condition']];base=item(run,b['identity']);new=item(run,r['identity'])
            old_by={q['id']:q for q in base['result']['ledger']}
            exact.append(dict(stage=stage,condition=r['condition'],seed=r['seed'],
                ledger_exact=new['result']['ledger']==base['result']['ledger'],
                transitions_exact=new['result']['transitions']==base['result']['transitions']))
            changed=[q for q in new['result']['ledger'] if q['priority']=='normal' and q['late_success'] and not old_by[q['id']]['late_success']]
            avoided=[q for q in new['result']['ledger'] if q['priority']=='normal' and not q['late_success'] and old_by[q['id']]['late_success']]
            deltas.append(dict(stage=stage,condition=r['condition'],seed=r['seed'],added=len(changed),avoided=len(avoided)))
            if not changed:continue
            saved=torch.load(run/'items'/(r['identity']+'.pt'),map_location='cpu',weights_only=False)['controller']
            waits=[s for s in saved['snapshots'] if s['action']['wait']>0]
            first=waits[0] if waits else None
            for q in changed:
                prior=old_by[q['id']]
                visible=next((s for s in saved['snapshots'] if s['tail_forecasts'][s['chosen']]['known']
                    and q['id'] in s['tail_forecasts'][s['chosen']]['prediction']),None)
                cf=visible['tail_forecasts'][visible['chosen']]['prediction'][q['id']]['response'] if visible else None
                bf=visible['tail_forecasts'][visible['base']]['prediction'][q['id']]['response'] if visible else None
                rows.append(dict(stage=stage,condition=r['condition'],arrival_seed=r['case']['seed'],family=r['case']['family'],
                    context=r['case']['context'],learning_seed=r['seed'],request_id=q['id'],ordinal=q['ordinal'],
                    arrival_s=q['arrival_ns']/1e9,deadline_s=q['deadline_offset_ns']/1e9,
                    L0_response_s=prior['response_ns']/1e9,new_response_s=q['response_ns']/1e9,
                    response_increase_s=(q['response_ns']-prior['response_ns'])/1e9,
                    first_actual_wait_s=first['now_ns']/1e9 if first else None,
                    request_not_arrived_at_first_wait=bool(first and q['arrival_ns']>first['now_ns']),
                    explicit_request_wait_s=saved['request_wait'].get(q['id'],0.),
                    first_visible_prediction_at_s=visible['now_ns']/1e9 if visible else None,
                    chosen_same_state_expected_response_s=cf-q['arrival_ns']/1e9 if cf is not None else None,
                    L0_same_state_expected_response_s=bf-q['arrival_ns']/1e9 if bf is not None else None,
                    prediction_admitted=bool(visible and visible['mask'][visible['chosen']]),
                    source_identity=r['identity']))
    with (out/'added_normal_failures.csv').open('w',encoding='utf-8',newline='') as stream:
        if rows:
            w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    groups=[]
    for stage in ('main_development','confirmation'):
        for seed in (11,23,37):
            vv=[r for r in deltas if r['stage']==stage and r['seed']==seed]
            ee=[r for r in exact if r['stage']==stage and r['seed']==seed]
            groups.append(dict(stage=stage,seed=seed,added_normal_late=sum(r['added'] for r in vv),
                avoided_normal_late=sum(r['avoided'] for r in vv),ledger_and_transitions_L0_exact=sum(r['ledger_exact'] and r['transitions_exact'] for r in ee),conditions=len(ee)))
    result=dict(status='completed_read_only_diagnosis',groups=groups,added_request_rows=len(rows),
        target_not_arrived_at_first_wait=sum(r['request_not_arrived_at_first_wait'] for r in rows),
        prediction_admission_is_not_global_guarantee=True,
        interpretation='L0 prediction uses the current already changed state; it is not the original full-episode L0 schedule. Future arrivals are viewed here only posthoc, never supplied to the policy.',
        causal_proof=False,new_environment_learning_device_starts=0,representative_rule='first added miss in condition/seed/ledger order; all rows preserved')
    (out/'guard_loss_diagnosis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(diagnose(Path(a.run),Path(a.output)),ensure_ascii=False,indent=2))
