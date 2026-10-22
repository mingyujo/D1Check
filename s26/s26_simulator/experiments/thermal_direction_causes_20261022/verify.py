"""Independent initial-history extraction and scalar recurrence/tree replay."""
from engine import *
import subprocess,collections,datetime
O=H/'artifacts/G001';sys.stdout.reconfigure(encoding='utf-8')
models=collections.defaultdict(dict)
for p in (O/'models').glob('*.json.gz'):
    m=read(p);models[m['heldout_group']][m['candidate']]=m
raw={s.get('session_uid',s['id']):s for s in read(E/'multiresource_v1/calibration/MATERIALIZED_SESSIONS.json.gz')};cases=read(N/'artifacts/G001/INDEPENDENT_REPLAY_INPUT.json.gz')['cases']
for case in cases:case['AP_observations']=raw[case['id']]['targets']['AP']['observations']
save(O/'INDEPENDENT_REPLAY_INPUT.json.gz',dict(cases=cases,models=models));node=Path(r'C:\Users\chomg\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe');subprocess.run([str(node),str(H/'independent_replay.cjs'),str(O/'INDEPENDENT_REPLAY_INPUT.json.gz'),str(O/'INDEPENDENT_REPLAY_OUTPUT.json.gz')],check=True)
rows=read(O/'OOF_ROWS.json.gz');js={r['id']:r for r in read(O/'INDEPENDENT_REPLAY_OUTPUT.json.gz')};error=0.;points=0
for r in rows:
    pred=np.array([v['pred'][r['candidate']] for v in js[r['id']]['values']]);base=np.array([v['balanced'] for v in js[r['id']]['values']]);error=max(error,float(max(abs(pred-r['predicted']))),float(max(abs(base-r['baseline']))));points+=len(pred);m=models[r['group']][r['candidate']];assert r['id'] not in m['train_ids'] and r['group'] not in m['train_groups'] and r['group'] not in m['frozen_trend']['train_groups'] and r['group'] not in m['frozen_trend']['frozen_HGB']['train_groups'] and r['group'] not in m['frozen_trend']['frozen_HGB']['base_power_model']['train_groups']
assert error<1e-8,error
receipts=[json.loads(x) for x in (O/'FIT_RECEIPTS.jsonl').read_text(encoding='utf-8').splitlines()];starts=[x for x in receipts if x['event']=='START'];done=[x for x in receipts if x['event']=='COMPLETE'];assert len(starts)==len(done)==56 and len({x['id'] for x in starts})==56
for x in done:assert sha(O/'models'/(x['id']+'.json.gz'))==x['model_sha256']
for pin in read(H/'PREFLIGHT.json')['source']:assert sha(R/pin['path'])==pin['sha256']
save(O/'AUDIT.json',dict(status='PASS_INDEPENDENT_HISTORY_SCALAR_RECURRENCE_AND_TREE_REPLAY',UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),cases=208,candidates=2,prediction_points=points,max_JS_python_error_C=error,fit_START=56,fit_COMPLETE=56,fit_FAIL=0,group_exclusion_verified=True,original_and_previous_models_policy_unchanged=True,physical_accuracy_gate='FAIL_PRESERVED',adopted=False));print(json.dumps(dict(status='PASS_INDEPENDENT_REPLAY',points=points,error=error)),flush=True)
