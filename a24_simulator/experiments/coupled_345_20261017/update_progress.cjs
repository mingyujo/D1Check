'use strict';
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),file=path.join(root,'CONTINUE.json'),prior=read(file);
const completed=[3701,3702,3703].filter(s=>fs.existsSync(path.join(root,'results/COUPLED_345_20261017_01/PROGRESS_S'+s+'.json')));
const state={status:'REGISTERED_FINITE_RESEARCH_RUNNING',report:'docs/COUPLED_345.md',
 operation:'experiments/coupled_345_20261017/OPERATION.json',entry:'experiments/coupled_345_20261017/run_experiment.py',
 output:'results/COUPLED_345_20261017_01',planned_START:602,reserved_cap:640,completed_seed_milestones:completed,
 per_completed_seed:{train_episodes:128,PPO_updates:64},
 proof_files:completed.map(s=>'results/COUPLED_345_20261017_01/PROGRESS_S'+s+'.json'),
 live_receipt:'results/COUPLED_345_20261017_01/receipts.jsonl',
 do_not_restart_running_or_completed_operation:true,generation_complete:false,policy_superiority_verified:false,
 model:'explicit thermal/power hypotheses; not calibrated A24 feedback',
 original_RL256_remaining:0,separate_RR1_untouched:true,new_device_commands:0,new_physical_fit:0,measured_J:null};
delete prior.coupled_345_development;
fs.writeFileSync(file,JSON.stringify({coupled_345_development:state,...prior},null,2)+'\n');
console.log(JSON.stringify(state));
