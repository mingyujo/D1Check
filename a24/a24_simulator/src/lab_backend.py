"""Local, pinned A24 integrated model; no network or import-time work.

Each call is one explicit comparison batch, never a periodic task. The original
five-phase/progress physics and the selected PPO checkpoint stay immutable.
"""
from __future__ import annotations
import argparse, copy, gzip, hashlib, importlib.util, json, math, os
from pathlib import Path
import sys, time, uuid
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
MODEL_WORK = BASE / 'reference/model_integration'
OLD_RL = BASE / 'reference/rolling'
GUARD_ENTRY = Path(os.environ.get('A24_LAB_GUARD_ENTRY', __file__))
sys.path.insert(0, str(MODEL_WORK))
from runtime_guard import append, canonical, free_guard, now, pin, read, sha, write_new
import runtime_guard
runtime_guard.OWN_TOKENS += ('s26-unified-dynamics-', 'a24-interactive-policy-lab-',)
from timing_model import build_timing_candidate, context_of, context_for_route, UnsupportedContext, NS
from forecast_overlay_run import apply_timing_bank_overlay, install_lookup_cache
from forecast_run import generated_activity, historical_mobile_comparator, ap_summary, deadline_summary, work_scope
import thermal_four_route as thermal_model
from four_route_model import FourRouteTiming, extend_thermal, extend_profile, conditional_energy, labels as resource_state
from interactive_kernel import simulate_protocol

POLICIES = ('ROLLING_ATC_RL', 'ROLLING_ATC_RL_NO_WAIT', 'FIFO_SERIAL_CG',
            'FIFO_FREE', 'EDD', 'ATC', 'MOBILE_DEADLINE_ENERGY')
LABELS = {'ROLLING_ATC_RL': '롤링 + ATC + RL', 'ROLLING_ATC_RL_NO_WAIT': '동일 RL · WAIT 제거',
          'FIFO_SERIAL_CG': 'FIFO · 고정 CG/DC 직렬', 'FIFO_FREE': 'FIFO · CPU/GPU 자유배정',
          'EDD': '납기 우선 EDD', 'ATC': '롤링 + ATC', 'MOBILE_DEADLINE_ENERGY': '모바일 납기·비용 규칙'}

def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()

def need(condition, message):
    if not condition:
        raise ValueError(message)

def number(x, name, lo, hi):
    need(type(x) in (int, float) and math.isfinite(x) and lo <= x <= hi, name + ': 범위 오류')
    return float(x)

def validate_input(value, catalog):
    need(isinstance(value, dict), '입력은 JSON object여야 합니다.')
    rows = value.get('requests')
    need(isinstance(rows, list) and 1 <= len(rows) <= 256, '요청은 1~256개입니다.')
    seed = value.get('seed', 20261016)
    need(type(seed) is int and 0 <= seed <= 2147483647, '표본 seed는 0~2147483647 정수입니다.')
    rlseed = value.get('rl_seed', 46201)
    need(type(rlseed) is int and rlseed in (46201, 46203, 46207, 20261028), '봉인 RL seed 오류')
    initial = value.get('initial_context', 'M128')
    need(initial in ('M128', 'L64', 'C252'), '초기 이력 기준 오류')
    alpha = number(value.get('alpha', .95), '서비스 목표', .7, 1.)
    need(alpha in (.7, .8, .9, .95, 1.), '등록된 서비스 목표를 사용하세요.')
    output = []
    for i, q in enumerate(rows):
        need(isinstance(q, dict), '요청 행은 object여야 합니다.')
        profile = q.get('profile')
        need(profile in catalog, f'{i+1}행: 지원 실측 작업을 선택하세요.')
        priority = q.get('priority', 'N')
        need(priority in ('U', 'N'), f'{i+1}행: 긴급/일반 구분 오류')
        a = number(q.get('arrival_s'), f'{i+1}행 도착', 0., 179.999)
        d = number(q.get('deadline_s'), f'{i+1}행 납기', a, 210.)
        # Ordinal is explicit list order. Import never treats an external array
        # index as a source request ordinal or a measured native identity.
        output.append({'ordinal': i, 'profile': profile, 'priority': priority,
                       'arrival_s': a, 'deadline_s': d})
    return {'requests': output, 'seed': seed, 'rl_seed': rlseed,
            'initial_context': initial, 'alpha': alpha}

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

class Model(FourRouteTiming):
    def __init__(self, model, contexts):
        super().__init__(model,contexts,read(HERE/'DG_TIMING_EVIDENCE.json'))

class RLPolicy:
    """Exact old bank/actor, with causally available integrated-model inputs.

    This is a declared model transfer. It does not reselect a checkpoint or
    claim the old actor was trained against the new timing/AP model.
    """
    def __init__(self, model, public, thermal, profile, checkpoint, alpha, allow_wait):
        import numpy as np
        import torch
        self.np, self.torch = np, torch
        torch.set_num_threads(1)
        self.bridge = load_module('a24_lab_four_route_policy_bridge', HERE / 'policy_bridge_four_route.py')
        self.learn = load_module('a24_lab_learner', OLD_RL / 'learner.py')
        snapshot = torch.load(checkpoint, map_location='cpu', weights_only=False)
        need(snapshot['schema'] == self.learn.SCHEMA and snapshot['family'] == 'JOINT_ATC_RL', 'RL ABI mismatch')
        previous = torch.random.get_rng_state()
        net = self.learn.Net()
        net.load_state_dict(snapshot['network']); net.eval()
        torch.random.set_rng_state(previous)
        need(self.learn.network_digest(net) == snapshot['network_sha256'], 'RL network digest mismatch')
        rng = torch.Generator(); rng.set_state(snapshot['action_rng'])
        learner = SimpleNamespace(net=net, family='JOINT_ATC_RL', steps=snapshot['steps'], action_rng=rng)
        self.controller = self.learn.Controller(learner, alpha, .5, False)
        self.model, self.public, self.thermal, self.profile = model, public, thermal, profile
        self.alpha, self.allow_wait = alpha, allow_wait
        self.waited = set(); self.previous_ap = None
        self.mobile = historical_mobile_comparator(profile)
        self.network_sha = snapshot['network_sha256']

    def __call__(self, state):
        t = state['now_ns']; ts = t / NS
        # Past activity is clipped by the engine at exactly now. There is no
        # sampled remaining work, future finish, or future AP in this adapter.
        intervals = state['past_activity']
        need(all(x['end_s'] <= ts and x['start_s'] < x['end_s'] for x in intervals), 'Future owner activity leaked')
        activity = copy.deepcopy(self.public)
        activity.update(owner_intervals=intervals, activity_coverage_s=[0., ts], observation_window_s=[0., ts])
        ap = thermal_model.predict(self.thermal, activity, times=[ts], allow_extrapolation=True)
        need(ap['status'] == 'CONDITIONAL_AP_PREDICTION', 'RL current AP unavailable: ' + str(ap.get('reason')))
        apvalue = ap['ap_c'][0]
        owners = {o['route']: dict(o, phase_index=state['owner_phases'][o['route']],
                     priority=self.model.contexts[o['request_id']]['_requests_by_id'][o['request_id']]['priority'])
                  for o in state['owners']}
        estimates = {}
        for q in [*state['queue'], *state['owners']]:
            source = self.model.contexts[q['request_id']]
            context, _ = context_of(source, source['_requests_by_id'][q['request_id']], True)
            e = {}
            for route in ('CPU', 'GPU'):
                try:
                    estimate = self.model.nominal(context_for_route(context, q['task'], route), q['task'], route, state=state)
                    e[route] = {**estimate, 'energy_proxy_j': self.mobile(q, route, estimate, state)}
                except UnsupportedContext:
                    continue
            need(e, 'RL nominal support unavailable')
            estimates[q['request_id']] = e
        power = self.profile['measured35']['baseline_w']
        if owners:
            key = resource_state([dict(o,route=route) for route,o in owners.items()])
            power += self.profile['cost_anchor']['energy_increment_w'][key]
        recent = {route: sum(max(0., min(ts, x['end_s']) - max(max(0., ts-5.), x['start_s']))
                             for x in intervals if x['route'] == route) / min(5., max(ts, 1e-9))
                  for route in ('CPU', 'GPU', 'NPU')}
        slope = 0. if self.previous_ap is None or ts <= self.previous_ap[0] else (apvalue-self.previous_ap[1])/(ts-self.previous_ap[0])
        obs = {'now_ns': t, 'queue': state['queue'], 'owners': owners, 'estimates': estimates,
               'last_release_ns': state['last_release_ns'], 'history': state['history_by_priority'],
               'wait_used_ns': state['wait_used_ns'], 'waited_request_ids': sorted(self.waited),
               'horizon_ns': self.public['service_stop_ns'], 'alpha': self.alpha, 'heat_weight': .5,
               'sensor': {'AP_c': apvalue, 'power_w': power, 'age_s': 0., 'recent_activity': recent,
                          'ap_slope_c_s': slope, 'power_slope_w_s': 0.}}
        bank = self.bridge.build_bank(obs, 'JOINT_ATC_RL', allow_wait=self.allow_wait)
        idx = self.controller.choose(bank, t, getattr(self, 'collect', False))
        action = copy.deepcopy(bank['actions'][idx])
        if action['kind'] == 'WAIT': self.waited.add(bank['diagnostic']['head_request_id'])
        self.previous_ap = (ts, apvalue)
        return action

def initialize(reg):
    for p in [*reg['source_pins'], *reg['input_pins']]: pin(p)
    parent = read(pin(reg['parent_operation_pin']))
    dataset = read(pin(parent['dataset_pin']))
    dataset, _ = apply_timing_bank_overlay(dataset, read(pin(parent['timing_bank_overlay_pin'])),
                                           parent['dataset_pin'], parent['timing_bank_overlay_pin']['sha256'])
    model = build_timing_candidate(dataset['sessions'], **parent['timing_configuration'])
    need(model.metadata['model_digest'] == reg['timing_model_digest'], 'Integrated timing model differs')
    install_lookup_cache(model, 'interactive-combined')
    thermal = read(pin(parent['thermal_models_pin']))['final_models']['combined']
    need(thermal['model_sha256'] == parent['thermal_model_sha256'], 'Integrated AP differs')
    profile = read(pin(parent['historical_profile_pin']))
    return model, extend_thermal(thermal), extend_profile(profile)

def prepare_public(value, templates, catalog):
    public = copy.deepcopy(templates[value['initial_context']])
    public.update(session_id='A24_USER_MIXED_COUNTERFACTUAL', bank='USER_MIXED', requests=[],
                  service_stop_ns=180*NS, drain_stop_ns=210*NS, observation_end_ns=210*NS,
                  request_id_mapping=[], initial_context_status='REAL_REFERENCE_HISTORY_USER_SELECTED_NOT_NEW_MEASUREMENT')
    contexts = {}
    for q in value['requests']:
        c = catalog[q['profile']]
        row = copy.deepcopy(c['reference_request'])
        row.update(request_id='user-'+str(q['ordinal']).zfill(4), ordinal=q['ordinal'],
                   priority=q['priority'], scheduled_arrival_ns=round(q['arrival_s']*NS),
                   deadline_ns=round(q['deadline_s']*NS), bank=c['bank'], group=q['ordinal']//8)
        public['requests'].append(row)
        source = copy.deepcopy(templates[c['bank']])
        registry = source['compatibility']['public_models']
        if 'D_CPU' in registry and 'D_GPU' not in registry:
            registry['D_GPU'] = copy.deepcopy(registry['D_CPU'])
            registry['D_GPU']['historical_GPU_timing_transfer_unverified_current_APK'] = True
        contexts[row['request_id']] = {**source, '_requests_by_id': {row['request_id']: row}}
    public['public_base_sha256'] = digest(value)
    public['public_scenario_sha256'] = digest(value)
    return public, contexts

def policy_result(policy, public, model, thermal, profile, value, start, reg):
    actor = None
    if policy.startswith('ROLLING_ATC_RL'):
        cp = reg['checkpoints'][str(value['rl_seed'])]
        actor = RLPolicy(model, public, thermal, profile, pin(cp), value['alpha'], policy == 'ROLLING_ATC_RL')
    potential_key = digest({'requests': value['requests'], 'seed': value['seed']})
    prediction = simulate_protocol(public, model, 'FROZEN_RL_REPLAY' if actor else 'FIFO' if policy=='FIFO_FREE' else policy,
        execution_guard=start, scenario_key=[potential_key, value['seed']], admission_protocol='SERIAL',
        redispatch_mode='ZERO_EXPLICIT_BASELINE', zero_baseline_id='COMMON_UNIDENTIFIED_CONTROLLER_IDEAL_ZERO',
        pair_scope='READY_QUEUE', frozen_policy=actor,
        frozen_policy_binding={'replay_only': True, 'checkpoint_sha256': reg['checkpoints'][str(value['rl_seed'])]['sha256'],
                               'input_contract_sha256': reg['adapter_contract_sha256']} if actor else None,
        mobile_energy=historical_mobile_comparator(profile), decision_cap=8192,
        concurrency_mode='DATA_DERIVED_PROGRESS', unidentified_overlap='SERIAL_INDEPENDENT')
    activity = generated_activity(public, prediction)
    ap = thermal_model.predict(thermal, activity, times=[i*.5 for i in range(421)], allow_extrapolation=True)
    energy = conditional_energy(activity, profile, 0., 180.)
    full_energy = conditional_energy(activity, profile, 0., 210.)
    deadlines = deadline_summary(prediction['requests'], service_stop_ns=180*NS, drain_stop_ns=210*NS)
    flags = list(ap.get('extrapolation_flags', []))
    flags.append('FOUR_ROUTE_TASK_DEVICE_THERMAL_ENERGY_FACTOR_TRANSFER_NOT_CURRENT_DG_MEASUREMENT')
    if any(q.get('route')=='GPU' and q['task']=='D' for q in prediction['requests']):
        flags.append('D_GPU_HISTORICAL_RATIO_CURRENT_CPU_TIMING_TRANSFER')
    if any('UNMEASURED_PAIR' in str(x.get('evidence',{})) for x in prediction.get('rate_history',[])):
        flags.append('UNMEASURED_PAIR_EXPLICIT_INDEPENDENT_SERVICE_EXTRAPOLATION')
    if any('UNIDENTIFIED' in str(x.get('evidence', {})) for x in prediction.get('rate_history', [])):
        flags.append('UNIDENTIFIED_OVERLAP_EXPLICIT_SERIAL_INDEPENDENT_FALLBACK')
    if any(q.get('timing', {}).get('bank_extrapolation') for q in prediction['requests']):
        flags.append('SAME_BINDING_BANK_TIMING_TRANSFER')
    summary = {'policy': policy, 'label': LABELS[policy], 'status': prediction['status'],
               'metrics': prediction['metrics'], 'deadlines': deadlines,
               **ap_summary(ap, public, [35., 180.]), 'AP_status': ap['status'],
               'J_proxy': energy['historical_conditional_J'], 'J_proxy_full': full_energy['historical_conditional_J'],
               'energy': energy, 'measured_J': None, 'energy_error_J': None, 'energy_CI': None,
               'gantt': activity['owner_intervals'], 'AP': {'t_s': ap['t_s'], 'ap_c': ap['ap_c']},
               'wait_s': sum(max(0, min(d['action']['wait_ns'],180*NS-d['time_ns']))
                             for d in prediction['decisions'] if d['action'].get('kind')=='WAIT')/NS,
               'wait_planned_s': prediction['wait_used_ns']/NS, 'flags': flags,
               'AVAILABLE_by180': sum(q['available_ns'] is not None and q['available_ns']<=180*NS for q in prediction['requests']),
               'controller_runtime': 'UNIDENTIFIED_COMMON_IDEAL_ZERO',
               'RL_status': ('FOUR_ROUTE_PPO_TRAINED_DEVELOPMENT_NOT_DEVICE_VALIDATED' if reg.get('four_route_retrained') else 'FROZEN_ACTOR_FOUR_ROUTE_OOD_MASK_TRANSFER_NOT_RETRAINED') if actor else 'RULE',
               'route_counts': {task+'_'+route:sum(q['task']==task and q['route']==route for q in prediction['requests']) for task in ('C','D') for route in ('CPU','GPU')},
               'legal_route_scope': {'C':['CPU','GPU'],'D':['CPU','GPU']},
               'D_GPU_legal_action_slots': sum(bool(f['mask'][i]) and bool(f['physical_mask'][i]) and
                    int(f['backend_index'][i])==1 and float(f['requests'][int(f['request_index'][i]),1])>.5
                    for f in actor.controller.frames for i in range(72)) if actor else None,
               'actor_decisions': len(actor.controller.decisions) if actor else 0,
               'network_sha256': actor.network_sha if actor else None,
               'work_scope': work_scope(prediction, public, [0., 180.]),
               'by_priority': {p: {'planned': sum(q['priority']==p for q in prediction['requests']),
                     'on_time': sum(q['priority']==p and q['response_ns'] is not None and q['response_ns']<=q['deadline_ns'] and q['response_ns']<=210*NS for q in prediction['requests']),
                     'missing': sum(q['priority']==p and (q['response_ns'] is None or q['response_ns']>210*NS) for q in prediction['requests'])} for p in ('U','N')},
               'requests': [{k:q.get(k) for k in ('request_id','task','priority','ordinal','scheduled_arrival_ns','deadline_ns','dispatch_ns','response_ns','available_ns','route','terminal_status')} for q in prediction['requests']]}
    from diagnostics import add_diagnostics
    add_diagnostics(summary, public, profile, ap, activity)
    return {'prediction': prediction, 'AP': ap, 'energy': energy, 'summary': summary}, actor

def audit_result(result, actor):
    rows = result['prediction']['requests']; checks = 0
    for q in rows:
        if q['dispatch_ns'] is None: continue
        need(q['dispatch_ns'] >= q['queue_entry_ns'] >= q['scheduled_arrival_ns'], 'Queue clock order'); checks += 1
        vals = [q.get(k+'_ns') for k in ('execution_start','output_ready','persist_complete','worker_release','lane_available')]
        known = [x for x in vals if x is not None]
        need(known == sorted(known), 'Five phase order'); checks += 1
        boundary = q.get('output_ready_ns' if q['task']=='C' else 'persist_complete_ns')
        need(q['response_ns'] == boundary, 'Response boundary'); checks += 1
    points = sorted({v for q in rows for v in (q['dispatch_ns'],q['available_ns']) if v is not None})
    for t in points:
        active = [q for q in rows if q['dispatch_ns'] is not None and q['dispatch_ns']<=t and (q['available_ns'] is None or t<q['available_ns'])]
        need(len(active)<=2 and len({q['route'] for q in active})==len(active), 'Physical resource overlap'); checks += 1
        if len(active)==2: need({q['route'] for q in active}=={'CPU','GPU'}, 'CPU/GPU lane exclusion')
    if actor:
        for f in actor.controller.frames:
            replay = actor.learn.replay_frame(actor.controller.learner.net, f)
            need(replay['argmax']==f['index'], 'NN argmax replay')
            need(abs(replay['logprob']-f['old_logp'])<1e-6, 'NN logprob replay')
            need(actor.np.allclose(replay['critic'],f['value'],rtol=1e-5,atol=1e-6), 'NN critic replay'); checks += 3
            need(actor.torch.equal(f['action_rng_before'],f['action_rng_after']), 'Evaluation consumed action RNG')
        need(actor.learn.network_digest(actor.controller.learner.net)==actor.network_sha, 'Frozen network changed')
    need(result['summary']['measured_J'] is None, 'Uncalibrated J promoted')
    return {'status':'PASS_SAVED_CLOCK_RESOURCE_NN_ARITHMETIC','checks':checks,'physical_accuracy_verified':False}

def run(reg_path, request_path, batch_id):
    reg = read(reg_path); need(reg['schema']=='A24-interactive-policy-lab-registration-v1','Registration schema')
    runtime_guard.process_guard(GUARD_ENTRY, reg.get('known_PS_producer_paths') or [])
    free_guard([HERE, reg['output_dir'], BASE])
    need(batch_id and all(c in '0123456789abcdef-' for c in batch_id) and len(batch_id)<=64, 'Batch identity')
    output = Path(reg['output_dir']); batch = output/'batches'/batch_id
    need(not batch.exists(), 'Consumed batch identity; automatic retry prohibited')
    # The OS lock spans model construction, all seven policies and final audit.
    import msvcrt
    lock = Path(reg['worker_lock_path']).open('r+b'); lock.seek(0)
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        catalog = read(pin(reg['catalog_pin']))
        value = validate_input(read(request_path),catalog['profiles'])
        ledger = output/'receipts.jsonl'
        used = sum(json.loads(x).get('event')=='START' for x in ledger.read_text().splitlines()) if ledger.exists() else 0
        need(used+len(POLICIES)<=reg['environment_cap'],'Registered interactive START budget exhausted')
        batch.mkdir(parents=True, exist_ok=False)
        write_new(batch/'BATCH_REGISTERED.json',{'batch_id':batch_id,'input':value,'input_sha256':digest(value),
              'source_registration_sha256':sha(reg_path),'policies':POLICIES,'utc':now(),'NN_training':0,'automatic_retry':False})
        model, thermal, profile = initialize(reg)
        public, contexts = prepare_public(value,catalog['templates'],catalog['profiles'])
        model = Model(model,contexts)
        need(model.metadata['model_digest']==reg['expected_four_route_timing_digest'],'Frozen four-route timing digest mismatch')
        need(thermal['model_sha256']==reg['expected_four_route_AP_sha256'],'Frozen four-route AP digest mismatch')
        write_new(batch/'PUBLIC_INPUT.json',public)
        summaries=[]
        for policy in POLICIES:
            runtime_guard.process_guard(GUARD_ENTRY, reg.get('known_PS_producer_paths') or []); free_guard([output,BASE])
            identity = digest([batch_id,policy,sha(reg_path)])
            start={'event':'START','identity':identity,'start_id':identity,'policy':policy,'batch_id':batch_id,
                   'utc':now(),'registration_sha256':sha(reg_path),'durable_START_consumed':True,
                   'input_sha256':digest(value),'new_environment':1}
            append(ledger,start)
            try:
                result, actor = policy_result(policy,public,model,thermal,profile,value,start,reg)
                audit = audit_result(result,actor)
                raw = batch/(policy+'.json.gz')
                with gzip.open(raw,'xt',encoding='utf-8') as f: f.write(canonical(result))
                if actor:
                    frames = batch/(policy+'.frames.pt'); actor.torch.save(actor.controller.frames,frames)
                    frames_pin={'path':str(frames),'sha256':sha(frames),'bytes':frames.stat().st_size}
                else: frames_pin=None
                prepared={'identity':identity,'policy':policy,'raw_sha256':sha(raw),'frames':frames_pin,
                          'audit':audit,'summary_sha256':digest(result['summary'])}
                write_new(batch/(policy+'.PREPARED.json'),prepared)
                append(ledger,{'event':'PREPARED','identity':identity,'batch_id':batch_id,'utc':now(),**prepared})
                write_new(batch/(policy+'.COMPLETE.json'),prepared)
                append(ledger,{'event':'COMPLETE','identity':identity,'batch_id':batch_id,'utc':now(),'raw_sha256':sha(raw)})
                summaries.append(result['summary'])
                write_new(batch/(policy+'.summary.json'),result['summary'])
                print(canonical({'policy':policy,'completed':len(summaries),'total':len(POLICIES)}),flush=True)
            except Exception as error:
                failure={'identity':identity,'policy':policy,'error':str(error),'type':type(error).__name__,'utc':now(),
                         'consumed':True,'automatic_retry':False}
                write_new(batch/(policy+'.FAILURE.json'),failure)
                append(ledger,{'event':'FAIL','batch_id':batch_id,**failure}); raise
        for p in [*reg['source_pins'], *reg['input_pins']]: pin(p)
        final={'batch_id':batch_id,'utc':now(),'input':value,'input_sha256':digest(value),'rows':summaries,
               'bindings':{'AP_model_sha256':thermal['model_sha256'],'timing_model_digest':model.metadata['model_digest'],
                           'cost_profile_sha256':profile['derived_profile_sha256'],'original_cost_profile_sha256':reg['historical_profile_sha256'],'same_public_input_for_all_policies':True,
                           'legal_route_scope':{'C':['CPU','GPU'],'D':['CPU','GPU']},'maximum_inflight':2,
                           'common_potential_seed':value['seed'],
                           'potential_roster_sha256':digest({'requests':value['requests'],'seed':value['seed']}),
                           'actor_seed_alpha_and_initial_history_do_not_change_latent_potential':True,
                           'NN_training':0,'actor_pretrained_four_route':bool(reg.get('four_route_retrained')),'measured_J':None,'fresh_confirmation':False},
               'initial_AP_c':public['initial_ap_c'],'initial_context':value['initial_context'],
               'qualification':'FOUR_ROUTE_POSTHOC_MODEL_EXTRAPOLATION_WITH_EXPLICIT_ACTOR_LINEAGE',
               'notes':['두 작업 모두 CPU/GPU가 후보이며 실제 자원 점유·AVAILABLE까지는 배정할 수 없습니다.',
                        '탐지 GPU 시간은 과거 matched GPU/CPU 5단계 비율을 현재 CPU 벡터에 전이한 예측입니다. 현재 APK의 GPU 실측은 아닙니다.',
                        '탐지 GPU·새 병행의 열/조건부 비용은 작업+장치 가산 및 공통 병행 항의 추정입니다. 미측정 상호작용은 식별되지 않았습니다.',
                        'RL 학습 계보와 DEV 선정은 models/TRAINING_RESULT.json을 참조합니다. 폰 RL/독립 실측 효과 검증은 아닙니다.',
                        '공통 실제 초기 AP 이력을 적용합니다. 같은 초기 AP가 내부 열이력/SOC 동등성을 보장하지 않습니다.',
                        'J*는 공통 역사 비용식의 조건부 예측이며 실측 J/에너지오차/CI는 미확정입니다.',
                        '제어기 실행 지연은 미식별이며 모든 정책에 명시적 공통 ideal-zero 진단을 적용했습니다.',
                        '미측정 혼합 부하와 열·병행 관계는 관측 기반 전용 가정이며 폰 정책 효과 검증이 아닙니다.']}
        from diagnostics import schedule_groups
        final['schedule_equivalence'] = schedule_groups(summaries)
        write_new(batch/'RESULT.json',final)
        write_new(batch/'COMPLETE.json',{'batch_id':batch_id,'result_sha256':sha(batch/'RESULT.json'),
                   'START':len(summaries),'COMPLETE':len(summaries),'FAIL':0,'utc':now()})
    finally:
        lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1); lock.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--registration',required=True)
    parser.add_argument('--request',required=True); parser.add_argument('--batch',required=True)
    args=parser.parse_args(); run(args.registration,args.request,args.batch)
