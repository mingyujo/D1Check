"""Bounded Triton rule study: preregister, audit, resumable PC execution."""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

from tools import d1_triton_rules as rules
from tools import d1_external_rules_study as prior

ROOT = prior.ROOT
BUNDLE = ROOT / 'docs/results/external_rules_02'
LOCAL = ROOT / 'output/external_rules_20261007_v2'
OLD = prior.BUNDLE
read, write, csv_write = prior.read, prior.write, prior.csv_write
TRITON_SHA = '3af839d613da6995051f9bcfab00efe2eac87d4c'
STARPU_SHA = '356c8e443d75dfec0eb9d00a95b92d6b3fb1b486'
# Conservative accounting anchor includes investigation/implementation before prepare.
START = '2026-10-07T13:45:00+00:00'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def journal(event, **fields):
    LOCAL.mkdir(parents=True, exist_ok=True)
    with (LOCAL / 'executions.jsonl').open('a', encoding='utf8') as stream:
        stream.write(json.dumps(dict(utc=stamp(), event=event, **fields), ensure_ascii=False) + '\n')


def consumption():
    path = LOCAL / 'executions.jsonl'
    entries = [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()] if path.exists() else []
    return dict(environment_starts=sum(x['event'] == 'start' for x in entries),
                fixture_starts=sum(x['event'] == 'start' and x.get('kind') == 'fixture' for x in entries),
                formal_starts=sum(x['event'] == 'start' and x.get('kind') == 'formal' for x in entries))


def begin_environment(kind, **fields):
    if consumption()['environment_starts'] >= 400:
        raise RuntimeError('400 environment budget exhausted')
    if (datetime.now(timezone.utc) - datetime.fromisoformat(START)).total_seconds() >= 9600:
        raise RuntimeError('last 20 minutes reserved for saving/documentation')
    journal('start', kind=kind, **fields)


def prepare():
    BUNDLE.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True, exist_ok=True)
    if (BUNDLE / 'contract.json').exists():
        return check()
    inventory = []
    sources = [('triton', 'triton-inference-server/core', TRITON_SHA, name)
               for name in ('src/rate_limiter.cc', 'src/rate_limiter.h', 'LICENSE')]
    sources.append(('starpu', 'starpu-runtime/starpu', STARPU_SHA,
                    'src/sched_policies/deque_modeling_policy_data_aware.c'))
    for system, repo, sha, path in sources:
        url = f'https://raw.githubusercontent.com/{repo}/{sha}/{path}'
        data = urllib.request.urlopen(url, timeout=30).read()
        target = LOCAL / 'sources' / system / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        inventory.append(dict(system=system, commit=sha, path=path,
                              url=f'https://github.com/{repo}/blob/{sha}/{path}',
                              raw_url=url, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)))
        if system == 'triton' and path == 'LICENSE':
            (BUNDLE / 'TRITON_LICENSE.txt').write_bytes(data)
    write(BUNDLE / 'sources.json', dict(sampled_utc=stamp(), files=inventory,
        triton=dict(rule='Rate limiter fixed specific FIFO instances',
            observations=['pending queues', 'instance available', 'token counts', 'completed executions', 'configured priority'],
            decisions='submit->stage->immediate AttemptAllocation; Release increments count and restages before final attempt',
            priority='exec_count * max(priority,1); min first; top-only allocation attempt',
            default_priority=1, zero_priority_means=1, resources='configured named counts; off by default',
            preemption=False, cost_prediction=None, missed_deadline='no drop in configured path; D1Check external evaluation',
            source_symbols={'rate_limiter.cc': ['OnStage', 'OnRelease', 'AttemptAllocation', 'StageInstanceIfAvailable',
                                                 'ModelInstanceContext::Release', 'ScaledPriority'],
                            'rate_limiter.h': ['ScaledPriorityComparator']},
            documentation='https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/rate_limiter.html'),
        starpu=dict(level='C - deferred for this batch',
            score='alpha*(expected_end-min_end)+beta*transfer_penalty+gamma*task_energy+idle_extension_cost',
            defaults=dict(alpha=1, beta=1, gamma_us_per_j=1000, idle_power_w=0),
            gaps=['task-attributed energy model not equivalent to state whole-device J',
                  'separate data residency/transfer/prefetch costs not measured',
                  'independent worker queues must respect unsupported D1Check joint states without changing source ranking'],
            meaning='not a claim that any limited adaptation is impossible; this bounded batch does not invent these inputs')))
    # Byte-identical prior input includes exogenous gate fields, not used here.
    (BUNDLE / 'inputs.json').write_bytes((OLD / 'inputs.json').read_bytes())
    original = read(OLD / 'contract.json')['old_sources']
    original = dict(original)
    for name in ('tools/d1_external_rules.py', 'tools/d1_external_rules_study.py',
                 'tools/d1_external_rules_report.py', 'docs/results/external_rules_01/results.csv',
                 'docs/results/external_rules_01/contract.json', 'docs/results/external_rules_01/inputs.json'):
        original[name] = digest(ROOT / name)
    users = [x for x in ROOT.iterdir() if x.is_file() and x.suffix.lower() in ('.html', '.pdf')]
    users += [x for x in (ROOT / '.vscode').rglob('*') if x.is_file()]
    for folder in ROOT.glob('*_files'):
        users += [x for x in folder.rglob('*') if x.is_file()]
    write(LOCAL / 'preserved_user_files.json', {x.relative_to(ROOT).as_posix(): digest(x) for x in users})
    spec = dict(version='external-rules-12-triton-v1', frozen_utc=stamp(),
        head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), dirty=True,
        start_utc=START, maximum_wall_s=10800, save_reserve_s=1200, environment_budget=400,
        configs=rules.CONFIGS, contexts=['mean', 'short_context', 'long_context'],
        conditions=48, formal_environment_runs=240, reused_policy_rows=384, final_rows=624,
        input_sha256=digest(BUNDLE / 'inputs.json'), mapping_sha256=digest(BUNDLE / 'mapping.md'),
        source_sha256=digest(BUNDLE / 'sources.json'), old_sources=original,
        physical_model_sha256=rules.prior.p.MODEL_SHA, initial_sha256=rules.prior.p.INITIAL_SHA,
        representative=dict(seed=610810001, context='mean', families=['queue', 'sustained']),
        seed_is_new_holdout=False, tune_after_results=False, device_commands=0, training_episodes=0,
        energy_window_s=[0, 120], ap_window_s=[35, 180], ap_safety_limit_c=None,
        strict_supported=False, experiment_ready=False, starpu='deferred; no performance rows')
    write(BUNDLE / 'contract.json', spec)
    return check()


def check():
    spec = read(BUNDLE / 'contract.json')
    for name, field in [('inputs.json', 'input_sha256'), ('mapping.md', 'mapping_sha256'), ('sources.json', 'source_sha256')]:
        if digest(BUNDLE / name) != spec[field]:
            raise ValueError('frozen evidence drift: ' + name)
    for name, sha in spec['old_sources'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('old source or result drift: ' + name)
    if spec['configs'] != rules.CONFIGS:
        raise ValueError('config drift')
    for name, sha in read(LOCAL / 'preserved_user_files.json').items():
        if digest(ROOT / name) != sha:
            raise ValueError('user artifact drift')
    return spec


def read_item(path):
    with gzip.open(path, 'rt', encoding='utf8') as stream:
        return json.load(stream)


def run(pilot=False):
    spec = check()
    sources = {name: digest(ROOT / name) for name in ('tools/d1_triton_rules.py', 'tools/d1_triton_study.py')}
    registered = LOCAL / 'registered_before_run.json'
    binding = dict(code_sha256=sources, contract_sha256=digest(BUNDLE / 'contract.json'))
    if registered.exists():
        if read(registered)['binding'] != binding:
            raise ValueError('execution source drift; no silent resume')
    else:
        write(registered, dict(utc=stamp(), binding=binding, head=spec['head'], dirty=True))
    lock = LOCAL / 'owner.json'
    with lock.open('x', encoding='utf8') as stream:
        json.dump(dict(pid=os.getpid(), utc=stamp()), stream)
    rows = []
    try:
        inputs = read(BUNDLE / 'inputs.json')
        frozen, _ = rules.prior.p.inputs(rules.prior.p.BUNDLE)
        initial = inputs['initial']
        jobs = [(work, context, policy) for work in inputs['workloads']
                for context in spec['contexts'] for policy in rules.CONFIGS]
        (LOCAL / 'items').mkdir(exist_ok=True)
        for index, (work, context, policy) in enumerate(jobs):
            if pilot and index >= 5:
                break
            path = LOCAL / 'items' / f'{index:04d}.json.gz'
            identity = dict(scope='resource', environment='immediate_allow', seed=work['seed'],
                            family=work['family'], context=context, policy=policy)
            if path.exists():
                item = read_item(path)
                if any(item['row'][k] != v for k, v in identity.items()):
                    raise ValueError('cached identity drift')
                if item['binding'] != binding:
                    raise ValueError('cached binding drift')
            else:
                begin_environment('formal', index=index)
                began = time.perf_counter()
                result, controller = rules.simulate(frozen, initial, work['tickets'], context, policy)
                prior.audit(result, work['tickets'])
                # Final observe has seen lane returns even if no queue remains.
                if all(x['status'] == 'succeeded' for x in result['ledger']):
                    assert sum(controller.rate.executions.values()) == len(work['tickets'])
                row, extra = prior.metrics(result, controller, initial, frozen)
                row.update(identity, origin='new_triton',
                    rate_resource_waits=sum(x['event'] == 'resource_wait' for x in controller.rate.events),
                    completed_execution_count=sum(controller.rate.executions.values()))
                item = dict(row=row, ledger=result['ledger'], decisions=result['decisions'],
                            rate_events=controller.rate.events, binding=binding, **extra)
                data = gzip.compress(json.dumps(item, ensure_ascii=False, allow_nan=False).encode('utf8'), mtime=0)
                tmp = path.with_suffix('.tmp')
                tmp.write_bytes(data)
                tmp.replace(path)
                journal('finish', kind='formal', index=index, wall_s=time.perf_counter() - began, item_sha256=digest(path))
            rows.append(item['row'])
            if len(rows) % 10 == 0:
                write(LOCAL / 'progress.json', dict(status='running', rows=len(rows), total=len(jobs), **consumption()))
                print(f'{len(rows)}/{len(jobs)}', flush=True)
        check()
        for name, sha in sources.items():
            if digest(ROOT / name) != sha:
                raise ValueError('source changed during batch')
        csv_write(LOCAL / 'new_results.csv', rows)
        write(LOCAL / 'progress.json', dict(status='pilot_completed' if pilot else 'completed',
                                          rows=len(rows), total=len(jobs), **consumption()))
        if not pilot:
            assert len(rows) == 240
            write(LOCAL / 'completion.json', dict(status='completed', utc=stamp(), rows=len(rows),
                planned_requests=sum(x['planned'] for x in rows), **consumption(),
                binding=binding, device_commands=0, training_episodes=0, experiment_ready=False))
    except BaseException as error:
        import traceback
        journal('failure', error=repr(error))
        write(LOCAL / 'failure.json', dict(utc=stamp(), saved_rows=len(rows), error=repr(error), stack=traceback.format_exc()))
        raise
    finally:
        lock.unlink()
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'check', 'run'])
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    if args.action == 'run':
        run(args.pilot)
    else:
        print(json.dumps(prepare() if args.action == 'prepare' else check(), ensure_ascii=False, indent=2))
