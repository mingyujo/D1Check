'use strict';
// Counterfactual template draws are offline bound inputs, never policy features.
const fs=require('fs'),z=require('zlib'),path=require('path'),H=__dirname,R=path.resolve(H,'../..');
const read=p=>JSON.parse((p.endsWith('.gz')?z.gunzipSync(fs.readFileSync(p)):fs.readFileSync(p)).toString('utf8').replace(/^\uFEFF/,''));
const packet=read(path.join(R,'experiments/multiresource_v1/PACKET.json.gz')),base=require('./source/s26_simulator.cjs'),tm=require('./source/multi_timing.cjs'),rc=require('./source/resource_contract.cjs');
const pm=read(path.join(R,'experiments/capacity_power_v1/artifacts/G001/MODEL.json')),c=pm.coef.map((x,j)=>x/pm.scale[j]);
const parent=read(path.join(R,'experiments/a24_stable_learning_v1/artifacts/G001/COMPARISON_SUMMARY.json'));
const inputs=read(path.join(R,'experiments/a24_stable_learning_v1/INPUTS.json')).cases,nom=tm.nominal(packet),pools=new Map,identities={};
for(const p of packet.templates.filter(p=>p.overlap_fraction===0&&!p.priority_transfer)){let k=p.route+'|'+p.priority;if(!pools.has(k))pools.set(k,[]);pools.get(k).push(p);if(!identities[p.route])identities[p.route]={...p,domain:'M8_READBACK_RENAME_RESPONSE'};}
const rows=[];
for(const old of parent.rows.filter(r=>r.kind==='EVAL'&&r.policy==='EDF_GPU_FIRST')){
 const inp=inputs.find(i=>i.id===old.input),ctx=inp.context.initial_context.targets,options=[];
 for(const q of inp.requests){const opts=[];for(const route of rc.allowed({task:q.task_id})){
  const pool=pools.get(route+'|'+q.priority),p=pool[base.seeded(inp.stream+'|phase|'+q.ordinal+'|'+route)%pool.length],v=p.offset_s;
  const residual=p.inference_s/base.timing(packet.timing,{...p,domain:'M8_READBACK_RENAME_RESPONSE'},p.AP??30,0);
  const infer=Math.min(...[26,60].map(AP=>tm.duration(packet,identities[route],AP,[],packet.multi.models.CENTRAL,residual)));
  const adm=v.host_inference_start_ns-v.execution_start_ns,post=v.lane_available_ns-v.output_ready_ns;
  const work=(rc.slot(route)==='CPU'?infer:0)+tm.service(packet,route,'ADMISSION',adm,packet.multi.models.CENTRAL)+tm.service(packet,route,'POST',post,packet.multi.models.CENTRAL);
  opts.push({route,slot:rc.slot(route),template:p.id,infer,cpu_work:work,cpu_wall:(rc.slot(route)==='CPU'?infer:0)+adm+post,occupied:v.execution_start_ns+adm+infer+(v.output_ready_ns-v.host_inference_return_ns)+post});
 }options.push({ordinal:q.ordinal,options:opts});}
 rows.push({input:inp.id,load:inp.nominal_load_ratio,mix:inp.mix,T:old.observation_s,baseline:(c[0]+ctx.POWER_API.baseline.median_api_w*c[1])*old.observation_s,EDF_J:old.full_API_J,old_RL_J:parent.rows.filter(r=>r.kind==='EVAL'&&r.input===old.input&&r.variant==='REPAIR').reduce((s,r)=>s+r.full_API_J,0)/3,options});
}
const output={schema:'CONDITIONAL_COUNTERFACTUAL_ROUTE_LP_V1',coef:c,rows,AP_range:[26,60],scope:'Frozen timing/power model; nonnegative CENTRAL overlap penalties, same latent template map, continuous assignment and no deadline/order constraints. This is an optimistic lower bound, not a feasible dispatch schedule or real-device certificate.'};
fs.writeFileSync(path.join(H,'ROUTE_BOUND_INPUT.json'),JSON.stringify(output)+'\n',{flag:'wx'});console.log('BOUND_EXPORTED',rows.length);
