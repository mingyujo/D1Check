// One-time source/input/ledger registration. Does not launch Python or a worker.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const pin=p=>{const b=fs.readFileSync(p);return {path:p,sha256:crypto.createHash('sha256').update(b).digest('hex'),bytes:b.length};};
const write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const reg=read(root+'/models/registration.json'),input=read(root+'/results/COMPETITION_INPUTS_20261017_01/INPUTS.json');
const ledger=root+'/runtime/receipts.jsonl',before=fs.readFileSync(ledger,'utf8').trim().split(/\r?\n/).map(JSON.parse).filter(x=>x.event==='START').length;
if(before!==397||input.witness_cases.length!==4||input.witness_START_cap!==8)throw Error('Budget/input drift');
const base={registered_utc:new Date().toISOString(),source_HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),
 known_PS_producer_paths:[],automatic_retry:false,automation:false,HTTP:0,new_device_measurement:0,new_global_reservation:0};
const sources=['run_witness.py','competition_design.cjs','prepare_operations.cjs','state_cost.py','fit_cost.py','test_state_cost.py'].map(x=>pin(path.join(__dirname,x)));
const common=['models/registration.json','results/COMPETITION_INPUTS_20261017_01/INPUTS.json','experiments/edf_cpu_first_20261016/policy.py',
 'experiments/protected48_v2_20261016/protected_policy.py','src/lab_backend.py','src/interactive_kernel.py','reference/rolling/learner.py','reference/model_integration/runtime_guard.py'].map(x=>pin(path.join(root,x)));
write(path.join(__dirname,'WITNESS_OPERATION.json'),{...base,schema:'A24-competition-witness-operation-v1',source_pins:sources,
 input_pins:common,checkpoint:pin(root+'/results/PROTECTED48_V2_20261016_01/PPO_PROTECTED48_EP024.pt'),
 ledger_prefix:pin(ledger),expected_child_START_before:before,new_environment_cap:8,parent_START:105,shared_cap:512,
 cases:input.witness_cases,output_dir:'results/COMPETITION_WITNESS_20261017_01',
 physical_model_unchanged:true,NN_training:0,input_selected_before_policy_outcomes:true,
 policies:['EDF_CPU_FIRST','ROLLING_ATC_RL_PROTECTED48']});
console.log('REGISTERED witness',pin(path.join(__dirname,'WITNESS_OPERATION.json')));
