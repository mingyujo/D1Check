"""Independently validate final tables/gates, preserve prior evidence, and seal."""
import json,gzip,csv,math,re,hashlib,subprocess,datetime
from pathlib import Path
V=Path(__file__).resolve().parent;R=V.parents[2];A=R/'a24_simulator';H=A/'experiments/a24_s26_matched_bc_20261022';O=A/'results/A24_S26_MATCHED_BC_20261022_01'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
checks=0;maxerr=0
def ok(x,m):
    global checks
    checks+=1
    if not x:raise AssertionError(m)
def near(a,b):
    global maxerr
    maxerr=max(maxerr,abs(a-b));ok(math.isfinite(a) and math.isfinite(b) and abs(a-b)<2e-7,('numeric',a,b))
def mean(v):v=list(v);return math.fsum(v)/len(v)
def p95(v):v=sorted(v);return v[math.ceil(.95*len(v))-1]
reg=read(H/'OPERATION.json');result=read(O/'RESULT.json');summary=read(O/'SUMMARY.json');rows=result['rows'];evals=[r for r in rows if r['kind']=='EVAL'];policies=['FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_OLD','BC_OLD','TEACHER_MATCH','TEACHER_GUARD','BC_GUARD_FROZEN','BC_MATCHED']
for p in reg['source_pins']:ok(sha(R/p['path'])==p['sha256'],'Frozen source '+p['path'])
ok(result['counts']=={'START':105,'COMPLETE':105,'FAIL':0},'Finite105');ok(len(rows)==102 and len(evals)==72,'Environment census');ok(result['new_NN_fits']==2 and result['new_residual_calibration']==1 and result['new_environments']==102,'Scientific count classification');ok(result['new_physical_fit']==result['new_measurements']==result['new_PPO']==result['old_completed_rerun']==0,'No unauthorized science')
events=[json.loads(l) for l in (O/'receipts.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='COMPLETE'];ok(len(events)==210 and len(starts)==len(ends)==105,'Receipts');ok(len({r['start_id'] for r in starts})==105,'Unique identities');ok(all(sum(e['start_id']==r['start_id'] for e in ends)==1 for r in starts),'One terminal each')
freeze=read(O/'FREEZE.json');ok(freeze['fit_stage']==2 and freeze['no_EVAL_selection'] and freeze['unix']<min(r['unix'] for r in starts if r['kind']=='EVAL'),'Stage2 freeze before any EVAL')
for f in result['fits']:
    for k in ['checkpoint','dataset','trace']:ok(sha(R/f[k]['path'])==f[k]['sha256'],'Saved fit '+k)
    ok(f['epochs']==128 and not f['EVAL_used_for_selection'] and f['critic_unchanged'],'Fixed fit')
with (O/'ALL_EPISODES.csv').open(encoding='utf-8-sig',newline='') as f:csvrows=list(csv.DictReader(f))
ok(len(csvrows)==102,'102 CSV rows');cm={r['label']:r for r in csvrows};ok(len(cm)==102,'CSV labels unique')
for r in rows:
    c=cm[r['label']];ok(c['kind']==r['kind'] and c['policy']==r['policy'],'CSV source identity');near(float(c['J']),r['metrics']['J']);near(float(c['AP']),r['metrics']['AP'])
    for g in ['ALL','U','N']:
        for k in ['n','on','missing','incomplete']:ok(int(c[g+'_'+k])==r['metrics']['service'][g][k],'CSV service')
        near(float(c[g+'_P95']),r['metrics']['service'][g]['P95'])
# Independent source-of-truth aggregation: raw requests, closed-window trace integrals.
ind=[]
for row in evals:
    ok(sha(R/row['raw']['path'])==row['raw']['sha256'],'EVAL raw hash');raw=read(R/row['raw']['path']);r=raw['result'];case=raw['case'];end=case['observation_end_s'];v={'cohort':row['condition']['cohort'],'mix':row['condition']['mix'],'policy':row['policy'],'J':r['config']['baseline']*end+math.fsum(t['increment'] for t in r['trace']),'AP':math.fsum(t['temperature_area'] for t in r['trace'])/(end-35),'service':{}};near(v['J'],row['metrics']['J']);near(v['AP'],row['metrics']['AP'])
    for g in ['ALL','U','N']:
        qq=[q for q in r['requests'] if g=='ALL' or q['priority']==g];ans=[q for q in qq if q['response_ns'] is not None and q['response_ns']<=round(end*1e9)];lat=[(q['response_ns']-q['scheduled_arrival_ns'])/1e9 for q in ans];v['service'][g]={'n':len(qq),'on':sum(q['response_ns']<=q['deadline_ns'] for q in ans),'missing':len(qq)-len(ans),'incomplete':sum(q['available_ns'] is None or q['available_ns']>round(end*1e9) for q in qq),'P95':p95(lat),'lat':lat}
    ind.append(v)
for c in summary['cohorts']:
    for a in c['overall']:
        rr=[r for r in ind if r['cohort']==c['cohort'] and r['policy']==a['policy']];ok(len(rr)==a['inputs'],'Input count');near(a['J'],mean(r['J'] for r in rr));near(a['AP'],mean(r['AP'] for r in rr))
        for g in ['ALL','U','N']:
            for k in ['n','on','missing','incomplete']:ok(a[g+'_'+k]==sum(r['service'][g][k] for r in rr),'Aggregate count')
            near(a[g+'_on_pct'],100*sum(r['service'][g]['on'] for r in rr)/sum(r['service'][g]['n'] for r in rr));near(a[g+'_P95'],mean(r['service'][g]['P95'] for r in rr));near(a[g+'_P95_pooled'],p95([t for r in rr for t in r['service'][g]['lat']]))
    b=c['overall'][-1];joint=True;mixok=True;quality=True
    for comp,a in zip(c['comparisons'],c['overall'][:-1]):
        ok(comp['reference']==a['policy'],'Reference order');near(comp['ALL_gain_pp'],b['ALL_on_pct']-a['ALL_on_pct']);near(comp['energy_saving_pct'],100*(a['J']-b['J'])/a['J']);near(comp['AP_reduction_C'],a['AP']-b['AP']);near(comp['U_P95_increase_s'],b['U_P95']-a['U_P95']);near(comp['N_P95_increase_s'],b['N_P95']-a['N_P95'])
        if a['policy'] in policies[:3]:joint=joint and comp['ALL_gain_pp']>1e-9 and comp['energy_saving_pct']>1e-9 and comp['AP_reduction_C']>1e-9
    for m in c['mixes']:
        for a in m['policies']:
            rr=[r for r in ind if r['cohort']==c['cohort'] and r['mix']==m['mix'] and r['policy']==a['policy']];near(a['J'],mean(r['J'] for r in rr));near(a['AP'],mean(r['AP'] for r in rr))
            for g in ['ALL','U','N']:near(a[g+'_on_pct'],100*sum(r['service'][g]['on'] for r in rr)/sum(r['service'][g]['n'] for r in rr))
        bb=m['policies'][-1];quality=quality and bb['ALL_on_pct']>=95 and bb['U_on_pct']>=99 and bb['ALL_missing']==bb['ALL_incomplete']==0
        for a in m['policies'][:3]:mixok=mixok and bb['ALL_on_pct']>=a['ALL_on_pct'] and bb['J']<a['J'] and bb['AP']<a['AP']
    ok(joint==c['joint_vs_baselines'] and mixok==c['mixed_nonworse_joint'] and quality==c['quality_gate'],'All gates independently recomputed');ok((joint and mixok and quality)==c['all_gates'],'No gate relaxed')
    for ab in c['ablations']:
        aa=next(a for a in c['overall'] if a['policy']==ab['policy']);ref=next(a for a in c['overall'] if a['policy']==ab['reference']);near(ab['ALL_gain_pp'],aa['ALL_on_pct']-ref['ALL_on_pct']);near(ab['energy_saving_pct'],100*(ref['J']-aa['J'])/ref['J']);near(ab['AP_reduction_C'],ref['AP']-aa['AP'])
for name,count in [('EVAL_POLICY_TABLE.csv',27),('EVAL_COMPARISONS.csv',24),('PER_INPUT_COMPARISONS.csv',64),('WINDOWS.csv',64)]:
    with (O/name).open(encoding='utf-8-sig',newline='') as f:rr=list(csv.DictReader(f))
    ok(len(rr)==count,'Output rows '+name)
for name in ['AUDIT_JS','AUDIT_PYTHON','FIXED_STATE_COMPARISON','TIME_SERIES_CHECK','REPORT_BUILD']:ok(read(O/(name+'.json'))['status']=='PASS',name)
primary=summary['cohorts'][0];new=primary['overall'][-1];old=next(a for a in primary['overall'] if a['policy']=='BC_OLD');teacher=next(a for a in primary['overall'] if a['policy']=='TEACHER_MATCH');ok(new['ALL_on']==old['ALL_on']==2047 and teacher['ALL_on']==2048,'Observed primary outcomes');ok(new['J']>old['J'] and new['AP']>old['AP'],'No false old-policy improvement');ok(not read(O/'INFERENCE_CONTRACT.json')['adopted'] and not read(O/'TEACHER_MATCH_CONTRACT.json')['uses_retrained_NN'],'No teacher-as-BC substitution/adoption')
ok(any(read(p)['owned_lock_returned'] for p in V.glob('LOCK_RELEASED_*.json')),'Worker actually returned lock')
controls=[R/'docs/PROJECT_STATUS.md',R/'docs/PROJECT_PLAN.md',R/'docs/DECISIONS.md',A/'docs/LATEST_EXECUTION_FILES.md'];cmap={p.relative_to(R).as_posix():i for i,p in enumerate(controls)};preservation=[]
for name,snapshots in [('A24_S26_SCALE_20261022_01',A/'reviews/A24_S26_JOINT_20261022_01'),('A24_S26_JOINT_20261022_01',A/'reviews/A24_S26_SENSITIVITY_20261022_01'),('A24_S26_SENSITIVITY_20261022_01',V)]:
    previous=read(A/'results'/name/'FINAL_PROOF.json');immutable=archived=0
    for pin in previous['files']:
        if pin['path'] in cmap:p=snapshots/f"CONTROL_BEFORE_{cmap[pin['path']]}.bin";archived+=1
        else:p=R/pin['path'];immutable+=1
        ok(sha(p)==pin['sha256'],'Prior evidence preserved '+pin['path'])
    preservation.append({'prior':name,'immutable_files_unchanged':immutable,'sealed_control_versions_preserved':archived})
save(V/'VISUAL_REVIEW.json',{'status':'PASS','reviewed':['PRIMARY_COMPARISON.png','PRIMARY_AP_TIME.png','PRIMARY_ENERGY_TIME.png'],'notes':'Nine policies have readable labels and zero-origin bars. All four PRIMARY inputs are shown in time plots; complete nine-policy series retained in CSV.','date':'2026-10-22'})
record=[]
for i,p in enumerate(controls):
    before=p.read_bytes();backup=V/f'CONTROL_COMPLETION_BEFORE_{i}.bin'
    with backup.open('xb') as f:f.write(before)
    href='../results/A24_S26_MATCHED_BC_20261022_01/REPORT_KO.md' if i==3 else '../a24_simulator/results/A24_S26_MATCHED_BC_20261022_01/REPORT_KO.md'
    block=f'''## 2026-10-22 A24-S26-MATCH-04 · 교사·BC 정렬 학습/분리평가 완료

[정본]({href}). 현재S26조건 TRAIN10개로여유재추정·긴급latest-start WAITguard/원BC50신경망2×128epoch학습을완료하고 새EVAL8입력×9정책을비교했다. 105START/105COMPLETE/FAIL0(환경102+여유1+BCfit2)·새실측/물리fit/PPO/기존완료재시작0이다. 이전규약/기준선/물리/체크포인트는보존했다.

주 N512·묶음8·명목25%·새draw201/202의2048건에서 기존/재학습BC 모두2047정시(99.9512%)·긴급1279/1280(99.9219%)다. 재학습판은기존BC비소비0.051865%·AP0.007178℃증가, 긴급/일반P95는0.011447/0.045034초단축해상충이다. EDF비전체+2.734375%p·소비1.087448%/AP0.238903℃감소지만 기존BC종합개선판으로자동채택하지않는다. 안전여유만맞춘교사는2048/2048정시·BC재학습성과가아니다.

동일한4437공개상태에서구NN→재학습NN 모방오류22→17회지만서비스추가이득없다. 고부하새BC전체66.7969%로구BC68.2617%보다악화했다. 새guard가모든조건개선하지않았으며혼합/고부하/NN오차비용·모든손해/표본공유한계를공개했다. 현재자료로학습부족만을주원인으로확정하지않으며기존기본은유지한다.

JS13,716,658/Python119,585검사·NN27,767선택/고정상태7072검사 PASS·공유잠금반환. 이전3봉인불변592파일/제어12버전보존, 최종검산/해시는결과폴더FINAL_PROOF.json,HEAD ac3a5af+미커밋이다. 자동추가/채택/게시0. 다음: 정본/상충검토 또는사용자후속요청. 아래는등록/이전이력이다.

''';p.write_bytes(block.encode()+before);ok(p.read_bytes().endswith(before),'Prior control full bytes retained');ok(p.read_bytes().endswith((V/f'CONTROL_BEFORE_{i}.bin').read_bytes()),'Prestudy control snapshot retained');record.append({'path':p.relative_to(R).as_posix(),'old_sha256':hashlib.sha256(before).hexdigest(),'new_sha256':sha(p)})
save(V/'CONTROL_COMPLETION.json',{'status':'PASS','files':record})
ok(subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==reg['HEAD'],'HEAD unchanged');ok(subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip()=='codex/a24-simulator-handoff-20261016','Branch unchanged')
proof=O/'FINAL_PROOF.json';links=[]
for p in [O/'REPORT_KO.md',O/'CONTINUE_RUNNING.md']:
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if not target.startswith(('http:','https:','#')):links.append((p.parent/target).resolve())
for p in links:ok(p.exists() or p==proof,'Local target '+str(p))
save(O/'FINAL_CHECK.json',{'status':'PASS','checks':checks,'max_abs_aggregate_error':maxerr,'raw_EVAL_to_tables_P95_gates_ablations_verified':True,'old_BC_energy_temperature_regression_disclosed':True,'prior_evidence':preservation,'source_pins_unchanged':len(reg['source_pins']),'script_sha256':sha(Path(__file__))})
files=[p for base in [H,O,V] for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+controls;pins=[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(files)) if p!=proof]
save(proof,{'status':'PASS','id':'A24-S26-MATCH-04','recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'HEAD':reg['HEAD'],'dirty':True,'scientific_START':105,'COMPLETE':105,'FAIL':0,'new_environments':102,'new_residual_calibration':1,'new_NN_fits':2,'new_measurements':0,'new_physical_fit':0,'new_PPO':0,'old_completed_rerun':0,'model_chosen_before_EVAL':True,'default_adopted':False,'primary_newBC_not_joint_improvement_vs_oldBC':True,'teacher_match_100_is_not_retrained_BC':True,'source_operation_sha256':sha(H/'OPERATION.json'),'prior_evidence_preserved':preservation,'local_links':len(links),'files':pins,'excludes_own_bytes':True})
for p in links:ok(p.exists(),'Actual link after proof')
for p in pins:ok(sha(R/p['path'])==p['sha256'],'Final seal')
print(json.dumps({'state':'FINAL_PASS','checks':checks,'sealed_files':len(pins),'max_abs_aggregate_error':maxerr,'prior_evidence':preservation,'PRIMARY_newBC_vs_oldBC':next(c for c in primary['comparisons'] if c['reference']=='BC_OLD')},ensure_ascii=False))
