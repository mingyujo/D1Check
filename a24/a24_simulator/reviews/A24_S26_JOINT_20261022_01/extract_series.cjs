'use strict';
// Saved traces only. Evaluate a partial analytic step; never run a policy/environment.
const fs=require('fs'),path=require('path'),z=require('zlib'),crypto=require('crypto');
const R=path.resolve(__dirname,'../../..'),A=path.join(R,'a24_simulator'),O=path.join(A,'results/A24_S26_JOINT_20261022_01');
const read=p=>JSON.parse(p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p));
const {step}=require(path.join(A,'experiments/a24_s26_method_20261019/audit.cjs'));
const data=read(path.join(O,'RESULT.json')),series=[];let checks=0;
function near(a,b,tol){checks++;if(Math.abs(a-b)>tol)throw Error('Series endpoint '+a+' / '+b);}
for(const row of data.rows.filter(x=>x.condition.role==='CONF')){
 const d=read(path.join(R,row.raw.path)),r=d.result,tr=r.trace,pj=[0],ph=[0];
 for(const s of tr){pj.push(pj.at(-1)+s.increment+r.config.baseline*s.dt);ph.push(ph.at(-1)+s.temperature_area);}
 const end=d.case.observation_end_s,ns=new Set([0,35e9,Math.round(end*1e9),Math.round(d.case.supply_stop_s*1e9)]);
 for(let t=36;t<end;t++)ns.add(t*1e9);
 const points=[];
 for(const t of [...ns].sort((a,b)=>a-b)){
  if(t<=35e9){points.push({t_s:t/1e9,AP_c:26,cumulative_J:r.config.baseline*t/1e9});continue;}
  let lo=0,hi=tr.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(tr[mid].start_ns<t)lo=mid;else hi=mid-1;}
  const s=tr[lo],x=step(s.state,s.active,(t-s.start_ns)/1e9,r.config,'ORIGINAL');
  points.push({t_s:t/1e9,AP_c:x.state.temperature_c,cumulative_J:35*r.config.baseline+pj[lo]+x.J+r.config.baseline*(t-s.start_ns)/1e9});
  if(t===Math.round(end*1e9)){near(points.at(-1).cumulative_J,row.metrics.J,1e-6);near((ph[lo]+x.H)/(end-35),row.metrics.AP,1e-8);}
 }
 series.push({label:row.label,condition:row.condition,policy:row.policy,supply_stop_s:d.case.supply_stop_s,observation_end_s:end,points});
}
fs.writeFileSync(path.join(O,'TIME_SERIES.json.gz'),z.gzipSync(Buffer.from(JSON.stringify({source:'Saved CONF analytic traces, one-second samples plus exact boundaries; no interpolation/smoothing',series}))),{flag:'wx'});
const csv=['label,policy,mix,draw,t_s,AP_c,cumulative_J'];
for(const s of series)for(const p of s.points)csv.push([s.label,s.policy,s.condition.mix,s.condition.draw,p.t_s,p.AP_c,p.cumulative_J].join(','));
fs.writeFileSync(path.join(O,'TIME_SERIES.csv'),'\ufeff'+csv.join('\n')+'\n',{flag:'wx'});
fs.writeFileSync(path.join(O,'TIME_SERIES_CHECK.json'),JSON.stringify({status:'PASS',checks,inputs:8,episodes:series.length,points:series.reduce((a,s)=>a+s.points.length,0),new_environments:0,script_sha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex')}),{flag:'wx'});
console.log('SERIES_PASS',checks,series.length);
