"""Read saved veto records for redesign; never import a plant or learner."""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT/'docs/results/reserved_thermal_01/final_rule_only'
RAW = ROOT/'output/reserved_thermal_20261008_v1/final_rule_only_v1/items'
OUT = ROOT/'docs/results/slack_residual_design_01'
CAP = 'reservation_predicted_violation'
ENERGY = 'energy_budget_rejection'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n', encoding='utf8')


def signatures(candidates, ignore=()):
    # This drops named recorded vetoes only. It does NOT re-check true deadlines
    # or show that two returns lead to different physical-time execution prefixes.
    return {tuple(c['effective_action']['signature']) for c in candidates
            if not (set(c['reasons'])-set(ignore))
            and c['effective_action']['kind'] not in ('INVALID_BUSY_DISPATCH', 'REJECTED')}


def analyze(item, tickets):
    row = item['row']; by = {q['id']: q for q in tickets}
    caps = {}
    counts = dict(scored_callbacks=0, recorded_admitted_multiple_actions=0,
        multiple_actions_ignoring_cap=0, multiple_actions_ignoring_local_energy=0,
        multiple_actions_ignoring_cap_and_energy=0, cap_only_veto_candidates=0,
        energy_only_veto_candidates=0, cap_energy_only_veto_candidates=0,
        additional_immediate_dispatch_callbacks_ignoring_cap=0)
    for record in item['records']:
        counts['scored_callbacks'] += 1
        for rid, cap in record['immutable_caps'].items():
            if rid in caps: assert caps[rid] == cap, 'cap changed'
            caps[rid] = cap
            assert by[rid]['arrival_ns'] <= record['now_ns']+1, 'future reservation input'
        candidates = record['candidates']
        accepted = signatures(candidates)
        without_cap = signatures(candidates, (CAP,))
        counts['recorded_admitted_multiple_actions'] += len(accepted)>1
        counts['multiple_actions_ignoring_cap'] += len(without_cap)>1
        counts['multiple_actions_ignoring_local_energy'] += len(signatures(candidates, (ENERGY,)))>1
        counts['multiple_actions_ignoring_cap_and_energy'] += len(signatures(candidates, (CAP, ENERGY)))>1
        counts['cap_only_veto_candidates'] += sum(set(c['reasons'])=={CAP} for c in candidates)
        counts['energy_only_veto_candidates'] += sum(set(c['reasons'])=={ENERGY} for c in candidates)
        counts['cap_energy_only_veto_candidates'] += sum(set(c['reasons'])=={CAP, ENERGY} for c in candidates)
        extra_dispatch = {sig for sig in without_cap-accepted if sig[0]=='DISPATCH'}
        counts['additional_immediate_dispatch_callbacks_ignoring_cap'] += bool(extra_dispatch)
    margins = [(by[rid]['arrival_ns']+by[rid]['deadline_offset_ns'])/1e9-cap for rid,cap in caps.items()]
    assert all(x >= -1e-9 for x in margins)
    return dict(seed=row['seed'], family=row['family'], context=row['context'], **counts,
        planned_requests=row['planned'], issued_caps=len(caps), missing_caps=row['planned']-len(caps),
        tighter_than_true_deadline_caps=sum(x>1e-9 for x in margins),
        mean_unused_deadline_slack_s=sum(margins)/len(margins) if margins else None,
        max_unused_deadline_slack_s=max(margins) if margins else None,
        hypothetical_signatures_are_not_new_feasible_actions=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT/'constraint_audit.json').exists():
        raise RuntimeError('existing design audit preserved; use its receipt rather than overwrite')
    verification = read(OLD/'verification.json')
    registration = read(OLD/'registration.json')
    assert read(OLD/'completion.json')['status']=='completed'
    assert digest(OLD/'inputs.json')==registration['inputs_sha256']
    for name, sha in registration['source_hashes'].items(): assert digest(ROOT/name)==sha, name
    inputs = read(OLD/'inputs.json')
    tickets = {(w['seed'],w['family']):w['tickets'] for w in inputs['workloads']}
    with (OLD/'results.csv').open(encoding='utf8',newline='') as f:
        policy_rows = list(csv.DictReader(f))
    selected = [(i,r) for i,r in enumerate(policy_rows) if r['policy']=='RESERVED_THERMAL_REQUEST_V1_NUMERIC_R2']
    assert len(selected)==192
    manifest = dict(utc=datetime.now(timezone.utc).isoformat(),
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), dirty=True,
        version='slack-residual-design-audit-v1',
        source_sha256=digest(Path(__file__)),
        inputs={p.relative_to(ROOT).as_posix():digest(p) for p in
            (OLD/'verification.json',OLD/'registration.json',OLD/'inputs.json',OLD/'results.csv')},
        raw_items={f'{i:04d}.json.gz':verification['local_item_hashes'][f'{i:04d}.json.gz'] for i,_ in selected},
        performance_data_status='previously seen final data; now consumed design diagnostics, not an unseen test',
        inference_limit='dropping veto labels is not recomputed original-SLA feasibility or execution diversity',
        environment_starts=0,training_episodes=0,device_commands=0)
    write(OUT/'audit_manifest.json',manifest)
    rows = []
    for index,row in selected:
        path = RAW/f'{index:04d}.json.gz'
        assert digest(path)==manifest['raw_items'][path.name]
        with gzip.open(path,'rt',encoding='utf8') as f:item=json.load(f)
        assert item['binding']==read(OLD/'completion.json')['binding']
        assert (str(item['row']['seed']),item['row']['family'],item['row']['context']) == \
            (row['seed'],row['family'],row['context'])
        rows.append(analyze(item,tickets[(item['row']['seed'],item['row']['family'])]))
    with (OUT/'constraint_audit.csv').open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    fields=[key for key in rows[0] if key not in ('seed','family','context',
        'mean_unused_deadline_slack_s','max_unused_deadline_slack_s','hypothetical_signatures_are_not_new_feasible_actions')]
    totals={key:sum(row[key] for row in rows) for key in fields}
    result=dict(version=manifest['version'],utc=datetime.now(timezone.utc).isoformat(),conditions=192,
        totals=totals,mean_unused_deadline_slack_s=sum(row['mean_unused_deadline_slack_s']*row['issued_caps']
            for row in rows if row['issued_caps'])/totals['issued_caps'],
        caveat=manifest['inference_limit'],
        audit_manifest_sha256=digest(OUT/'audit_manifest.json'),csv_sha256=digest(OUT/'constraint_audit.csv'),
        environment_starts=0,training_episodes=0,device_commands=0)
    write(OUT/'constraint_audit.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
