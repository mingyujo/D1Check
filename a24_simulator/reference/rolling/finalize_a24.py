"""Registered saved-evidence finalizer; no engine/NN/optimizer/CostState calls.

--preview imports only the standard library and renders zero result rows.
Full mode refuses incomplete executions, SHA drift, missing coverage, or failed
saved audits. Fresh phone CONFIRM archives/outcomes are never opened here.
Parent must register this exact source/template before either mode is executed.
Full mode also requires trace_auditor_path/trace_auditor_sha256 for the exact
stronger working audit_a24.py; production workers retain their frozen auditor.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import gzip
import hashlib
import importlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

B = Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo')
W = B / 'work/A24-INTEGRATED-SIM-20261016-G002'
O = B / 'outputs/A24-INTEGRATED-SIM-20261016-G002'
STRONGER_AUDITOR_SHA256 = '9af85870b589ed73d27703c86d225d754dc7e1e45239111e839da4d4080c891e'
TARGET = Path('C:/Users/chomg/Documents/ChatGPT/산공회/A24_에너지열_시뮬레이터.html')
LIVE = 'https://github.com/mingyujo/D1Check/blob/codex/a24-laptop-prep-20261014/docs/team/a24-measurement-revision02-20261015/LIVE_PROGRESS.md'
FIELDS = ('stage', 'family', 'learner_seed', 'episode', 'checkpoint_episode', 'case_id',
          'bank', 'model', 'context', 'alpha', 'removal', 'sample_seed')
BOOTSTRAP_SEED = 20261016


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def lines(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s.strip()] if Path(path).exists() else []


def save(path, payload):
    path = Path(path)
    require(not path.exists(), 'Immutable artifact already exists: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.part')
    data = payload if isinstance(payload, bytes) else canonical(payload)
    with temp.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)


def inside(path):
    path = Path(path).resolve()
    require(path.is_relative_to(O.resolve()), 'Artifact escapes registered output: ' + str(path))
    return path


def operation(path, preview):
    op = read(path)
    require(op['source_sha256'] == sha(__file__), 'Finalizer source SHA differs from registration')
    require(op['template_sha256'] == sha(W / 'view.template.html'), 'View template SHA differs from registration')
    require(op.get('allow_preview', False) if preview else op.get('allow_finalize', False), 'Mode not registered')
    require(Path(op.get('html_target', str(TARGET))).resolve() == TARGET.resolve(), 'Unexpected HTML target')
    if not preview:
        require(Path(op['trace_auditor_path']).resolve() == (W / 'audit_a24.py').resolve(), 'Registered stronger working auditor path required')
        require(sha(op['trace_auditor_path']) == op['trace_auditor_sha256'] == STRONGER_AUDITOR_SHA256, 'Stronger saved auditor exact source SHA')
    return op


def render_html(data):
    raw = (W / 'view.template.html').read_text(encoding='utf-8')
    require(raw.count('__A24_DATA_JSON__') == 1, 'View placeholder coverage')
    return raw.replace('__A24_DATA_JSON__', canonical(data).decode().replace('<', '\\u003c')).encode('utf-8')


def publish_html(data, op, archive_name):
    html = render_html(data)
    expected = op.get('allowed_existing_html_sha256')
    if TARGET.exists():
        require(expected is not None and sha(TARGET) == expected, 'Existing HTML is not the explicitly registered previous preview/version')
    else:
        require(expected is None, 'Expected previous HTML disappeared')
    save(O / archive_name, html)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temp = TARGET.with_name(TARGET.name + '.part')
    with temp.open('xb') as stream:
        stream.write(html); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, TARGET)
    require(sha(TARGET) == sha(O / archive_name), 'Published/archived HTML mismatch')
    return {'path': str(TARGET), 'sha256': sha(TARGET), 'bytes': TARGET.stat().st_size,
            'archive': str(O / archive_name), 'previous_sha256': expected}


def latest_intake():
    light = O / 'intake/LATEST_LIGHT_CHECK.json'
    if light.exists():
        obj = read(light); counts = obj.get('live_counts', {})
        checked = counts.get('updated_KST') or obj.get('checked_utc')
        label = str(checked or '시각 미제공')
        if counts.get('original_confirm_normal') is not None:
            label += ' · 실측 정상 ' + str(counts['original_confirm_normal']) + '/' + str(counts.get('original_target', '?'))
        if counts.get('original85_remaining') is not None:
            label += ' · 원등록 잔여 ' + str(counts['original85_remaining'])
        return {'checked_at': label, 'status': obj.get('status'), 'head_commit': obj.get('commit'),
                'path': str(light), 'sha256': sha(light), 'live_counts': counts,
                'raw_bundle_verification':'LIVE metadata counts are progress reports, not all received raw audits. Existing DEV8+CONFIRM17 raw and newly advertised ZIPs remain separate.'}
    paths = sorted((O / 'intake/checks').glob('*.json'))
    if not paths:
        return {'status': 'NO_SAVED_LIVE_SNAPSHOT', 'checked_at': None}
    p = paths[-1]; obj = read(p)
    return {'checked_at': obj.get('checked_UTC'), 'status': obj.get('status'),
            'head_commit': obj.get('head_commit'), 'path': str(p), 'sha256': sha(p)}


def meta_base(status):
    return {'live_url': LIVE, 'last_snapshot': latest_intake(),
            'goal': '정해진 납기를 최대한 만족하면서 열·에너지 감소',
            'primary_policy_status': status,
            'energy_status': '고정된 옛 A24 gauge 모형의 조건부 예측. 새 실측 J 단위 미해결·절감 미판정. 임의1000배 보정0.',
            'physical_accuracy_confirmed': False, 'new_phone_CONFIRM_outcomes_opened': 0}


def preview_payload():
    """Stdlib-only empty-row payload, also reproducible by parent Node/PS."""
    status = read(W / 'CONTINUE.json').get('current_status', '학습 대기') if (W / 'CONTINUE.json').exists() else '학습 대기'
    return {'meta': meta_base('주정책 롤링＋ATC＋RL · 실행 결과 대기 · ' + status), 'rows': []}


def preview(op):
    require(not any(n in sys.modules for n in ('torch', 'learner', 'a24_cost_adapter', 'a24_engine')), 'Preview must not import NN/model/engine')
    data = preview_payload()
    token = sha(__file__)[:12] + '_' + str(int(time.time()))
    save(O / ('PREVIEW_DATA_' + token + '.json'), data)
    html = publish_html(data, op, 'A24-preview-' + token + '.html')
    receipt = {'status': 'PREVIEW_ONLY_NO_RESULTS', 'html': html, 'source_sha256': sha(__file__),
               'rows': 0, 'new_environment': 0, 'new_NN': 0, 'CostState': 0, 'optimizer': 0,
               'learner_or_model_imports': 0, 'project_complete': False}
    save(O / ('PREVIEW_RECEIPT_' + token + '.json'), receipt)
    return receipt


def config_key(config):
    return tuple(config.get(k) for k in FIELDS)


def expected_configs(plan):
    wanted = []
    for family in plan['families']:
        for seed in plan['seeds']:
            wanted.extend({**e, 'stage': 'TRAIN', 'family': family} for e in plan['training'] if e['learner_seed'] == seed)
            for ep in plan['checkpoints']:
                wanted.extend({**c, 'stage': 'DEV', 'family': family, 'learner_seed': seed, 'checkpoint_episode': ep} for c in plan['development'])
    for case in plan['simulation_evaluation']:
        wanted.extend({**case, 'stage': 'SIM_EVAL_BASELINE', 'family': rule, 'alpha': .95} for rule in plan['baseline_' + case['bank']])
    for family in plan['families']:
        for seed in plan['seeds']:
            for case in plan['simulation_evaluation']:
                for alpha in plan['alphas']:
                    wanted.append({**case, 'stage': 'SIM_EVAL_LEARNED', 'family': family, 'learner_seed': seed, 'alpha': alpha})
                    if family == 'JOINT_ATC_RL':
                        for removal in ('NO_WAIT', 'TICK200'):
                            wanted.append({**case, 'stage': 'SIM_EVAL_REMOVAL', 'family': family,
                                           'learner_seed': seed, 'alpha': alpha, 'removal': removal})
    return collections.Counter(config_key(x) for x in wanted)


def state_digest(state):
    h = hashlib.sha256()
    for name, tensor in sorted(state.items()):
        a = tensor.detach().cpu().contiguous().numpy()
        h.update(name.encode()); h.update(a.dtype.str.encode()); h.update(repr(a.shape).encode()); h.update(a.tobytes())
    return h.hexdigest()


def frame_input_digest(frame):
    h = hashlib.sha256()
    for key in ('requests', 'resources', 'global_state', 'features', 'request_index', 'backend_index', 'mask', 'prior_logits'):
        a = frame[key]
        require(a.flags.c_contiguous, 'Saved NN input contiguous bytes')
        h.update(key.encode()); h.update(a.dtype.str.encode()); h.update(repr(a.shape).encode()); h.update(a.tobytes())
    return h.hexdigest()


def checkpoints(plan):
    import torch
    torch.set_num_threads(1)
    result = {}; cache = {}
    for path in sorted((O / 'checkpoints').rglob('*.pt')):
        snapshot = torch.load(path, map_location='cpu', weights_only=False)
        wanted = {'network', 'network_sha256', 'optimizer', 'action_rng', 'shuffle_rng', 'episodes', 'steps', 'updates', 'family', 'seed', 'settings', 'duals'}
        require(wanted <= set(snapshot), 'Incomplete checkpoint state: ' + str(path))
        actual = state_digest(snapshot['network'])
        require(actual == snapshot['network_sha256'], 'Checkpoint network tensor digest: ' + str(path))
        require(all(bool(torch.isfinite(t).all()) for t in snapshot['network'].values()), 'Nonfinite checkpoint tensor')
        require(snapshot['action_rng'].dtype == torch.uint8 and snapshot['shuffle_rng'].dtype == torch.uint8, 'Separate RNG states missing')
        require(snapshot['action_rng'].numel() > 0 and snapshot['shuffle_rng'].numel() > 0, 'Empty saved RNG states')
        if snapshot['updates']:
            states = snapshot['optimizer']['state']
            require(states and all({'step', 'exp_avg', 'exp_avg_sq'} <= set(s) for s in states.values()), 'Adam moments missing')
            require(all(int(s['step']) == int(snapshot['steps']) for s in states.values()), 'Adam step/checkpoint mismatch')
            require(all(bool(torch.isfinite(s[k]).all()) for s in states.values() for k in ('exp_avg', 'exp_avg_sq')), 'Nonfinite Adam state')
        cache[str(path.resolve())] = snapshot
        result[str(path)] = {'sha256': sha(path), 'network_sha256': actual, 'episodes': snapshot['episodes'],
                             'adam_steps': snapshot['steps'], 'updates': snapshot['updates'],
                             'family': snapshot['family'], 'seed': snapshot['seed'],
                             'action_rng_sha256': hashlib.sha256(snapshot['action_rng'].numpy().tobytes()).hexdigest(),
                             'shuffle_rng_sha256': hashlib.sha256(snapshot['shuffle_rng'].numpy().tobytes()).hexdigest()}
    for family in plan['families']:
        for seed in plan['seeds']:
            initial = cache[str((O / 'checkpoints' / family / str(seed) / 'EP000.pt').resolve())]
            for ep in (8, 16, 24, 32):
                path = O / 'checkpoints' / family / str(seed) / f'EP{ep:03}.pt'
                s = cache[str(path.resolve())]; proof = read(path.with_name(path.stem + '_PROOF.json'))
                require(s['episodes'] == ep and s['updates'] == ep // 8 and not s['pending'], 'Checkpoint episode/update/pending coverage')
                require(s['seed'] == seed and s['family'] == family and s['settings'] == initial['settings'], 'Checkpoint identity/settings changed')
                require(proof['network_sha256'] == s['network_sha256'] and proof['initial_network_sha256'] == initial['network_sha256'], 'Update proof/network binding')
                require(proof['actor_changed'] is True and s['network_sha256'] != initial['network_sha256'], 'Fresh learner unchanged')
                require(proof['updates'] == s['updates'] and proof['adam_steps'] == s['steps'], 'Update proof Adam counts')
                require(proof['duals'] == s['duals'].tolist(), 'Checkpoint dual state binding')
            final_path=O/'checkpoints'/family/str(seed)/'EP032.pt'
            final=cache[str(final_path.resolve())]
            actor_names=[k for k in initial['network'] if k.startswith('actor.')]
            require(actor_names,'Actual actor tensors absent from saved checkpoint')
            changed=[k for k in actor_names if not torch.equal(initial['network'][k],final['network'][k])]
            require(changed,'Actor did not change; critic-only update is not RL actor learning')
            require(not torch.equal(initial['action_rng'],final['action_rng']) and not torch.equal(initial['shuffle_rng'],final['shuffle_rng']),'Action/shuffle RNG must both reflect actual training')
            parameter_ids=[p for group in final['optimizer']['param_groups'] for p in group['params']]
            parameter_names=list(final['network'])
            require(len(parameter_ids)==len(parameter_names),'Saved Adam/network parameter coverage')
            actor_ids=[parameter_ids[parameter_names.index(k)] for k in actor_names]
            require(all(i in final['optimizer']['state'] for i in actor_ids),'Actor Adam moment coverage')
            result[str(final_path)]['actor_learning_proof']={'actor_tensors':actor_names,'changed_actor_tensors':changed,
                'changed_actor_tensor_count':len(changed),'actor_Adam_states':len(actor_ids),
                'action_rng_changed':True,'shuffle_rng_changed':True,'new_inference':0,'new_optimizer_steps':0}
    p0_initial=cache[str((O/'checkpoints/P0_EP000.pt').resolve())]
    p0_final=cache[str((O/'checkpoints/P0_EP008.pt').resolve())]
    actor_names=[k for k in p0_initial['network'] if k.startswith('actor.')]
    changed=[k for k in actor_names if not torch.equal(p0_initial['network'][k],p0_final['network'][k])]
    require(changed,'P0 actor did not change; network digest alone is insufficient')
    require(p0_final['steps']>0 and p0_final['optimizer']['state'],'P0 Adam moments absent')
    require(not torch.equal(p0_initial['action_rng'],p0_final['action_rng']) and not torch.equal(p0_initial['shuffle_rng'],p0_final['shuffle_rng']),'P0 separate RNG training state')
    result[str(O/'checkpoints/P0_EP008.pt')]['actor_learning_proof']={'changed_actor_tensors':changed,'changed_actor_tensor_count':len(changed),
        'action_rng_changed':True,'shuffle_rng_changed':True,'new_inference':0,'new_optimizer_steps':0}
    return result, cache


def selection_audit(plan, seal, summary, checkpoint_meta):
    import numpy as np
    def score(rr):
        scores = [[], [], [], [], []]
        for r in rr:
            m = r['metrics']; u = m['by_cohort']['U']; n = m['by_cohort']['N']
            ur = u['deadline_met'] / u['planned'] if u['planned'] else 1.
            nr = n['deadline_met'] / n['planned'] if n['planned'] else 1.
            scores[0].append(m['incomplete'] / m['planned'])
            scores[1].append((max(0., r['alpha'] - ur) if u['planned'] else 0.) + (max(0., r['alpha'] - nr) if n['planned'] else 0.))
            scores[2].append(-min(ur, nr)); scores[3].append(-m['deadline_met'] / m['planned'])
            scores[4].append(sum(r['cost_labels'][:2]) * .5)
        return [float(np.mean(v)) for v in scores]
    recomputed = {}; family_scores = {}
    require(seal['plan_sha256'] == sha(O / 'SEALED_PLAN.json'), 'Selection plan SHA')
    for family in plan['families']:
        for seed in plan['seeds']:
            key = family + ':' + str(seed); actual = seal['selected'][key]; choices = []
            for ep in plan['checkpoints']:
                rr = [r for r in summary if r['stage'] == 'DEV' and r['family'] == family and r['learner_seed'] == seed and r['checkpoint_episode'] == ep]
                require(len(rr) == len(plan['development']), 'DEV selection complete coverage')
                value = score(rr); stored = next(x['score'] for x in actual['DEV'] if x['episode'] == ep)
                require(max(abs(a-b) for a,b in zip(value, stored)) <= 1e-10, 'DEV lexicographic score mismatch')
                choices.append({'episode': ep, 'score': value})
            chosen = min(choices, key=lambda x: (x['score'], x['episode']))
            require(actual['episode'] == chosen['episode'] and sha(actual['path']) == actual['sha256'], 'Frozen selected checkpoint')
            require(str(Path(actual['path'])) in checkpoint_meta and checkpoint_meta[str(Path(actual['path']))]['episodes'] == actual['episode'], 'Selected checkpoint audited')
            recomputed[key] = chosen
    require(len(seal['selected']) == len(plan['families'])*len(plan['seeds']), 'Unexpected/missing selected model')
    for family in plan['families']:
        if family == 'NO_ATC_RL':
            continue
        family_scores[family] = np.mean([recomputed[f'{family}:{s}']['score'] for s in plan['seeds']],axis=0).tolist()
        require(max(abs(a-b) for a,b in zip(family_scores[family], seal['family_DEV_scores'][family])) <= 1e-10, 'Family DEV score mismatch')
    require(seal['recommended_family'] == min(family_scores, key=lambda f: family_scores[f]), 'DEV recommendation mismatch')
    return {'status': 'PASS', 'selected_models': recomputed, 'recommended_family': seal['recommended_family'], 'new_selection': False}


def service(row, cohort):
    m = row['metrics']['by_cohort'][cohort]
    return None if not m['planned'] else m['service_success'] / m['planned']


def eligible(row):
    return all(service(row, c) is None or service(row, c) + 1e-12 >= row['alpha'] for c in ('U','N'))


def paired(row, baseline):
    require(row['input_binding_sha256'] == baseline['input_binding_sha256'] and row['initial_binding_sha256'] == baseline['initial_binding_sha256'], 'Paired delta input/initial mismatch')
    require(row['sample_seed'] == baseline['sample_seed'] and row['model'] == baseline['model'], 'Paired model/sample stream mismatch')
    d = {k: row['cost'][k]-baseline['cost'][k] for k in ('continuous_J0_180','AP35_180_mean_c','AP0_180_peak_c','AP180_c','AP180_residual_from_initial_c')}
    d['energy_reduction_fraction'] = -d['continuous_J0_180']/baseline['cost']['continuous_J0_180'] if baseline['cost']['continuous_J0_180'] > 0 else None
    d['candidate_service_eligible'] = eligible(row); d['baseline_service_eligible'] = eligible(baseline)
    d['cohort_differences'] = {}
    harm = False
    for c in ('ALL','U','N'):
        a,b = row['metrics']['by_cohort'][c],baseline['metrics']['by_cohort'][c]
        require(a['planned'] == b['planned'], 'Paired planned denominators differ')
        dif = {k:a[k]-b[k] for k in ('deadline_met','service_success','responded','available','failed','incomplete')}
        d['cohort_differences'][c] = dif
        harm |= any(dif[k] < 0 for k in ('deadline_met','service_success','responded','available')) or dif['failed'] > 0 or dif['incomplete'] > 0
    d['deadline_or_completion_harm'] = harm
    d['full_available'] = row['metrics']['available'] == row['metrics']['planned'] and row['metrics']['failed'] == 0 and row['metrics']['incomplete'] == 0
    d['cost_joint_threshold'] = d['energy_reduction_fraction'] is not None and d['energy_reduction_fraction'] >= .10-1e-12 and d['AP35_180_mean_c'] <= -.5+1e-12
    d['model_conditional_joint_goal_pass'] = d['cost_joint_threshold'] and d['candidate_service_eligible'] and d['full_available'] and not harm
    d['physical_goal_confirmed'] = False
    return d


def percentile(values, p):
    a = sorted(values); x = (len(a)-1)*p; lo = math.floor(x); hi = math.ceil(x)
    return a[lo] + (a[hi]-a[lo])*(x-lo)


def effects_report(view_rows, plan):
    baseline = {(r['case_id'],r['alpha']):r for r in view_rows if r['policy']=='FIFO_SERIAL_CG'}
    entries = []
    for r in view_rows:
        b = baseline[r['case_id'],r['alpha']]
        entries.append({k:r[k] for k in ('run_id','case_id','bank','context','model','policy','seed','alpha','learned')} | {'baseline_run_id':b['run_id'],'delta':paired(r,b),'metrics':r['metrics'],'cost':r['cost']})
    reversals = []
    groups = collections.defaultdict(list)
    for e in entries:
        groups[e['bank'],e['context'],e['policy'],e['seed'],e['alpha']].append(e)
    for key, group in groups.items():
        by = {e['model']:e for e in group}
        if set(by) == set(('TREND27','MEASURED35')):
            fields = [f for f in ('continuous_J0_180','AP35_180_mean_c','AP180_c') if by['TREND27']['delta'][f]*by['MEASURED35']['delta'][f] < 0]
            if fields:
                reversals.append({'bank':key[0],'context':key[1],'policy':key[2],'seed':key[3],'alpha':key[4],
                                  'fields':fields,'delta':{m:{f:by[m]['delta'][f] for f in fields} for m in by},
                                  'caution':'Two models also use different sealed sample seeds. This is direction disagreement across registered model/case conditions, not an isolated coefficient-only causal effect.'})
    rng = random.Random(BOOTSTRAP_SEED)
    resamples = [tuple(rng.randrange(3) for _ in range(3)) for _ in range(2000)]
    intervals = []; grouped = collections.defaultdict(list)
    for e in entries:
        grouped[e['policy'],e['seed'],e['alpha'],e['model']].append(e)
    for key, group in grouped.items():
        if set(e['bank'] for e in group) != {'C252','L64','M128'} or len(group) != 3:
            continue
        group.sort(key=lambda e:e['bank'])
        item = {'policy':key[0],'seed':key[1],'alpha':key[2],'model':key[3],'bank_clusters':[e['bank'] for e in group],
                'cluster_count':3,'resamples':2000,'random_seed':BOOTSTRAP_SEED,'independent_phone_CI':False}
        for field in ('continuous_J0_180','AP35_180_mean_c'):
            v = [e['delta'][field] for e in group]
            boot = [statistics.mean(v[i] for i in index) for index in resamples]
            item[field] = {'paired_case_mean':statistics.mean(v),'case_min':min(v),'case_max':max(v),
                           'synthetic_cluster_percentile_95':[percentile(boot,.025),percentile(boot,.975)]}
        intervals.append(item)
    ranges = []; seed_groups = collections.defaultdict(list)
    for e in entries:
        if e['learned']:
            seed_groups[e['policy'],e['alpha'],e['bank'],e['model'],e['context']].append(e)
    for key, group in seed_groups.items():
        require({e['seed'] for e in group} == set(plan['seeds']), 'All three learned seeds required in descriptive range')
        ranges.append({'policy':key[0],'alpha':key[1],'bank':key[2],'model':key[3],'context':key[4],
                       'seeds':sorted(e['seed'] for e in group),
                       'delta_ranges':{f:[min(e['delta'][f] for e in group),max(e['delta'][f] for e in group)] for f in ('continuous_J0_180','AP35_180_mean_c')},
                       'deadline_met_range':[min(e['metrics']['deadline_met'] for e in group),max(e['metrics']['deadline_met'] for e in group)]})
    return {'schema':'A24-PAIRED-MODEL-EFFECTS-v1','comparisons':entries,'model_case_direction_disagreements':reversals,
            'three_seed_descriptive_ranges':ranges,'paired_synthetic_bank_bootstrap':intervals,
            'uncertainty_boundary':'Only three bank clusters per model. Two models share data; contexts are not six independent phone replications. Bootstrap is synthetic-model sensitivity, not real-device confidence or physical accuracy.',
            'goal':'E0-180 reduction >=10% AND APmean35-180 reduction >=0.5C AND U/N service bound AND all completed AND no baseline deadline/completion harm',
            'model_conditional_goal_pass_comparisons':sum(e['delta']['model_conditional_joint_goal_pass'] for e in entries),
            'physical_goal_pass':False,'new_environments':0,'new_NN':0,'new_fits':0,'CONFIRM_outcomes_opened':0}


def allcase_csv(rows):
    stream = io.StringIO(newline='')
    header = ['run_id','bank','case_id','context','model','policy','seed','alpha','learned','input_binding_sha256','initial_binding_sha256',
              'J0_180','APmean35_180_C','APpeak0_180_C','AP180_C','AP180_residual_C']
    for c in ('ALL','U','N','C','D','CU','CN','DU','DN'):
        header.extend(c+'_'+f for f in ('planned','responded','available','deadline_met','service_success','failed','incomplete','response_p95_ns'))
    writer=csv.DictWriter(stream,fieldnames=header);writer.writeheader()
    for r in rows:
        x={k:r[k] for k in header[:11]}
        x.update(J0_180=r['cost']['continuous_J0_180'],APmean35_180_C=r['cost']['AP35_180_mean_c'],APpeak0_180_C=r['cost']['AP0_180_peak_c'],AP180_C=r['cost']['AP180_c'],AP180_residual_C=r['cost']['AP180_residual_from_initial_c'])
        for c in ('ALL','U','N','C','D','CU','CN','DU','DN'):
            x.update({c+'_'+f:r['metrics']['by_cohort'][c].get(f) for f in ('planned','responded','available','deadline_met','service_success','failed','incomplete','response_p95_ns')})
        writer.writerow(x)
    return ('\ufeff'+stream.getvalue()).encode('utf-8')


def finalize(op):
    finished=read(O/'EXECUTION_FINISHED.json')
    require(finished['status']=='EXECUTION_FINISHED_PENDING_FINAL_AUDIT_REPORT','Execution is not finished')
    require(not (O/'FINAL_AUDIT.json').exists(),'Final audit already exists; inspect it, do not overwrite')
    import msvcrt
    lock=(O/'worker.lock').open('a+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    reg=read(O/'REGISTRATION.json');plan=read(O/'SEALED_PLAN.json')
    require(sha(O/'SEALED_PLAN.json')==reg['plan_sha256'],'Registered plan SHA')
    for path,h in reg['protected'].items():require(sha(path)==h,'Protected SHA changed: '+path)
    generation=finished['generation'];generation_path=W/'source_generations'/generation
    sys.path.insert(0,str(generation_path))
    adapter=importlib.import_module('a24_cost_adapter')
    auditor_spec=importlib.util.spec_from_file_location('a24_G002_registered_stronger_auditor',op['trace_auditor_path'])
    auditor=importlib.util.module_from_spec(auditor_spec);auditor_spec.loader.exec_module(auditor)
    models=adapter.modelsload()  # Defines exact frozen classes; constructs no CostState.
    profile=read(O/'DEV_PROFILE_NORMALIZED.json');contexts={x['context_id']:x for x in read(O/'INITIAL_CONTEXTS.json')['contexts']}
    for ctx in contexts.values():
        p=ctx['provenance'];require(sha(p['source_path'])==p['source_sha256'],'Initial raw HAL SHA')
        require(sha(p['common_event_path'])==p['common_event_sha256'],'Initial common event SHA')
    receipts=lines(O/'receipts.jsonl');rows=lines(O/'rows.jsonl');summary=lines(O/'summary.jsonl')
    grouped=collections.defaultdict(list)
    for e in receipts:grouped[e['identity']].append(e)
    start_events=[e for e in receipts if e['event']=='START']
    for index,event in enumerate(start_events):
        guards=event['guards']
        require(guards['new_starts']==index,'Every START guard must count all preceding consumed STARTs')
        require(guards['free_bytes']>=reg['budget']['min_free_bytes'] and guards['own_python_leaves']<=1 and guards['global_python_leaves']<=2,'Recorded START storage/own/global guards')
        require(guards['old_starts']+guards['new_starts']<reg['budget']['global_cap'],'Recorded START global budget guard')
    require(len(rows)==len({r['identity'] for r in rows})==len(grouped),'Unique row/START coverage')
    require(all([e['event'] for e in rr]==['START','PREPARED','COMPLETE'] for rr in grouped.values()),'Unresolved/failed/duplicate START or terminal')
    require(len(rows)<=reg['budget']['new_environment_cap'],'New environment budget')
    old_starts=sum(sum(x.get('event')=='START' for x in lines(p)) for p in reg['prior_ledgers'])
    require(old_starts+len(rows)<=reg['budget']['global_cap'],'Global environment budget')
    p0=read(O/'P0_AUDIT.json');numeric=read(O/'NUMERIC_AUDIT.json');activation=read(O/'P0_ACTIVATION_AUDIT.json')
    require(p0['status']==numeric['status']==activation['status']=='PASS','P0/numeric/activation saved audit')
    numeric_op=read(O/'NUMERIC_OPERATION_REGISTERED.json')
    require(sha(numeric_op['source_path'])==numeric_op['source_sha256'],'Numerical operator source SHA')
    train_op=read(O/'TRAIN_OPERATION_REGISTERED.json')
    require(sha(W/'train_worker.py')==train_op['worker_sha256'],'Producer worker source SHA')
    require(numeric.get('new_environment')==0 and numeric.get('new_NN_inference')==0 and numeric.get('optimizer_steps')==0,'Numeric-only operation evidence boundary')
    require(p0['native_updates']>0 and p0['adam_steps']>0 and p0['initial_network_sha256']!=p0['updated_network_sha256'],'P0 actual update proof')
    cost_receipts=lines(O/'cost_audit_receipts.jsonl')
    require([e['event'] for e in cost_receipts]==['START','COMPLETE'] and cost_receipts[-1]['sha256']==sha(O/'NUMERIC_AUDIT.json'),'Numerical audit receipt coverage/SHA')
    for test in numeric['tests']:
        require(test['max_original_J_difference']<=1e-8 and test['max_original_AP_difference_c']<=1e-9 and test['analytic_APmean_vs_001s_trapezoid_difference_c']<=1e-4,'Fixed numeric tolerances')
    prediction_rows=[r for r in rows if r['config']['stage']=='NEW_CONFIRM_PREDICTION']
    require(len(prediction_rows) in (0,8),'New CONFIRM input prediction is absent or a complete sealed eight-row block')
    prediction_scope={'stage':'NEW_CONFIRM_PREDICTION','environment_count':len(prediction_rows),'observed_outcomes_opened':0}
    if prediction_rows:
        prediction_freeze=O/'new_confirmation_predictions/PREDICTIONS_FROZEN.json'
        require(prediction_freeze.exists(),'New input predictions lack durable eight-row freeze')
        pf=read(prediction_freeze);pf_rows={p['identity']:p for p in pf['predictions']}
        require(pf['status']=='PREDICTIONS_FROZEN_BEFORE_NEW_OBSERVED_COMPARISON' and pf['environment_starts']==8 and len(pf_rows)==8,'Eight predictions sealed before observed comparison')
        require(pf['observed_response_postcommon_AP_or_J_metrics_parsed']==0 and pf['NN']==pf['fit']==pf['optimizer']==0,'New prediction scope remains results-blind/nonlearned')
        require(set(pf_rows)=={r['identity'] for r in prediction_rows},'Prediction freeze/committed identity coverage')
        for row in prediction_rows:
            p=pf_rows[row['identity']]
            require(p['row_sha256']==digest(row) and p['config']==row['config'] and p['raw_sha256']==row['raw_sha256'],'Prediction sealed row/manifest binding')
        prediction_operation=O/'NEW_CONFIRM_OPERATION_REGISTERED.json';pop=read(prediction_operation)
        require(sha(prediction_operation)==pf['operation_sha256'] and sha(W/'predict_confirmation.py')==pf['operator_sha256']==pop['operator_sha256'],'Prediction operator/operation source binding')
        require(sha(pop['trace_auditor_path'])==pop['trace_auditor_sha256'],'Prediction external auditor source binding')
        observer_path=O/'new_confirmation_predictions/cost_observer_receipts.jsonl'
        require(sha(observer_path)==pf['cost_observer_receipts_sha256'] and pf['cost_wrapper_instances']==16,'Registered cost-only observer consumption')
        observers=lines(observer_path);os_=[e for e in observers if e['event']=='COST_START'];oc=[e for e in observers if e['event']=='COST_COMPLETE']
        require(len(os_)==len(oc)==16 and {e['wrapper_identity'] for e in os_}=={e['wrapper_identity'] for e in oc},'All16 cost observer START/terminal identities')
        prediction_scope.update(freeze_path=str(prediction_freeze),freeze_sha256=sha(prediction_freeze))
    actual=collections.Counter(config_key(r['config']) for r in rows if r['config']['stage'] not in ('P0','P0_ACTIVATION','NEW_CONFIRM_PREDICTION'))
    require(actual==expected_configs(plan),'Full TRAIN/DEV/BASE/LEARNED/REMOVAL sealed coverage')
    require(len(rows)-len(prediction_rows)==sum(expected_configs(plan).values())+10==1686,'Exact base 1686 environment coverage')
    require(sum(r['config']['stage']=='P0' for r in rows)==p0['environment_starts']==len(p0['proof'])==8,'P0 consumed identities')
    require(sorted(r['config']['episode'] for r in rows if r['config']['stage']=='P0')==list(range(1,9)),'P0 episode1..8 coverage')
    require({r['identity'] for r in rows if r['config']['stage']=='P0'}=={r['identity'] for r in p0['proof']},'P0 proof identity coverage')
    require(sum(r['config']['stage']=='P0_ACTIVATION' for r in rows)==activation['new_environments']==2,'Activation consumed identities')
    require({r['config']['bank'] for r in rows if r['config']['stage']=='P0_ACTIVATION'}=={'M128','C252'},'Activation exact bank coverage')
    summary_index={r['identity']:r for r in summary}
    require(len(summary)==len(summary_index) and set(summary_index)=={r['identity'] for r in rows if r['config']['stage'] not in ('P0','NEW_CONFIRM_PREDICTION')},'Summary/row total coverage')
    seal=read(O/'DEV_SELECTION_FREEZE.json')
    require(sha(O/'DEV_SELECTION_FREEZE.json')==finished['selected_sha256'],'Finished selection SHA')
    controls=lines(O/'control_receipts.jsonl');seal_events=[e for e in controls if e['event']=='DEV_SELECTION_FROZEN']
    require(len(seal_events)==1 and seal_events[0]['sha256']==sha(O/'DEV_SELECTION_FREEZE.json'),'Selection durable receipt')
    eval_starts=[e for e in receipts if e['event']=='START' and e['manifest']['config']['stage'].startswith('SIM_EVAL')]
    dev_ids={r['identity'] for r in rows if r['config']['stage']=='DEV'}
    dev_complete=[e['unix'] for e in receipts if e['event']=='COMPLETE' and e['identity'] in dev_ids]
    require(len(dev_complete)==sum(v for k,v in expected_configs(plan).items() if k[0]=='DEV'),'All DEV terminal coverage before seal')
    require(eval_starts and max(dev_complete)<=seal['unix']<=seal_events[0]['unix']<=min(e['unix'] for e in eval_starts),'All DEV COMPLETE -> selection seal -> control receipt -> every eval START')
    cpmeta,cpcache=checkpoints(plan)
    require(cpmeta[str(O/'checkpoints/P0_EP000.pt')]['network_sha256']==p0['initial_network_sha256'] and cpmeta[str(O/'checkpoints/P0_EP008.pt')]['network_sha256']==p0['updated_network_sha256'],'P0 saved initial/final checkpoint proof binding')
    selected_audit=selection_audit(plan,seal,summary,cpmeta)
    import torch
    import numpy as np
    policy_bridge=importlib.import_module('policy_bridge')
    p0proof={p['identity']:p for p in p0['proof']};rawproof=[];view_rows=[];frame_total=0;generation_hashes={};train_rng={}
    learning=lines(O/'learning.jsonl');learning_index={(x['family'],x['seed'],x['episode']):x for x in learning}
    require(len(learning_index)==len(learning)==sum(r['config']['stage']=='TRAIN' for r in rows),'Learning episode log coverage')
    for row in rows:
        rid=row['identity'];start,prepared,complete=grouped[rid];manifest=start['manifest'];cfg=row['config']
        require(row['manifest']==manifest and manifest['config']==cfg,'START manifest row binding')
        require(manifest['identity']==rid==digest([manifest['generation'],manifest['label'],cfg])[:28] and row['label']==manifest['label'],'Durable predeclared identity/label digest')
        require(manifest['registration_sha256']==sha(O/'REGISTRATION.json'),'Run registered source binding')
        genpath=W/'source_generations'/manifest['generation']/'GENERATION.json';gen=read(genpath)
        require(sha(genpath)==manifest['generation_sha256'] and gen['source_hashes']==manifest['source_hashes'],'Per-run generation binding')
        require(gen['registration_sha256']==manifest['registration_sha256'],'Generation registration SHA binding')
        for p,h in manifest['source_hashes'].items():
            if p not in generation_hashes:require(sha(p)==h,'Frozen source changed: '+p);generation_hashes[p]=h
            require(generation_hashes[p]==h,'Conflicting source SHA in manifests')
        rawpath=inside(row['raw_path']);prep=O/'prepared'/(rid+'.json')
        require(sha(rawpath)==row['raw_sha256']==prepared['raw_sha256']==complete['raw_sha256'],'Raw SHA across commit chain')
        require(sha(prep)==prepared['prepared_sha256'] and read(prep)==row,'Prepared durable exact row')
        result=json.loads(gzip.decompress(rawpath.read_bytes()))
        require(result['manifest']==manifest and digest(result['scenario'])==cfg['scenario_sha256'],'Raw input/manifest digest')
        require(result['policy']['family']==cfg.get('family','JOINT_ATC_RL') and result['policy']['rule']==cfg.get('rule'),'Raw scheduler family/rule config binding')
        require(result['policy']['allow_wait']==cfg.get('allow_wait',True) and result['policy']['decision_mode']==cfg.get('decision_mode','EVENT'),'Raw WAIT/decision mode config binding')
        require(result['model']==cfg.get('model','MEASURED35') and result['seed']==cfg['sample_seed'] and result['alpha']==cfg.get('alpha',.95),'Raw model/sample seed/alpha config binding')
        require(result['scenario']['bank']==cfg.get('bank','M128'),'Raw input bank config binding')
        if cfg['stage']=='NEW_CONFIRM_PREDICTION':
            for path,h in cfg['bound_source_inputs'].items():require(sha(path)==h,'New prediction bound input SHA')
            require(cfg['initial_binding_sha256']==result['cost']['metrics']['initial_binding_sha256'],'New prediction actual initial SHA')
        require(result['metrics']==row['metrics'] and result['cost']['metrics']==row['cost_metrics'],'Saved row arithmetic binding')
        trace=auditor.inspect_result(result,profile,models=models)
        if cfg['stage']=='P0':
            saved=p0proof[rid];prior_trace=saved['trace_audit'];frames_audit=saved['frame_audit']
        elif cfg['stage']=='NEW_CONFIRM_PREDICTION':
            require('trace_audit_path' in row and 'trace_audit_sha256' in row,'New input prediction trace audit link missing')
            audit_path=inside(row['trace_audit_path'])
            require(sha(audit_path)==row['trace_audit_sha256'],'New input prediction audit SHA')
            saved=read(audit_path);require(saved['status']=='PASS' and saved['raw_sha256']==row['raw_sha256'],'New input prediction saved audit/raw binding')
            prior_trace=saved.get('trace',saved);frames_audit=None
            require('secondary_cost_path' in row and 'secondary_cost_sha256' in row,'New input secondary observer evidence missing')
            require(sha(inside(row['secondary_cost_path']))==row['secondary_cost_sha256'],'Secondary observer saved SHA')
        else:
            saved=read(O/'audits'/(rid+'.json'));require(saved['raw_sha256']==row['raw_sha256'],'Per-run audit raw SHA')
            prior_trace=saved['trace'];frames_audit=saved['frames']
            require(saved['nominal']['status']=='PASS','Per-run nominal audit')
            ss=summary_index[rid]
            require(ss['raw_sha256']==row['raw_sha256'] and ss['metrics']==result['metrics'] and ss['cost_metrics']==result['cost']['metrics'],'Summary/raw binding')
            require(ss['cost_labels']==result['cost_labels']['total'] and ss['initial_public_sha256']==result['cost']['metrics']['initial_binding_sha256'],'Selection reward/initial summary binding')
            require(all(k in ss and ss[k]==v for k,v in cfg.items() if k!='scenario_sha256'),'Summary full policy/config binding')
        require(prior_trace['status']=='PASS' and prior_trace['result_sha256']==trace['result_sha256'],'Saved independent trace audit binding')
        if 'rollout_path' in row:
            require(sha(inside(row['rollout_path']))==row['rollout_sha256'],'Saved rollout SHA')
            aux=torch.load(row['rollout_path'],map_location='cpu',weights_only=False);frames=aux['frames']
            require(frames_audit and frames_audit['status']=='PASS' and len(frames)==frames_audit['frames']==len(result['decisions']),'Saved NN audit/frame coverage')
            frame_total+=len(frames);network=frames_audit['network_sha256']
            known={x['network_sha256'] for x in cpmeta.values()}
            require(network in known,'Frame report network is not an audited saved checkpoint')
            if cfg['stage']=='TRAIN':
                before=(cfg['episode']-1)//8*8
                snap=cpcache[str((O/'checkpoints'/cfg['family']/str(cfg['learner_seed'])/f'EP{before:03}.pt').resolve())]
                require(network==snap['network_sha256'],'TRAIN immutable pre-update network')
                key=cfg['family'],cfg['learner_seed'];previous=train_rng.get(key,snap['action_rng'])
                require(torch.equal(frames[0]['action_rng_before'],previous),'Across-episode action RNG continuity')
                train_rng[key]=aux['action_rng_after']
                if cfg['episode']%8==0:
                    after=cpcache[str((O/'checkpoints'/cfg['family']/str(cfg['learner_seed'])/f'EP{cfg["episode"]:03}.pt').resolve())]
                    require(torch.equal(after['action_rng'],aux['action_rng_after']),'Checkpoint/action RNG frontier')
                log=learning_index[cfg['family'],cfg['learner_seed'],cfg['episode']]
                require(log['identity']==rid and log['updates']==cfg['episode']//8,'Learning state identity/update count')
                frontier=cfg['episode']//8*8
                saved_frontier=cpcache[str((O/'checkpoints'/cfg['family']/str(cfg['learner_seed'])/f'EP{frontier:03}.pt').resolve())]
                require(log['network_sha256']==saved_frontier['network_sha256'] and log['adam_steps']==saved_frontier['steps'],'Learning network/Adam exact saved frontier')
            elif cfg['stage'] in ('DEV','SIM_EVAL_LEARNED','SIM_EVAL_REMOVAL'):
                ep=cfg.get('checkpoint_episode',seal['selected'][f'{cfg["family"]}:{cfg["learner_seed"]}']['episode'])
                snap=cpcache[str((O/'checkpoints'/cfg['family']/str(cfg['learner_seed'])/f'EP{ep:03}.pt').resolve())]
                require(network==snap['network_sha256'],'Evaluation checkpoint network')
                if cfg['stage'].startswith('SIM_EVAL'):
                    require(cfg['selected_checkpoint_sha256']==seal['selected'][f'{cfg["family"]}:{cfg["learner_seed"]}']['sha256'],'Eval frozen checkpoint byte SHA')
            for i,frame in enumerate(frames):
                require(frame_input_digest(frame)==frame['input_sha'],'Saved NN input bytes/dtype digest')
                require(frame['network_sha256']==network and frame['index']==result['decisions'][i]['chosen_index'],'Saved NN checkpoint/chosen action')
                require(bool(frame['mask'][frame['index']]) and bool(frame['physical_mask'][frame['index']]),'Saved chosen mask legality')
                require(math.isfinite(float(frame['old_logp'])) and all(math.isfinite(float(v)) for v in frame['value']),'Finite saved logprob/critic')
                require(i==0 or torch.equal(frames[i-1]['action_rng_after'],frame['action_rng_before']),'Within-episode separate RNG continuity')
                decision=auditor._unwire(copy.deepcopy(result['decisions'][i]))
                family=decision['diagnostic']['family']
                bank=policy_bridge.build_bank(decision['observation'],family,allow_wait=result['policy']['allow_wait'])
                for key in ('requests','resources','global_state','features','request_index','backend_index','mask'):
                    require(np.array_equal(frame[key],bank[key]) and frame[key].dtype==bank[key].dtype,'Public decision to original NN input bytes/dtype: '+key)
                require(np.array_equal(frame['physical_mask'],bank['physical_mask']),'Public decision physical NN mask')
                prior=bank['prior_logits'] if family=='ATC_RESIDUAL_RL' else np.zeros(80,np.float32)
                require(np.array_equal(frame['prior_logits'],prior) and frame['prior_logits'].dtype==prior.dtype,'Original residual prior bytes')
            require(torch.equal(frames[-1]['action_rng_after'],aux['action_rng_after']),'Rollout post-action RNG')
            costs=aux['costs'];totals=costs.sum(axis=0).tolist()
            require(max(abs(a-b) for a,b in zip(totals,result['cost_labels']['total']))<=1e-8,'Saved cost/reward telescope')
        else:require(frames_audit is None,'Rule run must not claim NN frames')
        rawproof.append({'identity':rid,'stage':cfg['stage'],'raw_sha256':row['raw_sha256'],'trace':trace,'existing_NN_audit':frames_audit})
        if cfg['stage'].startswith('SIM_EVAL'):
            cm=result['cost']['metrics'];context=contexts[cfg['context']]
            require(cm['initial_binding_sha256']==digest(adapter.validate_initial(context)),'Exact initial/public cost binding')
            policy=cfg['family']+(' '+cfg['removal'] if cfg.get('removal') else '')
            base={'bank':cfg['bank'],'case_id':cfg['case_id'],'model':cfg['model'],'context':cfg['context'],
                  'policy':policy,'seed':cfg.get('learner_seed',0),'sample_seed':cfg['sample_seed'],
                  'alpha':cfg['alpha'],'learned':cfg['stage']!='SIM_EVAL_BASELINE','run_id':rid,
                  'input_binding_sha256':cfg['scenario_sha256'],'initial_binding_sha256':cm['initial_binding_sha256'],
                  'metrics':result['metrics'],'cost':cm,'curve':result['curve'],
                  'evidence':{'raw_path':row['raw_path'],'raw_sha256':row['raw_sha256'],'stage':cfg['stage'],'generation':manifest['generation']}}
            for alpha in plan['alphas'] if cfg['stage']=='SIM_EVAL_BASELINE' else [cfg['alpha']]:
                view_rows.append({**base,'alpha':alpha,'baseline_alpha_display_copy_only':cfg['stage']=='SIM_EVAL_BASELINE'})
    effects=effects_report(view_rows,plan)
    p0_frames=sum(x['frame_audit']['frames'] for x in p0['proof'])
    require(finished['audits']['trace']==len(summary) and finished['audits']['nominal']==len(summary),'Execution trace/nominal audit totals')
    require(finished['audits']['training_frames']+finished['audits']['eval_frames']==frame_total-p0_frames,'Execution saved NN frame totals')
    require({(x['family'],x['seed']) for x in finished['training_models']}=={(f,s) for f in plan['families'] for s in plan['seeds']},'Execution terminal model coverage')
    require(all(x['network_changed'] and x['episodes']==32 and x['updates']==4 and x['adam_steps']>0 for x in finished['training_models']),'Execution learner terminal states')
    korean={'status':'SAVED_EXECUTION_AUDIT_PASS_CONDITIONAL_SIMULATOR','recommended_family_from_DEV':seal['recommended_family'],
            'actual_new_environments':len(rows),'base_environment_count':len(rows)-len(prediction_rows),'new_input_prediction_scope':prediction_scope,'evaluation_runs':len(eval_starts),'display_rows':len(view_rows),
            'baseline_alpha_copies_are_not_new_environments':True,
            'model_conditional_joint_goal_pass_count':effects['model_conditional_goal_pass_comparisons'],
            'physical_goal':'미확인: 새 실측 J 단위·정책 Δ 정확도 검증 전',
            'goal_interpretation':'각 조건에서 E180 10%와 APmean 0.5℃를 동시에 낮추고, 긴급/일반 서비스 기준과 전량 완료를 만족하며 FIFO 대비 납기·완료 손해가 없어야 모형 내 공동목표 PASS다.',
            'uncertainty':'모형별 세 bank paired bootstrap2000과 학습3seed 범위. 세 bank뿐이며 실기기 독립 반복의 신뢰구간이 아니다.',
            'new_CONFIRM_outcomes_opened':0,'original_V2_complete':False,'project_complete':False,
            'important_limits':['M128/L64 분류GPU·탐지CPU;미지원경로확대0','AP_HAL≠표면온도','열→처리시간 피드백 미식별','기존 gauge 고정 비용;임의1000배 보정0','선정은DEV뿐이며SIM_EVAL로재선정0']}
    data={'meta':meta_base('롤링＋ATC＋RL 새 학습·DEV 선정·봉인된 모형 평가 완료 · 물리 정확도 확인 대기'),'rows':view_rows}
    data['meta'].update(source_freeze={'generation':generation,'registration_sha256':sha(O/'REGISTRATION.json'),'selection_sha256':sha(O/'DEV_SELECTION_FREEZE.json')},recommended_family=seal['recommended_family'])
    save(O/'ALL_CASES.csv',allcase_csv(view_rows));save(O/'EFFECTS_AND_COMPARISONS.json',effects);save(O/'RESULTS_KO.json',korean);save(O/'VIEW_DATA.json',data)
    report=['# A24 롤링＋ATC＋RL 시뮬레이터 결과','',
            '정해진 납기를 최대한 만족하면서 열·에너지 감소를 검토했다. 이 결과는 A24 DEV 기반의 고정 조건부 비용 모형 실험이며 실기기 절감 확정은 아니다.','',
            f'- 실제 소비: {len(rows)}환경. 학습4군×3seed, DEV로 동결한 추천군: {seal["recommended_family"]}.',
            f'- 전수 trace·입력·nominal·원장·저장 checkpoint/RNG와 기존 NN 감사 증거 검산 PASS. 이번 최종화 새 NN/환경/CostState/optimizer 0.',
            f'- 모형 내 공동목표 PASS 비교: {effects["model_conditional_goal_pass_comparisons"]}/{len(effects["comparisons"])}. 물리적 공동목표 달성은 미확인.',
            f'- 등록된 모형/표본 조건 사이 부호 불일치: {len(effects["model_case_direction_disagreements"])}건. 입력별 전체 손해는 EFFECTS_AND_COMPARISONS와 ALL_CASES에 보존.',
            '- 서비스70/80/90/95/100%,긴급/일반/전량완료,고정J180/AP35–180/peak/잔열을 모두 보존했다. 실패·미완료를 분모에서 제외하지 않았다.',
            '- 신뢰구간은 모형별 세 bank의 paired synthetic cluster bootstrap2000(seed20261016). 세 bank뿐이며 실기기 독립 CI가 아니다.3학습seed 범위도 별도 제공한다.',
            '- 새 CONFIRM 결과는 여기서 열지 않았고 같은 SIM_EVAL로 정책·checkpoint를 다시 고르지 않았다.','']
    save(O/'RESULTS_KO.md','\n'.join(report).encode('utf-8'))
    html_bytes=render_html(data)
    html_expected={'path':str(TARGET),'sha256':hashlib.sha256(html_bytes).hexdigest(),'bytes':len(html_bytes),
                   'publication_at_audit_boundary':'PENDING; completion receipt must confirm exact rendered bytes'}
    audit={'status':'PASS','schema':'A24-FINAL-SAVED-AUDIT-v1','generation':generation,'registration_sha256':sha(O/'REGISTRATION.json'),
           'environment_START':len(rows),'PREPARED':len(rows),'COMPLETE':len(rows),'FAIL':0,'unresolved_START':0,
           'all_source_and_protected_SHA_verified':True,'sealed_coverage_recomputed':True,'selection':selected_audit,
           'P0_audit_sha256':sha(O/'P0_AUDIT.json'),'numeric_audit_sha256':sha(O/'NUMERIC_AUDIT.json'),
           'cost_only_numeric_instances_previously_consumed':numeric.get('cost_only_model_wrapper_instances'),
           'checkpoint_states':cpmeta,'saved_frames_verified_without_new_inference':frame_total,'public_to_saved_NN_input_arrays_rebuilt':frame_total*7,'per_run':rawproof,
           'global_actual_START':old_starts+len(rows),'new_environment':0,'new_NN_inference':0,'new_optimizer_steps':0,'new_CostState':0,'new_input_prediction_scope':prediction_scope,
           'allcase_output_rows':len(view_rows),'html':html_expected,'physical_policy_delta_accuracy_confirmed':False,
           'CONFIRM_outcomes_opened':0,'project_complete':False,'finalizer_source_sha256':sha(__file__)}
    save(O/'FINAL_AUDIT.json',audit)
    html=publish_html(data,op,'A24-energy-thermal-simulator.html')
    require(html['sha256']==html_expected['sha256'],'Published HTML differs from audited rendered bytes')
    outputs={str(O/n):sha(O/n) for n in ('ALL_CASES.csv','EFFECTS_AND_COMPARISONS.json','RESULTS_KO.json','RESULTS_KO.md','VIEW_DATA.json','FINAL_AUDIT.json','A24-energy-thermal-simulator.html')}
    receipt={'status':'A24_MODEL_TRAINING_EVAL_AND_SAVED_AUDIT_COMPLETE_PHYSICAL_CONFIRM_PENDING','artifacts':outputs,'html':html,
             'new_finalizer_environments':0,'new_NN':0,'new_CostState':0,'project_complete':False,'browser_QA':'PARENT_REQUIRED_NOT_CLAIMED'}
    save(O/'COMPLETION_RECEIPT.json',receipt)
    lock.close()
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--operation',type=Path,default=O/'FINALIZER_OPERATION_REGISTERED.json')
    args=parser.parse_args();op=operation(args.operation,args.preview)
    result=preview(op) if args.preview else finalize(op)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # A failed finalization cannot overwrite PASS or existing raw evidence.
        failure=O/('FINALIZER_FAILURE_'+str(time.time_ns())+'.json')
        if O.exists():save(failure,{'status':'FAILED_NO_COMPLETION','error':str(error),'source_sha256':sha(__file__),'unix':time.time(),'new_environment':0,'new_NN':0})
        raise
