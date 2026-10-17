'use strict';
// Pure input generation; no policy/model/outcomes used to choose conditions.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),D=require('../competition_cost_20261017/competition_design.cjs');
function digest(x){return crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex')}
function extend(original,n){
 const x=JSON.parse(JSON.stringify(original)),q=x.input.requests,cycle=Math.max(...q.map(r=>r.arrival_s))-35+1.5;
 x.input.requests=Array.from({length:n},(_,i)=>{const p=q[i%48],offset=Math.floor(i/48)*cycle;
  return {...p,ordinal:i,arrival_s:+(p.arrival_s+offset).toFixed(8),deadline_s:+(p.deadline_s+offset).toFixed(8)}});
 const hi=+(Math.max(...x.input.requests.map(r=>r.arrival_s))+15).toFixed(8);
 return {...x,n,work_window:[35,hi],service_stop_s:hi,drain_stop_s:+(hi+30).toFixed(8),
         observation_end_s:+(hi+180).toFixed(8),common_potential_key:['RL_COST_20261017',x.input.seed,n,digest(x.input.requests)]};
}
const train=Array.from({length:96},(_,i)=>extend(D.generate(20268101+i)[i%12],[48,96,192][Math.floor(i/12)%3]));
const dev=D.generate(20268201).map((c,i)=>extend(c,[48,96,192][i%3]));
const fresh_eval=D.generate(20268301).map((c,i)=>extend(c,[48,96,192][i%3]));
const old=JSON.parse(fs.readFileSync(path.join(root,'experiments/rules_no_rl_20261017/INPUTS.json'),'utf8'));
const value={schema:'A24-cost-RL-inputs-v1',train,dev,fresh_eval,historical:old.cases,
 partition:{train_seed:[20268101,20268196],dev_seed:20268201,eval_seed:20268301,
  heldout_unit:'new simulation seed/recipes, not new physical device data',history:'already-seen fixed recipes; diagnostic only'},
 model_fit:0,selection_by_policy_result:false,maximum_requests:3072};
const file=path.join(__dirname,'INPUTS.json');fs.writeFileSync(file,JSON.stringify(value,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({train:train.length,dev:dev.length,eval:fresh_eval.length,historical:old.cases.length,planned_START:96+12+36+60+7+12}));
