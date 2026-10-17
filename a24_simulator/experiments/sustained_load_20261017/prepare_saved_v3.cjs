'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,'results/SUSTAINED_LOAD_REPORT_20261017_01'),r=read(path.join(out,'RESULT.json'));
if(r.new_START!==20||r.new_COMPLETE!==20)throw Error('Original finite run must finish first');
const amendment={utc:new Date().toISOString(),HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:true,
 original_operation:pin(path.join(__dirname,'OPERATION.json')),result_sha256:pin(path.join(out,'RESULT.json')).sha256,
 report_output_dir:'results/SUSTAINED_LOAD_REPORT_20261017_01',
 sources:[...['audit_v3.cjs','report_v3.cjs','diagnose_v3.cjs','prepare_saved_v3.cjs','assemble.cjs','tensor_reader.cjs'].map(f=>pin(path.join(__dirname,f))),pin(path.join(root,'experiments/work_window_20261017/reaccount.cjs'))],
 inputs:[pin(path.join(out,'MERGE_MANIFEST.json')),pin(path.join(__dirname,'CONTINUATION_OPERATION.json'))],
 reason:'Overload requires null completion energy. Original V1 and unexecuted Python V2 preserved. S26 occupies Python producer slot; V3 uses saved-only JS independent arithmetic and full neural action replay, no Python/native/training/fit and cooperative yield.',
 original_audit_v1_executed:false,original_report_v1_executed:false,Python_audit_v2_executed:false,native_records_immutable:true,new_environment_START:0,new_Python_processes:0,new_training:0,new_reservation:0,
 policy_physics_input_deadlines_service_window_changes:0,completion_energy_claim_requires_all_requests:true,
 audit_command:'C:/Program Files/nodejs/node.exe a24_simulator/experiments/sustained_load_20261017/audit_v3.cjs'};
fs.writeFileSync(path.join(__dirname,'SAVED_AUDIT_V3.json'),JSON.stringify(amendment,null,2)+'\n',{flag:'wx'});console.log('V3 saved-only censoring semantics pinned; native restart0.');
