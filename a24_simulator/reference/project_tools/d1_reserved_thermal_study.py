"""Registered fixture runner and a closed performance-review gate for stage 2."""
from __future__ import annotations

import argparse
import copy
import csv
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from tools import d1_reserved_thermal as rule
from tools import d1_external_rules_study as existing

ROOT = rule.P.ROOT
LOCAL = ROOT / 'output/reserved_thermal_20261008_v1'
BUNDLE = ROOT / 'docs/results/reserved_thermal_01'
VERSION = 'reserved-thermal-stage2-v1'
REFERENCE = ROOT/'docs/results/external_rules_02'


def object_digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf8')).hexdigest()


def immutable(path, obj):
    path = Path(path)
    if path.exists():
        if read(path) != obj:
            raise ValueError('immutable registration already exists: '+str(path.name))
        return
    write(path, obj)


def validate_design_chain(contract):
    paths = sorted((LOCAL/'design_revisions').glob('*.json'))
    if not paths:
        raise ValueError('design revision missing')
    previous = None
    for number, path in enumerate(paths, 1):
        item = read(path)
        if path.name != f'{number:03d}.json' or item['revision'] != number or item['parent_sha256'] != previous:
            raise ValueError('design revision chain or rollback')
        if number == 1:
            if item['design'] != contract['design']:
                raise ValueError('initial campaign design changed')
        else:
            if item['previous_design_sha256'] != object_digest(read(paths[number-2])['design']):
                raise ValueError('previous design digest mismatch')
            review_path = LOCAL/'design_reviews'/item['review_file']
            if digest(review_path) != item['review_sha256']:
                raise ValueError('design review evidence changed')
            review = read(review_path)
            if review['decision'] != 'REVISE_BEFORE_RUN' or review['design'] != read(paths[number-2])['design']:
                raise ValueError('unauthorized design revision')
            if digest(BUNDLE/'ASTRA_REVIEW.md') != review['report_sha256']:
                raise ValueError('design review report changed')
            validate_repair_design(review['design'], item['design'])
        previous = digest(path)
    return item, previous


def validate_repair_design(old, new):
    expected = dict(old, version='reserved-thermal-review-candidate-v2',
        retained_calendar='preserve each pending absolute start lower bound; log expiry or conflict',
        terminal_budget='B_final-J_common_0_120; partial work separately marked',
        pending_reservation='first seen and issued times separate during unknown overrun',
        diagnostics='candidate rejection, callback fallback and actual request violation separate')
    if old['version'] != 'reserved-thermal-review-candidate-v1' or new != expected:
        raise ValueError('design change outside reviewed repairs')


def register_design(contract):
    folder = LOCAL/'design_revisions'
    if not folder.exists():
        immutable(folder/'001.json', dict(revision=1, parent_sha256=None, design=contract['design']))
    latest, parent = validate_design_chain(contract)
    if latest['design'] != rule.specification():
        review_path = BUNDLE/'astra_review.json'
        review = read(review_path)
        if review['decision'] != 'REVISE_BEFORE_RUN' or review['design'] != latest['design']:
            raise ValueError('matching repair review required')
        validate_repair_design(latest['design'], rule.specification())
        sha = digest(review_path)
        archive = LOCAL/'design_reviews'/(sha+'.json')
        if not archive.exists():
            archive.parent.mkdir(parents=True,exist_ok=True)
            with archive.open('xb') as stream:
                stream.write(review_path.read_bytes())
        if digest(archive) != sha:
            raise ValueError('review archive mismatch')
        number = latest['revision']+1
        immutable(folder/f'{number:03d}.json', dict(revision=number, parent_sha256=parent,
            design=rule.specification(), previous_design_sha256=object_digest(latest['design']),
            review_sha256=sha, review_file=archive.name, registered_utc=utc()))
        journal('design_revision', revision=number, review_sha256=sha)
    return validate_design_chain(contract)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def write(path, obj):
    existing.write(path, obj)


def journal(event, **fields):
    with (LOCAL / 'executions.jsonl').open('a', encoding='utf8') as stream:
        stream.write(json.dumps(dict(utc=utc(), event=event, **fields), ensure_ascii=False,
            allow_nan=False)+'\n')
        stream.flush()


def consumption():
    path = LOCAL / 'executions.jsonl'
    entries = [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()] if path.exists() else []
    starts = [x for x in entries if x['event'] == 'start']
    return dict(environment_starts=len(starts), fixture_starts=sum(x['kind']=='fixture' for x in starts),
        pilot_starts=sum(x['kind']=='pilot' for x in starts), training_episodes=0, device_commands=0,
        failed_starts=sum(x['event']=='failed' for x in entries))


def source_hashes():
    old = existing.existing_sources()
    old.update({p.relative_to(ROOT).as_posix(): digest(p) for p in (
        Path(rule.__file__), Path(__file__), ROOT/'tools/test_d1_reserved_thermal.py')})
    # Actual helper implementations used for accounting/registration are pinned.
    for name in ('tools/d1_external_rules.py','tools/d1_external_rules_study.py'):
        old[name] = digest(ROOT/name)
    return old


def prepare():
    if (LOCAL/'owner.json').exists():
        raise RuntimeError('active or unresolved campaign owner; registration cannot change')
    LOCAL.mkdir(parents=True, exist_ok=True)
    BUNDLE.mkdir(parents=True, exist_ok=True)
    path = LOCAL/'campaign.json'
    if path.exists():
        contract = read(path)
        if (contract['version'] != VERSION or contract['environment_budget'] != 20000 or
                contract['stage2_environment_budget'] != 512 or contract['maximum_training_episodes'] != 6144):
            raise ValueError('unrelated output owner or campaign')
    else:
        if (BUNDLE/'campaign.json').exists():
            raise RuntimeError('existing campaign local state missing; budget cannot be recreated')
        contract = dict(version=VERSION, created_utc=utc(),
            start_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            environment_budget=20000, stage2_environment_budget=512, maximum_training_episodes=6144,
            current_stage='stage2_fixture_and_design_review', training_allowed=False,
            pilot_requires_astra_review=True, performance_results_seen=False,
            protected_sources=existing.existing_sources(), design=rule.specification(),
            planned_policy_rows=480, planned_new_rule_rows=48, planned_reused_rows=432,
            reference_input_sha256=digest(ROOT/'docs/results/external_rules_02/inputs.json'),
            experiment_ready=False, strict_supported=False, device_commands=0)
        write(path, contract)
        write(BUNDLE/'campaign.json', contract)
    for name, sha in contract['protected_sources'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('protected source changed before registration: '+name)
    design, design_sha = register_design(contract)
    # A repair registers a new immutable revision; it does not reset consumption.
    current = source_hashes()
    latest_path = LOCAL/'active_registration.json'
    latest = read(latest_path) if latest_path.exists() else None
    if latest is None or latest['source_hashes'] != current or latest.get('design_revision_sha256') != design_sha:
        revisions = list((LOCAL/'registrations').glob('*.json'))
        revision = len(revisions)+1
        latest = dict(revision=revision, registered_utc=utc(), source_hashes=current,
            design=rule.specification(), head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            dirty=True, before_performance_results=consumption()['pilot_starts']==0,
            design_revision=design['revision'], design_revision_sha256=design_sha,
            parent_registration_sha256=digest(LOCAL/f"registrations/{revision-1:03d}.json") if revision>1 else None,
            consumption=consumption())
        immutable(LOCAL/f'registrations/{revision:03d}.json', latest)
        write(latest_path, latest)
        write(BUNDLE/'implementation_registration.json', latest)
        journal('registration', revision=revision)
    return check()


def check():
    c = read(LOCAL/'campaign.json')
    r = read(LOCAL/'active_registration.json')
    if (c['version'] != VERSION or c['stage2_environment_budget'] != 512 or c['environment_budget'] != 20000 or
            c['maximum_training_episodes'] != 6144):
        raise ValueError('campaign budget drift')
    design, design_sha = validate_design_chain(c)
    if design['design'] != rule.specification() or r['design'] != rule.specification():
        raise ValueError('design drift; Astra review required')
    if r.get('design_revision_sha256') != design_sha or r.get('design_revision') != design['revision']:
        raise ValueError('design revision rollback')
    registrations = sorted((LOCAL/'registrations').glob('*.json'))
    if r['revision'] != len(registrations) or read(registrations[-1]) != r:
        raise ValueError('implementation registration rollback')
    if r['source_hashes'] != source_hashes():
        raise ValueError('source drift; register repair before next fixture')
    for path, sha in c['protected_sources'].items():
        if digest(ROOT/path) != sha:
            raise ValueError('protected source or model changed: '+path)
    if digest(ROOT/'docs/results/external_rules_02/inputs.json') != c['reference_input_sha256']:
        raise ValueError('reference input drift')
    used = consumption()
    if used['environment_starts'] > 20000 or used['fixture_starts']+used['pilot_starts'] > 512:
        raise ValueError('cumulative consumption exceeds budget')
    return dict(campaign=c, registration=r, consumption=used)


@contextmanager
def owner():
    path = LOCAL/'owner.json'
    with path.open('x', encoding='utf8') as stream:
        json.dump(dict(pid=os.getpid(), utc=utc(), version=VERSION), stream)
    try:
        yield
    finally:
        if path.exists() and read(path)['pid'] == os.getpid():
            path.unlink()


def begin_environment(kind, name):
    check()
    c = consumption()
    if c['environment_starts'] >= 20000 or c['fixture_starts']+c['pilot_starts'] >= 512:
        raise RuntimeError('cumulative campaign or stage2 budget exhausted')
    if kind == 'pilot':
        require_review()
    elif kind != 'fixture':
        raise ValueError('stage2 cannot start training or final evaluation')
    if not (LOCAL/'owner.json').exists() or read(LOCAL/'owner.json')['pid'] != os.getpid():
        raise RuntimeError('environment owner missing')
    number = c['environment_starts']+1
    journal('start', kind=kind, name=name, number=number,
        revision=read(LOCAL/'active_registration.json')['revision'])
    return number


def require_review(path=None, expected_sources=None, expected_design=None):
    path = Path(path) if path is not None else BUNDLE/'astra_review.json'
    if not path.exists():
        raise RuntimeError('Astra equation review missing: performance pilot is closed')
    review = read(path)
    if review.get('decision') not in ('PROCEED_PILOT', 'PROCEED_RULE_ONLY'):
        raise RuntimeError('Astra review does not permit performance pilot')
    expected_sources = source_hashes() if expected_sources is None else expected_sources
    expected_design = rule.specification() if expected_design is None else expected_design
    if review.get('source_hashes') != expected_sources or review.get('design') != expected_design:
        raise RuntimeError('Astra reviewed version does not match implementation')
    return review


def reference_rows():
    """Read only completed, input/source-bound rows; never run an old campaign."""
    contract = read(REFERENCE/'contract.json')
    artifact = read(REFERENCE/'artifact_verification.json')
    completion = read(REFERENCE/'completion.json')
    if artifact['status'] != 'PASSED' or completion['status'] != 'completed':
        raise ValueError('reference is not completed/audited')
    for name in ('results.csv','contract.json','inputs.json','sources.json','mapping.md','completion.json'):
        if digest(REFERENCE/name) != artifact['files'][name]:
            raise ValueError('reference artifact drift: '+name)
    for name, sha in contract['old_sources'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('reference source/result drift: '+name)
    if completion['binding']['contract_sha256'] != digest(REFERENCE/'contract.json'):
        raise ValueError('Triton execution contract mismatch')
    for name, sha in completion['binding']['code_sha256'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Triton execution source mismatch')
    old_completion = read(existing.BUNDLE/'completion.json')
    if old_completion['status'] != 'completed':
        raise ValueError('Band campaign incomplete')
    for name, sha in old_completion['source_sha256'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Band execution source mismatch')
    inputs = read(REFERENCE/'inputs.json')
    policies = list(contract['configs'])+['BAND_HEFT_WHOLE_REQUEST_ADAPT_V1','SHARED_EFT',
        'ENERGY_AP_REQUEST_V1','ARRIVED_QUEUE_J_PEAK_AREA_V1']
    def typed(value):
        if value=='': return None
        if value in ('True','False'): return value=='True'
        try: return float(value) if any(c in value for c in '.eE') else int(value)
        except ValueError: return value
    with (REFERENCE/'results.csv').open(encoding='utf8',newline='') as stream:
        rows = [dict((k,typed(v)) for k,v in row.items()) for row in csv.DictReader(stream)]
    selected = [row for row in rows if row['scope']=='resource' and row['environment']=='immediate_allow'
        and row['policy'] in policies]
    jobs = [(work,context) for work in inputs['workloads'] for context in contract['contexts']]
    expected = {(work['seed'],work['family'],context,policy) for work,context in jobs for policy in policies}
    keys = [(row['seed'],row['family'],row['context'],row['policy']) for row in selected]
    if len(jobs)!=48 or len(policies)!=9 or len(selected)!=432 or len(set(keys))!=432 or set(keys)!=expected:
        raise ValueError('reference condition/policy coverage mismatch')
    count = {(work['seed'],work['family']):len(work['tickets']) for work in inputs['workloads']}
    for row in selected:
        if row['planned'] != count[(row['seed'],row['family'])]:
            raise ValueError('reference planned request mismatch')
        row.update(reuse_source='docs/results/external_rules_02/results.csv',
            reuse_file_sha256=digest(REFERENCE/'results.csv'), reuse_original_origin=row['origin'])
    evidence = dict(input_sha256=digest(REFERENCE/'inputs.json'),
        source_files={name:digest(ROOT/name) for name in contract['old_sources']},
        execution_bindings=completion['binding'], reference_artifact_sha256=digest(REFERENCE/'artifact_verification.json'),
        band_completion_sha256=digest(existing.BUNDLE/'completion.json'),
        reused_csv_sha256=digest(REFERENCE/'results.csv'),
        rows_sha256=object_digest(selected), policies=policies, conditions=48, rows=432,
        representative=dict(seed=inputs['workloads'][0]['seed'],context='mean',families=['queue','sustained']))
    return inputs, jobs, selected, evidence


def prepare_pilot():
    check()
    _, jobs, rows, evidence = reference_rows()
    manifest = dict(version='reserved-thermal-pilot-v1', design=rule.specification(),
        source_hashes=source_hashes(), reference=evidence,
        conditions=[dict(seed=w['seed'],family=w['family'],context=ctx,
            tickets_sha256=object_digest(w['tickets'])) for w,ctx in jobs],
        new_rows=48,reused_rows=432,logical_rows=480,
        ap_optimizer_grid='integer seconds + state transition boundaries',
        ap_evaluation_grid='common integer seconds 35..180; incomplete 35..120 separately',
        incremental_controller_device_cost='existing model assumption 0; PC callback time measured',
        training_episodes=0,device_commands=0,experiment_ready=False)
    path = LOCAL/'pilot_manifest.json'
    revisions = LOCAL/'pilot_registrations'
    if path.exists() and not revisions.exists():
        immutable(revisions/'001.json',dict(revision=1,parent_sha256=None,manifest=read(path)))
    previous = read(path) if path.exists() else None
    if previous != manifest:
        if previous is not None:
            if consumption()['pilot_starts'] or dict(previous,source_hashes=manifest['source_hashes']) != manifest:
                raise ValueError('pilot manifest drift; evaluated settings cannot change')
        numbered=sorted(revisions.glob('*.json'))
        number=len(numbered)+1
        registration=dict(revision=number,parent_sha256=digest(numbered[-1]) if numbered else None,
            manifest=manifest)
        immutable(revisions/f'{number:03d}.json',registration)
        write(path,manifest)
        journal('pilot_registration',revision=number,before_performance=True)
    write(BUNDLE/'pilot_manifest.json', manifest)
    newest=sorted(revisions.glob('*.json'))[-1]
    write(BUNDLE/'pilot_registration.json',read(newest))
    write(BUNDLE/'reuse_manifest.json',evidence)
    return manifest


def run_pilot():
    check(); require_review()
    manifest = prepare_pilot()
    inputs, jobs, reused, _ = reference_rows()
    frozen, _ = rule.P.inputs(rule.P.BUNDLE)
    binding = dict(manifest_sha256=digest(LOCAL/'pilot_manifest.json'),source_hashes=source_hashes())
    rows=[]
    with owner():
        for index,(work,context) in enumerate(jobs):
            check(); require_review()
            name=f"{work['seed']}/{work['family']}/{context}"
            path=LOCAL/f'pilot_items/{index:04d}.json.gz'
            if path.exists():
                with gzip.open(path,'rt',encoding='utf8') as stream: item=json.load(stream)
                if item['binding']!=binding or item['identity']!=name:
                    raise ValueError('pilot cache/source mismatch')
                finishes=[json.loads(line) for line in (LOCAL/'executions.jsonl').read_text(encoding='utf8').splitlines()
                    if line.strip()]
                receipts=[e for e in finishes if e['event']=='completed' and e.get('kind')=='pilot' and e['name']==name]
                if not receipts or receipts[-1]['item_sha256'] != digest(path):
                    raise ValueError('pilot cache completion receipt mismatch')
                existing.audit(item['result'],work['tickets'])
            else:
                number=begin_environment('pilot',name); began=time.perf_counter()
                try:
                    row,result,c,extra=rule.simulate(frozen,inputs['initial'],work['tickets'],context,lambda:None)
                    existing.audit(result,work['tickets'])
                    common,curves=existing.metrics(result,c,inputs['initial'],frozen)
                    row.update(common,seed=work['seed'],family=work['family'],context=context,
                        scope='resource',environment='immediate_allow',origin='new_reserved_thermal')
                    item=dict(identity=name,binding=binding,row=row,result=result,
                        records=c.records,transactions=c.book.transactions,events=c.book.breaks,
                        pending=c.book.pending,first_seen=c.book.first_seen,curves=curves)
                    path.parent.mkdir(parents=True,exist_ok=True)
                    temp=path.with_suffix('.tmp')
                    temp.write_bytes(gzip.compress(json.dumps(item,ensure_ascii=False,allow_nan=False).encode('utf8'),mtime=0))
                    temp.replace(path)
                    journal('completed',kind='pilot',name=name,number=number,item_sha256=digest(path),
                        host_wall_s=time.perf_counter()-began)
                except BaseException as error:
                    journal('failed',kind='pilot',name=name,number=number,error=repr(error))
                    raise
            rows.append(item['row'])
            write(LOCAL/'pilot_progress.json',dict(saved_rows=len(rows),total=48,consumption=consumption()))
    check(); require_review()
    if len(rows)!=48: raise ValueError('incomplete pilot')
    existing.csv_write(BUNDLE/'pilot_results.csv',reused+rows)
    write(BUNDLE/'pilot_completion.json',dict(status='completed',new_rows=48,reused_rows=432,
        logical_rows=480,binding=binding,consumption=consumption(),training_episodes=0,device_commands=0))
    return dict(rows=480,consumption=consumption())


def fixture_tickets():
    def ticket(i, task, at):
        return dict(id='reserved-fixture/'+str(i), ordinal=i, task=task,
            priority='urgent' if task=='classification' else 'normal', arrival_ns=round(at*1e9),
            deadline_offset_ns=round((1.5 if task=='classification' else 6)*1e9))
    common = [ticket(0, 'classification', 35.), ticket(1, 'detection', 35.05)]
    return [
        ('single', common[:1], 'mean'),
        ('mixed', common+[ticket(2,'classification',35.1), ticket(3,'detection',35.2)], 'mean'),
        ('suffix_a', common+[ticket(2,'classification',36.)], 'mean'),
        ('suffix_b', common+[ticket(2,'detection',37.)], 'mean'),
        ('overrun', common+[ticket(2,'classification',35.1), ticket(3,'detection',35.2)], 'long_context'),
    ]


def run_fixtures():
    prepare()
    frozen, case = rule.P.inputs(rule.P.BUNDLE)
    initial = {k: case['initial'][k] for k in ('preload','preload_power_w')}
    output = {}
    with owner():
        for name, tickets, context in fixture_tickets():
            started = {}
            def before():
                started['number'] = begin_environment('fixture', name)
            try:
                row, result, controller, extra = rule.simulate(frozen, initial, tickets, context, before)
                number = started['number']
                payload = dict(name=name, context=context, tickets=tickets, row=row, result=result,
                    records=controller.records, transactions=controller.book.transactions,
                    reservation_breaks=controller.book.breaks, observed_j=controller.observed_j,
                    observed_at_s=controller.now, running_peak_c=controller.running_peak_c,
                    history=controller.history, observed_responses=controller.observed_responses,
                    pending=controller.book.pending,first_seen=controller.book.first_seen)
                path = LOCAL/f'fixtures/{number:05d}_{name}.json.gz'
                path.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(path,'wt',encoding='utf8') as stream:
                    json.dump(payload,stream,ensure_ascii=False,allow_nan=False)
                journal('completed', kind='fixture', name=name, number=number)
                output[name] = payload
            except BaseException as error:
                journal('failed', kind='fixture', name=name, number=started.get('number'),
                    error=type(error).__name__+': '+str(error))
                raise
    write(BUNDLE/'fixture_summary.json',dict(utc=utc(), consumption=consumption(),
        rows=[dict(name=name, **payload['row']) for name,payload in output.items()]))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','check','fixtures','prepare-pilot','pilot','status'))
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare()
    elif args.action == 'check':
        result = check()
    elif args.action == 'fixtures':
        fixtures = run_fixtures()
        result = dict(fixtures=list(fixtures), consumption=consumption())
    elif args.action == 'pilot':
        result = run_pilot()
    elif args.action == 'prepare-pilot':
        result = prepare_pilot()
    else:
        result = consumption()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
