'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const B=path.resolve(__dirname,'../..'),O=path.join(B,'outputs/S26-FAIR-TIE-DIAGNOSIS-20261016'),F=path.join(B,'outputs/S26-FAIR-RESOURCE-COMPARE-20261016'),U=path.join(B,'outputs/S26-UNIFIED-DYNAMICS-20261016');
const read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),sha=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex'),hash=v=>crypto.createHash('sha256').update(JSON.stringify(v)).digest('hex'),lines=f=>fs.readFileSync(f,'utf8').trim().split(/\r?\n/).map(JSON.parse);
const write=(f,v)=>fs.writeFileSync(f,JSON.stringify(v,null,2)+'\n',{flag:'wx'});
const physical=r=>({requests:r.requests,events:r.events,activity:r.activity,sensor:r.sensor,curve:r.curve,service:r.service,wait_s:r.wait_s});
function register(){
 const prior=read(path.join(O,'OPERATION.json')),inputs={...prior.source_hashes};for(const f of [__filename,path.join(O,'RESULT.json'),path.join(O,'DECISION_STATES.csv'),path.join(O,'NOMINALS.csv'),path.join(O,'LEGACY_SENSITIVITY.csv'),path.join(U,'SIMULATION_V1/ROWS.jsonl'),path.join(U,'SIMULATION_REMAINDER_V2/ROWS.jsonl')])inputs[f]=sha(f);
 const old=[...lines(path.join(U,'SIMULATION_V1/ROWS.jsonl')),...lines(path.join(U,'SIMULATION_REMAINDER_V2/ROWS.jsonl'))].filter(r=>r.phase==='FAIR'&&['FIFO_SERIAL_CG_V1','FIFO_PAIR_CG_V1'].includes(r.policy));assert.equal(old.length,96);
 for(const r of old){assert.equal(sha(r.raw_path),r.raw_sha256);inputs[r.raw_path]=r.raw_sha256}
 write(path.join(O,'VERIFICATION_OPERATION.json'),{status:'REGISTERED_BEFORE_SECOND_PASS',utc:new Date().toISOString(),input_hashes:inputs,new_policy_environments:0,new_CostState:0,new_fit:0,new_NN:0});console.log(JSON.stringify({files:Object.keys(inputs).length}));
}
function verify(){
 const op=read(path.join(O,'VERIFICATION_OPERATION.json')),result=read(path.join(O,'RESULT.json'));let checks=0;const test=(ok,label)=>{checks++;assert(ok,label)};
 const unchanged=()=>{for(const[f,h]of Object.entries(op.input_hashes))test(sha(f)===h,'source/input SHA '+f)};unchanged();
 const own=read(path.join(F,'REUSED_OWN_CASES.json')),baseline=lines(path.join(F,'PRODUCTION/ROWS.jsonl')).filter(x=>x.phase==='FAIR_RESOURCE');let equalATC=0,multi=0,tiedPairs=0,globalDifferences=0,blockFIFO=0;
 for(const ref of own){const r=read(ref.raw_path);
  for(const p of ['FIFO_FREE_ROUTE_V1','EDF_FREE_ROUTE_V1']){const b=baseline.find(b=>b.policy===p&&b.scenario===r.scenario&&b.config.stream===r.config.stream);test(!!b,'matched baseline');test(hash(physical(r))===hash(physical(read(b.raw_path))),'full physical trace tie');tiedPairs++}
  for(const d of r.policy_decisions){const qs=d.public_observation.ready,c=d.action.candidates.filter(c=>c.permitted),ids=new Set(c.map(c=>c.ordinal));if(ids.size>1){multi++;for(const key of ['task','priority','deadline'])test(new Set(qs.filter(q=>ids.has(q.ordinal)).map(q=>q[key])).size===1,'homogeneous eligible '+key);
    for(const route of new Set(c.map(c=>c.route))){const cs=c.filter(x=>x.route===route);test(new Set(cs.map(x=>x.ATC)).size===1,'ATC tie within route');test(new Set(cs.map(x=>x.response_estimate_s)).size===1,'same processing estimate within route')}equalATC++}
   test(c.every(x=>x.predicted_ready_misses===0&&x.predicted_max_lateness_s===0),'no candidate nominal risk');
   const fifo=qs.slice().sort((a,b)=>a.arrival-b.arrival||a.ordinal-b.ordinal)[0],edf=qs.slice().sort((a,b)=>a.deadline-b.deadline||a.arrival-b.arrival||a.ordinal-b.ordinal)[0];globalDifferences+=Number(fifo.ordinal!==edf.ordinal);blockFIFO+=Number(!ids.has(fifo.ordinal));
  }
 }
 test(multi===1551&&equalATC===1551,'all1551 ATC score ties');test(globalDifferences===349&&blockFIFO===571,'independent global vs legal counter');
 const old=[...lines(path.join(U,'SIMULATION_V1/ROWS.jsonl')),...lines(path.join(U,'SIMULATION_REMAINDER_V2/ROWS.jsonl'))].filter(r=>r.phase==='FAIR'&&['FIFO_SERIAL_CG_V1','FIFO_PAIR_CG_V1'].includes(r.policy));const legacy=[];
 for(const s of old.filter(r=>r.policy==='FIFO_SERIAL_CG_V1')){
  const p=old.find(p=>p.policy==='FIFO_PAIR_CG_V1'&&p.scenario===s.scenario&&p.config.stream===s.config.stream);test(!!p,'legacy matched same stream');const a=read(s.raw_path),b=read(p.raw_path);
  test(hash(a.planned_requests)===hash(b.planned_requests),'legacy exact arrivals/deadlines');
  const phase=x=>x.requests.slice().sort((a,b)=>a.ordinal-b.ordinal).map(q=>[q.ordinal,q.route,q.template_id,q.residual]);test(hash(phase(a))===hash(phase(b)),'legacy exact potential phase samples');test(hash(a.curve)!==hash(b.curve),'legacy physical curves differ');test(a.J_API0_180!==b.J_API0_180&&a.AP35_180_mean!==b.AP35_180_mean,'legacy costs differ');
  legacy.push({scenario:s.scenario,stream:s.config.stream,serial_raw:s.raw_path,serial_sha256:s.raw_sha256,pair_raw:p.raw_path,pair_sha256:p.raw_sha256,serial_J:a.J_API0_180,pair_J:b.J_API0_180,serial_AP:a.AP35_180_mean,pair_AP:b.AP35_180_mean,serial_on_time:a.service.all.on_time,pair_on_time:b.service.all.on_time});
 }
 test(legacy.length===48,'all48 legacy pairs');
 const gap=result.decision_AP.max-result.decision_AP.min,thermal=Object.fromEntries(Object.entries(result.route_nominals).map(([route,n])=>[route,{AP_range_C:gap,inference_duration_percent_change_over_observed_AP:100*Math.expm1(n.coefficients['AP:'+route]*gap/10),meaning:'Association coefficient of frozen inference model; not whole response, not identified causal DVFS'}]));
 unchanged();write(path.join(O,'VERIFICATION_RESULT.json'),{status:'PASS',checks,physical_tie_pairs:tiedPairs,homogeneous_multiple_states:multi,ATC_ties_within_route:equalATC,legacy_raw_pairs:legacy.length,thermal_association_sensitivity:thermal,all_input_SHA_unchanged:true,new_policy_environments:0,new_CostState:0,new_fit:0,new_NN:0});write(path.join(O,'LEGACY_PAIR_BINDINGS.json'),legacy);console.log(JSON.stringify({status:'PASS',checks,physical_tie_pairs:tiedPairs,multi,equalATC,legacy_raw_pairs:legacy.length,thermal},null,2));
}
if(process.argv[2]==='register')register();else if(process.argv[2]==='verify')verify();else throw Error('register | verify');
