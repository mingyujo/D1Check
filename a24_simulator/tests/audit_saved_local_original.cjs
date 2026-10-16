// Independent saved-only arithmetic and resource census; no simulation.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const P='C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/work/A24-GITHUB-HANDOFF-20261016/a24_simulator';
const read=p=>JSON.parse(fs.readFileSync(path.join(P,p),'utf8')),hash=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(P,p))).digest('hex');
let checks=0;function need(x,m){if(!x)throw Error(m);checks++;}function near(a,b){need(Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-7,'numeric mismatch '+a+' '+b);}
const data=read('results/FOUR_ROUTE_V2_EVAL.json'),train=read('models/TRAINING_RESULT.json');need(data.cases.length===14,'14 EVAL');need(train.actor_changed,'unchanged actor');need(train.episodes===64&&train.adam_steps>0,'training');
const totals={};let resourceEvents=0;
for(const c of data.cases){need(c.rows.length===7,'7 policies');let ids=c.input.requests.map((q,i)=>'user-'+String(i).padStart(4,'0'));
 for(const r of c.rows){let on=0,returned=0;need(r.requests.length===ids.length,'request denominator');
  for(const [i,q] of r.requests.entries()){need(q.request_id===ids[i],'ordinal identity');need(['CPU','GPU'].includes(q.route),'route');need(q.dispatch_ns>=q.scheduled_arrival_ns&&q.response_ns>=q.dispatch_ns&&q.available_ns>=q.response_ns,'clock');if(q.response_ns<=q.deadline_ns&&q.response_ns<=210e9)on++;if(q.available_ns<=180e9)returned++;}
  need(on===r.metrics.on_time,'deadline census');need(returned===r.AVAILABLE_by180,'available census');
  let times=[...new Set(r.requests.flatMap(q=>[q.dispatch_ns,q.available_ns]))].sort((a,b)=>a-b);
  for(const t of times){let active=r.requests.filter(q=>q.dispatch_ns<=t&&t<q.available_ns);need(active.length<=2&&new Set(active.map(q=>q.route)).size===active.length,'lane ownership');resourceEvents++;}
  near(r.J_proxy,r.energy.baseline_J+Object.values(r.energy.increment_terms_J).reduce((a,b)=>a+b,0));near(Object.values(r.energy.state_seconds).reduce((a,b)=>a+b,0),180);need(r.measured_J===null&&r.energy_error_J===null&&r.energy_CI===null,'uncalibrated energy');
  const pts=r.AP.t_s.map((t,i)=>[t,r.AP.ap_c[i]]).filter(([t])=>t>=35&&t<=180);let area=0;for(let i=1;i<pts.length;i++)area+=(pts[i][0]-pts[i-1][0])*(pts[i][1]+pts[i-1][1])/2;near(area/145,r.AP_mean_c);near(Math.max(...pts.map(p=>p[1])),r.AP_peak_c);
  let total=totals[r.policy]||={conditions:0,planned:0,ontime:0,J:0,AP:0,wait:0};total.conditions++;total.planned+=r.metrics.planned;total.ontime+=r.metrics.on_time;total.J+=r.J_proxy;total.AP+=r.AP_mean_c;total.wait+=r.wait_s;
 }
}
const ledger=fs.readFileSync(P+'/runtime/receipts.jsonl','utf8').trim().split(/\r?\n/).map(JSON.parse),counts={};ledger.forEach(x=>counts[x.event]=(counts[x.event]||0)+1);need(counts.START===187&&counts.COMPLETE===186&&counts.FAIL===1,'consumption incl failure');
for(const p of read('models/TRAINING_OPERATION_V2.json').source_pins)need(crypto.createHash('sha256').update(fs.readFileSync(p.path)).digest('hex')===p.sha256,'source drift');
const result={status:'PASS_SAVED_ARITHMETIC_RESOURCE_CONSUMPTION_NOT_PHYSICAL_ACCURACY',checks,resourceEvents,counts,totals,eval_sha256:hash('results/FOUR_ROUTE_V2_EVAL.json'),training_sha256:hash('models/TRAINING_RESULT.json'),measured_J:null,fresh_confirmation:false};fs.writeFileSync(P+'/results/INDEPENDENT_SAVED_AUDIT.json',JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({status:result.status,checks,counts,totals}));
