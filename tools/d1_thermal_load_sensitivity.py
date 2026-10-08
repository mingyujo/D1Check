"""Fixed-schedule stress with previously fitted rejected model variants; zero runs."""
import json
from tools import d1_thermal_load_gate_report as report
from tools import d1_policy_coefficient_sensitivity as sensitivity

def run():
    s=report.s;assert s.read(s.BUNDLE/'completion.json')['status']=='completed';models=sensitivity.models()
    contract=dict(models=[name for name,_ in models],source_freeze_sha256=s.sha(sensitivity.FREEZE),original_model_sha256=s.sha(sensitivity.j.m.MODEL),
        scope='all24 fresh final conditions, fixed complete Band/Triton/new-gate schedules under original plus4 already-fitted rejected development variants; no fitting, no changed-model policy replay, no CI or SLA recalc',
        selection_unchanged=True,new_environment_starts=0,new_learning_starts=0,device_commands=0)
    s.write(s.BUNDLE/'sensitivity_contract.json',contract)
    items=report.load_items();initial=s.read(s.BUNDLE/'inputs.json')['initial'];rows=[];policies=(s.BAND,s.TRITON,s.x.POLICY)
    for identity,item in items.items():
        row=item['row']
        if not identity.startswith('final/') or row['policy'] not in policies:continue
        assert row['completed']==row['planned'];segments=sensitivity.segments(item['result']['ledger'])
        for name,model in models:
            value=sensitivity.j.m.base.costs(segments,initial,list(range(35,181)),model,180.)
            rows.append(dict(seed=row['seed'],family=row['family'],context=row['context'],policy=row['policy'],model=name,energy_j=value['whole_120s_j'],peak_ap_c=max(value['ap_path'])))
    by={(r['seed'],r['family'],r['context'],r['policy'],r['model']):r for r in rows};pairs=[]
    for row in rows:
        if row['policy']!=s.x.POLICY:continue
        for ref in (s.BAND,s.TRITON):
            base=by[row['seed'],row['family'],row['context'],ref,row['model']]
            pairs.append(dict(seed=row['seed'],family=row['family'],context=row['context'],model=row['model'],reference=ref,
                delta_energy_j=row['energy_j']-base['energy_j'],delta_peak_ap_c=row['peak_ap_c']-base['peak_ap_c']))
    report.csv_write(s.BUNDLE/'coefficient_sensitivity.csv',rows);report.csv_write(s.BUNDLE/'coefficient_sensitivity_pairs.csv',pairs)
    stats=[]
    for seed in (813030101,813030102):
        group=[r for r in pairs if r['seed']==seed and r['family']=='low' and r['reference']==s.BAND]
        stats.append(dict(seed=seed,family='low',comparison='Band',rows=len(group),delta_energy_range_j=[min(r['delta_energy_j'] for r in group),max(r['delta_energy_j'] for r in group)],
            delta_ap_range_c=[min(r['delta_peak_ap_c'] for r in group),max(r['delta_peak_ap_c'] for r in group)],heat_down_all_models=all(r['delta_peak_ap_c']<-1e-9 for r in group),heat_up_all_models=all(r['delta_peak_ap_c']>1e-9 for r in group)))
    result=dict(status='completed',cost_rows=len(rows),paired_rows=len(pairs),low_seed_ranges=stats,new_environment_starts=0,physical_improvement_proven=False)
    s.write(s.BUNDLE/'sensitivity_summary.json',result);print(json.dumps(result,indent=2));return result

if __name__=='__main__':run()
