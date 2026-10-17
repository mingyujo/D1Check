'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'});
const d=require('./design.cjs').design();let checks=0;
const need=(x,s)=>{checks++;if(!x)throw Error(s);};
for(const c of d.cases){
 need(c.n<=3072&&c.n>96,'Finite expanded request count');
 need(c.input.requests.every((q,i)=>q.ordinal===i&&q.arrival_s<35+c.condition.supply_s&&q.deadline_s>q.arrival_s),'Supply/deadline contract');
 need(c.input.requests.every((q,i)=>i<48||Math.abs((q.deadline_s-q.arrival_s)-(c.input.requests[i%48].deadline_s-c.input.requests[i%48].arrival_s))<1e-7),'Relative deadlines unchanged');
 const longest=d.cases.find(x=>x.condition.pattern===c.condition.pattern&&x.condition.supply_s===600);
 need(JSON.stringify(c.input.requests)===JSON.stringify(longest.input.requests.slice(0,c.n)),'Paired input prefixes');
}
save(path.join(__dirname,'PURE_TEST_RESULT.json'),{status:'PASS',checks,new_environment_START:0});
save(path.join(__dirname,'INPUTS.json'),d);
const parentFile=path.join(root,'experiments/coupled_345_20261017/OPERATION.json'),parent=read(parentFile);
const previous=path.join(root,'experiments/savings_limit_20261017_v2/BUDGET_RESERVATION.json'),b=read(previous);
save(path.join(__dirname,'BUDGET_RESERVATION.json'),{utc:new Date().toISOString(),previous:pin(previous),
 previous_global_reserved:b.global_reserved,new_reservation:24,global_reserved:b.global_reserved+24,global_cap:b.global_cap,
 planned_START:20,cap:24,allocation:{P0:2,comparison:18},unused_coupled345_38_untouched:true,unused_savings8_untouched:true,separate_RR1_untouched:true,
 restored_frozen_timing_bank:1,new_physical_fit:0,new_training:0,
 global_accounting:'Tracked reservation snapshot, not a new all-host START census',
 user_authority:'User asks to extend actual work duration beyond22seconds; maximum3072 requests preserved',automatic_retry:false});
need(b.global_reserved+24<=b.global_cap,'Global tracked cap');
const cpPath=path.join(root,'results/COUPLED_345_20261017_01/SEED_3701_EP064.pt.gz');
const sources=['design.cjs','prepare.cjs','run.py','audit.py','report.cjs'].map(f=>pin(path.join(__dirname,f)));
save(path.join(__dirname,'OPERATION.json'),{schema:'A24-sustained-load-operation-v1',utc:new Date().toISOString(),
 base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),parent_operation:pin(parentFile),
 registration:parent.registration,physics:parent.physics,inputs:pin(path.join(__dirname,'INPUTS.json')),checkpoint:pin(cpPath),
 sources:[...parent.sources,...sources],input_pins:[...parent.input_pins,pin(parentFile),pin(cpPath),
  ...['BUDGET_RESERVATION.json','PURE_TEST_RESULT.json','INPUTS.json'].map(f=>pin(path.join(__dirname,f))),
  ...['RESULT.json','SELECTION_FROZEN.json','FRESH_02_EDF.raw.json.gz','FRESH_02_RL_S3701.raw.json.gz'].map(f=>pin(path.join(root,parent.output_dir,f)))],
 parent_output:parent.output_dir,output_dir:'results/SUSTAINED_LOAD_20261017_01',environment_cap:24,planned_START:20,
 P0:{case:'FRESH_02',policies:['EDF','RL_S3701']},learner_seed:3701,checkpoint_episode:64,
 objective:'Continuous request supply120/300/600s; own-completion energy and common same-time energy/AP; all requests and SLA harms retained',
 fixed_physics:true,new_physical_fit:0,new_training:0,new_device_actions:0,wall_clock_limit_s:3600,
 own_Python_limit:1,global_Python_limit:2,min_free_GiB:8,automatic_retry:false,original_artifacts_immutable:true,
 extrapolation:'Frozen short-training NN and uncalibrated thermal model extrapolated to long supply; whole-episode WAIT budget12s unchanged',measured_J:null});
console.log(JSON.stringify({status:'REGISTERED',checks,cases:d.cases.map(c=>({id:c.id,n:c.n,cycle:c.cycle_s})),planned_START:20,cap:24}));
