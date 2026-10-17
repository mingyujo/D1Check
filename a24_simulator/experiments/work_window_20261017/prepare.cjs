'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const pin=p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const parent='results/COUPLED_345_20261017_01',diagnosis='results/SAVINGS_LIMIT_V2_20261017_01';
const previous=read(path.join(root,parent,'RESULT.json')),next=read(path.join(root,diagnosis,'RESULT.json'));
const rows=[...previous.rows.filter(x=>x.kind==='FRESH'),...next.rows.filter(x=>x.kind==='FULL_WITNESS')];
if(rows.length!==132)throw Error('Exact96 original +36 offline rows required');
const files=[...['RESULT.json','COMPLETE.json','AUDIT.json'].flatMap(f=>[path.join(root,parent,f),path.join(root,diagnosis,f)]),path.join(root,diagnosis,'ANALYSIS.json'),path.join(root,diagnosis,'BOUNDS.json'),
 path.join(root,'experiments/coupled_345_20261017/INPUTS.json'),path.join(root,'experiments/coupled_345_20261017/OPERATION.json'),
 ...rows.map(r=>path.join(root,r.kind==='FRESH'?parent:diagnosis,r.label+'.raw.json.gz')),
 ...Array.from({length:12},(_,i)=>path.join(root,diagnosis,'FRESH_'+String(i).padStart(2,'0')+'.BANK.json.gz'))];
const op={schema:'A24-saved-work-window-reaccount-v1',utc:new Date().toISOString(),base_commit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),
 user_authority:'2026-10-17: shorten consumption scope to the task-processing interval',sources:['prepare.cjs','reaccount.cjs','audit.cjs','publish.cjs'].map(f=>pin(path.join(__dirname,f))),inputs:[...new Set(files)].map(pin),
 parent,diagnosis,output:'results/WORK_WINDOW_20261017_01',cases:12,saved_schedules:132,
 primary_policies:['EDF','FIFO','RR','ATC','EXACT','RL_S3701','RL_S3702','RL_S3703'],
 start:'35s, original common first scheduled arrival',
 windows:{original:'same original drain end, retained historical result',common:'maximum actual AVAILABLE among all8 frozen original policies for each case; same endpoint for all policies; posthoc descriptive window, not a new independent evaluation',completion:'each policy own final AVAILABLE, including waiting between jobs; task-completion energy, with differing durations disclosed'},
 failure_policy:'Any missing AVAILABLE keeps the original drain endpoint and is ineligible; no dropped requests',
 common_bound:'Reuse conservative work-energy lower bound and add the shorter common baseline; only valid for schedules completing all jobs by that common endpoint under original count SLA',
 completion_bound:'Reuse work lower bound and add baseline times an optimistic completion-time lower bound from releases/cold full work and two-lane capacity;1microsecond time safety margin; all jobs still required complete by original drain; no new solver',
 temperature:'same common energy window is the primary shortened AP window; own-completion mean has different duration and is descriptive only; previous AP/service window preserved',
 claims:'Posthoc metric change after seeing original evaluation. Original10%/.5C result is not retroactively promoted to PASS; no retraining or policy change.',
 native_START:0,training:0,model_fit:0,optimization_solves:0,new_reservation:0,source_results_immutable:true};
fs.writeFileSync(path.join(__dirname,'OPERATION.json'),JSON.stringify(op,null,2)+'\n',{flag:'wx'});console.log('REGISTERED_SAVED_REACCOUNT_132_NATIVE0');
