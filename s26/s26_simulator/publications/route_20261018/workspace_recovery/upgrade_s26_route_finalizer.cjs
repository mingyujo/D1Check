'use strict';
const fs=require('fs'),path=require('path'),p=path.join(__dirname,'finalize_s26_route_all.cjs');let s=fs.readFileSync(p,'utf8');
function sub(a,b){if(!s.includes(a))throw Error('Missing upgrade anchor '+a);s=s.replace(a,b);}
sub("'route_event_learning_v1'];","'route_event_learning_v1','route_group_learning_v1'];");
sub("summary=read(at(dirs[3],'COMPARISON_SUMMARY.json'))","groupNN=read(at(dirs[4],'NN_AUDIT.json')),summary=read(at(dirs[4],'COMPARISON_SUMMARY.json'))");
sub("read(path.join(R,'experiments/route_energy_v1/NUMERICAL_BUDGET_ALLOCATION.json'))","read(path.join(R,'experiments/route_group_learning_v1/WAVE_BUDGET_TOTALS.json'))");
sub("const family=read(at(dirs[3]","const family=read(at(dirs[4]");
sub("if(read(at(dirs[3],'FINAL_COMPONENT_SYNTHESIS.json'))","if(read(at(dirs[4],'FINAL_COMPONENT_SYNTHESIS.json'))");
sub('[420,18,54,134][i]','[420,18,54,134,114][i]');sub('eventNN.replayed_updates!==12','eventNN.replayed_updates!==12||groupNN.replayed_updates!==3');
sub('for(const d of [dirs[0],dirs[3]])','for(const d of [dirs[0],dirs[3],dirs[4]])');sub('if(d===dirs[3])names.push','if(d===dirs[3]||d===dirs[4])names.push');
sub('training_episodes:120,PPO_updates:60,BC_actor_fits:1,BC_steps:summary.BC_steps','training_episodes:126,PPO_updates:63,BC_actor_fits:2,BC_steps:summary.BC_steps+read(at(dirs[3],\'COMPARISON_SUMMARY.json\')).BC_steps');
sub('NN_checks:mainNN.checks+eventNN.checks,NN_frames:mainNN.frames+eventNN.frames','NN_checks:mainNN.checks+eventNN.checks+groupNN.checks,NN_frames:mainNN.frames+eventNN.frames+groupNN.frames');
sub("current_report:d===dirs[3]?", "current_report:d===dirs[4]?'../../S26_ROUTE_GROUP_RESULTS_KO.md':d===dirs[3]?");
s=s.replaceAll('TRAIN120·PPO60','TRAIN126·PPO63');sub('[최신 결과](S26_ROUTE_EVENT_RESULTS_KO.md)','[최신 희소경로 보완 결과](S26_ROUTE_GROUP_RESULTS_KO.md) · [앞 사건 RL 결과](S26_ROUTE_EVENT_RESULTS_KO.md)');
s=s.replaceAll('626환경·PPO60update','740환경·PPO63update');sub("experiments/route_event_learning_v1'),history", "experiments/route_group_learning_v1'),history");
sub("'S26_ROUTE_WITNESS_RESULTS_KO.md','S26_ROUTE_EVENT_RESULTS_KO.md'", "'S26_ROUTE_WITNESS_RESULTS_KO.md','S26_ROUTE_EVENT_RESULTS_KO.md','S26_ROUTE_GROUP_RESULTS_KO.md'");
sub("CURRENT_STATE.json).", "CURRENT_STATE.json).");
// Current entry follows the final group learner while preserving every earlier report.
s=s.replaceAll('(experiments/route_event_learning_v1/CURRENT_STATE.json)', '(experiments/route_group_learning_v1/CURRENT_STATE.json)');
fs.writeFileSync(path.join(__dirname,'finalize_s26_route_all_v2.cjs'),s,{flag:'wx'});
let component=fs.readFileSync(path.join(__dirname,'summarize_s26_route_final.cjs'),'utf8').replaceAll('route_event_learning_v1','route_group_learning_v1').replaceAll('S26_ROUTE_EVENT_RESULTS_KO.md','S26_ROUTE_GROUP_RESULTS_KO.md').replaceAll('r.seed===781000','r.seed===881000').replace("r.seed!==null?'EVENT_PPO'","r.seed===781081?'OLD_EVENT_RL':r.seed!==null?'EVENT_PPO'").replace("OLD_RL:'기존 RL'","OLD_RL:'기존 RL',OLD_EVENT_RL:'앞 사건 RL'").replace('updates.length!==12','updates.length!==3').replace('12개 PPO update','3개 PPO update');
fs.writeFileSync(path.join(__dirname,'summarize_s26_route_group_final.cjs'),component,{flag:'wx'});console.log('V2_FINALIZER_AND_SAVED_COMPONENT_SYNTHESIS_PREPARED');
