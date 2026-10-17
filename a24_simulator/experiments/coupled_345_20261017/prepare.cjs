'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'});
const data=require('./design.cjs').design();
for(const group of ['train','dev','fresh','p0'])for(const c of data[group]){
 if(c.input.requests.length!==c.n||c.work_window[0]!==35||c.temperature_c<26)throw Error('Input contract');
 for(const [i,q] of c.input.requests.entries())if(q.ordinal!==i||q.deadline_s<=q.arrival_s||!['C_M128','D_M128'].includes(q.profile))throw Error('Public request');
}
for(let i=0;i<6;i++)if(JSON.stringify(data.fresh[i].input)!==JSON.stringify(data.fresh[i+6].input))throw Error('Temperature pairs must share all work');
save(path.join(__dirname,'INPUTS.json'),data);
const physics={baseline:1.204399931712509,idle_c:26,reference_c:26,thermal_tau_s:25,thermal_resistance:12,idle_tail_s:.9,
 onset_c:32,cpu_slope:.07,gpu_slope:.045,minimum_speed:.45,leakage_fraction:.2,leakage_per_c:.025,strength:1,tick_s:.1};
save(path.join(__dirname,'PARAMETERS.json'),{physics,evidence:'EXPLICIT_RESEARCH_HYPOTHESES_NOT_A24_FITTED_FEEDBACK',
 unchanged_anchors:'historical SERIAL work and previous steady solo/shared coefficient decomposition',
 public_temperature:'scenario proxy at first arrival35s; not a calibrated CPU junction or Android thermal trip point',
 DVFS:'only execution progress scales; dynamic part uses f^3 assuming voltage scales with frequency; bounded temperature leakage',
 coupled_pair_progress:'explicit independent serial work, plus common thermal coupling; previous measured pair-rate association is preserved in the original simulator',
 references:['https://developer.android.com/games/optimize/adpf/thermal','https://www.kernel.org/doc/html/v6.7/driver-api/thermal/power_allocator.html'],
 objective_weights:[.5,.5,8,4,30],fixed_ATC_action_prior:0,
 candidate_set:'max8 current requests: EDF4 + FIFO head + RR head + ATC2; physical free routes, three bounded WAIT doses',
 current_cost_state_in_NN:['temperature','shared activation','CPU/GPU speed','same-integral nominal continuation costs'],
 original_baseline_and_models_unchanged:true,parameter_selection_by_evaluation_gap:false,measured_J:null});
const priorBudget=path.join(root,'experiments/rl_cost_20261017/BUDGET_RESERVATION.json'),p=read(priorBudget);
const previousProof=path.join(root,'results/SHARED_COST_POLICY_V2_20261017_01/FINAL_HANDOFF_PROOF.json');
if(read(previousProof).original_envelope_remaining!==0)throw Error('Inspect old remaining envelope');
save(path.join(__dirname,'BUDGET_RESERVATION.json'),{schema:'A24-coupled345-new-reservation-v1',
 previous_reservation_pin:pin(priorBudget),closed_original_256_proof:pin(previousProof),
 previous_global_reserved:p.global_reserved,new_reservation:640,global_reserved:p.global_reserved+640,global_cap:p.global_cap,
 unreserved:p.global_cap-p.global_reserved-640,planned_START:602,cap:640,
 allocation:{P0:4,TRAIN:384,DEV:42,FRESH:96,FEEDBACK_OFF:36,COST_MISMATCH:12,STRENGTH:24,TIMESTEP:4},
 original_RL256_remaining:0,separate_RR_unused1_untouched:true,automatic_retry:false,
 global_accounting:'latest tracked reservation snapshot at f025615; not a fresh all-host actual-start census',
 user_authority:'2026-10-17: improve3/4/5 with logically explained changes and actual scheduling/learning verification'});
const previous=read(path.join(root,'experiments/choice_opportunities_20261017/OPERATION_V2.json'));
const local=['dynamics.py','bootstrap.py','engine.py','controller.py','nn_train.py','rewards.py','run_experiment.py','audit.py','prepare.cjs','design.cjs','test_contracts.py'].map(p=>pin(path.join(__dirname,p)));
save(path.join(__dirname,'OPERATION.json'),{schema:'A24-coupled345-operation-v1',created_utc:new Date().toISOString(),
 base_commit:'f025615f86c068d16385746e888ca78b5aa4b435',sources:[...previous.sources,...local],
 registration:previous.registration,inputs:pin(path.join(__dirname,'INPUTS.json')),
 input_pins:[...['INPUTS.json','PARAMETERS.json','BUDGET_RESERVATION.json','PURE_TEST_RESULT.json','PRESTART_TEST_FAILURE_01.json'].map(p=>pin(path.join(__dirname,p))),
 pin(path.join(root,'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'))],
 output_dir:'results/COUPLED_345_20261017_01',environment_cap:640,planned_START:602,wall_clock_limit_s:10800,
 learner_seeds:[3701,3702,3703],train_episodes_per_seed:128,episodes_per_update:2,checkpoint_episodes:[64,128],
 physics,DEV_selection:'response missing, paired EDF ontime harm, then mean weighted objective; no fresh results',
 evaluate_all_three_seed_models:true,fixed_ATC_prior:0,new_physical_fit:0,automatic_retry:false,
 independent_physical_confirmation:false,measured_J:null,
 original_results_and_sources_immutable:true});
console.log('Registered602 planned START within new640 reservation; old256 remains consumed, RR1 separate.');
