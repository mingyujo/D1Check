'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const W=__dirname,O=path.resolve(W,'../../outputs/S26-FAIR-RESOURCE-COMPARE-20261016');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const mean=a=>a.reduce((s,v)=>s+v,0)/a.length,range=a=>[Math.min(...a),Math.max(...a)],tol=2e-8;
const policies=['FIFO_FREE_ROUTE_V1','EDF_FREE_ROUTE_V1','ROLLING_ATC_ROUTE_V2'];
const label={FIFO_FREE_ROUTE_V1:'FIFO 자동배정',EDF_FREE_ROUTE_V1:'EDF 자동배정',ROLLING_ATC_ROUTE_V2:'우리 롤링+ATC 자동배정'};
function main(){
 const audit=read(path.join(O,'AUDIT/RESULT.json'));if(audit.status!=='PASS')throw Error('Full audit not PASS');
 const out=path.join(O,'ANALYSIS_V1');fs.mkdirSync(out);
 const pr=read(path.join(O,'PRODUCTION_OPERATION.json'));
 const rows=fs.readFileSync(path.join(pr.output_dir,'ROWS.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse).filter(r=>r.phase==='FAIR_RESOURCE');
 const refs=read(path.join(O,'REUSED_OWN_CASES.json'));rows.push(...refs.map(x=>x.row));
 const cases=rows.map(r=>{if(sha(r.raw_path)!==r.raw_sha256)throw Error('Raw changed after audit');const raw=read(r.raw_path),draw=Number(r.logical_identity.match(/DRAW(\d+)$/)[1]);return{
  id:r.logical_identity,policy:r.policy,scenario:r.scenario,bank:r.scenario.includes('SMOOTH')?'SMOOTH128':'M128',block:r.scenario.split('-')[0],draw,stream:r.config.stream,
  hard_feasible:r.hard_feasible,completed:r.service.all.completed,on_time:r.service.all.on_time,urgent_on_time:r.service.urgent.on_time,normal_on_time:r.service.normal.on_time,p95:r.service.all.p95_s,urgent_p95:r.service.urgent.p95_s,normal_p95:r.service.normal.p95_s,
  J:r.J_API0_180,AP:r.AP35_180_mean,peak:r.AP_peak_sampled,AP180:r.AP180,unfinished:r.unfinished,tardiness:r.tardiness_s,wait_s:r.wait_s,route_counts:raw.policy_route_counts,
  owner_overlap_s:raw.activity[8].reduce((s,[a,b,w])=>s+(b-a)*w,0),raw_sha256:r.raw_sha256,raw_path:r.raw_path};});
 if(cases.length!==144)throw Error('Expected144 main cases');
 function summarize(a){return{cases:a.length,hard_feasible:a.filter(x=>x.hard_feasible).length,completed_total:a.reduce((s,x)=>s+x.completed,0),planned_total:a.length*128,on_time_total:a.reduce((s,x)=>s+x.on_time,0),on_time_rate:mean(a.map(x=>x.on_time))/128,urgent_on_time_rate:mean(a.map(x=>x.urgent_on_time))/96,normal_on_time_rate:mean(a.map(x=>x.normal_on_time))/32,
  ...Object.fromEntries(['J','AP','peak','AP180','unfinished','tardiness','wait_s','owner_overlap_s','p95','urgent_p95','normal_p95'].map(k=>[k,{mean:mean(a.map(x=>x[k])),range:range(a.map(x=>x[k]))}])),route_counts:Object.fromEntries(['classification_CPU','classification_GPU','classification_NPU','detection_CPU'].map(r=>[r,a.reduce((s,x)=>s+(x.route_counts[r]??0),0)]))};}
 const summaries=policies.map(policy=>({policy,...summarize(cases.filter(r=>r.policy===policy))}));
 const strata=['M128','SMOOTH128'].flatMap(bank=>policies.map(policy=>({bank,policy,...summarize(cases.filter(r=>r.policy===policy&&r.bank===bank))})));
 const pairs=[];
 for(const own of cases.filter(x=>x.policy===policies[2]))for(const policy of policies.slice(0,2)){
  const ref=cases.find(x=>x.policy===policy&&x.scenario===own.scenario&&x.stream===own.stream);if(!ref)throw Error('Unmatched case');
  pairs.push({baseline:policy,scenario:own.scenario,bank:own.bank,block:own.block,draw:own.draw,stream:own.stream,own_id:own.id,baseline_id:ref.id,
   own_feasible:own.hard_feasible,baseline_feasible:ref.hard_feasible,J_reduction:ref.J-own.J,J_reduction_percent:100*(ref.J-own.J)/ref.J,AP_reduction:ref.AP-own.AP,peak_reduction:ref.peak-own.peak,residual_reduction:ref.AP180-own.AP180,
   own_wait_s:own.wait_s,baseline_wait_s:ref.wait_s,own_on_time:own.on_time,baseline_on_time:ref.on_time,own_overlap_s:own.owner_overlap_s,baseline_overlap_s:ref.owner_overlap_s});
 }
 function band(a,key){const draws=[...new Set(a.map(x=>x.draw))].sort((a,b)=>a-b);const vectors=draws.map(d=>mean(a.filter(x=>x.draw===d).map(x=>x[key])));let state=26101671;const rnd=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296};const boot=Array.from({length:2000},()=>mean(vectors.map(()=>vectors[Math.floor(rnd()*vectors.length)]))).sort((a,b)=>a-b);return[boot[49],boot[1949]];}
 function contrast(a){const baseline=summaries.find(s=>s.policy===a[0].baseline),own=summaries[2];return{
  baseline:a[0].baseline,cases:a.length,J_reduction_mean:mean(a.map(x=>x.J_reduction)),J_reduction_range:range(a.map(x=>x.J_reduction)),J_reduction_percent_ratio_of_means:100*(baseline.J.mean-own.J.mean)/baseline.J.mean,
  AP_reduction_mean:mean(a.map(x=>x.AP_reduction)),AP_reduction_range:range(a.map(x=>x.AP_reduction)),J_conditional_MC_band:band(a,'J_reduction'),AP_conditional_MC_band:band(a,'AP_reduction'),
  joint_better:a.filter(x=>x.J_reduction>tol&&x.AP_reduction>tol).length,joint_no_worse:a.filter(x=>x.J_reduction>=-tol&&x.AP_reduction>=-tol).length,energy_worse:a.filter(x=>x.J_reduction< -tol).length,AP_worse:a.filter(x=>x.AP_reduction< -tol).length,ties:a.filter(x=>Math.abs(x.J_reduction)<=tol&&Math.abs(x.AP_reduction)<=tol).length,
  own_feasible:a.filter(x=>x.own_feasible).length,baseline_feasible:a.filter(x=>x.baseline_feasible).length};}
 const contrasts=policies.slice(0,2).map(p=>contrast(pairs.filter(x=>x.baseline===p)));
 const result={status:'PASS',meaning:'FAIR_RESOURCE_FIXED_POLICY_DEVELOPMENT_COMPARISON_NOT_PHONE_VALIDATION',created_utc:new Date().toISOString(),audit_sha256:sha(path.join(O,'AUDIT/RESULT.json')),summaries,strata,contrasts,
  conditional_band_method:'2000 bootstrap resamples of8 draw vectors shared across6 fixed scenario contexts; Monte Carlo-conditional summary, not independent phone samples or parameter/physical uncertainty',
  same_packet_sha256:sha(pr.packet_path),physical_model_changed:false,own_policy_changed:false,new_policy_environments:104,reused_own_cases:48,new_RL:0,new_fit:0,all_losses_retained:true,comparator_selection_after_results:false,
  limitation:'Same observed DEV recipe/model population; AP-temperature transfer remains an association assumption; API J not external-meter calibrated; original R21 absolute accuracy errors remain.'};
 fs.writeFileSync(path.join(out,'SUMMARY.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
 const csv=(file,data)=>{const keys=Object.keys(data[0]).filter(k=>!['route_counts'].includes(k));fs.writeFileSync(path.join(out,file),keys.join(',')+'\n'+data.map(r=>keys.map(k=>JSON.stringify(r[k]??null)).join(',')).join('\n')+'\n',{flag:'wx'})};
 csv('CASE_METRICS.csv',cases);csv('PAIRED_DELTAS.csv',pairs);
 fs.writeFileSync(path.join(out,'CASE_PROVENANCE.json'),JSON.stringify(cases.map(x=>({id:x.id,raw_sha256:x.raw_sha256,raw_path:x.raw_path})),null,2)+'\n',{flag:'wx'});
 let md='# S26 동일 자원 FIFO·EDF·롤링 ATC 비교\n\n2026-10-16. 세 정책 모두 분류CPU/GPU/NPU·탐지CPU, 같은 명목 납기/열/에너지 자원 선택기, 동일 병행·WAIT 조건을 사용했다. 각48조건/128요청, 부하2×초기이력3×합성표본8이다. 요청별 입력/잠재처리 표본과 물리계수는 불변이다.\n\n';
 md+='| 정책 | 기한 내 처리율 | 전량·납기 충족 조건 | API J0~180 평균 | AP35~180 평균 | WAIT 평균 |\n|---|---:|---:|---:|---:|---:|\n';
 for(const s of summaries)md+=`| ${label[s.policy]} | ${(100*s.on_time_rate).toFixed(4)}% | ${s.hard_feasible}/48 | ${s.J.mean.toFixed(9)}J | ${s.AP.mean.toFixed(9)}℃ | ${s.wait_s.mean.toFixed(6)}s |\n`;
 md+='\n절감은 비교군−우리 정책이며 음수는 우리 정책의 손해다.\n\n| 비교 기준 | 추가 J 감소 | 에너지 감소율 | 추가 AP 감소 | 에너지 손해 조건 | AP 손해 조건 |\n|---|---:|---:|---:|---:|---:|\n';
 for(const c of contrasts)md+=`| ${label[c.baseline]} | ${c.J_reduction_mean.toFixed(9)}J | ${c.J_reduction_percent_ratio_of_means.toFixed(6)}% | ${c.AP_reduction_mean.toFixed(9)}℃ | ${c.energy_worse}/48 | ${c.AP_worse}/48 |\n`;
 md+='\n## 부하별 결과\n\n| 부하 | 정책 | 납기 충족 조건 | 평균 API J | 평균 AP |\n|---|---|---:|---:|---:|\n';for(const s of strata)md+=`| ${s.bank} | ${label[s.policy]} | ${s.hard_feasible}/24 | ${s.J.mean.toFixed(9)} | ${s.AP.mean.toFixed(9)} |\n`;
 md+='\n## 비교 계약과 검증\n\nFIFO/EDF는 시작 가능한 ready 요청 중 도착순/절대기한순이다. 자원 선택 규칙은 원 롤링 정책의 명목 후보/손해 필터/에너지+열 점수를 공유하며, 불가능한 head 때문에 가능한 다른 작업을 강제로 유휴시키지 않는다. 우리 정책은 원48개 raw를 SHA로 검증하여 재사용했고 재실행하거나 재튜닝하지 않았다. 새104환경(수치8+비교96)과 재사용48개를 전수 감사했다. 저장 공개입력/후보/마스크/행동·응답·원장·SHA 및 독립 Python 고정비용 재적분152건을 검증했다.\n\n원 AP/API 모형과 실측 재현 오차는 그대로다. 이 결과는 현재 모형·부하에서의 조건부 개발 비교이며 실제 폰 절감·모형 정확도·RL 효과 인증이 아니다. CPU/GPU/NPU 후보를 공유해도 현재 모형이 특정 자원을 반복 선택하는 결과를 강제로 분산하지 않았다.\n\n전체144행과 쌍별96행, route/겹침/WAIT/P95/peak/잔열/모든손해는 CASE_METRICS.csv·PAIRED_DELTAS.csv·SUMMARY.json에 있다. 구간은8 Monte Carlo draw의6고정문맥 벡터를 공동 재표집한 조건부 요약이며 독립 실기기48표본이나 물리모형 전체의95% 신뢰구간이 아니다.\n';
 fs.writeFileSync(path.join(out,'REPORT_KO.md'),md,{flag:'wx'});
 console.log(JSON.stringify({status:'PASS',summaries:summaries.map(s=>({policy:s.policy,feasible:s.hard_feasible,J:s.J.mean,AP:s.AP.mean,routes:s.route_counts})),contrasts},null,2));
}
main();
