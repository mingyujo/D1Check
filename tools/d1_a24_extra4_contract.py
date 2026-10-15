"""Explicit four-arm rebaseline replication; never an extra CONFIRM block."""
from pathlib import Path

from d1_a24_laptop_plan import ARMS, identity
from d1_a24_laptop_validator import contained_file, load_json, sha256
from d1_a24_revision02_suite import RULES, ARM_KEYS, bound_document, require

SCHEMA = 'a24-user-approved-stable-reference-extra4-v1'
PLAN_ID = 'A24R02-EXTRA4-STABLE-20261016'
ORDER = ['WAIT200', 'BASE', 'PAIR_G', 'ORDER']
ROLE = 'POST_OBSERVATION_REBASELINE_REPLICATION_NOT_INDEPENDENT_CONFIRM40'


def validate_extra4_plan(plan):
    require(plan.get('schema') == SCHEMA and plan.get('plan_id') == PLAN_ID
            and plan.get('analysis_role') == ROLE, 'unrecognized extra4 revision')
    rows = plan.get('sessions', [])
    require(len(rows) == plan.get('session_count') == 4
            and [r.get('arm') for r in rows] == ORDER, 'exact four-arm scope required')
    require(plan.get('reference_rules') == RULES and plan.get('retry_or_replacement') == 0
            and plan.get('original_confirm40_preserved') is True
            and plan.get('pooled_with_original_confirm') is False, 'extra4 interpretation changed')
    ids = [identity(PLAN_ID, 'EXTRA4:'+arm) for arm in ORDER]
    owner = ids[0]
    for i, row in enumerate(rows):
        spec = next(s for s in ARMS if s[:2] == ('M128', ORDER[i]))
        require(row.get('session_id') == ids[i] and row.get('plan_id') == PLAN_ID
                and row.get('plan_ordinal') == i and row.get('stage') == 'DEV'
                and row.get('block') == 'REBASE_M128_01' and row.get('recipe') == 'M128',
                'extra4 identity/order changed')
        require(tuple(row.get(k) for k in ['order','route','concurrency','wait_ms']) == spec[2:]
                and row.get('prescription_id') == 'M128_'+ORDER[i]
                and row.get('request_count') == 128 and row.get('resident_mode') == 'STANDARD'
                and row.get('perfetto') == 'OFF', 'original prescription changed')
        require(row.get('reference_role') == ('SELECT_FIRST' if i == 0 else 'MATCH_FIXED')
                and row.get('reference_owner_session_id') == owner
                and row.get('gate_block_id') == PLAN_ID+'-REBASE_M128_01',
                'shared first stable reference changed')
    require(len({(r['bank_sha256'],r['bank_file'],r['input_seed']) for r in rows}) == 1,
            'extra4 paired input differs')
    require(rows[0]['bank_sha256'] == plan.get('original_M128_bank_sha256'),
            'original input SHA not retained')
    return rows


def validate_extra4_registration(manifest, config, authorization, gate):
    """Use the same byte-bound documents and runtime; validate the new4 contract."""
    plan = bound_document(config,authorization,'suite_plan_file','suite_plan_sha256')
    rows = validate_extra4_plan(plan)
    require(plan.get('status') == 'FROZEN_EXECUTION_PLAN' and plan.get('execution_authorized') is True,
            'extra4 not frozen/authorized')
    require(manifest.get('plan_sha256') == config['suite_plan_sha256'], 'extra4 plan SHA differs')
    row = next((r for r in rows if r['session_id'] == manifest.get('session_id')), None)
    require(row is not None and all(manifest.get(k) == v for k,v in row.items()),
            'manifest differs from exact extra4 arm')
    registry = Path(config.get('registry_root',''))
    require(registry.name == PLAN_ID and registry.parent.name == 'a24-laptop-measurement-v1'
            and not registry.is_symlink(), 'foreign extra4 registry')
    bank = contained_file(Path(config['suite_plan_file']).parent,row['bank_file'])
    require(sha256(bank) == row['bank_sha256']
            and load_json(bank)['requests'] == manifest.get('requests'), 'paired bank changed')
    contract = bound_document(config,authorization,'revision_contract_file','revision_contract_sha256')
    require(contract.get('status') == 'FROZEN_EXECUTION_CONTRACT'
            and contract.get('plan_sha256') == manifest['plan_sha256']
            and contract.get('reference_rules') == RULES
            and contract.get('energy_J') is None and contract.get('surface_temperature_verified') is False
            and contract.get('original_core179_unchanged') is True
            and contract.get('controller_lifecycle_AST_identical') is True, 'extra4 contract changed')
    budget = bound_document(config,authorization,'budget_file','budget_sha256')
    require(budget.get('authorized') is True and budget.get('project_cap') == 85
            and budget.get('original_plan_cap') == 81 and budget.get('additional_cap') == 4
            and budget.get('reserved_for_plan') == 4
            and budget.get('plan_sha256') == manifest['plan_sha256'], 'extra4 budget absent')
    require(budget['spent_before_plan'] + budget['reserved_original_pending'] + 4 == 85,
            'extra4 project budget arithmetic differs')
    require(contract.get('budget_sha256') == config['budget_sha256']
            and contract.get('window_sha256') == config['window_sha256']
            and contract.get('analysis_sha256') == config['analysis_contract_sha256'],
            'extra4 frozen document hash differs')
    require(gate.get('block_id') == row['gate_block_id']
            and gate.get('reference_role') == row['reference_role'], 'extra4 reference role differs')
    reference = Path(gate.get('block_reference_path',''))
    require(reference.resolve() == (Path(config['output_root']).parent/'references'/(row['gate_block_id']+'.json')).resolve()
            and not reference.is_symlink(), 'foreign extra4 reference')
    if row['reference_role'] == 'MATCH_FIXED':
        ref = load_json(reference)
        require(ref.get('block_id') == row['gate_block_id']
                and ref.get('reference_session_id') == row['reference_owner_session_id']
                and ref.get('frozen_before_any_main_request') is True, 'extra4 reference not frozen before MAIN')
    window = bound_document(config,authorization,'window_file','window_sha256')
    require(window.get('execution_authorized') is True
            and window.get('plan_sha256') == manifest['plan_sha256']
            and window.get('registered_session_ids') == [r['session_id'] for r in rows], 'extra4 window differs')
    from d1_a24_revision02_window import check_deadline
    check_deadline(window,'NEW_SESSION')
    analysis = bound_document(config,authorization,'analysis_contract','analysis_contract_sha256')
    require(analysis.get('frozen') is True and analysis.get('analysis_role') == ROLE
            and analysis.get('original_KPI_and_units_preserved') is True
            and analysis.get('pooled_with_original_confirm') is False, 'extra4 analysis meaning differs')
    evidence = bound_document(config,authorization,'new_protocol_functional_evidence','new_protocol_functional_evidence_sha256')
    require(evidence.get('status') == 'DEVICE_VALIDATED' and evidence.get('mock') is False
            and type(evidence.get('NN_calls')) is int and evidence['NN_calls'] > 0
            and set(evidence.get('supported_arms',[])) == ARM_KEYS
            and evidence.get('apk_sha256') == config['apk']['sha256']
            and evidence.get('source_sha256') == contract['original_core179_sha256']
            and evidence.get('device_fingerprint') == authorization.get('fingerprint'),
            'preserved runtime functional evidence differs')
    require(contract.get('controller_sha256') == authorization.get('control_source_sha256')
            and contract.get('source_sha256') == config['source_code_sha256'], 'extra4 host/source differs')
    return row
