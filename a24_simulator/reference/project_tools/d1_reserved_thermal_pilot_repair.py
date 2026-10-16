"""Bounded pilot continuation: remove sub-nanosecond retained lane overlap.

The reviewed source files, completed items, original manifests and budgets remain
immutable. This execution adapter is separately registered, and every new item
binds its runtime hash. It never relaxes a deadline, cap, budget or supported state.
"""
from __future__ import annotations

import gzip
import json
import time
from unittest.mock import patch

from tools import d1_reserved_thermal_study as study

rule = study.rule
VERSION = 'retained-lane-numeric-repair-v1'


class StrictPlacement:
    def __init__(self, forecaster):
        self.forecaster = forecaster

    def place(self, request, backend, earliest, jobs):
        for _ in range(len(jobs)+1):
            job = self.forecaster.place(request, backend, earliest, jobs)
            conflicts = [j for j in jobs
                if job['start'] < j['end'] and job['end'] > j['start']
                and (j['backend'] == backend or
                    '+'.join(sorted((job['state'], j['state']))) not in rule.P.STATES)]
            if not conflicts:
                return job
            if any(min(job['end'], j['end'])-max(job['start'], j['start']) > rule.EPS
                   for j in conflicts):
                raise ValueError('retained overlap exceeds numerical repair scope')
            earliest = max(job['start'], max(j['end'] for j in conflicts))
        raise ValueError('retained numerical placement failed to converge')


class Controller(rule.Controller):
    def finish_retained(self, sequence, queue, active, now, forecaster):
        return super().finish_retained(sequence, queue, active, now,
                                      StrictPlacement(forecaster))


def runtime_hashes():
    return {name: study.digest(study.ROOT/name) for name in
        ('tools/d1_reserved_thermal_pilot_repair.py',
         'tools/test_d1_reserved_thermal_pilot_repair.py')}


def register():
    study.check(); review = study.require_review()
    if (study.LOCAL/'owner.json').exists():
        raise RuntimeError('active owner; numeric repair cannot register')
    manifest = study.read(study.LOCAL/'pilot_manifest.json')
    if manifest != study.read(study.BUNDLE/'pilot_manifest.json'):
        raise ValueError('original manifest mismatch')
    registration_path = study.LOCAL/'pilot_numeric_repair.json'
    if registration_path.exists():
        registration = study.read(registration_path)
    else:
        paths = sorted((study.LOCAL/'pilot_items').glob('*.json.gz'))
        if len(paths) != 4 or study.consumption()['pilot_starts'] != 5:
            raise ValueError('unexpected pre-repair pilot state')
        registration = dict(version=VERSION, registered_utc=study.utc(),
            original_manifest_sha256=study.digest(study.LOCAL/'pilot_manifest.json'),
            review_sha256=study.digest(study.BUNDLE/'astra_review.json'),
            source_hashes=study.source_hashes(), runtime_hashes=runtime_hashes(),
            preserved_items={p.name: study.digest(p) for p in paths},
            repair='retained unsupported positive overlap <=1e-9s: snap start to lane end; otherwise raise',
            unchanged_design=rule.specification(), consumption=study.consumption(),
            failure_evidence_sha256=study.digest(study.LOCAL/'pilot_failure_reproduction.json'),
            user_scope='approved pilot; routine implementation error repair and continuation')
        study.immutable(registration_path, registration)
        study.journal('numeric_repair_registration', runtime_hashes=runtime_hashes())
    if (registration['runtime_hashes'] != runtime_hashes() or
            registration['source_hashes'] != study.source_hashes() or
            registration['unchanged_design'] != rule.specification() or
            registration['review_sha256'] != study.digest(study.BUNDLE/'astra_review.json') or
            registration['original_manifest_sha256'] != study.digest(study.LOCAL/'pilot_manifest.json')):
        raise ValueError('numeric repair or original review/source drift')
    for name, sha in registration['preserved_items'].items():
        if study.digest(study.LOCAL/'pilot_items'/name) != sha:
            raise ValueError('pre-repair completed item changed')
    study.write(study.BUNDLE/'pilot_numeric_repair.json', registration)
    return registration


def simulate(frozen, initial, tickets, context, before):
    # Only this owned synchronous call uses the opt-in numerical adapter.
    with patch.object(rule, 'Controller', Controller):
        return rule.simulate(frozen, initial, tickets, context, before)


def run():
    registration = register()
    inputs, jobs, reused, _ = study.reference_rows()
    frozen, _ = rule.P.inputs(rule.P.BUNDLE)
    original_binding = dict(manifest_sha256=study.digest(study.LOCAL/'pilot_manifest.json'),
                            source_hashes=study.source_hashes())
    binding = dict(original_binding,
        numeric_repair_sha256=study.digest(study.LOCAL/'pilot_numeric_repair.json'),
        runtime_hashes=runtime_hashes())
    rows = []
    with study.owner():
        for index, (work, context) in enumerate(jobs):
            study.check(); study.require_review()
            if runtime_hashes() != registration['runtime_hashes']:
                raise ValueError('runtime drift during continuation')
            name = f"{work['seed']}/{work['family']}/{context}"
            path = study.LOCAL/f'pilot_items/{index:04d}.json.gz'
            if path.exists():
                with gzip.open(path, 'rt', encoding='utf8') as f:
                    item = json.load(f)
                expected = original_binding if path.name in registration['preserved_items'] else binding
                if item['binding'] != expected or item['identity'] != name:
                    raise ValueError('pilot cache binding mismatch')
                entries = [json.loads(line) for line in
                    (study.LOCAL/'executions.jsonl').read_text(encoding='utf8').splitlines()]
                receipts = [x for x in entries if x['event']=='completed'
                    and x.get('kind')=='pilot' and x['name']==name]
                if not receipts or receipts[-1]['item_sha256'] != study.digest(path):
                    raise ValueError('pilot cache completion receipt mismatch')
                study.existing.audit(item['result'], work['tickets'])
            else:
                number = study.begin_environment('pilot', name)
                study.journal('numeric_repair_execution', number=number, runtime_hashes=runtime_hashes())
                began = time.perf_counter()
                try:
                    row, result, c, _ = simulate(frozen, inputs['initial'], work['tickets'], context, lambda:None)
                    study.existing.audit(result, work['tickets'])
                    common, curves = study.existing.metrics(result, c, inputs['initial'], frozen)
                    row.update(common, seed=work['seed'], family=work['family'], context=context,
                        scope='resource', environment='immediate_allow', origin='new_reserved_thermal')
                    item = dict(identity=name, binding=binding, row=row, result=result,
                        records=c.records, transactions=c.book.transactions, events=c.book.breaks,
                        pending=c.book.pending, first_seen=c.book.first_seen, curves=curves)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temp = path.with_suffix('.tmp')
                    temp.write_bytes(gzip.compress(json.dumps(item, ensure_ascii=False,
                        allow_nan=False).encode('utf8'), mtime=0))
                    temp.replace(path)
                    study.journal('completed', kind='pilot', name=name, number=number,
                        item_sha256=study.digest(path), host_wall_s=time.perf_counter()-began)
                except BaseException as error:
                    study.journal('failed', kind='pilot', name=name, number=number, error=repr(error))
                    raise
            rows.append(item['row'])
            study.write(study.LOCAL/'pilot_progress.json', dict(saved_rows=len(rows), total=48,
                consumption=study.consumption(), numeric_repair=VERSION))
            print(f'{len(rows)}/48 {name}', flush=True)
    study.check(); study.require_review()
    study.existing.csv_write(study.BUNDLE/'pilot_results.csv', reused+rows)
    study.write(study.BUNDLE/'pilot_completion.json', dict(status='completed', new_rows=48,
        reused_rows=432, logical_rows=480, binding=original_binding, numeric_repair=VERSION,
        numeric_repair_sha256=binding['numeric_repair_sha256'], runtime_hashes=runtime_hashes(),
        preserved_original_items=len(registration['preserved_items']), repaired_items=44,
        consumption=study.consumption(), training_episodes=0, device_commands=0))
    return dict(rows=480, consumption=study.consumption())


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False))
