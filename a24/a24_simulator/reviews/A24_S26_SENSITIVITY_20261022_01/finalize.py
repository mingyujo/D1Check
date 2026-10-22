"""Saved-only closure. No simulation, fit, sampling, or checkpoint import."""
import json,csv,re,hashlib,subprocess,datetime,math
from pathlib import Path
V=Path(__file__).resolve().parent;R=V.parents[2];A=R/'a24_simulator';H=A/'experiments/a24_s26_sensitivity_20261022';O=A/'results/A24_S26_SENSITIVITY_20261022_01'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
checks=0
def ok(v,m):
    global checks
    checks+=1
    if not v:raise AssertionError(m)
reg=read(H/'OPERATION.json');summary=read(O/'SUMMARY.json');audit=read(O/'AUDIT_JS.json');build=read(O/'BUILD.json')
for p in reg['source_pins']:ok(sha(R/p['path'])==p['sha256'],'Frozen source '+p['path'])
ok(audit['status']==build['status']=='PASS','Audits complete');ok(summary['unique_episodes']==160 and summary['DEV']==100 and summary['CONF']==60,'Source census');ok(summary['matched_factor_pairs']==120 and summary['factor_interactions']==60,'Contrast census');ok(summary['new_environments']==summary['new_fits']==summary['new_measurements']==0,'No new science')
controls=[R/'docs/PROJECT_STATUS.md',R/'docs/PROJECT_PLAN.md',R/'docs/DECISIONS.md',A/'docs/LATEST_EXECUTION_FILES.md'];cmap={p.relative_to(R).as_posix():i for i,p in enumerate(controls)};preservation=[]
for name,snapshots in [('A24_S26_SCALE_20261022_01',A/'reviews/A24_S26_JOINT_20261022_01'),('A24_S26_JOINT_20261022_01',V)]:
    previous=read(A/'results'/name/'FINAL_PROOF.json');immutable=archived=0
    for pin in previous['files']:
        if pin['path'] in cmap:p=snapshots/f"CONTROL_BEFORE_{cmap[pin['path']]}.bin";archived+=1
        else:p=R/pin['path'];immutable+=1
        ok(sha(p)==pin['sha256'],'Prior evidence '+pin['path'])
    preservation.append({'prior':name,'immutable_files_unchanged':immutable,'sealed_control_versions_preserved':archived})
for name,count in [('ALL_EPISODES.csv',160),('GRID_SUMMARY.csv',13),('MATCHED_CONTRASTS.csv',120),('INTERACTIONS.csv',60),('WEIGHT_THRESHOLDS.csv',6),('WINDOWS.csv',52)]:
    with (O/name).open(encoding='utf-8-sig',newline='') as f:rr=list(csv.DictReader(f))
    ok(len(rr)==count,'CSV rows '+name)
    if name=='ALL_EPISODES.csv':
        source={r['label']:r for r in read(O/'EPISODES.json')}
        for r in rr:
            s=source[r['label']];ok(r['policy']==s['policy'] and r['role']==s['role'],'CSV identity')
            for k in ['J','AP','ALL_on_pct','U_on_pct','ALL_P95','U_P95','N_P95','J_per_request','J_per_ontime']:ok(abs(float(r[k])-s[k])<1e-10,'CSV number '+k)
stable=read(O/'STABILITY_SUMMARY.json');draws=read(O/'DRAW_STABILITY.json')
for s in stable:
    rr=[r for r in draws if r['setting']==f"N{s['N']}_B8_L25"];ok(s['draws']==len(rr)==3,'Draw count');ok(s['aggregate_joint_pass_draws']==sum(r['aggregate_joint'] for r in rr),'Draw joint');ok(s['aggregate_joint_pass_draws']==3,'Observed three draws jointly positive')
cells=read(O/'CELLS.json');c=next(c for c in cells if c['role']=='CONF' and c['setting']=='N512_B8_L25');ok(c['aggregate_joint'] and not c['mixed_nonworse_joint'],'Preserved aggregate pass/mixed failure')
fs=read(O/'FACTORS.json')['summary'];bc={s['factor']:s for s in fs if s['policy']=='BC_NEURAL_URGENT'};order=sorted(bc,key=lambda f:-bc[f]['metrics']['ALL_on_pct']['mean_abs']);ok(order==summary['BC_abs_ALL_effect_order']==['LOAD','N','BURST'],'Recorded effect ordering')
save(V/'VISUAL_REVIEW.json',{'status':'PASS','reviewed_pngs':['FACTOR_EFFECTS.png','SCALE_GRID.png','SCENARIO_WEIGHTING.png','DRAW_STABILITY.png'],'Korean_labels_legible':True,'unrun_cells_marked':True,'DEVs_and_CONF_distinguished':True,'reweighting_not_new_simulation_labelled':True,'date':'2026-10-22'})
record=[]
for i,p in enumerate(controls):
    before=p.read_bytes();backup=V/f'CONTROL_COMPLETION_BEFORE_{i}.bin'
    with backup.open('xb') as f:f.write(before)
    href='../results/A24_S26_SENSITIVITY_20261022_01/REPORT_KO.md' if i==3 else '../a24_simulator/results/A24_S26_SENSITIVITY_20261022_01/REPORT_KO.md'
    block=f'''## 2026-10-22 A24-S26-SENS-03 · 저장자료 입력규모 민감도 분석 완료

[정본]({href}). 완료160행(DEV100/CONF60)만 재사용했고 새환경/학습/fit/실측/기존완료 재시작0이다. 균형DEV N256/512×묶음4/8×명목25/50%에서 대응120쌍·상호작용60개를 분석했다. BC전체정시 평균절대변화는 도착률14.697%p→요청수8.496→묶음5.029 순이다. 두배 변화 범위의 기술통계이며 보편인과순위가 아니다. 묶음변화에는 작업순서도 일부 변한다.

N512·묶음8에서 명목25→50%면 BC전체99.90→67.58%,25%에서 묶음8→16이면99.90→84.57%로 떨어진다. 묶음8·25% 두N의 DEV0/CONF1/CONF2 합산공동우위는3/3이나 분류75% 확인은 여전히긴급1건손해·혼합별비악화gate실패다. 입력구성·draw·계산창·분석적재가중을 구분했고 중간도착률/물리계수/기한/초기온도 민감도는 미평가다.

원S26평가기준/동결정책·모형 불변, J*는 미교정예측값·기존pool 후속분석이며 새독립실측 아니다. 독립JS21,870검사 PASS·모든160행/120쌍/60DID·4그림·손해/미실행 보존, 이전두봉인 불변550파일/제어8버전스냅샷 확인. 최종검증/해시는 결과폴더FINAL_PROOF.json,HEAD ac3a5af+미커밋이다. 자동추가·채택·게시0. 다음: 정본/발표자료검토 또는 사용자후속요청. 아래는 등록/이전이력이다.

''';p.write_bytes(block.encode()+before);ok(p.read_bytes().endswith(before),'Complete prior control bytes preserved');ok(p.read_bytes().endswith((V/f'CONTROL_BEFORE_{i}.bin').read_bytes()),'Preanalysis control suffix');record.append({'path':p.relative_to(R).as_posix(),'old_sha256':hashlib.sha256(before).hexdigest(),'new_sha256':sha(p)})
save(V/'CONTROL_COMPLETION.json',{'status':'PASS','files':record})
ok(subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==reg['HEAD'],'HEAD unchanged');ok(subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip()=='codex/a24-simulator-handoff-20261016','Branch unchanged')
proof=O/'FINAL_PROOF.json';links=[]
for p in [O/'REPORT_KO.md',O/'CONTINUE_RUNNING.md']:
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
        if not target.startswith(('http:','https:','#')):links.append((p.parent/target).resolve())
for p in links:ok(p.exists() or p==proof,'Local link '+str(p))
save(O/'FINAL_CHECK.json',{'status':'PASS','checks':checks,'saved_only':True,'previous_evidence':preservation,'source_pins_unchanged':len(reg['source_pins']),'csv_and_scope_verified':True,'script_sha256':sha(Path(__file__))})
files=[p for base in [H,O,V] for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+controls;pins=[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(files)) if p!=proof]
save(proof,{'status':'PASS','id':'A24-S26-SENS-03','recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'HEAD':reg['HEAD'],'dirty':True,'new_environments':0,'new_fits':0,'new_measurements':0,'reused_unique_episodes':160,'matched_contrasts':120,'DID':60,'source_operation_sha256':sha(H/'OPERATION.json'),'previous_evidence_preserved':preservation,'physics_parameter_sensitivity_not_tested':True,'no_population_CI_or_causal_rank_claim':True,'local_links':len(links),'files':pins,'excludes_own_bytes':True})
for p in links:ok(p.exists(),'Actual report link')
for p in pins:ok(sha(R/p['path'])==p['sha256'],'New seal')
print(json.dumps({'state':'FINAL_PASS','checks':checks,'sealed_files':len(pins),'prior_preservation':preservation,'new_environments':0,'factor_order':order},ensure_ascii=False))
