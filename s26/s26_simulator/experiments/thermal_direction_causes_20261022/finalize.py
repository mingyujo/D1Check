"""Check report/provenance, preserve registration snapshot and update this task's status."""
from engine import *
import csv,re,datetime,subprocess
O=H/'artifacts/G001';sys.stdout.reconfigure(encoding='utf-8')
r=read(O/'COMPARISON.json');audit=read(O/'AUDIT.json');conclusion=read(O/'CONCLUSION.json');math=read(H/'MATH_CHECK.json');pre=read(H/'PREFLIGHT.json');assert audit['prediction_points']==51950 and audit['max_JS_python_error_C']<1e-8
assert r['fit']['fit_START']==r['fit']['fit_COMPLETE']==56 and r['fit']['fit_FAIL']==0 and math['status'].startswith('PASS')
assert all(v['sessions']==208 and not v['missing'] and v['windows']==5879 for v in r['coverage'])
assert read(O/'START.json')['code_sha256']==sha(H/'fit.py')
for pin in pre['source']:assert sha(R/pin['path'])==pin['sha256'],pin['path']
old=read(R/'s26_simulator/publications/ppt_handoff_rolling_atc_bc_20261021/MD_SOURCE_MANIFEST.json')['sources']
for pin in old:assert sha(R/pin['path'])==pin['sha256']
with (O/'PAIRED_SESSIONS.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==1040
for kind in ['BASELINE','HISTGB_RESIDUAL','TREND_BALANCED','MARGIN_BALANCED','MARGIN_STEADY_GUARD']:
    ss=[v for v in rows if v['candidate']==kind];assert len({v['id'] for v in ss})==208
    target=next(v for v in r['point_summary'] if v['candidate']==kind and v['category']=='ALL')['MAE_C'];assert abs(np.mean([float(v['overall_MAE']) for v in ss])-target)<1e-12
    for cl in ['RISE','FALL','STEADY']:
        target=next(v for v in r['summary'] if v['candidate']==kind and v['category']=='LATE_GE256' and v['direction']==cl)['session_macro']['direction_percent'];picked=[float(v['LATE_'+cl+'_direction']) for v in ss if v.get('LATE_'+cl+'_direction')];assert abs(np.mean(picked)-target)<1e-12
    counts=r['confusion'][kind+'__ALL']['counts'];assert [sum(row) for row in counts]==[892,1601,3386]
md=(H/'REPORT_KO.md').read_text(encoding='utf-8');ht=(H/'REPORT_KO.html').read_text(encoding='utf-8');links=[]
for ref in re.findall(r'\]\(([^)]+)\)',md):
    if ':' not in ref and not ref.startswith('#'):assert (H/ref).resolve().exists(),ref;links.append(ref)
assert '\ufffd' not in md and '\ufffd' not in ht and ht.count('<table>')==9 and ht.count('<img ')==3
branch=subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip();head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();assert branch=='codex/s26-simulator-handoff-20261016' and head=='6cd0321ad87df72c8d24f94b0e3b8d66b604ae5f'
date=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d');utc=datetime.datetime.now(datetime.timezone.utc).isoformat();primary=conclusion['primary_metrics'];goal=next(v for v in r['comparisons'] if v['candidate']=='MARGIN_STEADY_GUARD')
block=f'''<!-- S26_DIRECTION_CAUSES_COMPLETE_20261022_BEGIN -->
{date} 사용자 요청 장시간 방향 저정확도 원인 진단 및 정체/온도 보호 비교 완료: [원인·2후보 비교 보고서]({{link}}). {conclusion['verdict']} 사전주후보MARGIN_STEADY_GUARD 전체MAE0.423→{primary['overall']:.3f}℃·장시간0.722→{primary['late']:.3f}℃, 장시간방향 상승5.46→{primary['late_rise_direction']:.2f}%·하강21.88→{primary['late_fall_direction']:.2f}%·정체86.96→{primary['late_steady_direction']:.2f}%. 주후보동시조건={'PASS' if goal['joint_goal_met'] else 'FAIL'}; 全후보·기존+5%p목표·그룹변동·민감도·실패保존. 진단:0.1℃격자/반복관측·10초창±2초시상승29.25/하강23.55%판정변화·모델활동없는창·조건부실측전력연관(인과미확정), 미래실측입력0/초기이력available<=anchor. 같은208세션/25,975점/27그룹제외·5,879창의개발비교/새독립확인아님. 신규열보완56START/56COMPLETE/FAIL0·기존모델再적합/전력fit/BC·RL학습/정책환경/실측/예약자동화재개0. 독립JS51,950점최대{audit['max_JS_python_error_C']:.3g}℃/초기이력별도계산/hinge유한차분PASS·기존정책/모델/全후보SHA보존. 미채택/미배치/물리gateFAIL유지·HEAD6cd0321a+로컬추가/미업로드. 근거 experiments/thermal_direction_causes_20261022/artifacts/G001/COMPARISON.json·AUDIT.json·FINAL_QA.json.
근거 한계: 장시간 상승 개선은36세션중1세션/35동률, 하강5개선·1악화·28동률이다. 방향 차이 재표집 구간은0포함·전체상승74.09→73.69%소폭하락·각+5%p목표미달이며 원인 해결이나 일반 우수성을 확정하지 않는다.
다음: (1) 온도/정체보존과 양방향 증가·원인 가설 검토, (2) 기존·신규 후보와 모든 실패 보존, (3) 후속 검증은 새 목적·설계 후 진행. 현재 계산 장애 없음.
<!-- S26_DIRECTION_CAUSES_COMPLETE_20261022_END -->

'''
for path,link in [(R/'docs/PROJECT_STATUS.md','../s26_simulator/experiments/thermal_direction_causes_20261022/REPORT_KO.html'),(R/'s26_simulator/STATUS.md','experiments/thermal_direction_causes_20261022/REPORT_KO.html')]:
    b=path.read_bytes();bom=b[:3] if b.startswith(b'\xef\xbb\xbf') else b'';body=b[len(bom):];start=body.index(b'<!-- S26_DIRECTION_CAUSES_REGISTERED_20261022_BEGIN -->');end=body.index(b'<!-- S26_DIRECTION_CAUSES_REGISTERED_20261022_END -->')+len(b'<!-- S26_DIRECTION_CAUSES_REGISTERED_20261022_END -->\r\n\r\n');assert start==0
    # The registration text remains in the immutable protocol and snapshot below.
    save(H/(path.parent.name+'_STATUS_REGISTRATION_SNAPSHOT.json'),dict(path=path.relative_to(R).as_posix(),registration=body[:end].decode('utf-8'),old_sha256=sha(path)))
    path.write_bytes(bom+block.format(link=link).replace('\n','\r\n').encode('utf-8')+body[end:]);assert path.read_bytes().endswith(body[end:])
status=read(H/'STATUS.json');save(H/'STATUS_REGISTERED_SNAPSHOT.json',status);(H/'STATUS.json').write_text(json.dumps(dict(status='COMPLETE_THERMAL_DIRECTION_CAUSE_COMPARISON',UTC=utc,report='REPORT_KO.html',fit_START=56,fit_COMPLETE=56,fit_FAIL=0,verdict=conclusion['verdict'],primary_joint_goal_met=goal['joint_goal_met'],original_models_and_previous_candidate_unchanged=True,old_physics_gate='FAIL_PRESERVED',adopted=False,new_measurements=0,new_BC_RL_training=0,new_policy_environments=0,automatic_followup=False),ensure_ascii=False,indent=2),encoding='utf-8')
files=[dict(path=x.relative_to(R).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(H.rglob('*')) if x.is_file() and '__pycache__' not in x.parts and x.name not in ['SOURCE_MANIFEST_FINAL.json','FINAL_QA.json']]
save(O/'SOURCE_MANIFEST_FINAL.json',dict(UTC=utc,HEAD=head,branch=branch,local_uncommitted=True,original_and_previous_source_pin_checks=len(pre['source']),prior_methodology_source_checks=len(old),files=files))
save(O/'FINAL_QA.json',dict(status='PASS_CURRENT_REPORT_MATH_AND_PROVENANCE',UTC=utc,HEAD=head,branch=branch,local_uncommitted=True,fit_START=56,fit_COMPLETE=56,fit_FAIL=0,source_pin_checks=len(pre['source']),prior_methodology_source_checks=len(old),paired_session_metric_reaggregation='PASS',confusion_true_counts='PASS',same_evaluation_coverage='208sessions/5879windows each',report_local_links=len(links),HTML_tables=9,HTML_images=3,visually_reviewed_figures=['01_temperature_retention.png','02_direction_and_steady.png','03_same_traces.png'],independent_scalar_prediction_points=51950,independent_math_check='PASS',first_replay_failure_preserved=True,constant_history_slope_handling_fixed_only_in_independent_JS=True,original_and_previous_models_policy_unchanged=True,old_physical_gate='FAIL_PRESERVED',adopted=False,new_measurements=0,new_policy_environments=0,new_BC_RL_training=0,commands=['diagnose.py: existing data only','fit.py --preflight','fit.py --fit:56 new identities only','check_math.py: no fits','analyze.py','verify.py: first failed replay retained','verify_v2.py: full PASS','paired.py','report.py','annotate_limits.py','finalize.py'],automatic_followup=False))
print(json.dumps(dict(status='PASS_FINAL_QA',verdict=conclusion['verdict'],files=len(files),links=len(links)),ensure_ascii=False))
