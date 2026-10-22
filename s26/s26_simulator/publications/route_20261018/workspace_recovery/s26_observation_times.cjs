'use strict';
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const root = path.resolve(__dirname, '../S26-D1Check/s26_simulator');
const html = fs.readFileSync(path.join(root, 'web/multiresource_v1.html'), 'utf8');
const match = html.match(/<script id="packedData"[^>]*>([\s\S]*?)<\/script>/);
if (!match) throw Error('Packed saved data missing');
const payload = Buffer.from(match[1].trim(), 'base64');
const data = JSON.parse(zlib.gunzipSync(payload));
const cases = data.cases ?? data.view;
if (!Array.isArray(cases) || cases.length !== 2592) throw Error('Unexpected saved cases: ' + JSON.stringify(Object.keys(data)));
function union(intervals) {
  intervals.sort((a,b)=>a[0]-b[0]);
  let total=0, left=null, right=null;
  for (const [a,b] of intervals) {
    if (left===null) {left=a;right=b;}
    else if (a<=right) right=Math.max(right,b);
    else {total+=right-left;left=a;right=b;}
  }
  return total+(left===null?0:right-left);
}
const rows=cases.map(c=>{
  if(c.requests.length!==128 || !c.requests.every(q=>Number.isFinite(q[5])&&Number.isFinite(q[6])&&Number.isFinite(q[15])) ) throw Error('Incomplete saved request times');
  const firstArrival=Math.min(...c.planned.map(q=>q[2]));
  const lastArrival=Math.max(...c.planned.map(q=>q[2]));
  const firstDispatch=Math.min(...c.requests.map(q=>q[6]));
  const lastResponse=Math.max(...c.requests.map(q=>q[5]));
  const lastAvailable=Math.max(...c.requests.map(q=>q[15]));
  return {id:c.row.id,capacity:c.row.capacity,model:c.row.model,policy:c.row.policy,burst:c.row.burst,
    first_arrival_s:firstArrival,last_arrival_s:lastArrival,first_dispatch_s:firstDispatch,
    last_response_s:lastResponse,last_available_s:lastAvailable,
    response_span_s:lastResponse-firstArrival,work_span_s:lastAvailable-firstArrival,
    any_slot_occupied_union_s:union(c.requests.map(q=>[q[6],q[15]])),
    post_work_observation_s:180-lastAvailable};
});
const stats=(items,key)=>({mean:items.reduce((s,r)=>s+r[key],0)/items.length,min:Math.min(...items.map(r=>r[key])),max:Math.max(...items.map(r=>r[key]))});
const summarise=items=>({cases:items.length,first_arrival_s:stats(items,'first_arrival_s'),last_arrival_s:stats(items,'last_arrival_s'),last_response_s:stats(items,'last_response_s'),last_available_s:stats(items,'last_available_s'),work_span_s:stats(items,'work_span_s'),any_slot_occupied_union_s:stats(items,'any_slot_occupied_union_s'),post_work_observation_s:stats(items,'post_work_observation_s')});
const groups=[];
for(const capacity of [1,2,3])for(const model of ['LOW','CENTRAL','HIGH'])for(const policy of ['FIFO','EDF','ATC']){
  groups.push({capacity,model,policy,...summarise(rows.filter(r=>r.capacity===capacity&&r.model===model&&r.policy===policy))});
}
const result={status:'PASS',source:'Existing G004 saved view request timestamps; no new environment or physical integration',observation_s:180,arrival_design_window_s:16,AP_mean_window_s:[35,180],energy_window_s:[0,180],all:summarise(rows),groups,rows,new_policy_environments:0,new_fit:0,new_RL:0};
fs.writeFileSync(path.join(__dirname,'S26_OBSERVATION_TIMES.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({...result,rows:undefined,groups:groups.filter(g=>g.capacity===3)},null,2));
