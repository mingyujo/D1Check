"""Exactly five post-observation diagnostic retries; historical failures remain."""
from pathlib import Path
from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import ARMS,contained_file,load_json,sha256
from d1_a24_revision02_suite import RULES,bound_document,require

PLAN_ID='A24-FAILED5-FOLLOWON-20261016'
ROLE='POST_OBSERVATION_FAILED_CASE_REPLICATION_NOT_INDEPENDENT_CONFIRM'
CASES=[
 ('C9_ORDER','edcaf9b7-01af-537b-a250-2fcafed6febf','M128_ORDER','A24R02C9'),
 ('C10_BASE','96782841-6ed6-5dac-a554-f94eaf5279cf','L64_BASE','A24R02C10'),
 ('R2_PAIR','cd025816-8525-543c-80a9-2541cf38f3fb','M128_PAIR_G','A24R02R2'),
 ('R3_ORDER','1622a87a-9331-51da-8806-c48c830de17c','M128_ORDER','A24R02R3'),
 ('SUP_ON','cdab3ce2-79b8-5704-8e79-298a8c322f4b','I_C32_ON','A24SUP12'),
]

def validate_plan(plan):
 rows=plan.get('sessions',[])
 require(plan.get('schema')=='a24-failed5-followon-v1' and plan.get('plan_id')==PLAN_ID
  and plan.get('analysis_role')==ROLE and len(rows)==plan.get('session_count')==5,'exact five failed cases required')
 require(plan.get('reference_rules')==RULES and plan.get('historical_failures_preserved') is True
  and plan.get('pooled_with_original_confirm') is False and plan.get('maximum_new_attempts_per_failed_ID')==1,'interpretation changed')
 for i,(name,old,key,_) in enumerate(CASES):
  r=rows[i];sid=identity(PLAN_ID,old)
  require(r.get('session_id')==sid and r.get('original_failed_session_id')==old and r.get('case_name')==name
   and r.get('plan_id')==PLAN_ID and r.get('plan_ordinal')==i and r.get('stage')=='DEV','identity/order changed')
  require(r.get('prescription_id')==key and tuple(r.get(k) for k in ['recipe','order','route','concurrency','wait_ms'])==ARMS[key]
   and r.get('request_count')==(64 if i==1 else 32 if i==4 else 128),'failed prescription changed')
  require(r.get('resident_mode')=='STANDARD' and r.get('perfetto')==('ON' if i==4 else 'OFF')
   and r.get('reference_role')=='SELECT_FIRST' and r.get('reference_owner_session_id')==sid
   and r.get('gate_block_id')==PLAN_ID+'-'+name,'runtime/reference changed')
 return rows

def validate_registration(manifest,config,authorization,gate):
 plan=bound_document(config,authorization,'suite_plan_file','suite_plan_sha256');rows=validate_plan(plan)
 require(plan.get('status')=='FROZEN_EXECUTION_PLAN' and plan.get('execution_authorized') is True,'plan not frozen')
 row=next((r for r in rows if r['session_id']==manifest.get('session_id')),None)
 require(row is not None and all(manifest.get(k)==v for k,v in row.items()) and manifest.get('plan_sha256')==config['suite_plan_sha256'],'foreign manifest')
 registry=Path(config['registry_root'])
 require(registry.name==PLAN_ID and registry.parent.name=='a24-laptop-measurement-v1' and not registry.is_symlink(),'foreign registry')
 bank=contained_file(Path(config['suite_plan_file']).parent,row['bank_file'])
 require(sha256(bank)==row['bank_sha256'] and load_json(bank)['requests']==manifest['requests'],'bank changed')
 c=bound_document(config,authorization,'revision_contract_file','revision_contract_sha256')
 require(c.get('status')=='FROZEN_EXECUTION_CONTRACT' and c.get('plan_sha256')==manifest['plan_sha256']
  and c.get('reference_rules')==RULES and c.get('energy_J') is None and c.get('surface_temperature_verified') is False
  and c.get('original_core179_unchanged') is True and c.get('only_runtime_difference')=='Perfetto config directory: documented Android12+ path','runtime contract changed')
 budget=bound_document(config,authorization,'budget_file','budget_sha256')
 require(budget.get('authorized') is True and budget.get('previous105_preserved') is True
  and budget.get('additional_cap')==budget.get('reserved_for_plan')==5 and budget.get('combined_accounting_ceiling')==110
  and budget.get('plan_sha256')==manifest['plan_sha256'],'finite budget missing')
 for name,key in [('source_sha256','source_code_sha256'),('budget_sha256','budget_sha256'),('window_sha256','window_sha256'),('analysis_sha256','analysis_contract_sha256')]:
  require(c.get(name)==config[key],'frozen document changed')
 require(c.get('controller_sha256')==authorization['control_source_sha256'],'controller changed')
 window=bound_document(config,authorization,'window_file','window_sha256')
 require(window.get('execution_authorized') is True and window.get('plan_sha256')==manifest['plan_sha256']
  and window.get('registered_session_ids')==[r['session_id'] for r in rows],'window changed')
 from d1_a24_revision02_window import check_deadline
 check_deadline(window,'NEW_SESSION')
 a=bound_document(config,authorization,'analysis_contract','analysis_contract_sha256')
 require(a.get('frozen') is True and a.get('analysis_role')==ROLE and a.get('pooled_with_original_confirm') is False
  and a.get('energy_J') is None and a.get('ON_only_is_not_overhead_comparison') is True,'analysis changed')
 expected=Path(config['output_root']).parent/'references'/(row['gate_block_id']+'.json')
 require(Path(gate['block_reference_path']).resolve()==expected.resolve() and not expected.is_symlink()
  and gate.get('reference_role')=='SELECT_FIRST' and gate.get('block_id')==row['gate_block_id'],'foreign reference')
 return row
