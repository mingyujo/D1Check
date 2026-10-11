"""Post-run diagnostics/roundtrip/source only; no environments or learning."""
import gzip,json
from pathlib import Path
from tools import d1_service_joint_rl_run as x
from tools.d1_overnight_rl_report import payload_digest

def run():
    reg=x.check();result=x.read(x.LOCAL/'completion.json');data=x.read(x.LOCAL/'inputs.json');diag=[];roundtrip=[];manifest={}
    dep=dict(contract_sha256=x.sha(x.LOCAL/'registration.json'),model=x.h.UPSTREAM_SHA,sources=reg['source_sha256'],objective=x.n.objective.OBJECTIVE)
    for seed in x.SEEDS:
        metrics=dict(seed=seed,decisions=0,physical_slots=0,admitted_slots=0,multiple_choices=0,non_reference=0,cooling=0,resource_wait=0,single=0,bundle=0,before_envelope_cost_improvers=0,after_envelope_cost_improvers=0)
        for q in result['rows']:
            if q.get('scope')!='confirmation' or q['learning_seed']!=seed:continue
            raw=json.loads(gzip.decompress((x.LOCAL/'items'/f'final_{q["policy"]}_{q["condition"]:02d}.json.gz').read_bytes()))
            for s in raw['snapshots']:
                metrics['decisions']+=1;metrics['physical_slots']+=sum(s['physical_mask']);metrics['admitted_slots']+=sum(s['mask']);metrics['multiple_choices']+=sum(s['mask'])>1;metrics['non_reference']+=s['chosen']!=0;kind=s['actions'][s['chosen']]['kind'];metrics[dict(cool_wait='cooling',resource_wait='resource_wait',single='single',bundle='bundle')[kind]]+=1
                refs=s['forecasts'][0]
                for i,a in enumerate(s['actions']):
                    fs=s['forecasts'][i]
                    if not s['physical_mask'][i] or not all(f['valid'] and ref['valid'] for f,ref in zip(fs,refs)):continue
                    nonworse=all(f['global_peak_ap_c']<=ref['global_peak_ap_c']+1e-9 and f['remaining_increment_j']<=ref['remaining_increment_j']+1e-9 for f,ref in zip(fs,refs));strict=any(f['global_peak_ap_c']<ref['global_peak_ap_c']-1e-9 or f['remaining_increment_j']<ref['remaining_increment_j']-1e-9 for f,ref in zip(fs,refs))
                    if nonworse and strict:metrics['before_envelope_cost_improvers']+=1;metrics['after_envelope_cost_improvers']+=bool(s['mask'][i])
        diag.append(metrics)
        for ep in (32,64):
            path=x.LOCAL/'checkpoints'/f'seed{seed}_ep{ep}.pt';before=x.r.torch.load(path,map_location='cpu',weights_only=False);learner=x.n.Learner.load(path,expected_schema_id=x.n.SCHEMA,expected_dependencies=dep);after=learner.snapshot();same={k:payload_digest(v)==payload_digest(after[k]) for k,v in before.items()};assert all(same.values());roundtrip.append(dict(seed=seed,episodes=ep,all_fields_exact=same,actual_new_learning=0))
    # Include the __main__ runner from the explicit pre-learning supplement.
    revision=x.read(x.LOCAL/'label_only_revision.json');effective=dict(reg['source_sha256'],**revision['effective_source_sha256'])
    import hashlib
    for name,digest in effective.items():manifest[name]=dict(executed_sha256=digest,canonical_lf_sha256=hashlib.sha256((x.ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest())
    x.write(x.PUBLIC/'selection_diagnostics.json',dict(status='PASS_posthoc',seeds=diag,epsilon_only_diagnostic=1e-9,actual_adoption_epsilon=0,condition_sensitivity_not_independent_trials=True,new_environment=0,new_learning=0))
    x.write(x.PUBLIC/'checkpoint_roundtrip.json',dict(status='PASS_typed_payload',archives=roundtrip,new_environment=0,new_learning=0,limitation='load snapshot identity, not actual continued training replay'))
    x.write(x.PUBLIC/'source_identity.json',dict(original_contract_sha256=x.sha(x.PUBLIC/'execution_contract.json'),revision_sha256=x.sha(x.PUBLIC/'label_only_revision.json'),sources=manifest))
    references=x.read(x.ROOT/'output/service_envelope_20261011_v1/confirmation_rows.json');mapped=[dict(q,policy='Rule') if q['policy']=='CostList' else q for q in references if q['policy'] in ('Band','Triton','CostList')]
    gates={f'FreshPPO{s}_64':x.old.gate_rows(mapped+[q for q in result['rows'] if q.get('scope')=='confirmation'],f'FreshPPO{s}_64',48) for s in x.SEEDS}
    x.write(x.PUBLIC/'original_gate.json',gates);print(json.dumps(dict(diagnostics=diag,gates={k:v['promising'] for k,v in gates.items()}),indent=2))

if __name__=='__main__':run()
