"""Saved-only final validation, preserve prior controls/proof, then seal this run."""
import json,gzip,csv,math,hashlib,re,datetime,subprocess
from pathlib import Path
V=Path(__file__).resolve().parent;R=V.parents[2];A=R/'a24_simulator';H=A/'experiments/a24_s26_joint_20261022';O=A/'results/A24_S26_JOINT_20261022_01'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
checks=0;error=0
def ok(v,m):
    global checks
    checks+=1
    if not v:raise AssertionError(m)
def near(a,b):
    global error
    error=max(error,abs(a-b));ok(abs(a-b)<2e-7,('numeric',a,b))
def avg(v):v=list(v);return math.fsum(v)/len(v)
def p95(v):v=sorted(v);return v[math.ceil(.95*len(v))-1]
reg=read(H/'OPERATION.json');sel=read(H/'SELECTION.json');result=read(O/'RESULT.json');summary=read(O/'SUMMARY.json');rows=result['rows'];policies=['FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_RISK','BC_NEURAL_URGENT']
for p in reg['source_pins']:ok(sha(R/p['path'])==p['sha256'],'Frozen source '+p['path'])
ok(result['counts']=={'START':40,'COMPLETE':40,'FAIL':0} and len(rows)==40,'40 finite terminal')
ok(result['new_TRAIN']==result['new_fit']==result['new_measurement']==result['old_results_rerun']==0,'No new fit/measurement/restart')
events=[json.loads(l) for l in (O/'receipts.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='COMPLETE'];ok(len(events)==80 and len(starts)==len(ends)==40,'Receipt count');ok(len({r['start_id'] for r in starts})==40,'Unique identities');ok(all(sum(e['start_id']==r['start_id'] for e in ends)==1 for r in starts),'Exactly one terminal');ok(sel['unix']<min(r['unix'] for r in starts),'Selection before every CONF START')
with (O/'ALL_EPISODES.csv').open(encoding='utf-8-sig',newline='') as f:cc=list(csv.DictReader(f))
ok(len(cc)==len({r['label'] for r in cc})==40,'CSV all40');csvmap={r['label']:r for r in cc};ind=[]
for row in rows:
    ok(sha(R/row['raw']['path'])==row['raw']['sha256'],'Raw SHA');raw=read(R/row['raw']['path']);r=raw['result'];c=raw['case'];end=c['observation_end_s'];v={'setting':row['condition']['setting'],'mix':row['condition']['mix'],'policy':row['policy'],'J':r['config']['baseline']*end+math.fsum(s['increment'] for s in r['trace']),'AP':math.fsum(s['temperature_area'] for s in r['trace'])/(end-35),'svc':{}}
    near(v['J'],row['metrics']['J']);near(v['AP'],row['metrics']['AP']);near(v['J'],float(csvmap[row['label']]['J']));near(v['AP'],float(csvmap[row['label']]['AP']))
    for group in ['ALL','U','N']:
        qs=[q for q in r['requests'] if group=='ALL' or q['priority']==group];ans=[q for q in qs if q['response_ns'] is not None and q['response_ns']<=round(end*1e9)];lat=[(q['response_ns']-q['scheduled_arrival_ns'])/1e9 for q in ans];s={'n':len(qs),'on':sum(q['response_ns']<=q['deadline_ns'] for q in ans),'missing':len(qs)-len(ans),'incomplete':sum(q['available_ns'] is None or q['available_ns']>round(end*1e9) for q in qs),'P95':p95(lat),'lat':lat};v['svc'][group]=s
        for k in ['n','on','missing','incomplete']:ok(s[k]==row['metrics']['service'][group][k]==int(csvmap[row['label']][group+'_'+k]),'Service raw/CSV')
        near(s['P95'],row['metrics']['service'][group]['P95']);near(s['P95'],float(csvmap[row['label']][group+'_P95']))
    ind.append(v)
for scale in summary['scales']:
    sid=scale['setting'];aa=scale['CONF_overall'];ok(len(aa)==5,'Five policies')
    for a in aa:
        rr=[r for r in ind if r['setting']==sid and r['policy']==a['policy']];ok(len(rr)==4,'Four inputs');near(a['J'],avg(r['J'] for r in rr));near(a['AP'],avg(r['AP'] for r in rr))
        for g in ['ALL','U','N']:
            for k in ['n','on','missing','incomplete']:ok(a[g+'_'+k]==sum(r['svc'][g][k] for r in rr),'Aggregate service')
            near(a[g+'_on_pct'],100*sum(r['svc'][g]['on'] for r in rr)/sum(r['svc'][g]['n'] for r in rr));near(a[g+'_P95'],avg(r['svc'][g]['P95'] for r in rr));near(a[g+'_P95_pooled'],p95([t for r in rr for t in r['svc'][g]['lat']]))
    b=aa[-1];joint=True
    for c,a in zip(scale['CONF_comparisons'],aa[:-1]):
        near(c['ALL_gain_pp'],b['ALL_on_pct']-a['ALL_on_pct']);near(c['energy_saving_pct'],100*(a['J']-b['J'])/a['J']);near(c['AP_reduction_C'],a['AP']-b['AP']);near(c['U_P95_increase_s'],b['U_P95']-a['U_P95']);near(c['N_P95_increase_s'],b['N_P95']-a['N_P95'])
        if a['policy'] in policies[:3]:joint=joint and c['ALL_gain_pp']>0 and c['energy_saving_pct']>0 and c['AP_reduction_C']>0
    ok(joint==scale['joint_aggregate_pass'],'Aggregate joint judgment')
    mixok=True;quality=True
    for m in scale['CONF_per_mix']:
        for a in m['policies']:
            rr=[r for r in ind if r['setting']==sid and r['policy']==a['policy'] and r['mix']==m['mix']];near(a['J'],avg(r['J'] for r in rr));near(a['AP'],avg(r['AP'] for r in rr))
            for g in ['ALL','U','N']:near(a[g+'_on_pct'],100*sum(r['svc'][g]['on'] for r in rr)/sum(r['svc'][g]['n'] for r in rr))
        bm=m['policies'][-1];quality=quality and bm['ALL_on_pct']>=95 and bm['U_on_pct']>=99 and bm['ALL_missing']==bm['ALL_incomplete']==0
        for a in m['policies'][:3]:mixok=mixok and bm['ALL_on_pct']>=a['ALL_on_pct'] and bm['J']<a['J'] and bm['AP']<a['AP']
    ok(mixok==scale['mix_nonworse_energy_AP_pass'],'Extra mixed guard unchanged');ok(quality==scale['service_quality_gate_pass'],'Service guard');ok((joint and mixok and quality)==scale['all_required_gates_pass'],'No gate silently relaxed')
    ok(not mixok and joint,'Observed aggregate pass/extra mixed guard failure both disclosed')
for name in ['AUDIT_JS','AUDIT_PYTHON','TIME_SERIES_CHECK','REPORT_BUILD']:ok(read(O/(name+'.json'))['status']=='PASS',name)
ok(read(O/'AUDIT_PYTHON.json')['numpy_Torch_frozen_NN_choices']==6238,'NN choices')
ok(any(read(p)['owned_lock_returned'] for p in V.glob('LOCK_RELEASED_*.json')),'Lock actually returned')
ok(subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==reg['HEAD'],'HEAD')
controls=[R/'docs/PROJECT_STATUS.md',R/'docs/PROJECT_PLAN.md',R/'docs/DECISIONS.md',A/'docs/LATEST_EXECUTION_FILES.md'];controlpaths={p.relative_to(R).as_posix():i for i,p in enumerate(controls)}
# Previous immutable evidence stays identical; mutable controls retain their exact old sealed bytes as snapshots.
prior=read(A/'results/A24_S26_SCALE_20261022_01/FINAL_PROOF.json');prior_actual=prior_snapshots=0
for pin in prior['files']:
    if pin['path'] in controlpaths:
        i=controlpaths[pin['path']];p=V/f'CONTROL_BEFORE_{i}.bin';prior_snapshots+=1
    else:p=R/pin['path'];prior_actual+=1
    ok(sha(p)==pin['sha256'],'Prior proof preserved '+pin['path'])
write(V/'VISUAL_REVIEW.json',{'status':'PASS','reviewed':['CONF_COMPARISON.png','N256_AP_TIME.png','N256_ENERGY_TIME.png','N512_AP_TIME.png','N512_ENERGY_TIME.png'],'notes':'Korean labels/units and all four inputs are visible. Energy image original-resolution check confirmed title and legend after resized tool preview crop.','date':'2026-10-22'})
completions=[]
for i,p in enumerate(controls):
    before=p.read_bytes();backup=V/f'CONTROL_COMPLETION_BEFORE_{i}.bin'
    with backup.open('xb') as f:f.write(before)
    href='../results/A24_S26_JOINT_20261022_01/REPORT_KO.md' if i==3 else '../a24_simulator/results/A24_S26_JOINT_20261022_01/REPORT_KO.md'
    block=f'''## 2026-10-22 A24-S26-JOINT-02 · 합산 정시·소비·온도 동시우위 확인 완료

[정본]({href}). 기존DEV100행을 새 목적(세 기준선 각각보다 strict 합산정시 우위·소비/AP감소)으로 저장 재사용하고 두후보를 사전고정,40새평가 COMPLETE/FAIL0로 확인했다. S26의분류긴급0.8초/탐지일반2초·두혼합·전체도착분모·입력별P95평균·고정소비/AP창은 유지했다. 동결A24-05 BC/원물리·CPU3·D_GPU전이가정, 새학습/fit/실측/기존완료 재시작0이다.

묶음8·명목25%·N256: BC전체99.9023/긴급99.8438%, EDF전체97.8516%, EDF비소비0.974877%/AP0.206189℃감소. N512: BC전체99.8535/긴급99.7656%, EDF전체97.8516%, 소비1.124746%/AP0.242416℃감소. FIFO/RR에도 합산3지표 동시우위다. N512긴급/일반P95는EDF비0.100911/0.026366초 단축했다.

추가 사전조건인 혼합별정시비악화는 두후보 모두 실패: 분류75% draw2에서 교사/BC긴급1건지각, 기준선전량정시다. 합산공동우위와 이추가gate실패를 모두 공개하며 gate를소급완화하거나 기본정책으로자동채택하지않는다. 교사/BC성과는거의같다. 같은실측pool/다른설정과잠재표본공유·후속개발확인이며 새독립실측/기기절감/전역최적 아님을 유지했다.

JS3,254,407/Python27,943검사·NN6,238선택 PASS, 모든40행·두후보/혼합별손해·8입력시간그래프 보존·공유잠금반환. 기존봉인422파일의 불변418파일/이전제어4스냅샷 보존을 확인했다. 최종검산/해시는 결과폴더FINAL_PROOF.json, HEAD ac3a5af+미커밋이다. 자동추가·재시도·게시0. 다음: 정본/발표자료검토 또는 사용자후속요청. 아래는 등록/이전 이력이다.

''';p.write_bytes(block.encode()+before);ok(p.read_bytes().endswith(before),'Control completion suffix');ok(p.read_bytes().endswith((V/f'CONTROL_BEFORE_{i}.bin').read_bytes()),'Old control suffix');completions.append({'path':p.relative_to(R).as_posix(),'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':sha(p)})
write(V/'CONTROL_COMPLETION.json',{'status':'PASS','files':completions})
proof=O/'FINAL_PROOF.json';links=[]
for p in [O/'REPORT_KO.md',O/'CONTINUE_RUNNING.md']:
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if not target.startswith(('http:','https:','#')):links.append((p.parent/target).resolve())
for p in links:ok(p.exists() or p==proof,'Local link '+str(p))
write(O/'FINAL_CHECK.json',{'status':'PASS','checks':checks,'max_abs_aggregate_error':error,'CONF_raw_to_summary_P95_CSV_verified':True,'both_aggregate_PASS_and_mixture_guard_FAIL_verified':True,'old_seal_files_unchanged':prior_actual,'old_control_sealed_snapshots_preserved':prior_snapshots,'new_environments':0,'new_fits':0,'script_sha256':sha(Path(__file__))})
files=[p for base in [H,O,V] for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+controls;pins=[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(files)) if p!=proof]
write(proof,{'status':'PASS','id':'A24-S26-JOINT-02','recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'HEAD':reg['HEAD'],'dirty':True,'scientific_START':40,'COMPLETE':40,'FAIL':0,'new_train_fit_measurement':0,'reused_DEV100_saved_only':True,'overall_joint_advantage_both_scales':all(s['joint_aggregate_pass'] for s in summary['scales']),'extra_mixture_nonworse_guard_passed_both':all(s['all_required_gates_pass'] for s in summary['scales']),'no_gates_redefined_after_CONFIRM':True,'default_adopted':False,'old_immutable_files_preserved':prior_actual,'old_controls_preserved_snapshots':prior_snapshots,'source_operation_sha256':sha(H/'OPERATION.json'),'local_links':len(links),'files':pins,'excludes_own_bytes':True})
for p in links:ok(p.exists(),'Actual link after proof')
for p in pins:ok(sha(R/p['path'])==p['sha256'],'New seal')
print(json.dumps({'state':'FINAL_PASS','checks':checks,'sealed_files':len(pins),'max_abs_error':error,'old_immutable_files':prior_actual,'old_control_snapshots':prior_snapshots,'scales':[{'setting':s['setting'],'aggregate_joint':s['joint_aggregate_pass'],'extra_mixture_guard':s['mix_nonworse_energy_AP_pass']} for s in summary['scales']]},ensure_ascii=False))
