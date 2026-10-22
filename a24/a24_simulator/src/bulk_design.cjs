(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.A24Bulk=factory();})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const policies=['ROLLING_ATC_RL','ROLLING_ATC_RL_NO_WAIT','FIFO_SERIAL_CG','FIFO_FREE','EDD','ATC','MOBILE_DEADLINE_ENERGY'];
 function need(b,m){if(!b)throw Error(m);}
 function list(x,name,test){need(Array.isArray(x)&&x.length>0&&x.length<=16,name+' 목록 오류');need(x.every(test),name+' 값 오류');need(new Set(x).size===x.length,name+' 중복 값');return x;}
 function generate(d){
  const counts=list(d.counts,'요청 수',x=>Number.isInteger(x)&&x>=1&&x<=256),mixes=list(d.mixes,'분류 비율',x=>Number.isFinite(x)&&x>=0&&x<=1),patterns=list(d.patterns,'도착 패턴',x=>['steady','burst'].includes(x)),slacks=list(d.slacks,'기준 납기 배율',x=>Number.isFinite(x)&&x>0&&x<=10),seeds=list(d.seeds,'seed',x=>Number.isInteger(x)&&x>=0&&x<=2147483647);
  const loads=list(d.loads||[.5,.85,1.2],'참조 부하',x=>Number.isFinite(x)&&x>0&&x<=5);
  const size=counts.length*mixes.length*patterns.length*slacks.length*seeds.length*loads.length;need(size<=64,'조건은 최대 64개입니다.');
  const initial=d.initial_context||'M128',alpha=d.alpha??.95,rl=d.rl_seed??20261028,cases=[];
  need(['M128','L64','C252'].includes(initial)&&[.7,.8,.9,.95,1].includes(alpha)&&[46201,46203,46207,20261028].includes(rl),'공통 설정 오류');
  for(const n of counts)for(const mix of mixes)for(const pattern of patterns)for(const slack of slacks)for(const seed of seeds)for(const rho of loads){
   // Nominal occupancy is pinned from the common A24 model, not chosen by outcomes.
   const reference=Math.max(mix*.255213692,(1-mix)*.568107423),gap=reference/rho,seen={C:0,D:0};
   const requests=Array.from({length:n},(_,i)=>{const task=Math.floor((i+1)*mix+1e-10)>Math.floor(i*mix+1e-10)?'C':'D';
    const priority=(seen[task]++%4===0)?'U':'N';
    const arrival=+(35+(pattern==='burst'?Math.floor(i/8)*8:i)*gap).toFixed(8);
    const due=(task==='C'?2.2:5)*(priority==='U'?.7:1)*slack;
    need(arrival<180&&arrival+due<=210,'조건의 도착/납기가 관측창을 넘습니다.');
    return {ordinal:i,profile:task+'_M128',priority,arrival_s:arrival,deadline_s:+(arrival+due).toFixed(8)};});
   cases.push({index:cases.length,label:n+'개 · 분류 '+Math.round(mix*100)+'% · '+pattern+' · 참조부하 '+rho+' · 기준납기×'+slack+' · seed '+seed,condition:{n,mix,pattern,slack,seed,reference_load:rho,gap_s:gap,deadline_basis:'C2.2/D5 experimental contract; U0.7/N1 exploratory, not SLA'},input:{requests,seed,rl_seed:rl,initial_context:initial,alpha}});
  }return cases;
 }
 function preset(name){return {counts:[48],mixes:[.25,.75],patterns:['steady','burst'],loads:[.5,.85,1.2],slacks:[1],seeds:name==='wide'?[20261029,20261030,20261031]:[20261029],initial_context:'M128',alpha:.95,rl_seed:20261028};}
 const finite=x=>typeof x==='number'&&Number.isFinite(x),mean=a=>a.length&&a.every(finite)?a.reduce((s,x)=>s+x,0)/a.length:null,delta=(a,b)=>finite(a)&&finite(b)?a-b:null;
 function aggregate(cases){
  const complete=cases.filter(c=>c.status==='COMPLETE');
  for(const c of complete){need(c.result&&c.result.rows.length===policies.length,'완료 조건의 7개 정책 누락');need(policies.every(p=>c.result.rows.filter(r=>r.policy===p).length===1),'정책 중복/누락');}
  const rows=policies.map(policy=>{
   const pairs=complete.map(c=>({r:c.result.rows.find(x=>x.policy===policy),b:c.result.rows.find(x=>x.policy==='FIFO_SERIAL_CG')}));
   const sum=f=>pairs.reduce((s,x)=>s+f(x),0),diff=(f,tol)=>({better:pairs.filter(x=>finite(f(x))&&f(x)<-tol).length,tied:pairs.filter(x=>finite(f(x))&&Math.abs(f(x))<=tol).length,worse:pairs.filter(x=>finite(f(x))&&f(x)>tol).length,unknown:pairs.filter(x=>!finite(f(x))).length});
   return {policy,label:pairs[0]?.r.label||policy,conditions:pairs.length,planned:sum(x=>x.r.metrics.planned),on_time:sum(x=>x.r.metrics.on_time),response_completed:sum(x=>x.r.metrics.response_completed),missing:sum(x=>x.r.metrics.response_missing),
    mean_condition_on_time_rate:mean(pairs.map(x=>x.r.metrics.on_time/x.r.metrics.planned)),mean_AP_c:mean(pairs.map(x=>x.r.AP_mean_c)),mean_AP_delta_c:mean(pairs.map(x=>delta(x.r.AP_mean_c,x.b.AP_mean_c))),mean_J_proxy:mean(pairs.map(x=>x.r.J_proxy)),mean_J_delta:mean(pairs.map(x=>delta(x.r.J_proxy,x.b.J_proxy))),
    deadline:diff(x=>x.b.metrics.on_time-x.r.metrics.on_time,0),energy:diff(x=>delta(x.r.J_proxy,x.b.J_proxy),1e-8),peak:diff(x=>delta(x.r.AP_peak_c,x.b.AP_peak_c),1e-6),
    not_all_available_by180:pairs.filter(x=>x.r.AVAILABLE_by180<x.r.metrics.planned).length,by_priority:Object.fromEntries(['U','N'].map(p=>[p,{planned:sum(x=>x.r.by_priority[p].planned),on_time:sum(x=>x.r.by_priority[p].on_time),missing:sum(x=>x.r.by_priority[p].missing)}]))};
  });
  return {planned_conditions:cases.length,complete_conditions:complete.length,failed_conditions:cases.filter(c=>c.status==='FAIL').length,not_started_conditions:cases.filter(c=>c.status==='NOT_STARTED').length,rows,measured_J:null,energy_error:null,CI:null,fresh_confirmation:false,aggregation:'모든 완료 조건의 동일 가중 평균 + 요청 분모 합계. 실패/미실행 조건 별도 보존. seed는 같은 모형의 반복이며 독립 실측이 아님.'};
 }
 return {policies,generate,preset,aggregate};
});
