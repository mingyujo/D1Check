'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),pin=p=>({path:p,sha256:sha(p),bytes:fs.statSync(p).size});
const save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2)+'\n',{flag:'wx'}),oldop=read(path.join(root,'experiments/density_headroom_20261018/OPERATION.json')),density=read(path.join(root,'experiments/load_density_20261017/OPERATION.json'));
const original=path.join(root,density.output_dir),potential=path.join(root,oldop.output_dir),summary=path.join(root,'results/DENSITY_HEADROOM_COUPLED_20261018_01');
if(read(path.join(potential,'RESULT.json')).new_COMPLETE!==82||read(path.join(summary,'AUDIT.json')).status!=='PASS')throw Error('Complete original headroom and saved-only bound refinement first');
const pre=read(path.join(__dirname,'PREFLIGHT_RESULT.json'));if(pre.status!=='PASS'||pre.new_environment_START!==0)throw Error('Meaningful mask/source tests and AST first');
for(const p of [...pre.AST,...pre.Node_check])if(sha(p.path)!==p.sha256)throw Error('Preflight source changed; preserve test record and register a new version');
const own=['pure_resources.py','guard_controller.py','bank_model.py','run.py','test_contracts.py','preflight.py','figures.py','audit.cjs','report.cjs','prepare.cjs','README.md'].map(f=>pin(path.join(__dirname,f)));
const deps=['controller.py','nn_train.py','rewards.py','engine.py','dynamics.py','bootstrap.py'].map(f=>pin(path.join(root,'experiments/coupled_345_20261017',f)));
const generated=[pin(path.join(root,'experiments/guard_ablation_20261018/ENVIRONMENT0_IMPORT_FAILURE.json')),pin(path.join(root,'experiments/guard_ablation_20261018/OPERATION.json')),pin(path.join(root,'experiments/guard_ablation_20261018/BUDGET_RESERVATION.json')),pin(path.resolve(root,'../../S26-D1Check/s26_simulator/experiments/a24_unprotected_v1/BUDGET_RESERVATION.json'))];
for(const dir of [potential,summary,original])for(const f of fs.readdirSync(dir))if(/BANK|raw\.json\.gz|RESULT|COMPLETE|AUDIT|EVALUATION|SUMMARY|ALL_ROWS|PHASE_PROOFS|DIAGNOSIS|PROOF|REPORT/.test(f))generated.push(pin(path.join(dir,f)));
const rewardFile=path.join(__dirname,'SAVED_REWARD_DIAGNOSIS.json'),reward=read(rewardFile);
generated.push(pin(rewardFile),...reward.sources.map(p=>pin(path.resolve(root,'..',p.path))));
const unique=a=>[...new Map(a.map(p=>[p.path.toLowerCase(),p])).values()];
const budget={schema:'A24-guard-ablation-reservation-v1',utc:new Date().toISOString(),new_global_reservation:0,transferred_unused_environment0_v1:44,total44:44,planned_START:40,
 source_operation_sha256:sha(path.join(root,'experiments/density_headroom_20261018/OPERATION.json')),source82_complete:true,old_headroom_remaining_after_transfer:0,
 known_tracked_global_snapshot_before:126576,known_tracked_global_snapshot_after:126576,global_ceiling:137712,not_a_fresh_all_host_census:true,
 existing_coupled38_savings8_sustained4_density4_RR1_untouched:true,automatic_retry:false,unused4_not_automatically_consumed:true};
const parallelFile=path.resolve(root,'../../S26-D1Check/s26_simulator/experiments/a24_unprotected_v1/BUDGET_RESERVATION.json'),parallel=read(parallelFile);if(parallel.new_reservation!==576)throw Error('Review parallel reservation');
let tracked=126000+parallel.new_reservation;const marginFile=path.resolve(root,'../../S26-D1Check/s26_simulator/experiments/a24_load_margin_v1/BUDGET_RESERVATION.json');if(fs.existsSync(marginFile)){const m=read(marginFile),extra=m.new_reservation??m.additional_reservation??0;if(!Number.isFinite(extra)||extra<0)throw Error('Parallel margin accounting');tracked+=extra;budget.parallel_margin=pin(marginFile);generated.push(pin(marginFile));}
budget.known_tracked_global_snapshot_before=tracked;budget.known_tracked_global_snapshot_after=tracked;budget.parallel_reservation=pin(parallelFile);save(path.join(__dirname,'BUDGET_RESERVATION.json'),budget);
save(path.join(__dirname,'OPERATION.json'),{schema:'A24-urgent-WAIT-guard-2x2-v1',utc:new Date().toISOString(),base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),
 output_dir:'results/GUARD_ABLATION_V2_20261018_01',potential_output:oldop.output_dir,original_output:density.output_dir,summary_output:'results/DENSITY_HEADROOM_COUPLED_20261018_01',
 sources:unique([...oldop.sources,...density.sources,...deps,...own]),input_pins:unique([...oldop.input_pins,...density.input_pins,...generated,pin(path.join(__dirname,'PUBLIC_CATALOG.json.gz')),pin(path.join(__dirname,'PREFLIGHT_RESULT.json')),pin(path.join(__dirname,'BUDGET_RESERVATION.json'))]),
 inputs:density.inputs,checkpoint:density.checkpoint,learner_seed:density.learner_seed,physics:oldop.physics,catalog:pin(path.join(__dirname,'PUBLIC_CATALOG.json.gz')),
 catalog_uncompressed_sha256:'4a55f81d9a7e934cc24460c277e30c278ff49bcb61f15e2a312a32f7efd58c4b',
 policies:['GUARD_ON_NN','GUARD_OFF_NN','GUARD_ON_ZERO','GUARD_OFF_ZERO'],planned_START:40,environment_cap:44,
 experiment:'Only urgent-deadline feasibility of WAIT candidates changes; all DISPATCH choices already NN-controlled. Common50ms coalescing and WAIT total/per-head caps stay identical. Original penalty weights unchanged.',
 zero_control:'Zero final neural actor layer only; canonical first action tie break. Not a newly trained policy.',
 physical_engine_unchanged:true,original_timing_model_restores:0,frozen_potential_banks:10,public_nominals_from:'Original baseline public estimates, checked constant per request; no actual latent vectors supplied to actor',
 all10_ON_NN_exact_original_trace_and_neural_banks_required:true,new_training:0,new_physical_fit:0,new_device_actions:0,
 own_Python_limit:1,global_Python_limit:2,min_free_GiB:8,wall_clock_limit_s:7200,automatic_retry:false,all_original112_plus_new40_displayed:true,
 follow_up:'After frozen ablation, diagnose before separately registering paired no-guard learning and targeted policy repair; no unbounded automatic search or new physical coefficients.',
 node_executable:'C:/Program Files/nodejs/node.exe'});
console.log(JSON.stringify({status:'REGISTERED_GUARD_ABLATION',new_reservation:0,transfer:44,cap:44,planned:40}));
