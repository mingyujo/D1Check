"""PC 계획 동결/검증 전용. 시간 진행, 난수 표본추출, 기기 실행 기능 없음."""
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath

import jsonschema

from tools import d1_bounded_empirical as bounded
from tools import d1_empirical_plan as empirical
from tools import d1_execution_manifest as atomic
from tools import d1_telemetry_v4 as telemetry

VERSION = 'pc-simulation-plan-v1'
MASTER_SEED = 2026092201
INPUT_SHA = '4eeae6f6f8e9954d153b010767ba5a84307e5b8d0a971e7a478b0255413c0fc5'
JOURNAL_SHA = 'db5a3f7733bae3b516e3fd08ca9cfb77cda230584b1a658200427a0ddcaed008'
REPORT_SHA = 'faa63c0d1107d663605621cf448b26bee95f2a094b077c4b77a483e7e7b7c614'
REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / 'tools/schemas/pc-simulation-plan-v1.schema.json'
BUNDLE = Path('C:/Users/LG/Documents/D1Check_Bounded_Empirical_Plan/plan_20260921_v1/frozen')
GOLDEN = Path('C:/Users/LG/Documents/D1Check_Decode_Resolution')
PRODUCTS = {'plan.json', 'input_registry.json', 'input_audit.json', 'no_op.json'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def contained(root, name):
    """상대 POSIX 경로만 허용; Windows ADS/drive/backslash 및 link 이탈 거부."""
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('unsafe path')
    path = PurePosixPath(name)
    if path.is_absolute() or any(x in ('', '.', '..') for x in name.split('/')):
        raise ValueError('unsafe path')
    root = Path(root).resolve(strict=True)
    target = root.joinpath(*path.parts)
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise ValueError('linked input')
    if not target.resolve(strict=True).is_relative_to(root) or not target.is_file():
        raise ValueError('path escape/non-file')
    return target


def seed(scenario, replicate, purpose):
    if not isinstance(scenario, str) or not scenario or type(replicate) is not int or replicate < 0:
        raise ValueError('invalid seed key')
    if purpose not in ('workload', 'joint_pair', 'bootstrap'):
        raise ValueError('policy-dependent/unknown random stream')
    return int.from_bytes(hashlib.sha256(canonical(
        [VERSION, MASTER_SEED, scenario, replicate, purpose])).digest()[:8], 'big')


def configuration():
    common = dict(non_preemptive=True, resident=True, runtime_change=False,
                  tie=['arrival_ns', 'request_id'], random_ties=False,
                  memory_failure='reject; no fallback; latch stops new dispatch',
                  gpu_refusal=['quality_unverified', 'thermal_nonzero', 'memory_rejected',
                               'nonresident_cell', 'unmeasured_schedule'],
                  deadline='soft: late success retained; no deadline cancellation',
                  thermal=[0], runtime_count=2, cpu_threads=1)
    policies = [
        dict(id='SP1/FIFO_CPU', queue='FIFO', mapping={'classification': 'CPU', 'detection': 'CPU'}, concurrency=1),
        dict(id='SP1/URGENT_CPU', queue='urgent EDF then normal FIFO', mapping={'classification': 'CPU', 'detection': 'CPU'}, concurrency=1),
        dict(id='SP1/STATIC', queue='global FIFO', mapping={'classification': 'CPU', 'detection': 'GPU'}, concurrency=1),
        dict(id='SP1/ALWAYS_CORUN', queue='per-lane FIFO; start each free lane immediately', mapping={'classification': 'CPU', 'detection': 'GPU'}, concurrency=2),
        dict(id='SP1/ADAPTIVE', queue='urgent EDF then normal FIFO', mapping=None, concurrency=2,
             selection='before setup choose one resident layout from current queue only; within layout support-gated dispatch',
             score=['feasibility', 'predicted urgent misses', 'predicted urgent lateness', 'predicted urgent completion', 'CPU layout tie'],
             estimator=None, feasibility_epsilon=None),
    ]
    return dict(version=VERSION, common=common, policies=policies,
                objective=dict(method='epsilon-constraint then lexicographic',
                               order=['safety/quality/support', 'normal service/efficiency bounds', 'urgent miss rate', 'urgent P95'],
                               tolerances=None, practical_effect=None),
                statistics=dict(paired_unit='scenario/replicate/pair_id', bootstrap_unit='whole source session; resident arms paired',
                                bootstrap_replicates=2000, confidence=0.95,
                                quantile='linear interpolation (same as frozen calibration)',
                                loso='remove each of five paired units jointly; remove solo sessions within family',
                                aggregate='equal scenario weight; never pool raw request tails',
                                multiple_comparisons='descriptive simultaneous claims forbidden; no confirmatory p-values',
                                success='all predeclared practical and epsilon bounds AND quality/memory/support; unresolved bounds prohibit success'),
                random=dict(master_seed=MASTER_SEED, derivation='SHA256 canonical UTF8 [version,master,scenario,replicate,purpose] first8 unsigned big-endian',
                            policy_independent=True, materialize_on_execution_only=True),
                execution=dict(simulator_version=None, simulator_sha256=None, replications=None,
                               primary_request_count=None, warmup='six measured invocations/runtime outside timed workload',
                               initial_state='resident; timed ordinal 7..12 only', drain=None),
                scenario_axes=dict(arrival_load=None, urgent_fraction=None, task_mix=None,
                                   deadline='frozen CPU Q50/Q90 x {0.75,1,1.5}; all candidates',
                                   burst=None, initial_queue=None, memory='observed admitted only'),
                sensitivity=['whole-block low', 'whole-block central', 'whole-block high', 'whole-block cold_stress', 'paired LOSO'],
                unresolved=[
                    dict(id='U1_SUPPORT', reason='fixed offset0 ordered 6+6 trace cannot identify changed-order/staggered-overlap service law'),
                    dict(id='U2_POLICY', reason='adaptive estimator and admissible alternative layouts/actions not established by joint input'),
                    dict(id='U3_CRITERIA', reason='normal loss bounds and practical urgent effect have no approved utility/precision rationale; 10%/2pp remain proposals'),
                    dict(id='U4_DESIGN', reason='load/mix/run length/replications/drain require supported service law; no arbitrary numbers'),
                    dict(id='U5_ENGINE', reason='no approved simulator version/hash implementing this new contract'),
                ])


def trace_signature(block):
    m = block['manifest']
    return [dict(task=m['models'][q['model_key']]['model']['task_id'], priority=q['priority'], offset_ms=q['offset_ms'],
                 backend=m['models'][q['model_key']]['execution']['backend']) for q in m['requests']]


def require_observed_schedule(reference, proposed):
    if proposed != reference:
        raise ValueError('unsupported counterfactual schedule; no latency substitution')
    return True


def register(block, registry):
    sid = block['session_id']
    receipt = block['receipt']
    requests = [q['request_id'] for q in receipt['samples']]
    if (sid in registry['sessions'] or receipt['trace_fingerprint'] in registry['traces']
            or len(set(requests)) != len(requests) or set(requests) & set(registry['requests'])):
        raise ValueError('consumed/replay identity or fingerprint')
    registry['sessions'].append(sid)
    registry['requests'].extend(requests)
    registry['traces'].append(receipt['trace_fingerprint'])


def validate_pair_blocks(pair):
    arms = {b['manifest']['paired']['arm']: b for b in pair}
    if len(pair) != 2 or set(arms) != {'A', 'B'}:
        raise ValueError('partial/duplicate pair')
    receipts = sorted([b['receipt'] for b in pair], key=lambda r: r['session_start_ns'])
    return telemetry.paired(arms['A']['manifest'], arms['B']['manifest'], receipts)


def output_equivalence(art, block, golden_hashes):
    from tools.d1_probe_compare import compare_decoded
    for sample in block['receipt']['samples']:
        query = next(q for q in block['manifest']['requests'] + block['manifest']['warmup_requests']
                     if q['request_id'] == sample['request_id'])
        image = query['sample_id']
        path = (GOLDEN/'host_validation_v2'/image/'golden.json' if sample['task'] == 'detection' else
                GOLDEN/'resume_20260920T090545Z/host_classification_v3'/image/'golden.json')
        gold = read(path)
        golden_hashes[str(path)] = digest(path)
        result = read(art/(sample['request_id']+'.result.json'))
        if sample['task'] == 'detection':
            passed = compare_decoded(gold['decoded'], result['results'])['passed']
        else:
            a, b = gold['results'], result['results']
            passed = len(a) == len(b) and all(x['label'] == y['label'] and x['class_index'] == y['class_index']
                and abs(x['score'] - y['score']) <= .001 for x, y in zip(a, b))
        if (not passed or gold['image_sha256'] != result['image_sha256']
                or gold['input_tensor_sha256'] != result['input_tensor_sha256']):
            raise ValueError('output equivalence')


def observed_metrics(block):
    """이미 완료된 trace의 고정 지표 재계산. scheduling/난수/시간 진행 없음."""
    import numpy as np
    events = block['events']
    start = telemetry.exactly(events, 'workload_start')['mono_ns']
    end = telemetry.exactly(events, 'workload_end')['mono_ns']
    urgent, normal = [], []
    for query in block['manifest']['requests']:
        es = [e for e in events if e['request_id'] == query['request_id']]
        name = 'output_ready' if query['priority'] == 'urgent' else 'persist_complete'
        response = telemetry.exactly(es, name)['mono_ns'] - (start + query['offset_ms']*1000000)
        (urgent if query['priority'] == 'urgent' else normal).append(response)
    return dict(urgent_P95_ns=float(np.quantile(urgent, .95)), makespan_ns=end-start,
                throughput_per_s=len(block['manifest']['requests'])*1e9/(end-start))


def audit(source):
    """원시 semantic validator 재사용. 기존 관측 검증만 수행하며 표본을 뽑지 않는다."""
    source = Path(source).resolve(strict=True)
    inp = source / 'simulation_input'
    for path, expected in [(inp/'simulation_input.json', INPUT_SHA),
                           (source/'execution_manifest.json', JOURNAL_SHA),
                           (source/'FINAL_REPORT.md', REPORT_SHA)]:
        if digest(path) != expected:
            raise ValueError('pinned empirical input/report/journal changed')
    m = read(inp/'simulation_input.json')
    for name, expected in m['files'].items():
        if digest(contained(inp, name)) != expected:
            raise ValueError('derived input hash mismatch')
    journal = atomic.read(source/'execution_manifest.json')
    # 과거 실행계획을 재생성하면 shuffle RNG를 호출한다. 여기서는 동결 bytes와
    # 원래 code/source pins만 검증하고 어떤 난수 생성기도 호출하지 않는다.
    if digest(BUNDLE/'freeze.json') != journal['binding']['freeze_sha256']:
        raise ValueError('original freeze binding')
    original_freeze = read(BUNDLE/'freeze.json')
    for name, expected in original_freeze['files'].items():
        if digest(contained(BUNDLE, name)) != expected:
            raise ValueError('original bundle mutation')
    pins = {**original_freeze['code'], **read(BUNDLE/'execution_sources.json')['pins']}
    for name, expected in pins.items():
        if digest(Path(name)) != expected:
            raise ValueError('original code/source/APK mutation')
    original_plan = read(BUNDLE/'plan.json')
    if digest(BUNDLE/'plan.json') != m['plan_sha256']:
        raise ValueError('original plan binding')
    sessions = journal['sessions']
    if journal['halt_reason'] is not None or any(s['state'] != 'completed' for s in sessions):
        raise ValueError('incomplete journal')
    registry = read(source/'consumed_registry.json')
    if registry != read(BUNDLE/'consumed_registry.json'):
        raise ValueError('prior consumed registry changed')
    original_registry = copy.deepcopy(registry)
    blocks = read(inp/'joint_blocks.json')
    if len(blocks) != 30 or {b['session_id'] for b in blocks} != {s['session_id'] for s in sessions}:
        raise ValueError('unexpected source sessions')
    calls = events = admissions = 0
    layouts, golden_hashes = {}, {}
    for block in blocks:
        sid = block['session_id']
        spec = m['source_artifacts'][sid]
        art = (source/'smokes'/sid/'artifacts').resolve(strict=True)
        if Path(spec['artifact_root']).resolve() != art:
            raise ValueError('source artifact path not canonical pinned root')
        empirical.validate_block(block, art, spec['manifest_sha256'],
                                 (art.parent/'delegate_log.txt').read_text(encoding='utf-8'), registry)
        output_equivalence(art, block, golden_hashes)
        row = next(s for s in sessions if s['session_id'] == sid)
        if row['native_manifest_sha256'] != telemetry.sha(block['manifest']):
            raise ValueError('journal manifest mismatch')
        if row['cleanup'] != {'force_stop': True, 'process_absent': True}:
            raise ValueError('cleanup missing')
        if any(row['validation'].get(k) is not True for k in
               ('equivalence', 'identity', 'memory', 'provenance', 'schema', 'terminal', 'thermal', 'timing')):
            raise ValueError('journal validation missing')
        register(block, registry)
        calls += len(block['receipt']['samples'])
        events += len(block['events'])
        for event in block['events']:
            if event['event'] == 'memory_admission':
                admissions += 1
                if event['data']['reason'] != 'admit' or event['data']['thermal_status'] != 0:
                    raise ValueError('memory/thermal outside observed support')
        layouts.setdefault(row['family'], []).append(dict(session_id=sid, pair_id=row['pair_id'],
            signature=trace_signature(block), fingerprint=block['receipt']['trace_fingerprint']))
    if calls != 480 or admissions != 550 or events != 11155:
        raise ValueError('empirical count mismatch')
    bounded.approve_blocks(blocks, original_plan)
    pairs = {}
    for row in sessions:
        if row['pair_id']:
            pairs.setdefault(row['pair_id'], []).append(row['session_id'])
    if len(pairs) != 5 or any(len(x) != 2 for x in pairs.values()):
        raise ValueError('partial paired source')
    by_id = {b['session_id']: b for b in blocks}
    differences = []
    frozen_metrics = read(inp/'paired_metrics.json')
    for ids in pairs.values():
        pair = [by_id[sid] for sid in ids]
        validate_pair_blocks(pair)
        arms = {b['manifest']['paired']['arm']: observed_metrics(b) for b in pair}
        for block in pair:
            actual = observed_metrics(block)
            frozen = next(x for x in frozen_metrics if x['session_id'] == block['session_id'])
            if any(actual[k] != frozen[k] for k in actual):
                raise ValueError('observed metric mismatch')
        differences.append({k: arms['B'][k]-arms['A'][k] for k in arms['A']})
    mean_difference = {k: sum(d[k] for d in differences)/5 for k in differences[0]}
    starts = [x for x in journal['history'] if x['reason'].startswith('running before Activity start ')]
    if len(starts) != 30 or len({x['reason'] for x in starts}) != 30:
        raise ValueError('retry/additional execution')
    registry['protocol'] = 'pc-simulation-consumed-input-v1'
    registry['role'] = 'all source sessions consumed calibration; resampling allowed, independent holdout reuse forbidden'
    registry['calibration_sessions'] = sorted(b['session_id'] for b in blocks)
    registry['prior_consumed_sha256'] = sha(original_registry)
    # 원본 전체 파일 hash를 결합하되 모델 bytes는 복사하지 않는다.
    hashes = {p.relative_to(source).as_posix(): digest(p) for p in sorted(source.rglob('*'))
              if p.is_file() and '__pycache__' not in p.parts}
    result = dict(sessions=30, calls=calls, events=events, admissions=admissions,
                  paired_units=5, device_starts=len(starts), failures=0, retries=0, replacements=0, additional_sessions=0,
                  source_sha256=INPUT_SHA, journal_sha256=JOURNAL_SHA, report_sha256=REPORT_SHA,
                  layouts=layouts, pairs=pairs, source_files=hashes, golden_hashes=golden_hashes,
                  original_bundle_sha256=journal['binding']['freeze_sha256'], original_code_source_pins=pins,
                  observed_paired_mean_difference=mean_difference, equivalence_calls=calls,
                  equivalence='raw result vs existing golden revalidated; original tolerances unchanged',
                  interpretation='calibration audit only; no new simulation results')
    return result, registry


def make_plan(audit_value):
    config = configuration()
    return dict(protocol=VERSION, schema_version=1, status='SIMULATION_PLAN_INCOMPLETE',
                research_question='A24의 session-level joint empirical distribution에서 앱 수준 상태 기반 CPU/GPU 배정이 CPU-only 및 정적 정책 대비 긴급 응답과 deadline 준수를 개선하면서 일반 완료율·makespan·throughput·메모리·열 손실을 사전 허용 범위에 유지할 수 있는가?',
                input_sha256=INPUT_SHA, configuration=config, configuration_sha256=sha(config),
                policies_sha256=sha(config['policies']), input_audit_sha256=sha(audit_value),
                execution_authorized=False, actual_simulation_executed=False)


def validate_plan(plan, audit_value):
    jsonschema.validate(plan, read(SCHEMA))
    if plan != make_plan(audit_value):
        raise ValueError('plan/schema/seed/policy/unresolved mutation')
    return True


def no_op(plan):
    return dict(status=plan['status'], validation='PASS', random_samples=0,
                dispatches=0, simulated_completions=0, result_files=0, device_commands=[],
                unresolved=[x['id'] for x in plan['configuration']['unresolved']])


def code_hashes():
    files = [p for p in (REPO/'tools').rglob('*') if p.is_file() and p.suffix in ('.py', '.json')
             and '__pycache__' not in p.parts]
    files += [REPO/'docs/SIMULATION_PROTOCOL.md', REPO/'docs/RELATED_WORK_GAP.md']
    return {p.relative_to(REPO).as_posix(): digest(p) for p in sorted(files)}


def generate(source, output):
    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('output may not overlap empirical source')
    if output.exists():
        raise ValueError('output replay/overwrite forbidden')
    a, registry = audit(source)
    plan = make_plan(a)
    validate_plan(plan, a)
    values = {'plan.json': plan, 'input_registry.json': registry, 'input_audit.json': a, 'no_op.json': no_op(plan)}
    output.mkdir(parents=True, exist_ok=False)
    for name, value in values.items():
        (output/name).write_bytes(canonical(value))
    freeze = dict(protocol=VERSION, source_root=str(source), files={n:digest(output/n) for n in sorted(PRODUCTS)}, code=code_hashes())
    (output/'freeze.json').write_bytes(canonical(freeze))
    return dict(freeze_sha256=digest(output/'freeze.json'), **no_op(plan))


def verify(output, expected):
    output = Path(output)
    if digest(output/'freeze.json') != expected:
        raise ValueError('freeze hash mismatch')
    f = read(output/'freeze.json')
    if set(f) != {'protocol', 'source_root', 'files', 'code'} or f['protocol'] != VERSION:
        raise ValueError('freeze schema')
    if set(f['files']) != PRODUCTS or {p.name for p in output.iterdir()} != PRODUCTS | {'freeze.json'}:
        raise ValueError('unexpected result/artifact/path')
    if f['code'] != code_hashes():
        raise ValueError('code/schema/protocol changed')
    for name, expected_file in f['files'].items():
        if digest(contained(output, name)) != expected_file:
            raise ValueError('product hash mismatch')
    a, registry = audit(Path(f['source_root']))
    if read(output/'input_audit.json') != a or read(output/'input_registry.json') != registry:
        raise ValueError('source/consumed registry mutation')
    plan = read(output/'plan.json')
    validate_plan(plan, a)
    if read(output/'no_op.json') != no_op(plan):
        raise ValueError('no-op mutation')
    return no_op(plan)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['generate', 'validate', 'dry-run'])
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    if args.command == 'generate':
        if args.source is None:
            parser.error('--source required')
        result = generate(args.source, args.output)
    else:
        if args.expected_sha256 is None:
            parser.error('--expected-sha256 required')
        result = verify(args.output, args.expected_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
