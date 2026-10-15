"""Bounded fresh OFF/ON pair using the documented Perfetto config directory."""
from pathlib import Path
from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import ARMS,contained_file,load_json,sha256
from d1_a24_revision02_suite import RULES,bound_document,require

PLAN_ID='A24-PERFETTO-PATH-REPAIR2-20261016'
ROLE='POST_FAILURE_INSTRUMENTATION_MATCHED_PAIR_NOT_CONFIRM'
KEYS=['I_C32_OFF','I_C32_ON']


def validate_plan(plan):
    rows=plan.get('sessions',[])
    require(plan.get('schema')=='a24-trace-config-path-repair2-v1' and plan.get('plan_id')==PLAN_ID
        and plan.get('analysis_role')==ROLE and len(rows)==plan.get('session_count')==2,'exact new pair required')
    require(plan.get('reference_rules')==RULES and plan.get('old_failures_preserved') is True
        and plan.get('pooled_with_original_confirm') is False,'interpretation or MAIN rules changed')
    owner=identity(PLAN_ID,KEYS[0])
    for i,(r,key) in enumerate(zip(rows,KEYS)):
        require(r.get('session_id')==identity(PLAN_ID,key) and r.get('plan_id')==PLAN_ID
            and r.get('plan_ordinal')==i and r.get('stage')=='DEV' and r.get('prescription_id')==key
            and tuple(r.get(k) for k in ['recipe','order','route','concurrency','wait_ms'])==ARMS[key],'identity/prescription changed')
        require(r.get('request_count')==32 and r.get('resident_mode')=='STANDARD' and r.get('perfetto')==('OFF' if i==0 else 'ON')
            and r.get('block')=='TRACE_REPAIR' and r.get('reference_owner_session_id')==owner
            and r.get('gate_block_id')==PLAN_ID+'-TRACE'
            and r.get('reference_role')==('SELECT_FIRST' if i==0 else 'MATCH_FIXED'),'pair runtime/reference changed')
    require(len({(r['bank_file'],r['bank_sha256'],r['input_seed']) for r in rows})==1,'paired input differs')
    return rows


def validate_registration(manifest,config,authorization,gate):
    plan=bound_document(config,authorization,'suite_plan_file','suite_plan_sha256');rows=validate_plan(plan)
    require(plan.get('status')=='FROZEN_EXECUTION_PLAN' and plan.get('execution_authorized') is True,'pair not frozen')
    row=next((r for r in rows if r['session_id']==manifest.get('session_id')),None)
    require(row is not None and all(manifest.get(k)==v for k,v in row.items())
        and manifest.get('plan_sha256')==config['suite_plan_sha256'],'foreign pair manifest')
    registry=Path(config['registry_root'])
    require(registry.name==PLAN_ID and registry.parent.name=='a24-laptop-measurement-v1' and not registry.is_symlink(),'foreign registry')
    bank=contained_file(Path(config['suite_plan_file']).parent,row['bank_file'])
    require(sha256(bank)==row['bank_sha256'] and load_json(bank)['requests']==manifest['requests'],'bank changed')
    c=bound_document(config,authorization,'revision_contract_file','revision_contract_sha256')
    require(c.get('status')=='FROZEN_EXECUTION_CONTRACT' and c.get('plan_sha256')==manifest['plan_sha256']
        and c.get('reference_rules')==RULES and c.get('energy_J') is None and c.get('surface_temperature_verified') is False
        and c.get('original_core179_unchanged') is True and c.get('only_runtime_difference')=='Perfetto config directory: documented Android12+ path',
        'runtime/contract changed')
    budget=bound_document(config,authorization,'budget_file','budget_sha256')
    require(budget.get('authorized') is True and budget.get('previous103_preserved') is True
        and budget.get('additional_cap')==budget.get('reserved_for_plan')==2
        and budget.get('combined_accounting_ceiling')==105 and budget.get('plan_sha256')==manifest['plan_sha256'],'finite repair2 budget absent')
    for name,key in [('source_sha256','source_code_sha256'),('budget_sha256','budget_sha256'),('window_sha256','window_sha256'),('analysis_sha256','analysis_contract_sha256')]:
        require(c.get(name)==config[key],'frozen document changed')
    require(c.get('controller_sha256')==authorization['control_source_sha256'],'controller changed')
    window=bound_document(config,authorization,'window_file','window_sha256')
    require(window.get('execution_authorized') is True and window.get('plan_sha256')==manifest['plan_sha256']
        and window.get('registered_session_ids')==[r['session_id'] for r in rows],'window changed')
    from d1_a24_revision02_window import check_deadline
    check_deadline(window,'NEW_SESSION')
    analysis=bound_document(config,authorization,'analysis_contract','analysis_contract_sha256')
    require(analysis.get('frozen') is True and analysis.get('analysis_role')==ROLE
        and analysis.get('pooled_with_original_confirm') is False,'analysis interpretation changed')
    require(gate.get('reference_role')==row['reference_role'] and gate.get('block_id')==row['gate_block_id'],'wrong gate')
    reference=Path(gate['block_reference_path'])
    require(reference.resolve()==(Path(config['output_root']).parent/'references'/(row['gate_block_id']+'.json')).resolve()
        and not reference.is_symlink(),'foreign reference')
    if row['reference_role']=='MATCH_FIXED':
        ref=load_json(reference)
        require(ref.get('reference_session_id')==row['reference_owner_session_id'] and ref.get('frozen_before_any_main_request') is True,'reference not fixed before MAIN')
    return row
