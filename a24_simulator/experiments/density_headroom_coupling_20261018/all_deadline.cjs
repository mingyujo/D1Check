'use strict';
// Necessary capacity only: for jobs released >=a and due <=b, even their
// fastest cold response-prefix work must fit within two lanes*(b-a).
function capacity(jobs){
 const q=values=>{const a=[...new Set(values)].sort((a,b)=>a-b);return [...new Set(Array.from({length:24},(_,i)=>a[Math.round(i*(a.length-1)/23)]))];};
 const entries=jobs.map(j=>({request_id:j.request_id,release:j.queue_entry_ns/1e9,due:j.deadline_ns/1e9,
  work:Math.min(...['CPU','GPU'].map(r=>j.routes[r].stages_ns.slice(0,j.task==='C'?2:3).reduce((a,b)=>a+b,0)/1e9))}));
 const constraints=[];
 for(const a of q([35,...entries.map(j=>j.release)]))for(const b of q(entries.map(j=>j.due))){
  if(b<=a)continue;const group=entries.filter(j=>j.release>=a-1e-10&&j.due<=b+1e-10).sort((a,b)=>b.work-a.work),sum=group.reduce((a,j)=>a+j.work,0),cap=2*(b-a);
  let left=sum,miss=0;while(left>cap+1e-7&&miss<group.length)left-=group[miss++].work;
  constraints.push({start_s:a,end_s:b,jobs:group.length,cold_prefix_work_s:sum,two_lane_capacity_s:cap,min_non_on_time:miss});
 }
 const strongest=constraints.reduce((a,b)=>a.min_non_on_time>b.min_non_on_time?a:b,{min_non_on_time:0});
 return {all_arrivals:jobs.length,minimum_non_on_time_proved:strongest.min_non_on_time,all_on_time_ruled_out:strongest.min_non_on_time>0,strongest,
  constraints,note:'A positive bound proves full-on-time impossible even with cold fastest prefixes, fractional route freedom, no suffix or heat cost. Zero does not prove feasibility.'};
}
module.exports={capacity};
