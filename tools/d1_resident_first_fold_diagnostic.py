"""Reproduce the first registered development holdout, without widening beta or confirming."""
import argparse
import json
from pathlib import Path
from tools import d1_resident_identification_analysis as a
from tools.d1_resident_identification_results import digest, table, write


def diagnose(inputs_file, original_file, output):
    out=Path(output)
    if out.exists():raise FileExistsError(out)
    if digest(original_file)!=a.j.m.MODEL_SHA:raise ValueError('original model changed')
    cases=a.j.m.read(inputs_file);original=a.j.m.read(original_file)
    if len(cases)!=4 or any(c['role']!='development' for c in cases) or len({c['id'] for c in cases})!=4:
        raise ValueError('exact four development sessions required; confirmation excluded')
    train=cases[1:]
    rows=[dict(study_phase='development',inputs=a.j.m.case_input(c,c['actual'])['inputs'],observed_ap_c=c['ap']) for c in train]
    ap,profile=a.j.m.thermal.fit(rows,original['ap']['parameters'])
    energy=a.energy_fit(train,original)
    blocked=ap['load_rank']!=2 or ap['numerical_rank']!=3 or ap['beta_boundary']
    result=dict(status='first_fold_unidentified_not_frozen' if blocked else 'first_fold_diagnostic_only_not_frozen',excluded_development=cases[0]['id'],
                training_development=[c['id'] for c in train],ap=ap,energy=energy,
                heldout_diagnostic=a.assess(cases[0],dict(ap=ap,energy=energy),original),
                original_model_sha256=digest(original_file),accuracy_pass=None,default=False,
                strict_support=False,experiment_ready=False)
    out.mkdir(parents=True);write(out/'first_fold.json',result);table(out/'beta_profile.csv',profile)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',required=True);p.add_argument('--original-model',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();r=diagnose(args.inputs,args.original_model,args.output)
    print(json.dumps(dict(status=r['status'],beta_boundary=r['ap']['beta_boundary']),ensure_ascii=False))
