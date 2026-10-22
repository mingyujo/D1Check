'use strict';
// One arrival/task/priority/deadline generator; no device or latent inputs.
function rng(seed){let x=seed>>>0;return ()=>{x+=0x6D2B79F5;let t=x;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return ((t^t>>>14)>>>0)/4294967296;};}
function plan({n,offered_requests_per_s,classification_share,urgent_share,deadlines_s,seed,start_s=35,pattern='uniform',burst_size=16}){
 if(!Number.isInteger(n)||n<1||!(offered_requests_per_s>0)||![classification_share,urgent_share].every(x=>x>=0&&x<=1)||!Number.isInteger(seed)||!['uniform','renewal','burst'].includes(pattern)||!Number.isInteger(burst_size)||burst_size<1)throw Error('Explicit common workload specification');
 for(const t of ['C','D'])for(const p of ['U','N'])if(!(deadlines_s?.[t]?.[p]>0))throw Error('Explicit task/priority response budgets required');
 const task=rng(seed),priority=rng(seed^0xA105),arrival=rng(seed^0x5A91),requests=[];let offset=0;
 for(let i=0;i<n;i++){
  if(i&&pattern==='renewal')offset+=-Math.log(Math.max(1e-12,1-arrival()))/offered_requests_per_s;
  else if(pattern==='uniform')offset=i/offered_requests_per_s;
  else if(pattern==='burst')offset=Math.floor(i/burst_size)*burst_size/offered_requests_per_s;
  const t=task()<classification_share?'C':'D',p=priority()<urgent_share?'U':'N';
  requests.push({id:'common-'+String(i).padStart(6,'0'),ordinal:i,task:t,priority:p,arrival_s:start_s+offset,deadline_s:start_s+offset+deadlines_s[t][p]});
 }
 return {version:'DEVICE_COMMON_WORKLOAD_V1',spec:{n,offered_requests_per_s,classification_share,urgent_share,deadlines_s,seed,start_s,pattern,burst_size},requests,load_is_not_CPU_utilization:true};
}
function bindAdmission(planned,admissions,{source_kind='MEASURED'}={}){
 return planned.requests.map(q=>{const d=admissions[q.id];if(!(d>=0&&Number.isFinite(d)))throw Error('Explicit nonnegative admission delay required');return {...q,ready_s:q.arrival_s+d,source_kind};});
}
module.exports={plan,bindAdmission};
