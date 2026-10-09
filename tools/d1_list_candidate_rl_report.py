"""Publish existing bounded-gate evidence; never runs an environment or trains."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import io
import json
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['identity', 'planned', 'completed', 'incomplete', 'urgent_failure',
          'normal_failure', 'urgent_p95_ms', 'normal_mean_ms', 'energy_j',
          'peak_ap_c', 'native_seconds']
LABELS = ['검사 ID', '예정', '완료', '미완료', '긴급 기한 위반', '일반 기한 위반',
          '긴급 P95 (ms)', '일반 평균 (ms)', '에너지 J120', '최고 모형 AP (°C)', 'PC 시간 (초)']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8', newline='\n')


def write_csv(path, fields, rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding='utf-8', newline='\n')


def publish(run, output):
    """Only read completed evidence and write small derived files."""
    first = read(run / 'summary.json')
    additional = read(run / 'additional_checks.json')
    representation = read(run / 'representation_checks.json')
    tree_path = run / 'checkpoint_tree_verification.json'
    tree = read(tree_path) if tree_path.exists() else dict(status='NOT_RUN')
    unit_path = run / 'unit_test_record.json'
    unit = read(unit_path) if unit_path.exists() else dict(status='NOT_RECORDED', passed=None)
    for record in (first, additional, representation):
        if record['status'] != 'completed':
            raise ValueError('incomplete evidence cannot be published as a completed gate')
    starts, completed = {}, {}
    for line in (run / 'execution.jsonl').read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        target = starts if 'event' not in record else completed
        if record['number'] in target:
            raise ValueError('duplicate start/completion number')
        target[record['number']] = record
    if set(starts) != set(range(1, 33)) or set(completed) != set(starts):
        raise ValueError('expected exactly 32 registered, completed starts')
    rows = []
    for number, start in sorted(starts.items()):
        end = completed[number]
        if end['status'] != 'completed' or end['identity'] != start['identity']:
            raise ValueError('failed or mismatched execution')
        path = run / 'items' / (start['identity'] + '.json.gz')
        if hashlib.sha256(path.read_bytes()).hexdigest() != end['artifact_sha256']:
            raise ValueError('changed raw artifact: ' + start['identity'])
        item = json.loads(gzip.decompress(path.read_bytes()))
        row = dict(identity=start['identity'], **item['row'])
        if row['planned'] != start['planned'] or row['completed'] != end['completed']:
            raise ValueError('request denominator mismatch')
        rows.append(row)
    consumption = dict(new_native_environment_starts=32, cumulative_environment_starts=6549,
                       new_learning_starts=0, cumulative_learning_starts=641,
                       optimizer_steps=0, device_commands=0, failed=0,
                       planned_requests=sum(r['planned'] for r in rows),
                       completed_requests=sum(r['completed'] for r in rows))
    if consumption['planned_requests'] != 1748 or consumption['completed_requests'] != 1748:
        raise ValueError('unexpected total requests')
    summary = dict(task=first['registration']['task'],
                   status='implementation_and_bounded_validation_completed', consumption=consumption,
                   registration=first['registration'],
                   implementation=dict(opt_in_engine=True, old_engine_unchanged=True,
                       public_journal=True, finite_hold=True, physical_bank=True, L0=True,
                       risk5_fixed_rule=True, masked_actor_critic=True, posthoc_targets=True,
                       episode_loss=True, controller_RNG_archive=True,
                       training_epoch_dual_minibatch_runner=False, live_engine_resume=False),
                   tests=dict(unit_tests_passed=unit['passed'], unit_test_record=unit,
                       legacy_nonregression=first['nonregression'],
                       native_event_zero_duration=True, original_tensor_alias=first['tensor_alias'],
                       original_full_control_alias=first['input_alias'], C_next_repair=additional['repair'],
                       gradient=additional['gradient'], checkpoint=additional['checkpoint'],
                       checkpoint_tree=tree),
                   c2=first['c2'], behavior=first['behavior'],
                   known_success_replay=first['known_success_replays'],
                   representation=dict(scope=representation['scope'],
                       cases=[dict(context=c['context'], counts=c['counts']) for c in representation['cases']],
                       full_new_policy_chronology_proven=False,
                       credit_source='optimistic upper .25, no original wait debit replay'),
                   learning_ready=False, not_selected_as_final_method=True,
                   remaining=['actual epoch/minibatch/dual training runner and post-update resume equivalence',
                       'full old successful schedule representation under new hold/credit chronology',
                       'fresh common-budget three-seed development and final performance',
                       'phone/controller energy and surface-temperature support'],
                   scope='measured-coefficient PC validation; no physical policy improvement or RL training',
                   frozen_model_sha256=first['registration']['frozen_model_sha256'],
                   frozen_initial_sha256=first['registration']['frozen_initial_sha256'])
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'summary.json', summary)
    write_csv(output / 'native_results.csv', FIELDS, rows)
    c2 = [dict(identity=c['identity'], **c['row'], **c['core_response_s']) for c in first['c2']]
    write_csv(output / 'c2_results.csv', FIELDS + ['C1', 'D1', 'C2'], c2)
    coverage = [dict(context=c['context'], **r) for c in representation['cases'] for r in c['records']]
    write_csv(output / 'source_intent_coverage.csv',
              ['context', 'at_ns', 'source_action_kind', 'status', 'reason', 'source_credit_s', 'declared_wait_s'],
              coverage)
    table = '<table><thead><tr>' + ''.join('<th>' + s + '</th>' for s in LABELS) + '</tr></thead><tbody>'
    table += ''.join('<tr>' + ''.join('<td>' + html.escape(str(row[key])) + '</td>' for key in FIELDS)
                     + '</tr>' for row in rows) + '</tbody></table>'
    template = (ROOT / 'tools/templates/d1_list_candidate_gate.html').read_text(encoding='utf-8')
    (output / 'index.html').write_text(template.replace('@@TABLE@@', table), encoding='utf-8', newline='\n')
    return dict(status='PASS', raw_artifacts_sha_checked=32, native_rows=len(rows),
                source_intent_rows=len(coverage), new_native_starts=0,
                recorded_gate_consumption=consumption)


def check_browser(run, output):
    """Use a fresh owned headless profile, leaving existing browsers untouched."""
    target = (output / 'index.html').resolve()
    profile = (run / ('browser_profile_' + uuid.uuid4().hex[:8])).resolve()
    profile.mkdir()
    shot = (run / 'dashboard.png').resolve()
    chrome = Path('C:/Program Files/Google/Chrome/Application/chrome.exe')
    result = subprocess.run([str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
                             '--no-default-browser-check', '--user-data-dir=' + str(profile),
                             '--window-size=1800,1080', '--screenshot=' + str(shot),
                             '--dump-dom', target.as_uri()], capture_output=True, timeout=45,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    dom = result.stdout.decode('utf-8')
    if result.returncode or dom.count('<tbody>') != 1 or dom.count('<tr>') != 33:
        raise ValueError('offline browser rendering failed')
    if not shot.exists() or shot.stat().st_size == 0 or '@@TABLE@@' in dom:
        raise ValueError('offline screenshot/table missing')
    for name in ('README.md', 'summary.json', 'native_results.csv', 'source_intent_coverage.csv'):
        if not (output / name).exists():
            raise ValueError('broken local dashboard link: ' + name)
    evidence = dict(status='PASS', surface='isolated headless Chrome; offline file page',
                    native_rows=32, links_checked=4, screenshot='dashboard.png',
                    screenshot_sha256=hashlib.sha256(shot.read_bytes()).hexdigest(),
                    new_native_starts=0, new_learning_starts=0, device_commands=0)
    write_json(run / 'browser_verification.json', evidence)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check-browser', action='store_true')
    args = parser.parse_args()
    evidence = publish(args.run, args.output)
    if args.check_browser:
        evidence['browser'] = check_browser(args.run, args.output)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
