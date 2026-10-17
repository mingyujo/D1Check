'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const parentPath=path.join(__dirname,'OPERATION.json'),old=read(parentPath),out=path.join(root,old.output_dir),failure=read(path.join(out,'FAILURE.json'));
const receipts=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split('\n').map(JSON.parse),starts=receipts.filter(r=>r.event==='START'),done=receipts.filter(r=>r.event==='COMPLETE');
if(starts.length!==18||done.length!==18||receipts.some(r=>r.event==='FAIL')||failure.new_START!==18)throw Error('Exactly18 completed native executions required');
if(starts.some(r=>['SUPPLY_600_1_ATC','SUPPLY_600_1_RL'].includes(r.label)))throw Error('Remaining identities already consumed');
const budget={utc:new Date().toISOString(),previous:pin(path.join(__dirname,'BUDGET_RESERVATION.json')),global_new_reservation:0,
 global_reserved:125790,global_cap:137712,original_cap:24,original_native_START:18,original_native_COMPLETE:18,
 transferred_unused_slots:2,continuation_cap:2,continuation_planned_START:2,untransferred_unused_slots:4,
 restored_frozen_timing_bank_total:2,new_training:0,new_physical_fit:0,automatic_retry:false,
 reason:'External transient Python caused global leaf guard rejection beforeSTART19. Old closed namespace preserved; execute only two never-started labels under new identities.'};
fs.writeFileSync(path.join(__dirname,'CONTINUATION_BUDGET.json'),JSON.stringify(budget,null,2)+'\n',{flag:'wx'});
const sources=['continue_two.py','prepare_continuation.cjs'].map(f=>pin(path.join(__dirname,f)));
const op={...old,schema:'A24-sustained-load-never-started-two-continuation-v1',utc:new Date().toISOString(),
 base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),parent_native_operation:pin(parentPath),
 sources:[...old.sources,...sources],input_pins:[...old.input_pins,pin(path.join(__dirname,'CONTINUATION_BUDGET.json')),
  pin(path.join(out,'FAILURE.json')),pin(path.join(out,'receipts.jsonl')),...done.map(r=>pin(path.join(out,r.label+'.json')))],
 output_dir:'results/SUSTAINED_LOAD_CONT_20261017_01',environment_cap:2,planned_START:2,
 continuation_only:['SUPPLY_600_1_ATC','SUPPLY_600_1_RL'],old_native_reexecution:0};
fs.writeFileSync(path.join(__dirname,'CONTINUATION_OPERATION.json'),JSON.stringify(op,null,2)+'\n',{flag:'wx'});console.log('Registered only2 never-started executions; global reservation unchanged.');
