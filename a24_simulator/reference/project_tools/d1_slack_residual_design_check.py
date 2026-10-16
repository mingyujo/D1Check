"""Check shared redesign contracts and audit tables; no raw engine state needed."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/slack_residual_design_01'


def read(path):return json.loads(path.read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    v=read(BUNDLE/'design_verification.json')
    for rel,h in v['source_hashes'].items():assert sha(ROOT/rel)==h,'source drift: '+rel
    for name,h in v['outputs'].items():assert sha(BUNDLE/name)==h,'output drift: '+name
    manifest=read(BUNDLE/'audit_manifest.json')
    assert sha(ROOT/'tools/d1_slack_residual_design_audit.py')==manifest['source_sha256']
    for rel,h in manifest['inputs'].items():assert sha(ROOT/rel)==h,'evidence drift: '+rel
    with (BUNDLE/'constraint_audit.csv').open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
    r=read(BUNDLE/'constraint_audit.json')
    assert len(rows)==r['conditions']==192
    assert len({(x['seed'],x['family'],x['context']) for x in rows})==192
    for field,total in r['totals'].items():assert sum(int(x[field]) for x in rows)==total,field
    assert all(x['hypothetical_signatures_are_not_new_feasible_actions']=='True' for x in rows)
    c=read(BUNDLE/'design_contract.json');obs=c['observation'];b=c['budget_proposal']
    assert len(obs['state_fields'])==len(set(obs['state_fields']))==obs['state_dimension']==107
    assert len(obs['candidate_fields'])==len(set(obs['candidate_fields']))==obs['candidate_dimension']==61
    assert c['ppo_proposal']['state_encoder'][0]==107
    assert c['frozen']['deadlines_ns']=={'urgent_output_ready':1500000000,'normal_persisted':6000000000}
    assert c['training_allowed'] is False and c['environment_run_allowed_by_this_design'] is False
    assert c['ppo_proposal']['closed_episode_references']==['exact SHARED_EFT','source-pinned Band HEFT adapter']
    assert c['semantics']['baseline_controller_estimates_stay_mean']
    assert b['additional_environment_maximum']==sum(b['environment_allocation'].values())==13912
    assert b['conservative_final_used']==2241+13912<=20000
    assert b['main_learning_total']+b['learning_fixture_ceiling']==6144
    assert max(8+n+n*(8-n)+2 for n in range(9))==30<=32
    for m in range(2,33):
        prior=math.exp(math.log(9*(m-1)))
        assert abs(prior/(prior+m-1)-.9)<1e-14
    return dict(status='PASS',audit_conditions=192,state_dimension=107,candidate_dimension=61,
        action_slots=32,proposed_environment_max=13912,actual_engine_starts=0,
        actual_learning_episodes=0,device_commands=0,controller_implemented=False)


if __name__=='__main__':print(json.dumps(check(),ensure_ascii=False,indent=2))
