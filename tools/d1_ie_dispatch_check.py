"""Portable read-only shared bundle check. Stdlib only; no raw/plant required."""
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'docs/results/ie_dispatch_01'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def rows(path):
    with path.open(encoding='utf8',newline='') as stream:return list(csv.DictReader(stream))


def check():
    v=read(BUNDLE/'share_verification.json')
    for name,expected in v['bundle_sha256'].items():
        if sha(BUNDLE/name)!=expected:raise ValueError('shared output drift: '+name)
    for name,expected in v['source_sha256'].items():
        if sha(ROOT/name)!=expected:raise ValueError('source drift: '+name)
    c=read(BUNDLE/'contract.json');done=read(BUNDLE/'completion.json')
    for name,expected in c['source_hashes'].items():
        if sha(ROOT/name)!=expected:raise ValueError('registered source drift: '+name)
    if sha(ROOT/c['input_path'])!=c['input_sha256']:raise ValueError('input drift')
    if sha(ROOT/c['prior_verification_path'])!=c['prior_verification_sha256']:raise ValueError('prior verification drift')
    if sha(BUNDLE/'mapping.md')!=c['mapping_sha256']:raise ValueError('mapping drift')
    if sha(BUNDLE/'contract.json')!=done['contract_sha256']:raise ValueError('contract drift')
    rs=rows(BUNDLE/'results.csv');pairs=rows(BUNDLE/'pairs.csv')
    ids={(r['seed'],r['family'],r['context'],r['policy']) for r in rs}
    if len(rs)!=1728 or len(ids)!=1728 or len(pairs)!=3456:raise ValueError('row denominators')
    by={policy:[r for r in rs if r['policy']==policy] for policy in c['new_policies']+c['reused_policies']}
    if any(len(xs)!=192 or sum(int(r['planned']) for r in xs)!=12672 for xs in by.values()):
        raise ValueError('policy denominator')
    for r in rs:
        if int(r['planned'])!=int(r['completed'])+int(r['incomplete']):raise ValueError('work denominator')
        if int(r['planned'])!=int(r['deadline_met'])+int(r['urgent_service_failure'])+int(r['normal_service_failure']):
            raise ValueError('service denominator')
    used=done['consumption']
    if used['previous_starts']!=2241 or used['new_starts']!=584 or used['cumulative_starts']!=2825:
        raise ValueError('cumulative budget')
    if used['training_episodes'] or used['device_commands'] or used['new_failed_starts']:
        raise ValueError('execution summary')
    if c['experiment_ready'] or c['strict_supported']:raise ValueError('unsupported promotion')
    print(json.dumps(dict(status='PASS',rows=1728,pairs=3456,conditions=192,
        new_environment_starts=584,cumulative_environment_starts=2825,
        training_episodes=0,device_commands=0,hashes=len(v['bundle_sha256'])+len(v['source_sha256'])),ensure_ascii=False))


if __name__=='__main__':check()
