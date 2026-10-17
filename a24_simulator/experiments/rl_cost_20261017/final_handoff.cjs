// Closed-evidence handoff only. Never starts an environment or optimizer.
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/RL_COST_20261017_01');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const pin=p=>{const b=fs.readFileSync(p);return {path:path.resolve(p),bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex')}};
const need=(x,s)=>{if(!x)throw Error(s)};
const snapshot=read(process.argv[2]);
need(snapshot.active_python.length===0&&snapshot.active_known_producers.length===0,'Fresh producer-free snapshot required');
need(snapshot.volumes.every(x=>x.free_bytes>=8589934592),'All access volumes 8GiB');
const result=read(path.join(out,'RESULT.json')),complete=read(path.join(out,'COMPLETE.json'));
const nn=read(path.join(out,'NN_AUDIT.json')),saved=read(path.join(out,'SAVED_AUDIT.json')),ui=read(path.join(out,'UI_QA/RESULT.json')),data=read(path.join(out,'REPORT_DATA.json'));
need(complete.new_COMPLETE===223&&complete.result_sha256===pin(path.join(out,'RESULT.json')).sha256,'Exact223 COMPLETE');
need(nn.status.startsWith('PASS_EXACT')&&saved.status==='PASS'&&ui.status==='PASS','Actual three audits');
need(ui.html_sha256===pin(path.join(out,'REPORT.html')).sha256,'QA HTML');
const operations=['OPERATION.json','POSTRUN_OPERATION.json','SAVED_AUDIT_OPERATION.json','REPORT_OPERATION.json','DOCUMENT_OPERATION.json'];
let checked=0;for(const f of operations)for(const p of read(path.join(__dirname,f)).pins){const actual=pin(p.path);need(actual.sha256===p.sha256&&actual.bytes===p.bytes,'Pin drift '+p.path);checked++}
const budget=read(path.join(__dirname,'BUDGET_RESERVATION.json')),ledgers=[];
const currentReserved=Math.max(budget.global_reserved,...snapshot.reservation_registry.map(r=>r.global_reserved));
need(currentReserved<=budget.global_cap,'Fresh registered reservations within global cap');
need(currentReserved===budget.global_reserved,'New reservation requires an explicit fresh ledger union, never silently incomplete accounting');
// Caller verified no producers; Node file opens allow sharing and never lock a writer.
for(const item of [...budget.global_ledgers,{path:path.join(out,'receipts.jsonl')}]){
 if(ledgers.some(r=>r.path.toLowerCase()===item.path.toLowerCase()))continue;
 const lines=fs.readFileSync(item.path,'utf8').replace(/^\uFEFF/,'').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
 const start=lines.filter(r=>r.event==='START').length;
 ledgers.push({...pin(item.path),START:start,COMPLETE:lines.filter(r=>r.event==='COMPLETE').length,FAIL:lines.filter(r=>r.event==='FAIL').length});
}
const total=ledgers.reduce((s,r)=>s+r.START,0);need(total<=budget.global_cap&&total<=currentReserved,'Global START ceiling');
const artifact=process.argv[3];need(pin(artifact).sha256===ui.html_sha256,'User artifact exact');
const proof={schema:'A24-RR-cost-RL-final-handoff-v1',created_utc:new Date().toISOString(),git_before_final:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:root}).toString().trim(),
 completed:{RR_START:7,RR_COMPLETE:7,RR_FAIL:0,RL_START:223,RL_COMPLETE:223,RL_FAIL:0,TRAIN:96,DEV:48,fresh_eval:60,historical:7,NN_removed:12,updates:result.updates,Adam_steps:result.Adam_steps,selected_episode:result.selected.episode},
 DEV_qualified:data.DEV_qualified,nominal_joint_goal:data.nominal_joint_goal,interactive_default_replaced:false,
 audits:{NN:pin(path.join(out,'NN_AUDIT.json')),saved:pin(path.join(out,'SAVED_AUDIT.json')),UI:pin(path.join(out,'UI_QA/RESULT.json')),pins_rechecked:checked},
 evidence:['RESULT.json','COMPLETE.json','SELECTION_FROZEN.json','REPORT_DATA.json','REPORT.html'].map(f=>pin(path.join(out,f))),
 documentation:pin(path.join(root,'docs/COST_RL_COMPARISON.md')),source:pin(__filename),producer_snapshot:pin(process.argv[2]),user_artifact:pin(artifact),
 budget:{global_reserved:currentReserved,global_reserved_at_this_registration:budget.global_reserved,global_cap:budget.global_cap,actual_START:total,ledgers,RR_reserved:8,RR_used:7,RL_reserved:256,RL_used:223,remaining_not_automatically_authorized:34},
 limits:{measured_J:null,energy_error:null,CI:null,physical_goal:false,phone_RL_verified:false,periodic_measurement_polling:false,recurring_automation_created:false,original_physics_modified:false},
 incident:pin(path.join(root,'experiments/rr_20261017/CROSS_WORK_READ_SHARING_INCIDENT.json'))};
fs.writeFileSync(path.join(out,'FINAL_HANDOFF_PROOF.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'FINAL_HANDOFF_SAVED',START:total,checked,proof_sha256:pin(path.join(out,'FINAL_HANDOFF_PROOF.json')).sha256}));
