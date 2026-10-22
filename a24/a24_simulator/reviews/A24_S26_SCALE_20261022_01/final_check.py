"""Independent saved-output accounting and final manifest; never starts science."""
import json,gzip,csv,math,hashlib,re,subprocess,datetime,collections
from pathlib import Path
V=Path(__file__).resolve().parent;R=V.parents[2];A=R/'a24_simulator';H=A/'experiments/a24_s26_scale_20261022';O=A/'results/A24_S26_SCALE_20261022_01'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=0;maxerr=0
def ok(v,m):
    global checks
    checks+=1
    if not v:raise AssertionError(m)
def near(x,y,tol=2e-7):
    global maxerr
    maxerr=max(maxerr,abs(x-y));ok(math.isfinite(x) and math.isfinite(y) and abs(x-y)<tol,('numeric',x,y))
def mean(v):v=list(v);return math.fsum(v)/len(v)
def pct95(v):v=sorted(v);return v[math.ceil(.95*len(v))-1]
reg=read(H/'OPERATION.json');result=read(O/'RESULT.json');s=read(O/'SUMMARY.json');sel=read(O/'DEV_SELECTION.json');rows=result['rows'];conf=[r for r in rows if r['condition']['role']=='CONF']
for p in reg['source_pins']:ok(sha(R/p['path'])==p['sha256'],'Frozen source '+p['path'])
ok(len(rows)==120 and len(conf)==20 and all(r['status']=='COMPLETE' for r in rows),'Finite census')
ok(result['counts']=={'START':120,'COMPLETE':120,'FAIL':0},'Receipt counts')
receipts=[json.loads(l) for l in (O/'receipts.jsonl').read_text().splitlines()];starts=[r for r in receipts if r['event']=='START'];ends=[r for r in receipts if r['event']=='COMPLETE']
ok(len(starts)==len(ends)==120 and len(receipts)==240,'No missing receipt')
ok(len({r['start_id'] for r in starts})==120,'No restart')
ok(all(sum(e['start_id']==r['start_id'] for e in ends)==1 for r in starts),'Exactly one terminal')
ok(sel['unix']<min(r['unix'] for r in starts if '_CONF_' in r['label']),'DEV selection before CONF')
ok(s['selection']==result['selected']==sel['selected']['setting'],'Selection same')
ok(all(r['condition']['setting']==s['selection']['id'] for r in conf),'No CONF reselect')
ok(result['new_TRAIN']==result['new_fit']==result['new_measurement']==result['old_results_rerun']==0,'No hidden training/fit')
with (O/'ALL_EPISODES.csv').open(encoding='utf-8-sig',newline='') as f:csvrows=list(csv.DictReader(f))
ok(len(csvrows)==120 and len({r['label'] for r in csvrows})==120,'CSV full120')
bylabel={r['label']:r for r in csvrows}
for r in rows:
    c=bylabel[r['label']];ok(c['policy']==r['policy'] and c['role']==r['condition']['role'],'CSV binding');near(float(c['J']),r['metrics']['J']);near(float(c['AP']),r['metrics']['AP'])
    for g in ['ALL','U','N']:
        for k in ['n','on','missing','incomplete']:ok(int(c[g+'_'+k])==r['metrics']['service'][g][k],'CSV count')
        near(float(c[g+'_P95']),r['metrics']['service'][g]['P95'])
# Recompute CONF metrics directly from requests/traces, then check aggregate/CSV/P95.
ind=[]
for r in conf:
    raw=read(R/r['raw']['path']);ok(sha(R/r['raw']['path'])==r['raw']['sha256'],'CONF raw sha');out=raw['result'];case=raw['case'];end=case['observation_end_s'];d={'policy':r['policy'],'mix':r['condition']['mix'],'J':out['config']['baseline']*end+math.fsum(t['increment'] for t in out['trace']),'AP':math.fsum(t['temperature_area'] for t in out['trace'])/(end-35),'groups':{}}
    near(d['J'],r['metrics']['J']);near(d['AP'],r['metrics']['AP'])
    for g in ['ALL','U','N']:
        qq=[q for q in out['requests'] if g=='ALL' or q['priority']==g];ans=[q for q in qq if q['response_ns'] is not None and q['response_ns']<=round(end*1e9)];lat=[(q['response_ns']-q['scheduled_arrival_ns'])/1e9 for q in ans]
        d['groups'][g]={'n':len(qq),'on':sum(q['response_ns']<=q['deadline_ns'] for q in ans),'lat':lat,'P95':pct95(lat),'missing':len(qq)-len(ans),'incomplete':sum(q['available_ns'] is None or q['available_ns']>round(end*1e9) for q in qq)}
        for k in ['n','on','missing','incomplete']:ok(d['groups'][g][k]==r['metrics']['service'][g][k],'Independent CONF count')
        near(d['groups'][g]['P95'],r['metrics']['service'][g]['P95'])
    ind.append(d)
for a in s['CONF']:
    rr=[d for d in ind if d['policy']==a['policy']];ok(len(rr)==4,'Four inputs per policy');near(a['J_mean'],mean(d['J'] for d in rr));near(a['AP_mean'],mean(d['AP'] for d in rr));near(a['J_sum'],math.fsum(d['J'] for d in rr))
    for g in ['ALL','U','N']:
        for k in ['n','on','missing','incomplete']:ok(a[g+'_'+k]==sum(d['groups'][g][k] for d in rr),'Aggregate service')
        near(a[g+'_P95_session_mean'],mean(d['groups'][g]['P95'] for d in rr));near(a[g+'_P95_pooled'],pct95([v for d in rr for v in d['groups'][g]['lat']]))
        near(a[g+'_on_pct'],100*sum(d['groups'][g]['on'] for d in rr)/sum(d['groups'][g]['n'] for d in rr))
    ok(a['ALL_n']==a['ALL_on']==2048 and a['U_n']==a['U_on']==1280 and a['N_n']==a['N_on']==768,'All methods100%')
for pm in s['CONF_per_mix']:
    for a in pm['policies']:
        rr=[d for d in ind if d['policy']==a['policy'] and d['mix']==pm['mix']];near(a['J_mean'],mean(d['J'] for d in rr));near(a['AP_mean'],mean(d['AP'] for d in rr))
        for g in ['ALL','U','N']:near(a[g+'_P95_session_mean'],mean(d['groups'][g]['P95'] for d in rr))
bc=s['CONF'][-1]
for c,ref in zip(s['CONF_comparisons'],s['CONF'][:-1]):
    ok(c['reference']==ref['policy'],'Comparison order');near(c['energy_saving_pct'],100*(ref['J_mean']-bc['J_mean'])/ref['J_mean']);near(c['AP_reduction_C'],ref['AP_mean']-bc['AP_mean']);near(c['J_reduction_per_input'],ref['J_mean']-bc['J_mean'])
    near(c['U_P95_increase_s'],bc['U_P95_session_mean']-ref['U_P95_session_mean']);near(c['N_P95_increase_s'],bc['N_P95_session_mean']-ref['N_P95_session_mean'])
for filename,expected in [('CONF_POLICY_TABLE.csv',5),('CONF_COMPARISONS.csv',4),('GRID_SUMMARY.csv',10),('PER_INPUT_COMPARISONS.csv',96),('WINDOW_SENSITIVITY.csv',96),('HARMS.csv',167)]:
    with (O/filename).open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
    ok(len(records)==expected,'Rows '+filename)
for name in ['AUDIT_JS','AUDIT_PYTHON','REPORT_BUILD','TIME_SERIES_CHECK']:ok(read(O/(name+'.json'))['status']=='PASS',name)
ok(read(V/'VISUAL_REVIEW.json')['status']=='PASS','Visual inspected4')
for i,p in enumerate([R/'docs/PROJECT_STATUS.md',R/'docs/PROJECT_PLAN.md',R/'docs/DECISIONS.md',A/'docs/LATEST_EXECUTION_FILES.md']):
    ok(p.read_bytes().endswith((V/f'CONTROL_COMPLETION_BEFORE_{i}.bin').read_bytes()),'Completion preserves entire previous control')
    ok(p.read_bytes().endswith((V/f'CONTROL_BEFORE_{i}.bin').read_bytes()),'Original control retained')
ok(any(read(p)['owned_lock_returned'] for p in V.glob('LOCK_RELEASED_*.json')),'Worker actually returned shared lock')
ok(subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==reg['HEAD'],'HEAD unchanged')
ok(subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip()=='codex/a24-simulator-handoff-20261016','Branch unchanged')
links=[]
for p in [O/'REPORT_KO.md',O/'CONTINUE_RUNNING.md']:
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if not target.startswith(('http:','https:','#')):links.append((p.parent/target).resolve())
proof=O/'FINAL_PROOF.json'
for p in links:ok(p.exists() or p==proof,'Report local target '+str(p))
def write(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,allow_nan=False,indent=2)
write(O/'FINAL_CHECK.json',{'status':'PASS','checks':checks,'max_abs_aggregate_error':maxerr,'all120_csv_counts_verified':True,'CONF20_raw_to_aggregate_verified':True,'P95_session_mean_and_pooled_verified':True,'frozen_source_pins_unchanged':len(reg['source_pins']),'old_control_bytes_preserved':True,'new_environments':0,'new_fits':0,'script_sha256':sha(Path(__file__))})
files=[p for base in [H,O,V] for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+[R/'docs/PROJECT_STATUS.md',R/'docs/PROJECT_PLAN.md',R/'docs/DECISIONS.md',A/'docs/LATEST_EXECUTION_FILES.md']
pins=[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(files)) if p!=proof]
write(proof,{'status':'PASS','id':'A24-S26-SCALE-01','recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'HEAD':reg['HEAD'],'dirty':True,'source_operation_sha256':sha(H/'OPERATION.json'),'scientific_START':120,'COMPLETE':120,'FAIL':0,'new_train_fit_measurement':0,'selected_setting':s['selection'],'DEV_selection_before_CONF':True,'CONF_all_policies_ontime_100':True,'not_global_optimum':True,'not_new_independent_device_holdout':True,'not_adopted_as_default':True,'audits':{k:read(O/(k+'.json'))['status'] for k in ['AUDIT_JS','AUDIT_PYTHON','TIME_SERIES_CHECK','REPORT_BUILD','FINAL_CHECK']},'local_links':len(links),'files':pins,'manifest_excludes_only_own_bytes':True,'report_erratum':read(V/'REPORT_ERRATA.json')})
for p in links:ok(p.exists(),'Final actual link exists')
for p in pins:ok(sha(R/p['path'])==p['sha256'],'Seal actual sha')
print(json.dumps({'state':'FINAL_PASS','aggregate_checks_before_seal':read(O/'FINAL_CHECK.json')['checks'],'total_checks_including_seal':checks,'sealed_files':len(pins),'report_links':len(links),'max_abs_aggregate_error':maxerr,'CONF_EDF_comparison':s['CONF_comparisons'][1]},ensure_ascii=False))
