"""One prospective replacement attempt per explicitly enumerated failed ID.

Historical failures remain immutable. These are post-observation development
replications, never replacements in either frozen independent-confirmation set.
"""
from pathlib import Path

from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import ARMS, contained_file, load_json, sha256
from d1_a24_revision02_suite import RULES, bound_document, require

PLAN_ID = 'A24-FAILED-SUPPLEMENT12-20261016'
ROLE = 'POST_OBSERVATION_FAILED_CASE_REPLICATION_NOT_INDEPENDENT_CONFIRM'
# Fixed snapshot, not an open-ended retry budget. F-GPU was recovered in its
# original execution; APP0 deferrals that later completed are also excluded.
CASES = [
    ('I_UNRESIDENT', '12086e3c-817f-520f-88b0-53340522ad79', 'IDLE_UNRESIDENT'),
    ('I_RESIDENT', '422172fe-f64c-57a4-a883-e9e4fd4efea0', 'IDLE_RESIDENT'),
    ('I_TRACE_OFF', '1e029f47-dfaf-53bb-9bb0-9bb44668521e', 'I_C32_OFF'),
    ('I_TRACE_ON', '3efaf233-a720-528b-805b-83ce814e5ac8', 'I_C32_ON'),
    ('F_CPU', 'ee85f47b-02cf-5e83-8def-38bfc34d512e', 'C252_CPU'),
    ('DEV_CPU', '7c7ffa1c-7934-5067-a126-27485fe9506e', 'C252_CPU'),
    ('OLD_CONFIRM_PAIR', '9ac438a5-acfc-5a3c-a709-860114cdc92a', 'L64_PAIR_G'),
    ('OLD_CONFIRM_STOP', '69326999-8ee2-5bd5-be0e-e5f84621344b', 'M128_ORDER'),
    ('W1_CPU', 'f7c0e261-bf56-54a5-850c-68ac2f20305f', 'C252_CPU'),
    ('W3_GPU', 'cba05f5d-d4c1-57de-b8ea-59a224aba469', 'C252_GPU'),
    ('C9_ORDER', 'edcaf9b7-01af-537b-a250-2fcafed6febf', 'M128_ORDER'),
    ('R2_PAIR', 'cd025816-8525-543c-80a9-2541cf38f3fb', 'M128_PAIR_G'),
]


def validate_plan(plan):
    require(plan.get('schema') == 'a24-failed-supplement-v1'
            and plan.get('plan_id') == PLAN_ID and plan.get('analysis_role') == ROLE,
            'not the explicitly enumerated failed-case supplement')
    rows = plan.get('sessions', [])
    require(len(rows) == plan.get('session_count') == len(CASES), 'exact12 scope required')
    require(plan.get('reference_rules') == RULES and plan.get('pooled_with_original_confirm') is False
            and plan.get('historical_failures_preserved') is True
            and plan.get('maximum_new_attempts_per_failed_ID') == 1, 'retry interpretation changed')
    for i, (name, old, key) in enumerate(CASES):
        row = rows[i]
        require(row.get('session_id') == identity(PLAN_ID, old)
                and row.get('original_failed_session_id') == old and row.get('case_name') == name
                and row.get('plan_id') == PLAN_ID and row.get('plan_ordinal') == i
                and row.get('stage') == 'DEV', 'old/duplicate/foreign supplement identity')
        require(row.get('prescription_id') == key
                and tuple(row.get(k) for k in ['recipe','order','route','concurrency','wait_ms']) == ARMS[key],
                'failed prescription changed')
        count = 0 if key.startswith('IDLE') else 32 if key.startswith('I_C32') else 252 if key.startswith('C252') else 64 if key.startswith('L64') else 128
        require(row.get('request_count') == count and row.get('resident_mode') == ('NONE' if i == 0 else 'STANDARD')
                and row.get('perfetto') == ('ON' if i == 3 else 'OFF'), 'instrumentation/runtime/count changed')
        owner = rows[2]['session_id'] if i == 3 else row['session_id']
        group = 'TRACE' if i in {2, 3} else name
        require(row.get('reference_role') == ('MATCH_FIXED' if i == 3 else 'SELECT_FIRST')
                and row.get('reference_owner_session_id') == owner
                and row.get('gate_block_id') == PLAN_ID+'-'+group, 'reference algorithm/group changed')
    require(rows[2]['bank_sha256'] == rows[3]['bank_sha256'], 'trace off/on inputs differ')
    return rows


def validate_registration(manifest, config, authorization, gate):
    plan = bound_document(config, authorization, 'suite_plan_file', 'suite_plan_sha256')
    rows = validate_plan(plan)
    require(plan.get('status') == 'FROZEN_EXECUTION_PLAN' and plan.get('execution_authorized') is True,
            'supplement plan not frozen/authorized')
    row = next((r for r in rows if r['session_id'] == manifest.get('session_id')), None)
    require(row is not None and all(manifest.get(k) == v for k, v in row.items())
            and manifest.get('plan_sha256') == config['suite_plan_sha256'], 'unregistered supplement manifest')
    registry = Path(config['registry_root'])
    require(registry.name == PLAN_ID and registry.parent.name == 'a24-laptop-measurement-v1'
            and not registry.is_symlink(), 'foreign supplement registry')
    bank = contained_file(Path(config['suite_plan_file']).parent, row['bank_file'])
    require(sha256(bank) == row['bank_sha256'] and load_json(bank)['requests'] == manifest['requests'], 'input bank changed')
    contract = bound_document(config, authorization, 'revision_contract_file', 'revision_contract_sha256')
    require(contract.get('status') == 'FROZEN_EXECUTION_CONTRACT' and contract.get('plan_sha256') == manifest['plan_sha256']
            and contract.get('reference_rules') == RULES and contract.get('energy_J') is None
            and contract.get('surface_temperature_verified') is False
            and contract.get('original_core179_unchanged') is True
            and contract.get('controller_lifecycle_AST_identical') is True, 'supplement contract changed')
    budget = bound_document(config, authorization, 'budget_file', 'budget_sha256')
    require(budget.get('authorized') is True and budget.get('original_reserved_cap') == 85
            and budget.get('supplement_cap') == budget.get('reserved_for_plan') == 12
            and budget.get('combined_accounting_ceiling') == 97
            and budget.get('plan_sha256') == manifest['plan_sha256'], 'explicit finite supplemental budget missing')
    require(contract.get('source_sha256') == config['source_code_sha256']
            and contract.get('controller_sha256') == authorization['control_source_sha256']
            and contract.get('budget_sha256') == config['budget_sha256']
            and contract.get('window_sha256') == config['window_sha256']
            and contract.get('analysis_sha256') == config['analysis_contract_sha256'], 'frozen binding differs')
    window = bound_document(config, authorization, 'window_file', 'window_sha256')
    require(window.get('execution_authorized') is True and window.get('plan_sha256') == manifest['plan_sha256']
            and window.get('registered_session_ids') == [r['session_id'] for r in rows], 'supplement window differs')
    analysis = bound_document(config, authorization, 'analysis_contract', 'analysis_contract_sha256')
    require(analysis.get('frozen') is True and analysis.get('analysis_role') == ROLE
            and analysis.get('pooled_with_original_confirm') is False and analysis.get('energy_J') is None,
            'supplement cannot replace confirmation or validate J')
    expected = Path(config['output_root']).parent/'references'/(row['gate_block_id']+'.json')
    require(Path(gate['block_reference_path']).resolve() == expected.resolve()
            and gate['reference_role'] == row['reference_role'] and gate['block_id'] == row['gate_block_id'], 'foreign reference')
    if row['reference_role'] == 'MATCH_FIXED':
        ref = load_json(expected)
        require(ref['reference_session_id'] == row['reference_owner_session_id']
                and ref['frozen_before_any_main_request'] is True, 'paired trace reference missing')
    return row
