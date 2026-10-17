'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),r=read(path.join(out,'RESULT.json'));
if(r.new_START!==20||r.new_COMPLETE!==20)throw Error('Original finite run must finish first');
const amendment={utc:new Date().toISOString(),HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:true,
 original_operation:pin(path.join(__dirname,'OPERATION.json')),result_sha256:pin(path.join(out,'RESULT.json')).sha256,
 sources:['audit_v2.py','report_v2.cjs','diagnose.cjs','prepare_saved_v2.cjs'].map(f=>pin(path.join(__dirname,f))),
 reason:'Observed overload leaves requests never AVAILABLE. Completion energy must be undefined/null, not drain-censored energy. Original unused V1 postprocessors preserved; speed descriptive metric also clipped at supply boundary.',
 original_audit_v1_executed:false,original_report_v1_executed:false,native_records_immutable:true,new_environment_START:0,new_training:0,new_reservation:0,
 policy_physics_input_deadlines_service_window_changes:0,completion_energy_claim_requires_all_requests:true,
 audit_command:'C:/Users/user/anaconda3/python.exe a24_simulator/experiments/sustained_load_20261017/audit_v2.py'};
fs.writeFileSync(path.join(__dirname,'SAVED_AUDIT_V2.json'),JSON.stringify(amendment,null,2)+'\n',{flag:'wx'});console.log('V2 saved-only censoring semantics pinned; native restart0.');
