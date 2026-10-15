"""One bounded, matched restart-state cohort; never repair old confirmation IDs."""
from pathlib import Path
from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import ARMS, contained_file, load_json, sha256
from d1_a24_revision02_suite import RULES, bound_document, require

PLAN_ID='A24-THERMAL-REBASELINE6-20261016'
ROLE='POST_OBSERVATION_MATCHED_REPLICATION_NOT_INDEPENDENT_CONFIRM'
KEYS=['L64_BASE','L64_PAIR_G','M128_BASE','M128_ORDER','M128_PAIR_G','M128_WAIT200']


def validate_plan(plan):
    require(plan.get('schema')=='a24-matched-rebaseline6-v1' and plan.get('plan_id')==PLAN_ID
        and plan.get('analysis_role')==ROLE,'wrong matched cohort')
    rows=plan.get('sessions',[])
    require(len(rows)==plan.get('session_count')==6 and plan.get('reference_rules')==RULES
        and plan.get('pooled_with_original_confirm') is False and plan.get('old_failures_preserved') is True,
        'exact six new attempts and unchanged MAIN rules required')
    for i,(row,key) in enumerate(zip(rows,KEYS)):
        group=key.split('_')[0];first=0 if i<2 else 2
        require(row.get('plan_id')==PLAN_ID and row.get('session_id')==identity(PLAN_ID,key)
            and row.get('prescription_id')==key and row.get('plan_ordinal')==i and row.get('stage')=='DEV'
            and tuple(row.get(k) for k in ['recipe','order','route','concurrency','wait_ms'])==ARMS[key],
            'identity/order/prescription changed')
        require(row.get('request_count')==(64 if group=='L64' else 128)
            and row.get('resident_mode')=='STANDARD' and row.get('perfetto')=='OFF','runtime/count changed')
        require(row.get('block')=='NEW_'+group and row.get('gate_block_id')==PLAN_ID+'-'+group
            and row.get('reference_owner_session_id')==identity(PLAN_ID,KEYS[first])
            and row.get('reference_role')==('SELECT_FIRST' if i==first else 'MATCH_FIXED'),
            'all members must share the first pre-MAIN stable reference')
    for group in ['L64','M128']:
        rs=[r for r in rows if r['recipe']==group]
        require(len({(r['bank_file'],r['bank_sha256'],r['input_seed']) for r in rs})==1,'paired input differs')
    return rows


def validate_registration(manifest,config,authorization,gate):
    plan=bound_document(config,authorization,'suite_plan_file','suite_plan_sha256');rows=validate_plan(plan)
    require(plan.get('status')=='FROZEN_EXECUTION_PLAN' and plan.get('execution_authorized') is True,'unfrozen cohort')
    row=next((r for r in rows if r['session_id']==manifest.get('session_id')),None)
    require(row is not None and all(manifest.get(k)==v for k,v in row.items())
        and manifest.get('plan_sha256')==config['suite_plan_sha256'],'manifest not exact registered row')
    registry=Path(config['registry_root'])
    require(registry.name==PLAN_ID and registry.parent.name=='a24-laptop-measurement-v1'
        and not registry.is_symlink(),'foreign registry')
    bank=contained_file(Path(config['suite_plan_file']).parent,row['bank_file'])
    require(sha256(bank)==row['bank_sha256'] and load_json(bank)['requests']==manifest['requests'],'bank changed')
    contract=bound_document(config,authorization,'revision_contract_file','revision_contract_sha256')
    require(contract.get('status')=='FROZEN_EXECUTION_CONTRACT' and contract.get('plan_sha256')==manifest['plan_sha256']
        and contract.get('reference_rules')==RULES and contract.get('energy_J') is None
        and contract.get('surface_temperature_verified') is False and contract.get('original_core179_unchanged') is True
        and contract.get('controller_lifecycle_AST_identical') is True,'contract changed')
    budget=bound_document(config,authorization,'budget_file','budget_sha256')
    require(budget.get('authorized') is True and budget.get('previous97_preserved') is True
        and budget.get('additional_cap')==budget.get('reserved_for_plan')==6
        and budget.get('combined_accounting_ceiling')==103
        and budget.get('plan_sha256')==manifest['plan_sha256'],'bounded extra6 budget missing')
    for key,cfg in [('source_sha256','source_code_sha256'),('controller_sha256','control_source_sha256'),
                    ('budget_sha256','budget_sha256'),('window_sha256','window_sha256'),('analysis_sha256','analysis_contract_sha256')]:
        require(contract.get(key)==(authorization if cfg=='control_source_sha256' else config)[cfg],'frozen binding changed')
    window=bound_document(config,authorization,'window_file','window_sha256')
    require(window.get('execution_authorized') is True and window.get('plan_sha256')==manifest['plan_sha256']
        and window.get('registered_session_ids')==[r['session_id'] for r in rows],'wrong window')
    from d1_a24_revision02_window import check_deadline
    check_deadline(window,'NEW_SESSION')
    analysis=bound_document(config,authorization,'analysis_contract','analysis_contract_sha256')
    require(analysis.get('frozen') is True and analysis.get('analysis_role')==ROLE
        and analysis.get('pooled_with_original_confirm') is False,'analysis role changed')
    require(gate.get('block_id')==row['gate_block_id'] and gate.get('reference_role')==row['reference_role'],'wrong gate')
    reference=Path(gate['block_reference_path'])
    require(reference.resolve()==(Path(config['output_root']).parent/'references'/(row['gate_block_id']+'.json')).resolve()
        and not reference.is_symlink(),'foreign reference')
    if row['reference_role']=='MATCH_FIXED':
        ref=load_json(reference)
        require(ref.get('reference_session_id')==row['reference_owner_session_id']
            and ref.get('frozen_before_any_main_request') is True,'reference not frozen before MAIN')
    return row
