'use strict';
const fs=require('fs'),path=require('path'),{spawnSync}=require('child_process');
const O=__dirname,B=path.resolve(O,'../..'),P=path.join(B,'work/S26-GITHUB-HANDOFF-20261016/repository/s26_simulator'),D=path.join(P,'experiments/state_aware_v1');
const read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,''));
const summary=read(path.join(D,'SUMMARY.json'));let checks=0;
function test(ok,label){if(!ok)throw Error(label);checks++}
function cli(args){const r=spawnSync(process.execPath,[path.join(P,'cli/s26.cjs'),...args],{encoding:'utf8'});test(r.status===0,'CLI success '+args.join(' '));return JSON.parse(r.stdout)}
for(const bank of ['ALL','M128_BASE','SMOOTH128_BASE','COMPETE_A','COMPETE_B']){
 const result=cli(['replay','--comparison','state-aware-v1','--bank',bank]),expected=bank==='ALL'?summary.all:summary.tables.filter(x=>x.bank===bank);
 test(result.results.length===6,'six policies retained');test(result.new_simulator_instances===0&&result.new_training===0,'stored results only');
 for(const row of result.results){const x=expected.find(x=>x.policy===row.policy);for(const [a,b]of [['cases','cases'],['hard_feasible_cases','feasible'],['on_time_rate','on_time_rate'],['urgent_on_time_rate','urgent_on_time_rate'],['normal_on_time_rate','normal_on_time_rate'],['API_J_mean','J'],['AP_C_mean','AP'],['AP_peak_mean','peak'],['AP180_mean','AP180'],['unfinished','unfinished'],['tardiness_s','tardiness']])test(row[a]===x[b],bank+' '+row.policy+' '+a);test(JSON.stringify(row.route_counts)===JSON.stringify(x.route_counts),'actual route counts');}
}
const selected=cli(['replay','--comparison','state-aware-v1','--policy','ATC_STATE','--bank','COMPETE_A']);test(selected.results.length===1&&selected.results[0].policy==='ATC_STATE','policy filter');
for(const args of [['--bank','M128'],['--policy','DOES_NOT_EXIST']]){const r=spawnSync(process.execPath,[path.join(P,'cli/s26.cjs'),'replay','--comparison','state-aware-v1',...args],{encoding:'utf8'});test(r.status!==0,'invalid filter rejected')}
for(const comparison of ['legacy','fair-resource-v1'])test(cli(['replay','--comparison',comparison]).results.length>0,'previous stored comparison preserved');
const result={status:'PASS',checks,new_policy_environments:0,new_NN:0,new_fit:0,source_summary:'SUMMARY.json',method:'Real CLI output for all five bank selections and a policy filter compared to audited full summary; invalid filter rejection and previous comparisons retained.'};
fs.writeFileSync(path.join(O,'PUBLIC_CLI_QA.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
fs.copyFileSync(path.join(O,'PUBLIC_CLI_QA.json'),path.join(D,'PUBLIC_CLI_QA.json'),fs.constants.COPYFILE_EXCL);
console.log(JSON.stringify(result));
