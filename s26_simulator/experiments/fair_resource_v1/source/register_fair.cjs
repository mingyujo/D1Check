'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const W=__dirname,B=path.resolve(W,'../..'),O=path.join(B,'outputs',path.basename(W));
const oldW=path.join(B,'work/S26-UNIFIED-DYNAMICS-20261016'),oldO=path.join(B,'outputs/S26-UNIFIED-DYNAMICS-20261016');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const save=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n',{flag:'wx'}),copy=(a,b)=>fs.copyFileSync(a,b,fs.constants.COPYFILE_EXCL);
const parent=read(path.join(oldO,'RESOURCE_PRODUCTION_OPERATION_V2.json'));
if(process.argv.includes('--prepare')){
 for(const f of['s26_simulator.cjs','dynamic_cost_math_v2.cjs','rolling_action_v2.cjs','s26_simulator_v2.cjs'])copy(path.join(oldW,'source_generations/SIM002_G001',f),path.join(W,f));
 let run=fs.readFileSync(parent.node_entry,'utf8').replace("require('./s26_simulator_v2.cjs')","require('./fair_simulator.cjs')");fs.writeFileSync(path.join(W,'fair_case.cjs'),run,{flag:'wx'});
 let prod=fs.readFileSync(path.join(oldW,'run_resource_study_v2.py'),'utf8').replace('def main(op):','def main(op):\n u.verify({"protected_hashes":op["reuse_parent_hashes"]})');
 fs.writeFileSync(path.join(W,'run_fair_study.py'),prod,{flag:'wx'});
 const originals=read(parent.case_plan_path).filter(c=>c.phase==='RESOURCE_DYNAMIC');if(originals.length!==48)throw Error('Parent coverage');
 const rows=fs.readFileSync(path.join(parent.output_dir,'ROWS.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse),by=new Map(rows.map(r=>[r.logical_identity,r]));
 const reuse=originals.map(c=>{const r=by.get(c.identity);if(!r||sha(r.raw_path)!==r.raw_sha256)throw Error('Parent raw SHA');return {config:c,row:r,raw_sha256:r.raw_sha256,raw_path:r.raw_path,config_path:path.join(parent.output_dir,'configurations',c.identity+'.json')}});
 save(path.join(O,'REUSED_OWN_CASES.json'),reuse);
 const cases=[],policies=['FIFO_FREE_ROUTE_V1','EDF_FREE_ROUTE_V1'];
 for(const [bank,index]of[['M128',0],['SMOOTH128',24]])for(const policy of policies)for(const [label,dt]of[['DT5',.005],['DT25',.0025]])cases.push({...originals[index],identity:'FAIR1_P0_'+bank+'_'+policy+'_'+label,phase:'P0',policy,dt_s:dt,numeric_pair:bank+'_'+policy,stream:260016490+(index===24?2:0)+(policy.startsWith('EDF')?1:0)});
 for(const original of originals)for(const policy of policies)cases.push({...original,identity:'FAIR1_'+policy+'_'+original.identity.replace('RES2_DYNAMIC_',''),phase:'FAIR_RESOURCE',policy,paired_own_identity:original.identity});
 save(path.join(O,'CASE_PLAN.json'),cases);
 const ledgers=new Set([...parent.global_accounting_ledgers,parent.receipts_path].map(p=>path.resolve(p).toLowerCase()));
 for(const name of fs.readdirSync(path.join(B,'outputs')))if(/^A24-(INTERACTIVE-POLICY-LAB|FOUR-ROUTE-POLICY-LAB)-20261016/.test(name)){
  const dir=path.join(B,'outputs',name);if(fs.statSync(dir).isDirectory())for(const f of fs.readdirSync(dir))if(/^receipts.*\.jsonl$/i.test(f))ledgers.add(path.join(dir,f).toLowerCase());
 }
 let actual=0;const counts=[...ledgers].map(p=>{let n=0;if(fs.existsSync(p))for(const l of fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'').split(/\r?\n/))if(l.trim()&&JSON.parse(l).event==='START')n++;actual+=n;return {path:p,START:n}});
 save(path.join(O,'BUDGET_RESERVATION.json'),{created_utc:new Date().toISOString(),previous_global_reserved:120774,new_reservation:112,global_reserved:120886,global_cap:137712,unreserved:16826,actual_prior_START:actual,global_ledgers:counts,new_planned:104,P0:8,main:96,reused_own:48,prior512_remaining12_unchanged:true,unused_cap_not_retry_credit:8,new_RL:0,new_fit:0,cost_audit_replays_cap:152,nominal_model_constructions_cap:104,nominal_predict_calls_cap:1040});
 save(path.join(O,'CONTINUE.json'),{status:'REGISTERED_PREPARATION',work:W,output:O,plan:path.join(W,'PLAN.md'),budget:path.join(O,'BUDGET_RESERVATION.json'),new_policy_environments:0,reused_own:48,new_RL:0,source_generation:'FAIR001_G001'});
 console.log(JSON.stringify({status:'PREPARED',planned:cases.length,reused:reuse.length,prior_START:actual,global_reserved:120886}));
}
if(process.argv.includes('--seal')){
 if(read(path.join(O,'PURE_TESTS.json')).status!=='PASS')throw Error('Pure tests not PASS');
 const gen=path.join(W,'source_generations/FAIR001_G001');fs.mkdirSync(gen,{recursive:true});
 for(const f of fs.readdirSync(W))if(/\.cjs$/.test(f)&&f!=='register_fair.cjs')copy(path.join(W,f),path.join(gen,f));
 const source={},inputs={},protectedHashes={},reused={};
 for(const f of fs.readdirSync(W))if(/\.(cjs|py|md)$/.test(f))source[path.join(W,f)]=sha(path.join(W,f));
 for(const f of fs.readdirSync(gen))source[path.join(gen,f)]=sha(path.join(gen,f));
 for(const f of['shared_S26-ROLLING-ATC-RL-TRAIN-20261016_unified_owner_v1.py','guard_snapshot_v2.py','timing_model.py','audit_resource_v2.py','audit_simulation_study.py'])source[path.join(oldW,f)]=sha(path.join(oldW,f));
 const utility=path.join(B,'work/S26-INTEGRATED-MODEL-20261016/shared_S26-ROLLING-ATC-RL-TRAIN-20261016_forecast_owner.py');source[utility]=sha(utility);
 for(const p of[parent.packet_path,parent.case_plan_path,path.join(O,'CASE_PLAN.json'),path.join(O,'REUSED_OWN_CASES.json'),path.join(O,'BUDGET_RESERVATION.json'),path.join(O,'PURE_TESTS.json')])inputs[p]=sha(p);
 for(const f of['s26_simulator.cjs','dynamic_cost_math_v2.cjs','rolling_action_v2.cjs','s26_simulator_v2.cjs']){const p=path.join(oldW,'source_generations/SIM002_G001',f);protectedHashes[p]=sha(p)}
 const parentAudit=path.join(oldO,'RESOURCE_AUDIT_FINAL_V3/RESULT.json');if(read(parentAudit).status!=='PASS')throw Error('Parent final audit not PASS');protectedHashes[parentAudit]=sha(parentAudit);
 for(const c of read(path.join(O,'REUSED_OWN_CASES.json')))for(const p of[c.raw_path,c.config_path])reused[p]=sha(p);
 const budget=read(path.join(O,'BUDGET_RESERVATION.json'));
 const op={schema:'S26_UNIFIED_STAGE_OPERATION_V1',stage:'FAIR_RESOURCE_COMPARISON_V1',created_utc:new Date().toISOString(),entry:path.join(W,'run_fair_study.py'),node_entry:path.join(gen,'fair_case.cjs'),node_path:parent.node_path,packet_path:parent.packet_path,case_plan_path:path.join(O,'CASE_PLAN.json'),runtime_dir:path.join(O,'PRODUCTION_OWNER'),output_dir:path.join(O,'PRODUCTION'),receipts_path:path.join(O,'receipts.jsonl'),result_path:path.join(O,'PRODUCTION/EXECUTION_RESULT.json'),source_hashes:source,input_hashes:inputs,protected_hashes:protectedHashes,reuse_parent_hashes:reused,shared_byte_mutex:parent.shared_byte_mutex,volumes:['C:/','D:/'],global_accounting_ledgers:budget.global_ledgers.map(x=>x.path),environment_cap:112,planned:104,global_reserved:120886,global_cap:137712,new_policy_environments:104,new_NN:0,new_RL:0,source_generation:'FAIR001_G001',reused_own_manifest:path.join(O,'REUSED_OWN_CASES.json'),original_owner_guard_and_mutex:true};
 save(path.join(O,'PRODUCTION_OPERATION.json'),op);save(path.join(O,'REGISTRATION.json'),{status:'SEALED_BEFORE_FIRST_START',created_utc:new Date().toISOString(),production_operation:path.join(O,'PRODUCTION_OPERATION.json'),production_operation_sha256:sha(path.join(O,'PRODUCTION_OPERATION.json')),source_hashes:source,input_hashes:inputs,plan_sha256:sha(path.join(W,'PLAN.md')),new_reservation:112,global_reserved:120886});
 const ao=read(path.join(oldO,'RESOURCE_AUDIT_OPERATION_V2.json'));const audit={...op,stage:'FAIR_RESOURCE_SAVED_AUDIT_V1',entry:path.join(W,'audit_fair.py'),runtime_dir:path.join(O,'AUDIT_OWNER'),output_dir:path.join(O,'AUDIT'),result_path:path.join(O,'AUDIT/RESULT.json'),production_operation:path.join(O,'PRODUCTION_OPERATION.json'),direct_math:ao.direct_math,new_policy_environments:0,audit_cost_replays_cap:152};audit.source_hashes={...source,[ao.direct_math]:sha(ao.direct_math)};audit.input_hashes={...inputs,[path.join(O,'PRODUCTION_OPERATION.json')]:sha(path.join(O,'PRODUCTION_OPERATION.json'))};save(path.join(O,'AUDIT_OPERATION.json'),audit);
 console.log(JSON.stringify({status:'SEALED',planned:104,new_reservation:112,generation:'FAIR001_G001',direct_math:ao.direct_math}));
}
