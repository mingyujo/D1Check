'use strict';
// Saved-only audit in a separate language. No producer/engine imports.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const H=__dirname,A=path.resolve(H,'../..'),R=path.dirname(A),O=path.join(A,'results/A24_ATC_BC600_20261019_01'),Q=path.join(A,'results/A24_BC_600_20261019_01'),P=path.join(A,'results/A24_DURATION_040_20261019_01');
const read=p=>JSON.parse(p.endsWith('.gz')?zlib.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const save=(n,x)=>fs.writeFileSync(path.join(O,n),JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const {step,integral}=require('../a24_s26_method_20261019/audit.cjs');
let checks=0,maxerr=0;
function ok(v,m){checks++;if(!v)throw Error(m);}
function near(a,b,m,tol=3e-7){maxerr=Math.max(maxerr,Math.abs(a-b));ok(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=tol,`${m}: ${a} != ${b}`);}
const result=read(path.join(O,'RESULT.json')),op=read(path.join(H,'OPERATION.json'));
ok(result.START===2&&result.COMPLETE+result.FAIL===2,'Two new START only');
for(const p of op.pins){const f=path.join(R,p.path);ok(sha(f)===p.sha256&&fs.statSync(f).size===p.bytes,'Registered source/input '+p.path);}
const allReceipts=fs.readFileSync(path.join(O,'receipts.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
ok(allReceipts.filter(r=>r.kind==='FIT'&&r.event==='START').length===1,'One BC fit');
const receipts=allReceipts.filter(r=>r.kind==='EVAL');
ok(receipts.filter(r=>r.event==='START').length===2,'Two durable START');
ok(receipts.filter(r=>r.event==='COMPLETE').length===result.COMPLETE,'COMPLETE census');
ok(receipts.filter(r=>r.event==='FAIL').length===result.FAIL,'FAIL census');
ok(new Set(receipts.filter(r=>r.event==='START').map(r=>r.start_id)).size===2,'Unique START IDs');
const originals=read(path.join(P,'RESULT.json')).rows.filter(r=>r.condition.supply_s===600);
const all=[...originals.map(r=>({...r,raw:{path:path.relative(R,path.join(P,r.label+'.raw.json.gz')),sha256:r.raw_sha256},reused:true})),...read(path.join(Q,'RESULT.json')).rows.map(r=>({...r,reused:true})),...result.rows.map(r=>({...r,reused:false}))];
ok(all.length===10,'Eight saved comparators and two new ATC BC rows');
let derived=[];
const rawCache=new Map();
for(const row of all){
 const file=path.join(R,row.raw.path);ok(sha(file)===row.raw.sha256,'Stored raw hash');
 const d=read(file);rawCache.set(row.label,d);
 if(row.status==='FAIL'){ok(d.partial_not_complete_trace&&row.metrics===null,'Guard failure not fabricated');derived.push({label:row.label,case:row.case,policy:row.policy,failed:true,failure:row.failure,reused:row.reused,raw:row.raw});continue;}
 const r=d.result,c=d.case,bank=Object.fromEntries(read(path.join(A,'experiments/a24_duration_040_20261019/banks',c.id+'.BANK.json.gz')).jobs.map(j=>[j.request_id,j]));
 const qmap=new Map(r.requests.map(q=>[q.request_id,q])),work=new Map();
 ok(r.requests.length===c.n&&new Set(r.requests.map(q=>q.request_id)).size===c.n,'All arrivals once');
 for(const q of r.requests){const src=c.input.requests[q.ordinal];ok(q.scheduled_arrival_ns===Math.round(src.arrival_s*1e9)&&q.deadline_ns===Math.round(src.deadline_s*1e9)&&q.task===src.profile[0]&&q.priority===src.priority,'Same public requests');ok(q.queue_entry_ns===bank[q.request_id].queue_entry_ns,'Same admission');if(q.route)ok(JSON.stringify(q.timing.stages_ns)===JSON.stringify(bank[q.request_id].routes[q.route].stages_ns),'Same latent route work');}
 let prev=null;
 for(const t of r.trace){
  ok(t.end_ns>t.start_ns,'Positive clock');near(t.dt,(t.end_ns-t.start_ns)/1e9,'dt',1e-12);
  if(prev){ok(t.start_ns===prev.end_ns,'Contiguous clock');near(t.state.temperature_c,prev.next_state.temperature_c,'T continuity',1e-10);const dispatchReset=r.requests.some(q=>q.dispatch_ns===t.start_ns);near(t.state.shared_z,dispatchReset?1:prev.next_state.shared_z,'Tail continuity or explicit dispatch reset',1e-10);}prev=t;
  ok(t.active.filter(j=>j.route==='CPU').length<=3&&t.active.filter(j=>j.route==='GPU').length<=1,'Capacity');
  const a=step(t.state,t.active,t.dt,r.config,'ORIGINAL');near(a.state.temperature_c,t.next_state.temperature_c,'Independent T');near(a.state.shared_z,t.next_state.shared_z,'Independent tail');near(a.J,t.increment,'Independent E');near(a.H,t.temperature_area,'Independent AP area');
  for(const j of t.active){near(a.rates[j.request_id],t.speeds[j.request_id],'Progress rate',1e-12);const q=qmap.get(j.request_id);ok(q&&q.route===j.route&&q.dispatch_ns<=t.start_ns&&(q.available_ns===null||q.available_ns>=t.end_ns),'Nonpreemptive ownership');const k=j.request_id+'|'+j.stage;work.set(k,(work.get(k)||0)+t.dt*a.rates[j.request_id]);}
 }
 for(const q of r.requests)if(q.available_ns!==null){for(let k=0;k<5;k++)near(work.get(q.request_id+'|'+k)||0,q.timing.stages_ns[k]/1e9,'Conserved five-stage work',7e-9);ok(q.response_ns===(q.task==='C'?q.output_ready_ns:q.persist_complete_ns),'C/D response boundary');}
 ok(d.calls.length===r.decisions.length,'Actor call census');let capped=0,forecasts=0;
 for(let i=0;i<d.calls.length;i++){
  const call=d.calls[i],dec=r.decisions[i],s=dec.public_state;
  ok(s.now_ns===dec.time_ns&&s.queue.every(q=>q.queue_entry_ns<=s.now_ns),'Causal visible queue');
  if(dec.action.kind==='DISPATCH')ok(s.queue.some(q=>q.request_id===dec.action.request_id),'Visible dispatch');
  if(call.forecasts){const ids=new Set([...s.queue,...s.owners].map(q=>q.request_id));ok(call.future_information===false&&call.post_NN_override===false,'No future inputs/override');ok(JSON.stringify(call.actions[call.chosen])===JSON.stringify(call.action),'Selected action returned');for(const f of call.forecasts){forecasts++;capped+=Number(f.capped);ok(f.no_future_arrivals&&f.no_future_latents&&f.visible_ids.every(id=>ids.has(id)),'Public forecast IDs');}}
 }
 const service={};for(const p of ['ALL','U','N']){const qs=r.requests.filter(q=>p==='ALL'||q.priority===p),ans=qs.filter(q=>q.response_ns!==null&&q.response_ns<=c.drain_stop_s*1e9),lat=ans.map(q=>(q.response_ns-q.scheduled_arrival_ns)/1e9).sort((a,b)=>a-b);service[p]={n:qs.length,on:ans.filter(q=>q.response_ns<=q.deadline_ns).length,missing:qs.length-ans.length,P95:lat.length?lat[Math.ceil(.95*lat.length)-1]:null,latencies_s:lat};}
 const incomplete=r.requests.filter(q=>q.available_ns===null||q.available_ns>c.drain_stop_s*1e9).length;
 ok(service.ALL.on===row.metrics.on_time&&service.U.on===row.metrics.urgent_on_time&&incomplete===row.metrics.incomplete,'Independent service census');
 near(integral(r,'ORIGINAL',c.drain_stop_s*1e9).J,row.metrics.total_J_proxy,'Producer total J',4e-6);
 const finish=incomplete?null:Math.max(c.supply_stop_s*1e9,...r.requests.map(q=>q.available_ns));
 const own=finish===null?null:integral(r,'ORIGINAL',finish);
 const ownTail=finish===null?null:integral(r,'ORIGINAL',finish+30e9).J-30*r.config.baseline;
 if(row.score&&finish!==null)near(ownTail,row.score.own_with_activity_tail_J,'Own+activity tail',4e-6);
 derived.push({label:row.label,case:c.id,policy:row.policy,pattern:c.condition.pattern_index,reused:row.reused,raw:row.raw,service,incomplete,finish_ns:finish,own,own_tail_J:ownTail,supply:integral(r,'ORIGINAL',c.supply_stop_s*1e9),wait_s:row.metrics.wait_s,route_counts:row.metrics.route_counts,decisions:d.calls.length,capped_forecasts:capped,forecasts});
}
for(const row of derived.filter(r=>!r.failed)){
 const same=derived.filter(r=>r.case===row.case),d=rawCache.get(row.label);
 const end=same.every(r=>!r.failed&&r.finish_ns!==null)?Math.max(d.case.supply_stop_s*1e9,...same.map(r=>r.finish_ns)):d.case.drain_stop_s*1e9;
 row.common_end_ns=end;row.common=integral(d.result,'ORIGINAL',end);
}
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length,groups=[];
for(const policy of ['FIFO_CPU','EDF_CPU','OLD_PPO','BC','ATC_BC']){
 const rr=derived.filter(r=>r.policy===policy),complete=rr.filter(r=>!r.failed),failed=rr.length-complete.length;
 if(failed){groups.push({policy,patterns:rr.length,failed,service:null,common_J:null,AP:null});continue;}
 const service={};for(const p of ['ALL','U','N']){const lat=rr.flatMap(r=>r.service[p].latencies_s).sort((a,b)=>a-b);service[p]={n:rr.reduce((s,r)=>s+r.service[p].n,0),on:rr.reduce((s,r)=>s+r.service[p].on,0),missing:rr.reduce((s,r)=>s+r.service[p].missing,0),mean_session_P95_s:mean(rr.map(r=>r.service[p].P95)),pooled_P95_s:lat.length?lat[Math.ceil(.95*lat.length)-1]:null};}
 groups.push({policy,patterns:rr.length,failed:0,service,common_J:mean(rr.map(r=>r.common.J)),AP:mean(rr.map(r=>r.common.AP)),peak:mean(rr.map(r=>r.common.peak)),supply_J:mean(rr.map(r=>r.supply.J)),own_tail_J:mean(rr.map(r=>r.own_tail_J)),incomplete:rr.reduce((s,r)=>s+r.incomplete,0),wait_s:mean(rr.map(r=>r.wait_s)),capped_forecasts:rr.reduce((s,r)=>s+r.capped_forecasts,0)});
}
const bc=groups.find(g=>g.policy==='ATC_BC'),comparisons=[];
if(!bc.failed)for(const base of groups.filter(g=>g.policy!=='ATC_BC')){
 const per=derived.filter(r=>r.policy==='ATC_BC').map(r=>{const b=derived.find(b=>b.case===r.case&&b.policy===base.policy);return {pattern:r.pattern,joint:r.service.U.on===r.service.U.n&&r.service.ALL.on/r.service.ALL.n>=.95&&r.incomplete===0&&r.service.ALL.missing===0&&['ALL','U','N'].every(k=>r.service[k].on>=b.service[k].on)&&r.common.J<b.common.J&&r.own_tail_J<b.own_tail_J&&r.common.AP<b.common.AP&&r.common.peak<=b.common.peak};});
 comparisons.push({baseline:base.policy,saved_common_J:base.common_J-bc.common_J,saving_pct:100*(1-bc.common_J/base.common_J),AP_delta:bc.AP-base.AP,peak_delta:bc.peak-base.peak,U_P95_delta_s:bc.service.U.mean_session_P95_s-base.service.U.mean_session_P95_s,ALL_P95_delta_s:bc.service.ALL.mean_session_P95_s-base.service.ALL.mean_session_P95_s,own_tail_saving_pct:100*(1-bc.own_tail_J/base.own_tail_J),per_pattern:per,both_patterns_joint:per.every(p=>p.joint)});
}
save('DERIVED.json',derived);save('SUMMARY.json',{groups,ATC_BC_comparisons:comparisons,old_results_rerun:0,new_BC_START:result.START,new_BC_fit:1,local_only:true,logic_repair_applied:true});
save('AUDIT.json',{status:'PASS',utc:new Date().toISOString(),checks,max_absolute_error:maxerr,rows:derived.length,new_environment:0,source_sha256:sha(__filename),dispatch_reset_checked:true,analytic_reference_sha256:sha(path.join(A,'experiments/a24_s26_method_20261019/audit.cjs')),code_version:op.code_version,endpoint_peak_definition_preserved:true});
const f=(x,n=3)=>x===null||x===undefined?'미정':x.toFixed(n);
let md='# 롤링+ATC+BC · 부하0.4·600초·두 패턴\n\n기존 TRAIN 저장 상태를 재라벨링해 새 BC1fit·600초 EVAL2환경을 등록했다. FIFO/EDF/PPO/기존BC 8세션은 저장 원자료를 재사용했다. 실측자료·물리계수·입력·latent·명목을 유지하고 ATC 후보/특징·동률정답·계산논리 보완을 적용한 새 정책 패키지다. ATC만의 독립 효과로 해석하지 않는다. 새 PPO·물리fit·실기기0이다.\n\n소비·온도·P95는 두 세션 평균, 정시/미완료는 두 패턴 합계다. 주 소비는 다섯 정책의 동일 공통창이다. J*는 예측 소비다.\n\n|정책|소비 J*|평균AP ℃|최고AP ℃|전체정시|긴급정시|일반정시|긴급P95 초|전체P95 초|미완료|\n|---|---:|---:|---:|---|---|---|---:|---:|---:|\n';
for(const g of groups)md+=g.failed?`|${g.policy}|미정|미정|미정|미정|미정|미정|미정|미정|guard FAIL ${g.failed}|\n`:`|${g.policy}|${f(g.common_J)}|${f(g.AP)}|${f(g.peak)}|${g.service.ALL.on}/${g.service.ALL.n}|${g.service.U.on}/${g.service.U.n}|${g.service.N.on}/${g.service.N.n}|${f(g.service.U.mean_session_P95_s)}|${f(g.service.ALL.mean_session_P95_s)}|${g.incomplete}|\n`;
md+='\n## 롤링+ATC+BC와 각 정책의 차이\n\n양수 절감=ATC+BC 소비 감소, 음수 온도차=ATC+BC 온도 감소다. P95 차이가 양수면 ATC+BC가 더 느리다.\n\n|비교 기준|소비 절감 J*|소비 절감 %|평균AP 차 ℃|최고AP 차 ℃|긴급P95 차 초|전체P95 차 초|자체꼬리 절감 %|두 패턴 공동개선|\n|---|---:|---:|---:|---:|---:|---:|---:|---|\n';
for(const c of comparisons)md+=`|${c.baseline}|${f(c.saved_common_J)}|${f(c.saving_pct)}|${f(c.AP_delta)}|${f(c.peak_delta)}|${f(c.U_P95_delta_s)}|${f(c.ALL_P95_delta_s)}|${f(c.own_tail_saving_pct)}|${c.both_patterns_joint}|\n`;
md+='\n## 패턴별 전체10행\n\n|패턴|정책|공통창 초|소비 J*|평균AP ℃|전체정시|긴급정시|미완료|긴급P95 초|공급창 J*|자체꼬리 J*|구버전 예측cap 수|기록|\n|---:|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|\n';
for(const r of derived)md+=r.failed?`|—|${r.policy}|미정|미정|미정|미정|미정|미정|미정|미정|미정|미정|${r.failure}; 원행 보존|\n`:`|${r.pattern}|${r.policy}|${f(r.common_end_ns/1e9-35)}|${f(r.common.J)}|${f(r.common.AP)}|${r.service.ALL.on}/${r.service.ALL.n}|${r.service.U.on}/${r.service.U.n}|${r.incomplete}|${f(r.service.U.P95)}|${f(r.supply.J)}|${f(r.own_tail_J)}|${r.capped_forecasts}|${r.reused?'기존 저장물':'새 ATC+BC'}|\n`;
md+='\n## 검토·검증·범위\n\nBC 학습자료는 기존4개 TRAIN 교사 궤적의 공개 상태1320개를 새 롤링+ATC 교사로 재라벨링했다. 새로운 교사 궤적을 실행하지 않았으므로 방문상태 분포의 한계가 있다. 기존48특징망을 재사용하지 않고 새50특징 ABI로 학습한다. 학습 성적은 BC_TRAINING.json, 데이터 출처는 ../../experiments/a24_atc_bc_20261019/DATASET.json을 따른다.\n\n[원자료·전체정시·평균/Pooled P95](DERIVED.json) · [요약/패턴별판정](SUMMARY.json) · [독립물리/서비스](AUDIT.json) · [Float64 NN](NN_AUDIT.json) · [전체체크포인트/RNG 불변](REPLAY.json). 비교 표의 최고온도는 모든 정책에 동일한 trace 끝점 정의이며 새 보완 물리의 연속구간 peak는 원자료에 보존한다. 새로운 환경/학습 단위는 BC1fit+EVAL2=3이며 승인된 추가예산을 OPERATION.json에서 확인한다. 기존실험재시작·새PPO·새물리fit·새실기기0이다. 두패턴 조건부 비교이며 모든조건 최적/ATC 단독효과를 주장하지 않는다.\n';
fs.writeFileSync(path.join(O,'REPORT_KO.md'),md,{flag:'wx'});
console.log(JSON.stringify({status:'PASS',checks,maxerr,groups,comparisons}));
