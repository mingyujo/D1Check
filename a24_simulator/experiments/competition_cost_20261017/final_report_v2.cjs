// Independent saved arithmetic + correlated-transfer sensitivity + offline report.
const fs=require('fs'),path=require('path'),c=require('crypto');
const root=path.resolve(__dirname,'../..'),dir=path.join(root,'results/COMPETITION_COST_REPORT_V2_20261017_01');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),pin=p=>{let b=fs.readFileSync(p);return {path:path.relative(root,p).replaceAll('\\','/'),sha256:c.createHash('sha256').update(b).digest('hex'),bytes:b.length};};
const write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const resultPath=root+'/results/COMPETITION_COST_COMPARISON_20261017_01/RESULT.json',x=read(resultPath),model=read(root+'/results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),cv=read(root+'/results/STATE_COST_IDENTIFICATION_20261017_01/VALIDATION.json'),native=read(root+'/results/STATE_COST_IDENTIFICATION_20261017_01/NATIVE_RELATIVE_MODEL.json');
const sourcePin=pin(__filename),inputs=[path.join(__dirname,'report_ui.js'),resultPath,root+'/results/COMPETITION_COST_COMPARISON_20261017_01/COMPLETE.json',root+'/results/STATE_COST_IDENTIFICATION_20261017_01/COMPLETE.json',root+'/results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json',root+'/results/STATE_COST_IDENTIFICATION_20261017_01/VALIDATION.json',root+'/results/STATE_COST_IDENTIFICATION_20261017_01/NATIVE_RELATIVE_MODEL.json',root+'/results/COMPETITION_WITNESS_V2_20261017_01/RESULT.json',root+'/results/COMPETITION_WITNESS_V2_20261017_01/COMPLETE.json',root+'/results/COMPETITION_INPUTS_20261017_01/INPUTS.json',path.join(__dirname,'WITNESS_V2_INPUTS.json')].map(pin);
if(fs.existsSync(dir))throw Error('Consumed report output');
fs.mkdirSync(dir);write(dir+'/OPERATION.json',{schema:'A24-competition-cost-report-operation-v1',sourcePin,inputs,new_START:0,automatic_retry:false,method:'analytic convolution integral; shared state coefficients for paired sensitivity; preserve preceding conservative independent-policy bound'});
let checks=0;const need=(q,label)=>{if(!q)throw Error(label);checks++;},close=(a,b,label)=>need(Math.abs(a-b)<1e-8,label);
need(read(root+'/results/COMPETITION_COST_COMPARISON_20261017_01/COMPLETE.json').result_sha256===pin(resultPath).sha256,'Analysis terminal SHA');
need(read(root+'/results/COMPETITION_WITNESS_V2_20261017_01/COMPLETE.json').result_sha256===pin(root+'/results/COMPETITION_WITNESS_V2_20261017_01/RESULT.json').sha256,'Witness terminal SHA');
const witness=read(root+'/results/COMPETITION_WITNESS_V2_20261017_01/RESULT.json');
const afterMask={dispatch:0,multiple_request_candidates:0,single_request_candidate:0,critical_calls:0,removed_action_occurrences:0};
for(const cc of witness.cases)for(const b of cc.rows[1].protection_decisions){
 afterMask.critical_calls+=b.protection.critical_request!==null;afterMask.removed_action_occurrences+=b.protection.removed_actions;
 if(b.action.kind!=='DISPATCH')continue;
 const ids=new Set(b.mask.slice(0,72).flatMap((v,i)=>v?[Math.floor(i/3)]:[]));
 need(ids.size>=1,'dispatch candidate after mask');afterMask.dispatch++;
 afterMask[ids.size>1?'multiple_request_candidates':'single_request_candidate']++;
}
x.competition_after_mask=afterMask;
const states=model.supported_states,beta=model.coefficients_W_proxy,lookup=Object.fromEntries(states.map((s,i)=>[s,beta[i]]));lookup.detection_GPU=.6013808404579677;
const F=(s,tau)=>s<=0?0:tau?s-tau*(-Math.expm1(-s/tau)):s;
function verify(row,m,lo,hi){
 const edges=[...new Set([0,210,...row.gantt.flatMap(g=>[g.start_s,g.end_s])])].sort((a,b)=>a-b),segments=[];
 for(let i=1;i<edges.length;i++){
  const a=edges[i-1],b=edges[i],active=row.gantt.filter(g=>g.start_s<b&&g.end_s>a);need(active.length<=2,'max2');need(new Set(active.map(g=>g.route)).size===active.length,'exclusive resources');
  const s=active.map(g=>(g.task==='C'?'classification':'detection')+'_'+g.route).sort().join('+')||'idle';segments.push({a,b,s});
 }
 let supported=0,transfer=0;const unknown={};
 for(let {a,b,s} of segments){
  if(states.includes(s))supported+=lookup[s]*(F(hi-a,model.tau_s)-F(hi-b,model.tau_s)-F(lo-a,model.tau_s)+F(lo-b,model.tau_s));
  else if(s!=='idle'){
   const seconds=Math.max(0,Math.min(hi,b)-Math.max(lo,a)),power=s.split('+').reduce((v,k)=>v+lookup[k],0);
   if(seconds){transfer+=seconds*power;unknown[s]=(unknown[s]||0)+seconds;}
  }
 }
 const n=m.new_state_cost;close(supported,n.supported_increment_J_proxy,'independent convolution integral');close(transfer,n.transferred_increment_J_proxy,'independent transferred cost');close(n.baseline_J_proxy,1.204399931712509*(hi-lo),'same baseline');close(n.total_J_proxy,n.baseline_J_proxy+supported+transfer,'total telescope');
 const responded=row.requests.filter(q=>q.response_ns!==null);need(responded.filter(q=>q.response_ns<=q.deadline_ns).length===m.on_time,'deadline denominator');need(responded.length+m.missing===m.planned,'missing denominator');
 const t=row.AP.t_s,y=row.AP.ap_c,interp=v=>{let i=t.findIndex(q=>q>=v);if(t[i]===v)return y[i];return y[i-1]+(y[i]-y[i-1])*(v-t[i-1])/(t[i]-t[i-1]);};
 const ts=[lo,...t.filter(a=>a>lo&&a<hi),hi],vals=ts.map(interp);let area=0;for(let i=1;i<ts.length;i++)area+=(ts[i]-ts[i-1])*(vals[i]+vals[i-1])/2;
 close(area/(hi-lo),m.mean_AP_c,'independent AP integral');close(Math.max(...vals),m.peak_AP_c,'independent peak');
 return {supported,unknown};
}
const fixedInterval=(known,deltas)=>{let lo=known,hi=known;for(let [state,delta] of Object.entries(deltas)){let v=2*state.split('+').reduce((v,k)=>v+lookup[k],0)*delta;lo+=Math.min(v,0);hi+=Math.max(v,0);}return [lo,hi];};
need(JSON.stringify(fixedInterval(0,{detection_GPU:0}))==='[0,0]','identical trace sensitivity cancels');
for(let cc of x.cases){
 const w=witness.cases.find(t=>t.index===cc.index),[lo,hi]=cc.window_s,proof=w.rows.map((r,i)=>verify(r,cc.metrics[i],lo,hi));let d={};
 for(let s of new Set(proof.flatMap(a=>Object.keys(a.unknown))))d[s]=(proof[1].unknown[s]||0)-(proof[0].unknown[s]||0);
 cc.delta.shared_state_cost_sensitivity_delta=fixedInterval(proof[1].supported-proof[0].supported,d);
 cc.delta.shared_state_cost_sensitivity_method='Same unknown state coefficient across EDF/RL; bounds0..2x additive transfer, not CI. Previous independent-policy envelope retained in source result.';
 need(cc.delta.shared_state_cost_sensitivity_delta[0]<=cc.delta.total_J_proxy+1e-8&&cc.delta.shared_state_cost_sensitivity_delta[1]>=cc.delta.total_J_proxy-1e-8,'nominal inside sensitivity');
}
const aggregate=policy=>{let m=x.cases.map(s=>s.metrics.find(r=>r.policy===policy)),mean=k=>m.reduce((s,v)=>s+k(v),0)/m.length;return {policy,on_time:m.reduce((s,v)=>s+v.on_time,0),planned:m.reduce((s,v)=>s+v.planned,0),urgent_on_time:m.reduce((s,v)=>s+v.by_priority.U.on_time,0),urgent_planned:48,missing:m.reduce((s,v)=>s+v.missing,0),old_total_J:mean(v=>v.total_J_proxy),total_J:mean(v=>v.new_state_cost.total_J_proxy),increment_J:mean(v=>v.new_state_cost.increment_J_proxy),baseline_J:mean(v=>v.new_state_cost.baseline_J_proxy),mean_AP:mean(v=>v.mean_AP_c),peak_AP:mean(v=>v.peak_AP_c),P95:mean(v=>v.P95_completed_response_s)};};
x.aggregate=['EDF_CPU_FIRST','ROLLING_ATC_RL_PROTECTED48'].map(aggregate);x.cost_validation=cv.scores;x.native_validation=native.scores;x.native_support=native.model.support;x.conditional_tau_s=model.tau_s;x.audit_checks=checks;
write(dir+'/PRESENTATION_DATA.json',x);write(dir+'/ARITHMETIC_AUDIT.json',{status:'PASS_INDEPENDENT_SAVED_ARITHMETIC',checks,sourcePin,inputs,new_START:0,measured_J:null,correlated_sensitivity_preserves_identical_trace_zero:true});
const data=JSON.stringify(x).replaceAll('<','\\u003c');
const html=`<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>A24 입력·비용 보완 비교</title><style>
:root{color-scheme:light dark;--bg:#f4f6fa;--card:white;--text:#172b3a;--muted:#536b7c;--border:#d6e0e8;--accent:#147a73;--bad:#9e4f19}*{box-sizing:border-box}body{font:15px/1.65 system-ui,'Malgun Gothic',sans-serif;background:var(--bg);color:var(--text);margin:0}main{max-width:1200px;margin:auto;padding:30px 22px 60px}h1{font-size:30px;margin:6px 0}h2{font-size:19px;margin:0 0 10px}p{margin:8px 0}.eyebrow{color:var(--accent);font-weight:750;letter-spacing:.08em;font-size:12px}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:22px 0}.card,section{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px}.big{font-size:29px;font-weight:750;letter-spacing:-1px}.note{border-left:4px solid var(--bad);padding:10px 16px;background:var(--card);margin:18px 0}section{margin:16px 0}label{font-weight:650;display:block;margin:12px 0 6px}select,button{font:inherit;padding:9px 12px;border:1px solid var(--border);border-radius:7px;background:var(--card);color:inherit;max-width:100%}.tablewrap{overflow:auto;max-width:100%}table{width:100%;border-collapse:collapse;white-space:nowrap}th,td{padding:10px 12px;border-bottom:1px solid var(--border);text-align:right}th:first-child,td:first-child{text-align:left}th{font-size:13px;color:var(--muted)}.win{color:var(--accent)}.warn{color:var(--bad)}svg{width:100%;height:auto}.controls>div{min-width:0}.controls{display:grid;grid-template-columns:2fr 1fr;gap:18px}.pill{display:inline-block;background:var(--bg);border:1px solid var(--border);padding:3px 9px;border-radius:30px;font-size:12px;margin:3px}details{padding:10px 0}a{color:var(--accent)}#inputPreview{max-height:300px;overflow:auto;font-size:13px}.legend{display:flex;gap:18px}.edf{color:#3977b7}.rl{color:#d57731}footer{font-size:12px;color:var(--muted);margin-top:25px}@media(prefers-color-scheme:dark){:root{--bg:#101b26;--card:#192936;--text:#e1ebf4;--muted:#a3bacb;--border:#344b5e;--accent:#67cdb7;--bad:#f5b173}}@media(max-width:700px){main{padding:20px 12px}h1{font-size:24px}.grid,.controls{grid-template-columns:1fr}.card,section{padding:15px}.big{font-size:26px}}
</style><main><div class="eyebrow">A24 · INPUT & COST DEVELOPMENT · 2026.10.17</div><h1>입력 선택 경쟁과 비용 모형을 보완했어</h1><p class="muted">동일한 A24 처리시간·열 모형, 동일한 입력과 작업 구간에서 EDF와 고정 롤링+ATC+RL을 비교한 4개 진단 조건.</p><div class="grid"><div class="card"><div class="muted">마스크 후 복수 요청 선택 가능</div><div class="big">34.1% → 45.3%</div><p>대기열의 복수 후보는 56.3%, 실제 마스크 뒤에도 87/192회 선택 여지가 남았어.</p></div><div class="card"><div class="muted">과거 전력 투영 예측 오차</div><div class="big">−37.98%</div><p>35세션 묶음 검증. 같은 기저 보정만 한 모형 대비 추가 −6.18%.</p></div><div class="card"><div class="muted">새 실측 상대 전류 응답 오차</div><div class="big">−14.61%</div><p>71세션·23cohort 검증. 단위 환산 없이 실행 전 전류 대비 비율을 사용.</p></div></div>
<div class="note"><strong>정책 우수성 목표는 아직 미달이야.</strong> 두 정책 모두 185/192 정시, 전량 응답·완료. RL은 긴급 46/48(EDF45/48), 평균 AP는 낮아졌지만 새 명목 비용의 평균은 소폭 늘었어. 미측정 GPU 비용 때문에 실제 에너지 우위는 확정할 수 없어.</div>
<section><h2>같은 작업 구간의 비교</h2><div class="controls"><div><label for="condition">입력 조건</label><select id="condition"><option value="all">4조건 평균 / 전체 분모</option></select></div><div><label for="observer">비용 관측식</label><select id="observer"><option value="new">보완 상태·잔류 응답 J*</option><option value="old">이전 고정 점유식 J*</option><option value="native">새 실측 상대 전류 지수</option></select></div></div><p id="window" class="muted"></p><div class="tablewrap"><table><thead id="thead"></thead><tbody id="tbody"></tbody></table></div><p id="sensitivity" class="muted"></p><p>총소비 = 같은 구간의 기저 + 작업 증분. J*는 역사 자료의 조건부 비용 예측이며 교정 실측 J가 아니야. 상대 전류 지수와 J*를 합산하지 않아.</p></section>
<section><h2>관측 범위와 원인</h2><p>확인된 CC·CG·DC·CG+DC는 상태별 계수와 인과적 0.9초 응답을 사용해. 이 0.9초가 센서 주기와 가까워 물리적 잔류 소비와 센서 지연은 아직 분리되지 않았어.</p><p>D_GPU 및 미측정 병행에는 같은 할인값을 복사하지 않아. 명목 가산 전이와 공유 계수 민감도를 표시해. 새 실측 상대 전류는 해당 경로 지원이 없으면 <strong>미검증</strong>으로 보여. CPU/GPU 배정 자체를 막지는 않았어.</p><p>이번 RL은 이전 비용 모형으로 학습한 EP024를 고정했어. 새 모형으로 재학습하지 않았고, 온도→처리속도/전력 피드백도 추가하지 않았어. 더 많은 선택 경쟁이 자동으로 RL 우위를 보장하지 않는다는 결과까지 보존했어.</p><details><summary>정확한 검증·실패·예산 경계</summary><p>입력 정적80, 비용 순수21/AST7, 8환경의 원장·NN·저장 검사. 첫 입력op 필수 등록 필드 누락으로 START1/FAIL1을 보존하고 seed퇴역. V2 새seed20261741은 8/8완료. 기존502+실패1+새8=공유511/512, 남은1. 추가 학습/기기/예약·주기조회0. 과거 확인 자료를 쓴 사후 검증이며 독립 새 실측 확인이 아니야. 4개 조건은 결과 전 입력으로만 골랐고 모든 손해·미완료 분모를 유지했어.</p></details></section>
<section><h2>새 입력을 직접 사용하기</h2><p>여러 작업·긴급/일반·3단계 납기 여유·두 파형을 함께 구성한 고정 목록이야. 아래 목록을 다운로드하면 기존 통합 시뮬레이터의 JSON 입력으로 사용할 수 있어. 이 화면은 저장된 검증 결과를 읽으며 새로운 실험을 자동 실행하지 않아.</p><label for="inputSelect">입력 목록</label><select id="inputSelect"></select> <button id="download">입력 JSON 저장</button><details><summary>요청 목록 보기</summary><div id="inputPreview" class="tablewrap"></div></details></section><footer>실측 J·에너지 오차·CI: null · 폰 RL/물리 절감 검증: 미완료 · 예약 OFF · ${sourcePin.sha256.slice(0,16)}<br>소스·모형·원자료·결과: GitHub a24_simulator/docs/COMPETITION_COST_DEVELOPMENT.md</footer></main><script>const D=${data};const I=__INPUTS__;__SCRIPT__</script></html>`;
const allInputs=read(root+'/results/COMPETITION_INPUTS_20261017_01/INPUTS.json'),fresh=read(root+'/experiments/competition_cost_20261017/WITNESS_V2_INPUTS.json');
const options=[...allInputs.developmental.map(c=>({...c,role:'개발 정적'})),...allInputs.confirmation.map(c=>({...c,role:'원 확인 입력·seed퇴역/미실행'})),...fresh.cases.map(c=>({...c,role:'실제 검증 V2'}))];
const script=fs.readFileSync(path.join(__dirname,'report_ui.js'),'utf8');
fs.writeFileSync(dir+'/REPORT.html',html.replace('__INPUTS__',JSON.stringify(options).replaceAll('<','\\u003c')).replace('__SCRIPT__',script),{flag:'wx'});
write(dir+'/COMPLETE.json',{status:'SAVED_REPORT_AND_ARITHMETIC_COMPLETE',presentation_pin:pin(dir+'/PRESENTATION_DATA.json'),HTML_pin:pin(dir+'/REPORT.html'),audit_pin:pin(dir+'/ARITHMETIC_AUDIT.json'),actual_browser_QA:'PENDING',utc:new Date().toISOString()});
console.log(JSON.stringify({checks,aggregate:x.aggregate,HTML:pin(dir+'/REPORT.html')}));
