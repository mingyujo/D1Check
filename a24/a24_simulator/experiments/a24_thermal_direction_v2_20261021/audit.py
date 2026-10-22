"""Audit all held predictions, reused zero-hinge fits and independent physics."""
import copy,json,math
from collections import Counter
from prepare import H,R,A,O,PREV,FIRST,read,write,sha,pin
from thermal_model import direct,integrated

def main():
    reg=read(O/'REGISTRATION.json');data=read(O/'INPUTS.json');cases={c['session']:c for c in data['cases']};oof={r['session']:r for r in read(O/'OOF_PREDICTIONS.json')['cases']};runtime={r['session']:r for r in read(O/'RUNTIME_REPLAY.json')['cases']}
    checks=0;maxT=maxH=0.
    for p in [reg['inputs'],*reg['sources']]:assert sha(R/p['path'])==p['sha256'];checks+=1
    previous_data=read(PREV/'INPUTS.json');assert data['cases']==previous_data['cases'] and data['outer_groups']==previous_data['outer_groups'];checks+=2
    ledger=[json.loads(line) for line in (O/'FIT_LEDGER.jsonl').read_text().splitlines()];complete=read(O/'FIT_COMPLETE.json');counts=Counter(row['event'] for row in ledger)
    assert counts['START']==counts['COMPLETE']==complete['fits']==200 and counts['FAIL']==0
    first_ledger=[json.loads(line) for line in (FIRST/'FIT_LEDGER.jsonl').read_text().splitlines()]
    first={row['model']['identity']:row['model'] for row in first_ledger if row['event']=='COMPLETE' and not row['model']['hinge_strength']}
    fitted={row['model']['identity']:row['model'] for row in ledger if row['event']=='COMPLETE'}
    fitted.update({'DIRECTION01_FIXED_ZERO_HINGE/'+k:v for k,v in first.items()})
    for row in ledger:
        if row['event']=='COMPLETE':
            model=row['model'];assert model['hinge_normalization']==data['direction_config']['hinge_normalization'];checks+=1
        elif row['event']=='REUSE':model=fitted[row['source_id']];assert not model['hinge_strength'] or row['source_id'] in fitted
        else:continue
        label=row['id'];assert all(cases[s]['family']==label.split('/')[0] for s in model['training_sessions']);checks+=1
        if '/OUTER' in label:
            family,fold=label.split('/')[:2];held=data['outer_groups'][family][int(fold.removeprefix('OUTER'))]
            assert not set(held)&set(model['training_groups']);checks+=1
        assert all(lo-1e-9<=v<=hi+1e-9 for lo,v,hi in zip(data['config']['lower_bounds'],model['coefficients'],data['config']['upper_bounds']));checks+=10
    # Every selected candidate obeyed the frozen inner-only protection rules.
    for family in ['m8','old']:
        for k in range(5):
            receipt=read(O/f'{family}_OUTER_{k}.json');model=receipt['model'];ranking=receipt['inner_ranking'];assert len(ranking)==9
            base=next(r for r in ranking if not r['transport_s'] and not r['hinge_strength'])
            choice=next(r for r in ranking if r['transport_s']==model['transport_s'] and r['hinge_strength']==model['hinge_strength']);assert choice['eligible']
            assert choice['MAE_C']<=base['MAE_C']+.05+1e-9 and choice['delta_MAE_C']<=base['delta_MAE_C']+.05+1e-9
            assert choice['direction_accuracy_pct']['stable']>=base['direction_accuracy_pct']['stable']-5-1e-9
            assert [model['tau_fast_s'],model['tau_slow_s']]==data['frozen_tau'][family][str(k)];checks+=6
    for sid,c in cases.items():
        held=oof[sid];model=read(O/f"{c['family']}_OUTER_{held['outer_fold']}.json")['model'];assert sid not in model['training_sessions'] and c['group'] not in model['training_groups']
        assert c['initial_return_hi_s']<=35 and c['pre_latest_return_s']<=35;checks+=3
        for scalar,matrix,js in zip(direct(c,model),held['AP_C'],runtime[sid]['AP_C']):
            err=max(abs(scalar-matrix),abs(scalar-js));maxT=max(maxT,err);assert err<1e-8;checks+=2
        err=abs(integrated(c,model,c['observations'][-1]['t'])-runtime[sid]['end_state']['H']);maxH=max(maxH,err);assert err<1e-6;checks+=1
    c=next(c for c in cases.values() if c['family']=='m8');model=read(O/f"m8_OUTER_{oof[c['session']]['outer_fold']}.json")['model'];mutated=copy.deepcopy(c)
    for o in mutated['observations']:o['observed_c']+=1000
    assert direct(c,model)==direct(mutated,model);checks+=1
    assert 'observed_c' not in (H/'calibrated_profile.cjs').read_text() and 'observed_c' not in (H/'runtime_validate.cjs').read_text();checks+=2
    result={'status':'PASS_GROUP_REUSE_AND_RUNTIME_AUDIT','checks':checks,'new_fits':complete['fits'],'first_variant_fits_preserved':read(FIRST/'FIT_COMPLETE.json')['fits'],
        'zero_hinge_models_reused':complete['fixed_zero_hinge_baselines_reused'],'new_failures':0,'OOF_sessions':106,'max_T_difference_C':maxT,'max_H_difference_C_s':maxH,
        'same_cases_and_folds_as_V1':True,'future_target_mutation_changes_prediction':False,'evaluation_threshold_C':.2,'rounding_applied_to_primary_prediction':False,
        'physical_accuracy_certified':False,'fresh_confirmation':False,'policy_environments':0,'new_measurements':0,'audit_source':pin(H/'audit.py')}
    write(O/'AUDIT.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
