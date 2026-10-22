from pathlib import Path
import csv,datetime,hashlib,json,re,shutil,subprocess,zipfile
W=Path(__file__).resolve().parents[1];R=W/'S26-D1Check';S=R/'s26_simulator';H=S/'experiments/final_four_rr_v1';O=H/'artifacts/G001';OUT=W/'output/S26_RR_20261019';Q=W/'tmp/pdfs/s26_four_rr'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
 with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def text(p,s):Path(p).write_text(s,encoding='utf-8',newline='\n')
utc=datetime.datetime.now(datetime.timezone.utc).isoformat();D=read(O/'SUMMARY.json');result=read(O/'RESULT.json');audit=read(O/'AUDIT.json');fig=read(OUT/'FIGURE_PROVENANCE.json');reports=read(Q/'REPORT_MANIFEST.json')
assert audit['status']=='PASS' and result['START']==result['COMPLETE']==4 and result['REUSE']==12 and result['FAIL']==0
assert fig['plot_code_sha256']==sha(W/'recovery/plot_s26_four_rr.py') and fig['source_summary_sha256']==sha(O/'SUMMARY.json')
for entry in fig['outputs']+reports['outputs']:assert sha(entry.get('path',entry.get('file')))==entry['sha256']
with (OUT/'comparison_data.csv').open(encoding='utf-8-sig',newline='') as f:
 for row in csv.DictReader(f):
  d=D[row['method']];assert float(row['energy_API_J'])==d['J'] and float(row['mean_AP_C'])==d['AP_mean'] and float(row['overall_on_time_percent'])==d['service']['all']['pooled_on_percent']
rows={m:{r['input']:r for r in result['rows'] if r['method']==m} for m in ['FIFO','EDF','RR','OURS']};paired=[]
for c in read(H/'INPUTS.json')['cases']:
 a=rows['RR'][c['id']];b=rows['FIFO'][c['id']]
 import gzip
 ar=json.loads(gzip.decompress((O/(a['label']+'.raw.json.gz')).read_bytes()));br=json.loads(gzip.decompress((O/(b['label']+'.raw.json.gz')).read_bytes()))
 seq=lambda raw:[(x['time'],x['action']['ordinal'],x['action'].get('route')) for x in raw['policy_decisions']]
 paired.append(dict(input=c['id'],same_dispatch_sequence=seq(ar)==seq(br),energy_RR_minus_FIFO_API_J=a['J']-b['J'],AP_RR_minus_FIFO_C=a['AP_mean']-b['AP_mean'],on_time_RR_minus_FIFO=a['service']['all']['on_time']-b['service']['all']['on_time']))
put(O/'RR_FIFO_PAIRED_DIAGNOSIS.json',dict(rows=paired,new_environment=0))
qa={'status':'PASS','utc':utc,'report_pages_visually_inspected':9,'figure_PDF_pages_visually_inspected':4,'PNG_figures_visually_inspected':4,'axes_units_checked':['API-J','Celsius','percent','percentage points','seconds'],'zero_baseline_energy_bars':True,'zoomed_dot_axes_explicit':True,'no_significance_claims':True,'paired_dots_are_not_CI':True,'clipping_missing_glyphs_overlap':False,'CSV_and_PDF_tables_match_summary':True,'source_summary_sha256':sha(O/'SUMMARY.json')}
put(Q/'VISUAL_AND_NUMERIC_QA.json',qa)
fig['status']='PASS_VISUAL_AND_NUMERIC_QA';fig['QA']=qa;text(OUT/'FIGURE_PROVENANCE.json',json.dumps(fig,ensure_ascii=False,indent=2)+'\n')
put(H/'REPORT_RECEIPT.json',dict(utc=utc,reports=reports['outputs'],figure_bundle=str(OUT/'S26_FIFO_EDF_RR_우리정책_비교그래프.pdf'),figure_provenance_sha256=sha(OUT/'FIGURE_PROVENANCE.json'),QA=qa,uploaded=False))
lines=['# S26 FIFO EDF 비선점 RR 우리 정책 비교','', '2026-10-19 · 사용자가 선택한 비선점 작업종류별 큐 RR을 추가했다.','',
'RR은 분류/탐지 두 큐를 한 건씩 순환한다. 큐 내부는 도착/ordinal FIFO이며 실행 불가능한 큐는 건너뛴다. 초기 다음 큐=분류. 성공적 배정 뒤 다른 큐로 이동하고 NONE에서는 포인터를 유지한다. CPU시간 균등화나 OS 타임퀀텀 선점 RR이 아니다. 납기/우선순위/예측/신경망/자발WAIT는 없다.','',
'같은 원85%·4입력·입력당1024요청·CPU3·원전력/열·기한·비선점/AVAILABLE·관측창이다. FIFO/EDF/RR의 분류 경로는 GPU→NPU→CPU, 탐지는CPU다. 우리 정책은 최종단일881087(롤링+ATC+공개교사초기화+PPO,argmax)이며 납기보호는 없다.','',
'|방법|전체 API-J|평균 AP/℃|전체 정시율/%|긴급 정시율/%|전체 P95/초|긴급 P95/초|미완료|','|---|---:|---:|---:|---:|---:|---:|---:|']
for m,label in [('FIFO','FIFO'),('EDF','EDF'),('RR','RR 큐순환'),('OURS','우리 최종881087')]:
 d=D[m];s=d['service'];lines.append(f"|{label}|{d['J']:.3f}|{d['AP_mean']:.3f}|{s['all']['pooled_on_percent']:.3f}|{s['urgent']['pooled_on_percent']:.3f}|{s['all']['mean_case_P95_s']:.3f}|{s['urgent']['mean_case_P95_s']:.3f}|{d['unfinished']}|")
lines+=['','우리 정책의 소비/평균AP/전체정시 차이:', '']
for b in ['FIFO','EDF','RR']:
 t=D['OURS']['versus_'+b];lines.append(f"- 대{b}: 소비{t['energy_percent']:.6f}%, 평균AP{t['AP_C']:.6f}℃, 전체정시{t['on_pp']:+.6f}%p.")
lines+=['','RR은 FIFO와 정시율이 같고 소비는약0.0843%높다. 4입력중2개는 실제 배정 순서가 FIFO와 완전히 같고 다른2개도 정시건수는같다. 이 작은격차를 사후 조정하지않았다.','',
'관측창평균245.557627초·기저172.827788API-J. 전체소비는냉각/기저포함, AP평균35초부터끝, 작업경과는첫도착→마지막AVAILABLE다. P95는세션별P95의평균이며전체pooledP95가아니다. 전체정시분모는각4096건, 일반군은pooled1536건을사용한다.','',
'우리긴급P95는기준선보다길다. 교사직후대조777.781API-J/97.070%보다PPO추가이득은미입증이다. 전력열정확도gateFAIL·CPU3추가전력/열/간섭·기기제어비용미측정·AP지원26~46.6℃밖외삽을유지한다. 모형결과이며 실기기절감인증이아니다. 새k배수/온도상한/가짜스로틀링0. 고정두도착템플릿의4입력으로넓은일반화/통계우위/최강경로기준선우위를주장하지않는다.','',
'RR4START/4COMPLETE/FAIL0·기존FIFO/EDF/우리12SHA재사용·새학습/실측/물리fit/완료환경재실행0. 16기록/16384요청/548406저장계산검사PASS. 회전포인터·실행불가큐skip·큐내FIFO·정적경로·CPU/슬롯/납기/독립전력열을전수검산했다.','',
'그림4개는 절대값,EDF대비차이,전체/긴급/일반P95,AP시간궤적이다. 에너지막대는0시작,AP/정시율확대는점그래프에만쓰고범위를명시,개별입력점은CI가아님을표시했다. X/Y라벨/단위/양음효과를검토했고 보고서9쪽+그림PDF4쪽+PNG4개를시각검수했다. PNG/SVG/그림PDF/CSV/코드를output/S26_RR_20261019에보존했다. 두버전보고서에도RR을반영하고과거보고서는보존했다.','',
'공유예약은앞선분기합산최소137754에RR4회만더한137758로유한등록했다. 사용자의명시적RR추가비교및기존근거있는제약완화허용에따른것이며새학습/peer쿼터/환급/전host최신census주장0.','',
'정본: experiments/final_four_rr_v1/PROTOCOL.json·INPUTS.json·REUSE_PLAN.json·OPERATION.json·artifacts/G001/RESULT.json·SUMMARY.json·AUDIT.json·RR_FIFO_PAIRED_DIAGNOSIS.json. 최종모델/과거모든실패/원자료/교사대조/통제학습은보존한다. GitHub새게시와commit없음.']
report=S/'S26_FINAL_FOUR_RR_RESULTS_KO.md';text(report,'\n'.join(lines)+'\n')
block='<!-- S26_FOUR_RR_CURRENT_BEGIN -->\n2026-10-19 사용자선택 비선점분류/탐지큐RR 추가4방법비교완료. 원85%·N1024·4입력·CPU3·GPU>NPU>CPU. API-J/AP/정시%: FIFO840.480/39.433758/96.923828, EDF833.273/39.335384/96.704102, RR841.189/39.443696/96.923828, 우리881087 777.831/38.685053/97.070313. 긴급100%·미완료0공통. RR대FIFO소비+0.0843%·정시동일, 2입력배정완전동일. 우리대RR소비−7.532%·AP−0.759℃·정시+0.146%p. RR은작업큐1건순환/큐내FIFO/불가큐skip이며OS선점RR/CPU시간균등이아님. RR4START/4COMPLETE/FAIL0·기존3방법12SHA재사용·16기록/548406저장검사PASS·새학습/실측/fit/완료재실행0. 4그림(PNG/SVG/4쪽PDF)+CSV+두보고서9쪽/총13PDF쪽QA완료. 확대점축/에너지0시작/EDF차이%와%p/입력별점非CI를명시. 정본S26_FINAL_FOUR_RR_RESULTS_KO.md·experiments/final_four_rr_v1,산출물workspace output/S26_RR_20261019. 우리긴급P95증가/PPO추가기여미입증/전력열FAIL·CPU3기기비용미측정/실기기인증불가유지. 유한로컬예약137754+4=137758(사용자RR추가및근거제약완화허용,환급/peer쿼터/전hostcensus0). 과거PDF/전체자료보존·업로드0. 다음: 그래프/수정두보고서사용,근거보존,추가요청전새실행0.\n<!-- S26_FOUR_RR_CURRENT_END -->\n\n'
for rel in ['s26_simulator/START_HERE.md','s26_simulator/STATUS.md','s26_simulator/HANDOFF.md','s26_simulator/docs/NEXT_STEPS.md','docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md']:
 p=R/rel;shutil.copyfile(p,H/'history'/('BEFORE_FINALIZE__'+rel.replace('/','__')));old=p.read_text(encoding='utf-8-sig');old=re.sub(r'<!-- S26_FOUR_RR_CURRENT_BEGIN -->.*?<!-- S26_FOUR_RR_CURRENT_END -->\s*','',old,flags=re.S);m=re.match(r'<!-- S26_FINAL_POLICY_ADOPTED_BEGIN -->.*?<!-- S26_FINAL_POLICY_ADOPTED_END -->\s*',old,re.S);assert m;text(p,old[:m.end()]+block+old[m.end():])
runtime=H/'workspace_recovery';runtime.mkdir()
for name in ['prepare_s26_four_rr.py','plot_s26_four_rr.py','build_s26_four_rr_reports.py','build_s26_contrast_reports.py','finalize_s26_four_rr.py']:shutil.copyfile(W/'recovery'/name,runtime/name)
shutil.copyfile(W/'recovery/plot_s26_four_rr.py',OUT/'plot_s26_four_rr.py')
# Archive the complete output set; the ZIP contains a fixed snapshot of these files.
package=OUT/'S26_RR_보고서_그래프_원본묶음.zip'
with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(OUT.iterdir()):
  if p.is_file() and p!=package:z.write(p,p.name)
with zipfile.ZipFile(package) as z:
 for name in z.namelist():assert z.read(name)==(OUT/name).read_bytes()
outputs=H/'outputs';outputs.mkdir()
for p in OUT.iterdir():
 if p.is_file():shutil.copyfile(p,outputs/p.name)
core=S/'CORE_MANIFEST.json';shutil.copyfile(core,H/'history/CORE_MANIFEST_BEFORE_FINAL_EXTENSION.json')
state={'status':'COMPLETE_FOUR_POLICY_RR_COMPARISON_AND_FIGURES','utc':utc,'START':4,'COMPLETE':4,'FAIL':0,'REUSE':12,'methods':['FIFO','EDF','RR','OURS'],'selected_seed':881087,'RR':'Nonpreemptive two task queues, one dispatch per turn','audit':'PASS','figure_QA':'PASS','report_pages':9,'figure_PDF_pages':4,'new_training':0,'new_fits':0,'new_measurements':0,'uploaded':False}
text(H/'CURRENT_STATE.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
files=[dict(path=p.relative_to(H).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(H.rglob('*')) if p.is_file() and p not in [H/'MANIFEST.json',H/'FINAL_PROOF.json']]
put(H/'MANIFEST.json',dict(schema='S26_FINAL_FOUR_RR_MANIFEST_V1',utc=utc,files=files,new_RR=4,REUSE=12,new_training=0,physical_validation=False))
m=read(core)
for e in m['files']:
 if e['path'] in ['START_HERE.md','STATUS.md','HANDOFF.md','docs/NEXT_STEPS.md']:
  p=S/e['path'];e.update(bytes=p.stat().st_size,sha256=sha(p))
for e in m.get('local_document_changes',[]):
 p=S/e['path']
 if p.exists():e['local_sha256']=sha(p)
m['final_four_RR_extension']=dict(path='experiments/final_four_rr_v1/MANIFEST.json',sha256=sha(H/'MANIFEST.json'),new_START=4,reused_EVAL=12,new_training=0,selected_model_changed=False,deadline_protection=False,RR_definition='nonpreemptive task queues, not OS time-quantum RR',uploaded=False)
text(core,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
proof={'status':'PASS_FOUR_METHOD_RR_AND_FIGURES_COMPLETE','utc':utc,'manifest_sha256':sha(H/'MANIFEST.json'),'core_manifest_sha256':sha(core),'audit_sha256':sha(O/'AUDIT.json'),'report_sha256':sha(report),'new_START':4,'REUSE':12,'new_training':0,'model_changed':False,'figures':4,'report_PDFs':2,'total_PDF_pages':13,'package':dict(path=str(package),bytes=package.stat().st_size,sha256=sha(package)),'QA':qa,'uploaded':False}
put(H/'FINAL_PROOF.json',proof)
for e in files:assert sha(H/e['path'])==e['sha256']
assert {x['path'] for x in files}=={p.relative_to(H).as_posix() for p in H.rglob('*') if p.is_file() and p not in [H/'MANIFEST.json',H/'FINAL_PROOF.json']}
print(json.dumps({k:v for k,v in proof.items() if k not in ['QA','package']},ensure_ascii=False))
