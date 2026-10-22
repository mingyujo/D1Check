'use strict';
// Same denominator/window/P95 definitions for either profile. Units stay separate.
function service(requests,end_s){const result={};for(const group of ['ALL','U','N']){
 const qs=requests.filter(q=>group==='ALL'||q.priority===group),ans=qs.filter(q=>Number.isFinite(q.response_s)&&q.response_s<=end_s),lat=ans.map(q=>q.response_s-q.arrival_s).sort((a,b)=>a-b);
 result[group]={arrived:qs.length,responded:ans.length,on_time:ans.filter(q=>q.response_s<=q.deadline_s+1e-9).length,missing:qs.length-ans.length,dropped:qs.filter(q=>q.dropped===true).length,incomplete:qs.filter(q=>!Number.isFinite(q.available_s)||q.available_s>end_s).length,P95_s:lat.length?lat[Math.ceil(.95*lat.length)-1]:null};
}return result;}
function commonEnd(runs,supply_stop_s,drain_stop_s){if(runs.some(r=>r.failed||r.requests.some(q=>!Number.isFinite(q.available_s))))return drain_stop_s;return Math.max(supply_stop_s,...runs.flatMap(r=>r.requests.map(q=>q.available_s)));}
function compareUnits(a,b){if(a.energy_unit!==b.energy_unit)throw Error('Cross-device API_J and J_PROXY are not interchangeable');return a.J-b.J;}
function integrate(trace,profile,start_s,end_s){let J=0,H=0;
 if(!trace.length||start_s<trace[0].start_s-1e-8||end_s>trace.at(-1).end_s+1e-8)throw Error('Accounting window outside recorded trajectory');
 for(const t of trace){if(t.start_s>=end_s)break;if(t.end_s<=start_s)continue;
  if(t.start_s>=start_s&&t.end_s<=end_s){J+=t.J;H+=t.H;continue;}
  const phys=profile.fromPublic(t.cost_state),low=profile.fromPublic(t.cost_state),cpus=new Set(t.cpu_services),lo=Math.max(start_s,t.start_s),hi=Math.min(end_s,t.end_s);
  profile.advance(phys,t.owners,cpus,hi-t.start_s);profile.advance(low,t.owners,cpus,lo-t.start_s);J+=phys.J-low.J;H+=phys.H-low.H;
 }return {J,H,AP_mean:H/(end_s-start_s),energy_unit:profile.energy_unit,start_s,end_s};}
module.exports={service,commonEnd,compareUnits,integrate};
