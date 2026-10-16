"""Registered 64-start/60-minute numerical audit; same cumulative journal."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import subprocess
import time
from tools import d1_reserved_thermal_study as s
from tools import d1_reserved_thermal_numeric_r2 as r2
from tools import d1_reserved_thermal_pilot_repair as prior

LOCAL = s.LOCAL/'stage3_numeric_audit_v1'
BUNDLE = s.BUNDLE/'numeric_r2'
RUNTIME = ('tools/d1_reserved_thermal_numeric_r2.py', 'tools/test_d1_reserved_thermal_numeric_r2.py',
           'tools/d1_reserved_thermal_numeric_study.py')


def csv_read(path):
    from tools.d1_reserved_thermal_pilot_analysis import typed
    with Path(path).open(encoding='utf8', newline='') as stream:
        return [{k: typed(v) for k, v in row.items()} for row in csv.DictReader(stream)]


def sources():
    return {name: s.digest(s.ROOT/name) for name in RUNTIME}


def reuse():
    inputs, jobs, _, evidence = s.reference_rows()
    rows = csv_read(s.BUNDLE/'pilot_results.csv')
    verification = s.read(s.BUNDLE/'pilot_verification.json')
    for name, sha in verification['outputs'].items():
        if s.digest(s.BUNDLE/name) != sha: raise ValueError('original pilot artifact drift: '+name)
    path = s.ROOT/'docs/results/external_rules_01/results.csv'
    expected = s.read(s.REFERENCE/'contract.json')['old_sources'][path.relative_to(s.ROOT).as_posix()]
    if s.digest(path) != expected: raise ValueError('internal EFT source drift')
    internal = [r for r in csv_read(path) if r['policy']=='EFT_REFERENCE'
                and r['scope']=='resource' and r['environment']=='immediate_allow']
    keys = {(w['seed'], w['family'], ctx) for w, ctx in jobs}
    if len(rows)!=480 or len(internal)!=48 or {(r['seed'], r['family'], r['context']) for r in internal} != keys:
        raise ValueError('reused row coverage mismatch')
    for r in internal:
        r.update(reuse_source=path.relative_to(s.ROOT).as_posix(), reuse_file_sha256=expected)
    return inputs, jobs, rows+internal, dict(reference=evidence,
        pilot_verification_sha256=s.digest(s.BUNDLE/'pilot_verification.json'),
        pilot_csv_sha256=s.digest(s.BUNDLE/'pilot_results.csv'),
        internal_eft_csv_sha256=expected, rows_sha256=s.object_digest(rows+internal))


def register():
    s.check(); prior.register()
    review = s.read(s.BUNDLE/'stage3_review.json')
    if (review['decision'] != 'REVISE_BEFORE_RUN' or review['source_hashes'] != s.source_hashes()
        or review['runtime_hashes'] != prior.runtime_hashes()
        or review['report_sha256'] != s.digest(s.BUNDLE/'ASTRA_STAGE3_REVIEW.md')
        or review['evidence_sha256'] != s.digest(s.BUNDLE/'stage3_review_evidence.json')):
        raise ValueError('stage3 reviewed evidence drift')
    inputs, jobs, rows, evidence = reuse()
    path = LOCAL/'registration.json'
    if path.exists():
        registration = s.read(path)
    else:
        if (s.LOCAL/'owner.json').exists() or s.consumption()['environment_starts'] != 71:
            raise ValueError('registration requires preserved cumulative 71 and no owner')
        registration = dict(version='stage3_numeric_audit_v1', registered_utc=s.utc(),
            head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), dirty=True,
            source_hashes=s.source_hashes(), runtime_hashes=sources(),
            prior_runtime_hashes=prior.runtime_hashes(), review_sha256=s.digest(s.BUNDLE/'stage3_review.json'),
            public_policy=r2.PUBLIC_POLICY, baseline_consumption=s.consumption(),
            additional_environment_starts=64, wall_seconds=3600, save_reserve_seconds=300,
            scope='mechanical correction and telemetry; same development inputs; no new holdout or RL',
            correction='total start displacement <=1e-9s; reject candidate otherwise',
            conditions=[dict(seed=w['seed'], family=w['family'], context=ctx,
                tickets_sha256=s.object_digest(w['tickets'])) for w, ctx in jobs],
            reused_rows=528, logical_rows=576, reuse=evidence, training_episodes=0, device_commands=0,
            original_items={p.name: s.digest(p) for p in sorted((s.LOCAL/'pilot_items').glob('*.gz'))})
        s.immutable(path, registration)
        s.journal('numeric_r2_registration', registration_sha256=s.digest(path), runtime_hashes=sources())
    if (registration['runtime_hashes'] != sources() or registration['source_hashes'] != s.source_hashes()
        or registration['prior_runtime_hashes'] != prior.runtime_hashes()
        or registration['review_sha256'] != s.digest(s.BUNDLE/'stage3_review.json')
        or registration['reuse'] != evidence):
        raise ValueError('numeric R2 registration drift')
    for name, sha in registration['original_items'].items():
        if s.digest(s.LOCAL/'pilot_items'/name) != sha: raise ValueError('original completed item changed')
    s.write(BUNDLE/'registration.json', registration)
    return registration


def guard(registration):
    s.check()
    if sources() != registration['runtime_hashes']: raise ValueError('runtime drift')
    if s.consumption()['environment_starts']-registration['baseline_consumption']['environment_starts'] >= 64:
        raise RuntimeError('numeric substage environment budget exhausted')
    path = LOCAL/'clock.json'
    if not path.exists(): s.immutable(path, dict(start_utc=s.utc()))
    began = datetime.fromisoformat(s.read(path)['start_utc'])
    if (datetime.now(timezone.utc)-began).total_seconds() >= 3300:
        raise TimeoutError('numeric audit saving reserve reached; no budget reset')


def read_item(path, binding, name, tickets):
    with gzip.open(path, 'rt', encoding='utf8') as f: item = json.load(f)
    if item['binding'] != binding or item['identity'] != name: raise ValueError('cache binding mismatch')
    entries = [json.loads(line) for line in (s.LOCAL/'executions.jsonl').read_text(encoding='utf8').splitlines()]
    receipts = [e for e in entries if e['event']=='completed' and e.get('name')==name]
    if not receipts or receipts[-1].get('item_sha256') != s.digest(path): raise ValueError('cache receipt mismatch')
    s.existing.audit(item['result'], tickets)
    return item


def execute(registration, kind, name, tickets, context, initial, frozen, simulator, path):
    binding = dict(registration_sha256=s.digest(LOCAL/'registration.json'), runtime_hashes=sources())
    if path.exists(): return read_item(path, binding, name, tickets)
    guard(registration)
    started = {}
    def before():
        started['number'] = s.begin_environment(kind, name)
        s.journal('numeric_r2_execution', number=started['number'], runtime_hashes=sources())
    began = time.perf_counter()
    try:
        row, result, c, _ = simulator(frozen, initial, tickets, context, before)
        s.existing.audit(result, tickets)
        common, curves = s.existing.metrics(result, c, initial, frozen)
        row.update(common)
        item = dict(identity=name, binding=binding, row=row, result=result, records=c.records,
            numeric_events=getattr(c, 'numeric_events', []), action_audit=getattr(c, 'action_audit', []),
            transactions=c.book.transactions, events=c.book.breaks, pending=c.book.pending,
            first_seen=c.book.first_seen, curves=curves)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_bytes(gzip.compress(json.dumps(item, ensure_ascii=False, allow_nan=False).encode('utf8'), mtime=0))
        temp.replace(path)
        s.journal('completed', kind=kind, name=name, number=started['number'],
                  item_sha256=s.digest(path), host_wall_s=time.perf_counter()-began)
        return item
    except BaseException as error:
        s.journal('failed', kind=kind, name=name, number=started.get('number'), error=repr(error))
        raise


def fixtures():
    registration = register()
    inputs, _, _, _ = reuse(); frozen, _ = s.rule.P.inputs(s.rule.P.BUNDLE)
    checks = []
    with s.owner():
        for name, tickets, context in s.fixture_tickets():
            pair = []
            for label, simulator in (('original', s.rule.simulate), ('r2', r2.simulate)):
                item = execute(registration, 'fixture', f'numeric_r2/fixture/{name}/{label}',
                    tickets, context, inputs['initial'], frozen, simulator,
                    LOCAL/f'fixtures/{name}_{label}.json.gz')
                pair.append(item)
            for field in ('planned', 'completed', 'deadline_met', 'urgent_p95_ms', 'normal_mean_ms', 'energy_j', 'peak_ap_c'):
                if pair[0]['row'][field] != pair[1]['row'][field]: raise ValueError('fixture behavior changed: '+field)
            if pair[0]['result']['ledger'] != pair[1]['result']['ledger']: raise ValueError('fixture ledger changed')
            checks.append(dict(fixture=name, same_ledger_and_metrics=True))
    s.write(BUNDLE/'fixture_verification.json', dict(utc=s.utc(), checks=checks,
        source_hashes=sources(), consumption=s.consumption(), environment_starts=10, device_commands=0))
    return checks


def run():
    registration = register()
    if not (BUNDLE/'fixture_verification.json').exists(): raise ValueError('small fixtures must precede pilot')
    inputs, jobs, reused, _ = reuse(); frozen, _ = s.rule.P.inputs(s.rule.P.BUNDLE)
    rows = []
    with s.owner():
        for index, (work, ctx) in enumerate(jobs):
            name = f"numeric_r2/pilot/{work['seed']}/{work['family']}/{ctx}"
            item = execute(registration, 'pilot', name, work['tickets'], ctx, inputs['initial'], frozen,
                           r2.simulate, LOCAL/f'pilot_items/{index:04d}.json.gz')
            row = dict(item['row'], seed=work['seed'], family=work['family'], context=ctx,
                       scope='resource', environment='immediate_allow', origin='numeric_r2')
            rows.append(row)
            s.write(LOCAL/'progress.json', dict(completed_conditions=len(rows), total=48, consumption=s.consumption()))
            print(f'{index+1}/48 {name}', flush=True)
    s.existing.csv_write(BUNDLE/'results.csv', reused+rows)
    result = dict(status='completed', utc=s.utc(), conditions=48, new_rows=48, reused_rows=528,
        logical_rows=576, registration_sha256=s.digest(LOCAL/'registration.json'),
        runtime_hashes=sources(), consumption=s.consumption(), training_episodes=0, device_commands=0)
    s.write(BUNDLE/'completion.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('register', 'fixtures', 'pilot', 'check'))
    action = parser.parse_args().action
    print(json.dumps(fixtures() if action=='fixtures' else run() if action=='pilot' else register(), ensure_ascii=False, indent=2))
