"""Recover the saved terminal index only, after tuple/list serialization mismatch."""
import ast,collections,json
import study as S
H,R,O=S.H,S.R,S.O
op=S.read(H/'OPERATION.json');S.verify(op['source_pins'])
assert (O/'BATCH_FAILURE.json').exists() and not (O/'RESULT.json').exists()
failure=S.read(O/'BATCH_FAILURE.json');assert 'assert read(O/\'MODEL.json\')==model' in failure['traceback']
receipts=[json.loads(x) for x in (O/'receipts.jsonl').read_text().splitlines()]
starts=[x for x in receipts if x['event']=='START'];ends=[x for x in receipts if x['event']=='COMPLETE']
assert len(starts)==len(ends)==15 and {x['start_id'] for x in starts}=={x['start_id'] for x in ends}
assert collections.Counter(x['kind'] for x in starts)=={'TRAIN':6,'BC_FIT':1,'EVAL':8}
assert all(x['event'] in ('START','COMPLETE') for x in receipts)
rows=[S.read(O/(x['label']+'.json')) for x in starts if x['kind']!='BC_FIT']
assert len(rows)==14 and all(x['status']=='COMPLETE' for x in rows)
for row in rows:
    S.verify([row['raw']])
    if 'frames' in row:S.verify([row['frames']])
modelpin=next(x['model'] for x in ends if x['kind']=='BC_FIT');S.verify([modelpin])
model=S.read(O/'MODEL.json')
tree=ast.parse((H/'policy.py').read_text(encoding='utf8'));features=ast.literal_eval(next(x.value for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FEATURE_NAMES' for t in x.targets)))
assert isinstance(features,tuple) and isinstance(model['feature_names'],list) and list(features)==model['feature_names']
roundtrip=json.loads(json.dumps(dict(model,feature_names=features)));assert roundtrip==model
S.new(O/'SAVED_FINALIZATION_RECOVERY.json',dict(status='SAVED_INDEX_RECOVERED_PENDING_INDEPENDENT_AUDIT',failure_preserved=S.pin(O/'BATCH_FAILURE.json'),
    reason='In-memory FEATURE_NAMES tuple serializes to JSON list; final dict equality was type-sensitive. Every per-episode deepcopy equality and frozen model SHA check completed before the assertion.',
    model_from_fit_receipt_unchanged=True,tuple_list_roundtrip_identical=True,producer_source_edited=False,new_environment=0,new_fit=0,scientific_retry=0))
S.new(O/'RESULT.json',dict(status='BATCH_TERMINAL_WITH_SAVED_FINALIZATION_RECOVERY',rows=rows,model=modelpin,science_START=15,new_TRAIN=6,new_fit=1,new_EVAL=8,
    elapsed_s=sum(x['elapsed_s'] for x in rows),elapsed_scope='Sum of saved environment wall times; excludes fit/final checks',new_PPO=0,new_measurement=0,new_physical_fit=0,old_results_rerun=0,adopted=False,finalization_failure_preserved=True))
print('SAVED_FINALIZATION_RECOVERY',len(rows),'environments, 1 fit, 0 retries',flush=True)
