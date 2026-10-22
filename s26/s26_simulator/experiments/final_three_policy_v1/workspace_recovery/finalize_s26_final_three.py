import datetime,hashlib,json,re,shutil,subprocess
from pathlib import Path
W=Path(__file__).resolve().parents[1];R=W/'S26-D1Check';S=R/'s26_simulator';H=S/'experiments/final_three_policy_v1';O=H/'artifacts/G001';Q=W/'tmp/pdfs/s26_three_compare'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
 with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
utc=datetime.datetime.now(datetime.timezone.utc).isoformat();d=read(O/'SUMMARY.json');result=read(O/'RESULT.json');audit=read(O/'AUDIT.json');assert audit['status']=='PASS' and len(result['rows'])==16
pdf=read(Q/'manifest.json');assert pdf['primary_methods']==['FIFO','EDF','OURS']
for out in pdf['outputs']:assert sha(out['file'])==out['sha256']
qa={'status':'PASS','utc':utc,'pages_inspected':9,'render_dpi':144,'final_pages_byte_identical_to_reviewed_previous':7,'modified_final_pages_inspected':['honest_final-5.png','selective_final-3.png'],'missing_glyphs_or_clipping':False,'three_method_tables_match_summary':True}
put(Q/'VERIFICATION.json',qa)
put(H/'REPORT_RECEIPT.json',dict(utc=utc,outputs=pdf['outputs'],QA=qa,source_summary_sha256=sha(O/'SUMMARY.json'),old_reports_preserved=True,uploaded=False))
lines=['# S26 최종 FIFO EDF 우리 정책 동일 입력 비교','', '2026-10-19 · 주 비교는 FIFO·EDF·최종 단일 모델 881087이다. 우리 정책은 롤링+ATC+공개 교사 초기화+PPO이며 납기 보호는 없다.','',
'같은 원 85% 명목 부하·N1024·4입력·CPU3·기존 전력/열·납기·관측창을 사용했다. FIFO/EDF 경로 순서는 원 비교의 GPU→NPU→CPU로 고정했다. FIFO4회만 추가했고 EDF4·우리4·보조BC4는 원자료 SHA를 확인해 재사용했다. 추가 학습·물리fit·기기측정·완료 실험 재실행은 없다.','',
'|방법|전체 API-J|평균 AP/℃|전체 정시율/%|긴급 정시율/%|완료 응답 P95/초|미완료|','|---|---:|---:|---:|---:|---:|---:|']
for m,label in [('FIFO','FIFO'),('EDF','EDF'),('OURS','우리 최종 정책 881087')]:
 x=d[m];lines.append(f"|{label}|{x['J']:.3f}|{x['AP_mean']:.3f}|{x['service']['all']['pooled_on_percent']:.3f}|{x['service']['urgent']['pooled_on_percent']:.3f}|{x['service']['all']['mean_case_P95_s']:.3f}|{x['unfinished']}|")
lines+=['','P95는 세션 P95의 평균이다. 전체 정시율의 분모는 방법마다 전체 도착4096건이다. 우리 정책의 대FIFO 소비−7.4539%·평균AP−0.7487℃·정시+0.1465%p, 대EDF 소비−6.6535%·평균AP−0.6503℃·정시+0.3662%p다.','',
'긴급 P95는 FIFO0.366초/EDF0.340초/우리0.604초로 우리 쪽이 길다. 긴급 정시율100% 유지가 모든 군의 응답성 개선은 아니다. 일반 정시율 pooled는 FIFO91.796875%/EDF91.2109375%/우리92.1875%다.','',
'보조 BC 고정 대조는777.781API-J·38.684415℃·정시97.0703125%로, 최종 단일 PPO의777.831API-J보다 소비가0.00646% 낮고 정시율은 같다. PPO 추가 기여는 미입증이며 전체 정책 효과로 설명한다.','',
'관측창 평균245.557627초·기저172.827788API-J. 첫 도착부터 마지막AVAILABLE까지 작업 경과는FIFO120.353062초/EDF120.463833초/우리120.294285초다. 전체 소비는 기저와 냉각을 포함하고 AP 평균은35초부터 종료까지다.','',
'전력/열 실측 정확도gate FAIL·CPU3 추가 전력/열/간섭과 제어 비용 미측정, API-J/AP 모형 예측이라는 한계는 유지한다. 같은 두 템플릿의4입력이므로 넓은 일반화나 통계적 우월성을 주장하지 않는다. GPU우선 기준선의 결과이며 다른 정적 경로순서의 강한 기준정책 모두에 대한 우위로 확대하지 않는다.','',
'4START/4COMPLETE/FAIL0·12REUSE·16기록/16384요청/377680저장계산검사PASS. 감사 입력 task_id 및 구형 EDF 메타데이터 호환 수정만 있었고 실패 코드/등록은history와AUDIT_SCHEMA_REPAIR에 보존했다. 원자료는 변경하거나 재실행하지 않았다.','',
'공유 예약은 공통137542 뒤 A24+144와 S26+64의 분기를 합치면 기존 로컬 최소137750이다. max137686만 사용하면64가 누락된다. 사용자의 근거 있는 제약 완화 허용에 따라 이번 필수FIFO4회에 한해137754까지 유한 예외를 등록했다. 과거 미사용 환급·다른 프로젝트의 새 쿼터 부여·전host 최신census 주장은 없다.','',
'근거: experiments/final_three_policy_v1/PROTOCOL.json · INPUTS.json · REUSE_PLAN.json · BUDGET_RESERVATION.json · OPERATION.json · artifacts/G001/RESULT.json · SUMMARY.json · AUDIT.json. 수정 PDF 두 개는 workspace output/pdf에 보존한다. GitHub 새 게시와 Git commit은 하지 않았다.']
report=S/'S26_FINAL_THREE_POLICY_RESULTS_KO.md';report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
block='<!-- S26_FINAL_THREE_CURRENT_BEGIN -->\n2026-10-19 FIFO/EDF/우리최종881087 동일원85%·N1024·4입력·CPU3·GPU>NPU>CPU 비교완료. 주표API-J/AP/정시%: FIFO840.480/39.433758/96.923828, EDF833.273/39.335384/96.704102, 우리777.831/38.685053/97.070313. 긴급100%·미완료0공통. 우리대FIFO소비−7.4539%·AP−0.7487℃·정시+0.1465%p, 대EDF−6.6535%/−0.6503℃/+0.3662%p. 긴급P95는우리0.604초로FIFO0.366/EDF0.340보다길고BC대조대비PPO추가이득미입증. FIFO4START/4COMPLETE/FAIL0·EDF/우리/BC12SHA재사용·16기록/377680저장검사PASS·새학습/실측/fit/완료재실행0. 정본S26_FINAL_THREE_POLICY_RESULTS_KO.md·experiments/final_three_policy_v1. 주표3방법으로두PDF수정/9페이지QA완료·원PDF보존. 로컬예약분기137542+A24서로다른144+S26별도64=최소137750를확인; 사용자논리제약완화허용근거로필수FIFO4회만137754까지유한예외(전hostcensus/환급/peer새쿼터0). 전력열정확도FAIL·CPU3및기기비용미측정·실기기절감인증불가/업로드0유지. 다음: 수정두보고서사용, 자료/실패/교사대조보존, 새요청전추가실행0.\n<!-- S26_FINAL_THREE_CURRENT_END -->\n\n'
rels=['s26_simulator/START_HERE.md','s26_simulator/STATUS.md','s26_simulator/HANDOFF.md','s26_simulator/docs/NEXT_STEPS.md','docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md']
for rel in rels:
 p=R/rel;backup=H/'history'/('BEFORE_FINALIZE__'+rel.replace('/','__'));shutil.copyfile(p,backup)
 text=p.read_text(encoding='utf-8-sig');text=re.sub(r'<!-- S26_FINAL_THREE_CURRENT_BEGIN -->.*?<!-- S26_FINAL_THREE_CURRENT_END -->\s*','',text,flags=re.S);p.write_text(block+text,encoding='utf-8')
recovery=H/'workspace_recovery';recovery.mkdir()
for name in ['prepare_s26_final_three.py','build_s26_three_reports.py','build_s26_contrast_reports.py','finalize_s26_final_three.py']:shutil.copyfile(W/'recovery'/name,recovery/name)
state={'status':'COMPLETE_THREE_POLICY_SAME_INPUT_AND_REPORT_QA','utc':utc,'START':4,'COMPLETE':4,'FAIL':0,'REUSE':12,'primary_methods':['FIFO','EDF','OURS'],'selected_seed':881087,'audit_status':'PASS','new_training':0,'new_measurements':0,'new_fits':0,'uploaded':False}
(H/'CURRENT_STATE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
files=[]
for p in sorted(H.rglob('*')):
 if p.is_file():files.append({'path':p.relative_to(H).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
put(H/'MANIFEST.json',dict(schema='S26_FINAL_THREE_MANIFEST_V1',utc=utc,files=files,new_FIFO=4,REUSE=12,physical_validation=False))
core=S/'CORE_MANIFEST.json';m=read(core);shutil.copyfile(core,H/'history/CORE_MANIFEST_BEFORE_EXTENSION.json')
for entry in m['files']:
 p=S/entry['path']
 if entry['path'] in ['START_HERE.md','STATUS.md','HANDOFF.md','docs/NEXT_STEPS.md']:
  entry['sha256']=sha(p);entry['bytes']=p.stat().st_size
for entry in m.get('local_document_changes',[]):
 p=S/entry['path']
 if p.exists():entry['local_sha256']=sha(p)
m['final_three_policy_extension']=dict(path='experiments/final_three_policy_v1/MANIFEST.json',sha256=sha(H/'MANIFEST.json'),new_START=4,reused_EVAL=12,new_training=0,model_changed=False,selected_seed=881087,deadline_protection=False,uploaded=False)
core.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
receipt={'status':'PASS_FIFO_EDF_OURS_SAME_INPUT_AND_TWO_REPORTS','utc':utc,'manifest_sha256':sha(H/'MANIFEST.json'),'core_manifest_sha256':sha(core),'audit_sha256':sha(O/'AUDIT.json'),'report_sha256':sha(report),'new_START':4,'REUSE':12,'new_training':0,'checkpoint_changed':False,'uploaded':False,'reports':pdf['outputs']}
put(H/'FINAL_PROOF.json',receipt)
for entry in files:assert sha(H/entry['path'])==entry['sha256']
print(json.dumps({k:v for k,v in receipt.items() if k!='reports'},ensure_ascii=False))
