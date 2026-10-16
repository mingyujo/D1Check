const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),design=require(path.join(root,'src/bulk_design.cjs'));
const pin=p=>{const b=fs.readFileSync(p);return {path:p,sha256:crypto.createHash('sha256').update(b).digest('hex'),bytes:b.length};};
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const reg=read(path.join(root,'models/registration.json')),config=read(path.join(__dirname,'CONFIG_DESCRIPTION.json'));
const generate=(counts,mixes,patterns,loads,seeds)=>design.generate({counts,mixes,patterns,loads,seeds,slacks:[1],alpha:1,rl_seed:20261028,initial_context:'M128'});
const train=Array.from({length:64},(_,i)=>generate([48],[.25,.75],['steady','burst'],[.5,.85,1.2],[20262001+i])[i%12]);
const dev=generate([48],[.25,.75],['steady','burst'],[.65,1.15],[20263001]);
const fresh=generate([48],[.25,.75],['steady','burst'],[.5,.85,1.2],[20264001,20264002]);
// Reorder as seed blocks so the first12 mechanism cases form a complete grid.
fresh.sort((a,b)=>a.input.seed-b.input.seed||a.index-b.index);
const receipts=fs.readFileSync(path.join(root,'runtime/receipts.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const before=receipts.filter(x=>x.event==='START').length;if(before!==201)throw Error('Shared START snapshot differs');
const original=read(path.join(root,'results/FOUR_ROUTE_V2_EVAL.json'));
const op={schema:'A24-protected48-training-operation-v1',registered_utc:new Date().toISOString(),
 protection_config:config.protection_config,reward_spec:config.reward_spec,
 learner_seed:20261032,learner_settings:{episodes_per_update:8,epochs:4,minibatch_frames:256,learning_rate:.0001,clip:.15,value_coef:.5,entropy_coef:.005,gradient_clip:.5,kl_stop:.03,gae_time_s:20,dual_lr:5},
 warm_start_network_sha256:original.cases[0].rows[0].network_sha256,
 checkpoint_episodes:[24,48,64],mechanism_control_conditions:12,
 cases:{train,dev,fresh_eval:fresh},
 new_environment_cap:194,expected_child_START_before:before,parent_START:105,shared_cap:512,
 output_dir:'results/PROTECTED48_20261016_01',runtime_dir:'runtime/protected48_20261016_01',
 stage_counts:{TRAIN:64,DEV_EDF:8,DEV_policy:24,fresh_EDF_old_new:72,mechanism_control:12,historical_new_only:14},
 source_pins:['protected_policy.py','dense_rewards.py','run_training.py','test_protected.py','prepare_plan.cjs'].map(x=>pin(path.join(__dirname,x))),
 input_pins:['models/registration.json','models/PPO_FOUR_ROUTE_EP032.pt','results/FOUR_ROUTE_V2_EVAL.json','results/EDF_CPU_FIRST_20261016_01/RESULT.json','models/TRAINING_RESULT.json','src/bulk_design.cjs','experiments/edf_cpu_first_20261016/policy.py','experiments/protected48_20261016/CONFIG_DESCRIPTION.json','experiments/protected48_20261016/TEST_RESULTS.json'].map(x=>pin(path.join(root,x))),
 model_source_pins:reg.source_pins,model_input_pins:reg.input_pins,
 DEV_selection:['missing','urgent_misses','normal_misses','joint_harm_count','10pct_total_and_0.5C_target_shortfall','total_J','mean_AP'],
 targets:{service:'No deadline/completion harm versus EDF, maximize all requested on-time',total_reduction:.10,mean_AP_reduction_c:.5,increment_reported_separately:true},
 no_outcome_adaptive_grid:true,reselection_after_eval:false,new_global_reservation:0,model_fit:0,HTTP:0,device_commands:0,periodic:false,automatic_retry:false,
 source_HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim()};
const ledger=pin(path.join(root,'runtime/receipts.jsonl'));op.ledger_prefix_before=ledger;
write(path.join(__dirname,'OPERATION.json'),op);
console.log(JSON.stringify({operation:pin(path.join(__dirname,'OPERATION.json')),new_START_cap:194,shared_after_max:105+before+194,remaining_after:512-105-before-194}));
