'use strict';
// New postprocessing source; never mutates registered production source or raw values.
const C=require('./common.cjs'),{fs,path}=C,op=C.read(path.join(C.HERE,'OPERATION.json'));
const dir=op.output,summary=C.read(path.join(dir,'SUMMARY.json')),audit=C.read(path.join(dir,'AUDIT.json')),terminal=C.read(path.join(dir,'TERMINAL.json'));
if(audit.status!=='PASS_FOR_SAVED_COMPLETES')throw Error('Saved audit missing');
const inputNames=['SUMMARY.json','AUDIT.json','TERMINAL.json','RECOVERY_EDF_PURE_PROOF.json'];
const termCases=[['SHORT','CENTRAL','EDF'],['LONG64','CENTRAL','EDF'],['LONG64','CENTRAL','ATC'],['LONG256','LOW','ATC']];
const post={schema:'S26_SUSTAINED_POSTPROCESS_V1',utc:new Date().toISOString(),source:C.pin(__filename),inputs:inputNames.map(f=>C.pin(path.join(dir,f))),production_operation:C.pin(path.join(C.HERE,'OPERATION.json')),recovery_operation:C.pin(path.join(C.HERE,'RECOVERY_OPERATION.json')),new_environments:0,new_fit:0,new_RL:0,AP_term_evaluations:termCases,scope:'Descriptive saved outcomes/trace equality and four saved-curve peak AP term decompositions; no policy or model reselection'};
C.write(path.join(dir,'POSTPROCESS_OPERATION.json'),post);
const failed=[];
for(const spec of op.cases){const f=path.join(dir,spec.id+'.failure.json');if(!fs.existsSync(f))continue;const error=C.read(f),raw=path.join(dir,'raw',spec.id+'.failed.json.gz'),partial=fs.existsSync(raw)?C.read(raw):null;
 const reason=(error.stderr??'').match(/Error:\s*([^\r\n]+)/)?.[1]??error.error??'Unknown';
 failed.push({id:spec.id,kind:spec.kind,input:spec.input_id??'P0',policy:spec.config.policy,model:spec.config.model,reason,time_at_stop_s:partial?.time??null,completed_at_stop:partial?.done?.length??null,planned:spec.n,failed_before_simulator:spec.id==='P0_CENTRAL_EDF',raw_partial_preserved:Boolean(partial),automatic_retry:false});
}
C.write(path.join(dir,'FAILURES.json'),failed);
const ties=[];
for(const input of ['SHORT','LONG64','LONG256','DENSE64'])for(const model of ['LOW','CENTRAL','HIGH']){
 const rows=summary.rows.filter(r=>r.input===input&&r.model===model&&['EDF','ATC'].includes(r.policy));if(rows.length!==2||rows.some(r=>r.status!=='COMPLETE'))continue;
 const spec=policy=>op.cases.find(s=>s.kind==='COMPARISON'&&s.input_id===input&&s.config.model===model&&s.config.policy===policy),a=C.read(path.join(dir,'raw',spec('ATC').id+'.json.gz')).simulation,b=C.read(path.join(dir,'raw',spec('EDF').id+'.json.gz')).simulation;
 const by=new Map(b.requests.map(q=>[q.ordinal,q]));let routes=0,dispatch=0,response=0,clock=0,missing=0;
 for(const q of a.requests){const r=by.get(q.ordinal);if(!r){missing++;continue;}if(q.route!==r.route)routes++;if(Math.abs(q.times.dispatch-r.times.dispatch)>1e-8)dispatch++;if(Math.abs(q.response-r.response)>1e-8)response++;for(const k of Object.keys(q.times))if(q.times[k]!==null&&r.times[k]!==null)clock=Math.max(clock,Math.abs(q.times[k]-r.times[k]));}
 ties.push({input,model,ATC_completed:a.requests.length,EDF_completed:b.requests.length,route_changed:routes,dispatch_changed:dispatch,response_changed:response,missing_completed_ids:missing,max_clock_difference_s:clock,all_request_traces_equal:a.requests.length===b.requests.length&&missing===0&&routes===0&&dispatch===0&&response===0&&clock<1e-8});
}
C.write(path.join(dir,'EDF_ATC_TRACE_COMPARISON.json'),ties);
const packet=C.read(C.packetPath),math=require('./source/dynamic_cost_math_v2.cjs'),inputs=C.read(path.join(C.HERE,'INPUTS.json')).inputs,terms=[];
for(const [input,model,policy] of termCases){
 const spec=op.cases.find(s=>s.kind==='COMPARISON'&&s.input_id===input&&s.config.model===model&&s.config.policy===policy),file=path.join(dir,'raw',spec.id+'.json.gz');if(!fs.existsSync(file))continue;
 const raw=C.read(file).simulation,peak=raw.curve.reduce((a,b)=>a[1]>b[1]?a:b),context=inputs.find(s=>s.id===input).context.initial_context;
 const features=math.rawFeatures(packet.AP,{history_start_s:-30,activity9:{intervals:raw.activity},targets:context.targets},[peak[0]])[0],values=features.map((v,j)=>(v-packet.AP.mean[j])/packet.AP.scale[j]*packet.AP.coef[j]);
 const anchor=context.targets.AP.anchor.AP_c??context.targets.AP.anchor.AP,channels=Array.from({length:9},(_,j)=>values[j]+values[9+j]),history=values.slice(18).reduce((a,b)=>a+b,0),sum=anchor+history+channels.reduce((a,b)=>a+b,0);
 if(Math.abs(sum-peak[1])>1e-7)throw Error('AP saved peak term reconstruction');
 terms.push({input,model,policy,curve_sample_step_s:.5,time_s:peak[0],predicted_AP_C:peak[1],anchor_AP_C:anchor,initial_history_contribution_C:history,classification_CPU_C:channels[0],detection_CPU_C:channels[1],GPU_C:channels[2],NPU_C:channels[3],admission_wall_proxy_C:channels[4],post_wall_proxy_C:channels[5],owner_union_C:channels[6],unallocated_C:channels[7],overlap_C:channels[8],sum_C:sum,interpretation:'Fitted AP model terms, not physical heat or chip decomposition; wall proxies include blocked time.'});
}
C.write(path.join(dir,'AP_TERM_DIAGNOSIS.json'),terms);
const f=(v,d=2)=>Number.isFinite(v)?v.toFixed(d):'NA',pc=v=>Number.isFinite(v)?(v*100).toFixed(1)+'%':'NA';
let text='# S26 작업량·지속 시간 확장 — 실행과 한계\n\n';
text+='원 G004와 분리한 새 stream1·초기 이력0·MIX·최대3슬롯의 개발 진단이다. 128/16초,512/64초,2048/256초,혼잡2048/64초를 같은 납기(.8/2초)·계수·동결 공통배정기로 비교했다. RL/물리fit/기기실행0이며 보정 범위 안에서도 새3자원 전이의 실기기 정확도가 입증된 것은 아니다.\n\n';
text+='## 실행·검증\n\n';
text+=`START ${terminal.started} = 저장완료 ${terminal.complete} + 보존실패 ${terminal.fail}. 새 비교36 중 ${summary.rows.filter(r=>r.status==='COMPLETE').length}건 저장완료, ${failed.filter(r=>r.kind==='COMPARISON').length}건 계산실패다. 순수12,984/forecast60, 실제 정확P05건과 EDF128공개상태 귀납검증, 저장검산${audit.checks}·공개digest${audit.publicDigests} 및 Python 독립 에너지${audit.independent.checks}검사 PASS다. 계산 검산은 물리 타당성 검증이 아니다.\n\n`;
text+='P0 EDF1은 root agent가 봉인 후 후처리 파일을 수정하여 모델 생성 전 SHA 검사에서 실패했다. 원 파일을 등록 당시 SHA로 복원했고 완료4건/실패1건을 보존했다. 미시작37만 복구했으며 failed EDF 환경은 재실행하지 않았다. 마지막 실제 ATC P0 trace를 저장 EDF와 전량 대조하고 각 공개 상태에서 EDF가 같은 행동을 선택함을 별도 귀납 증거로 남겼다. 원6개 환경이 모두 정상 실행됐다고 보고하지 않는다.\n\n';
text+='## LOW의 공급 시간 확대\n\n각 행 단일 입력/초기 이력/stream이다. 작업시간은 첫 도착35초부터 마지막 AVAILABLE까지이고, 기저 비중은 같은 전체 관측창의 총소비 대비다.\n\n';
text+='|요청/공급초|정책|실제 작업초|정시/전체|전체 API-J|기저 비중|초과 API-J|분류NPU 비중|peak AP℃|\n|---|---|---:|---:|---:|---:|---:|---:|---:|\n';
for(const r of summary.rows.filter(r=>r.model==='LOW'&&r.input!=='DENSE64'))text+=`|${r.n}/${r.duration_s}|${r.policy}|${f(r.work_span_s)}|${r.on_time}/${r.planned}|${f(r.total_API_J)}|${pc(r.baseline_fraction)}|${f(r.above_baseline_API_J)}|${pc(r.NPU_share)}|${f(r.AP_peak)}|\n`;
text+='\n## 모든36조건\n\n';
text+='|입력|가정|정책|상태|완료/전체|정시/전체|전체 API-J|기저%|평균 공급 AP℃|peak AP℃|AP표본범위|\n|---|---|---|---|---:|---:|---:|---:|---:|---:|---|\n';
for(const r of summary.rows)text+=`|${r.input}|${r.model}|${r.policy}|${r.status==='COMPLETE'?'실행완료':'계산실패'}|${r.status==='COMPLETE'?r.completed+'/'+r.planned:'NA'}|${r.status==='COMPLETE'?r.on_time+'/'+r.planned:'NA'}|${f(r.total_API_J)}|${pc(r.baseline_fraction)}|${f(r.AP_supply_mean)}|${f(r.AP_peak)}|${r.status==='COMPLETE'?(r.AP_outside_fit?'범위 밖':'범위 안'):'NA'}|\n`;
text+='\n## 해석과 계산실패\n\n';
text+='화면0.5초 표본 중 최고 AP의 모형항 분해(AP_TERM_DIAGNOSIS.json)는 실제 칩별 발열 분해가 아니다. 원벽시계 POST 대리변수는 CPU서비스 대기 중에도 유지되므로 해당 항이 장시간 예측을 지배하는지 확인한다.\n\n';
text+='|입력/가정/정책|곡선 최고 AP℃|초기 AP℃|초기이력항℃|POST벽시계항℃|그 외 활동항℃|\n|---|---:|---:|---:|---:|---:|\n';
for(const r of terms)text+=`|${r.input}/${r.model}/${r.policy}|${f(r.predicted_AP_C)}|${f(r.anchor_AP_C)}|${f(r.initial_history_contribution_C)}|${f(r.post_wall_proxy_C)}|${f(r.predicted_AP_C-r.anchor_AP_C-r.initial_history_contribution_C-r.post_wall_proxy_C)}|\n`;
text+='\n';
text+='공통 기저 비중은 감소하지만 같은 입력의 절대 J 차이를 만들어내는 항은 아니다. EDF/ATC의 전량 trace 동률 여부는 EDF_ATC_TRACE_COMPARISON.json에 기록했다. 총/기저초과/요청당/공급창/자기완료창/공통완료창·긴급/일반 정시·미완료는 SUMMARY.csv에 남겼다. 어느 정책이 미완료면 세 정책 공통 완료창은 NA다.\n\n';
text+='AP 보정표본은26~46.6℃다. 범위 밖 예측, 납기 손해와 서로 다른 완료량이 있는 큰 차이를 실제 절감 성과로 채택하지 않는다. 더 긴 부하에서 AP 피드백/공유CPU 가정의 불확실성이 커진다. 후보 rollout이 등록 관측 종료를 넘겨 예외가 난 조건은 정책 실행 중 계산실패이며 실제 기기에서 처리 불가능하다는 증거가 아니다. 중단 조건은 실패 당시 부분상태를 보존했고 제로 에너지/제로 정시로 대체하지 않았다.\n\n';
text+='|실패 identity|원인|중단시각|중단당시 완료/예정|\n|---|---|---:|---:|\n';
for(const r of failed)text+=`|${r.id}|${r.reason}|${f(r.time_at_stop_s)}|${r.completed_at_stop===null?'NA':r.completed_at_stop+'/'+r.planned}|\n`;
text+='\n다음은 공유CPU 실제 서비스/대기와 pair/triple 근거, 지원 밖 AP·후보 horizon 실패 처리의 별도 새 모델/정책 계약 검증이다. 이번 입력으로 계수나 정책을 재선정하지 않았고, 실패 identity의 대체seed/재수집도 없다. 새 RL은 이 검증 뒤의 별도 범위다.\n';
fs.writeFileSync(path.join(dir,'FINAL_REPORT_KO.md'),text);
C.write(path.join(dir,'FINAL_HANDOFF_PROOF.json'),{status:'LOCAL_EXPERIMENT_AND_SAVED_AUDIT_FINISHED_WITH_FAILURES_RETAINED',source:C.pin(__filename),postprocess_operation_sha256:C.sha(fs.readFileSync(path.join(dir,'POSTPROCESS_OPERATION.json'))),report:C.pin(path.join(dir,'FINAL_REPORT_KO.md')),summary:C.pin(path.join(dir,'SUMMARY.json')),CSV:C.pin(path.join(dir,'SUMMARY.csv')),audit:C.pin(path.join(dir,'AUDIT.json')),failures:C.pin(path.join(dir,'FAILURES.json')),AP_terms:C.pin(path.join(dir,'AP_TERM_DIAGNOSIS.json')),trace_comparison:C.pin(path.join(dir,'EDF_ATC_TRACE_COMPARISON.json')),START:terminal.started,COMPLETE:terminal.complete,FAIL:terminal.fail,comparison_cases:36,comparison_complete:summary.rows.filter(r=>r.status==='COMPLETE').length,new_RL:0,new_fit:0,physical_policy_advantage_proven:false,failed_identity_retry:false});
console.log(JSON.stringify({status:'FINAL_REPORT_WRITTEN',started:terminal.started,complete:terminal.complete,fail:terminal.fail,science_complete:summary.rows.filter(r=>r.status==='COMPLETE').length,trace_comparisons:ties.length,report:path.join(dir,'FINAL_REPORT_KO.md')}));
