const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process'),design=require('./competition_design.cjs');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'results/COMPETITION_INPUTS_20261017_01');
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
if(fs.existsSync(out))throw Error('Registered input output exists');
const test=JSON.parse(cp.execFileSync(process.execPath,[path.join(__dirname,'test_design.cjs')],{encoding:'utf8'}));
const developmental=design.generate(20261711),confirmation=design.generate(20261731),witnessIndices=[0,3,5,10];
const all={schema:'A24-competition-public-inputs-v1',SPEC:design.SPEC,developmental,confirmation,
 static_audits:[...developmental,...confirmation].map(c=>({label:c.label,...design.audit(c)})),
 witness_indices:witnessIndices,witness_cases:witnessIndices.map(i=>confirmation[i]),
 witness_policy_plan:['EDF_CPU_FIRST','ROLLING_ATC_RL_PROTECTED48'],witness_START_cap:8,
 existing_shared_START:502,shared_cap:512,maximum_after_witness:510,global_reservation_increment:0,
 evaluation_after_policy_result_selection:false,NN_training:0,physical_model_fits:0,previous24_preserved:true,
 actor_scope:'same frozen EP024 and independent EDF; diagnostic input evaluation, not fresh device confirmation',
 source_pins:['competition_design.cjs','test_design.cjs','prepare_inputs.cjs'].map(n=>pin(path.join(__dirname,n))),
 source_HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),utc:new Date().toISOString()};
fs.mkdirSync(out,{recursive:false});fs.writeFileSync(path.join(out,'INPUTS.json'),JSON.stringify(all,null,2)+'\n',{flag:'wx'});
fs.writeFileSync(path.join(out,'STATIC_TESTS.json'),JSON.stringify(test,null,2)+'\n',{flag:'wx'});
fs.writeFileSync(path.join(out,'COMPLETE_STATIC.json'),JSON.stringify({status:'COMPLETE_STATIC_INPUT_DESIGN_ONLY',input:pin(path.join(out,'INPUTS.json')),test,actual_policy_environments:0,actual_queue_competition_PASS:false,utc:new Date().toISOString()},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:'COMPLETE_STATIC_INPUT_DESIGN_ONLY',cases:24,requests_per_case:48,assertions:test.assertions,input:pin(path.join(out,'INPUTS.json'))}));
