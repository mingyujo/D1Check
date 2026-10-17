'use strict';
// Deterministic mathematical fixtures. No Simulator, sampled episode, or fitting.
const fs=require('fs'),math=require('./dynamic_cost_math_v2.cjs'),base=require('./s26_simulator.cjs'),tm=require('./multi_timing.cjs'),rc=require('./resource_contract.cjs');
const p=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),fixtures=[],rates=[];
for(let ci=0;ci<3;ci++)for(let variant=0;variant<6;variant++){
 const ctx=p.scenarios.find(s=>s.context_index===ci).context,ints=ctx.pre_activity9.intervals.map(xs=>xs.map(x=>x.slice()));
 const patterns=[[0,0,0,0,0,0,0,0,0],[0,0,1,0,0,0,1,0,0],[0,1,1,0,0,0,1,0,1],[0,1,1,1,0,0,1,0,4],[1,0,1,1,0,0,1,0,6],[0,0,1,1,1,0,1,0,6]];
 for(let k=0;k<9;k++)if(patterns[variant][k])for(let n=0;n<3;n++)ints[k].push([35+n*2,35+n*2+.2,patterns[variant][k]]);
 const ts=[0,.025,34.5,35,35.02,35.5,36.2,39,60,120,180],session={history_start_s:-30,activity9:{intervals:ints},targets:ctx.initial_context.targets};
 fixtures.push({ints,targets:session.targets,ts,AP:math.predict(p.AP,session,ts),power:math.predict(p.power,session,ts)});
}
const nom=tm.nominal(p);for(const route of rc.ROUTES)for(const model of ['LOW','CENTRAL','HIGH'])for(const AP of [29,35,40])for(const peers of [[],rc.ROUTES.filter(x=>rc.slot(x)!==rc.slot(route)).slice(0,1).map(route=>({route})),rc.ROUTES.filter(x=>rc.slot(x)!==rc.slot(route)).slice(0,2).map(route=>({route}))])rates.push({route,identity:nom[route].identity,model,AP,peers,residual:nom[route].residual,rate:1/tm.duration(p,nom[route].identity,AP,peers,p.multi.models[model],nom[route].residual)});
process.stdout.write(JSON.stringify({fixtures,rates,seeds:['271017100|phase|0|classification_NPU','271017300|enqueue|127'].map(s=>[s,base.seeded(s)]),new_policy_environments:0}));
