'use strict';
// Publish closed DEV evidence and the already-frozen selection; never reselect.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir);
const selection=read(path.join(out,'SELECTION_FROZEN.json'));
if(selection.fresh_outcomes_opened!==0)throw Error('Frozen DEV-only selection required');
const lines=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8').trim().split(/\r?\n/),rows=lines.map(JSON.parse);
const completed=rows.filter(r=>r.event==='COMPLETE'&&r.kind==='DEV');
if(completed.length!==42)throw Error('All closed DEV runs required');
const files=[path.join(out,'SELECTION_FROZEN.json')];
for(const r of completed){
 const summary=path.join(out,r.label+'.json'),raw=path.join(out,r.label+'.raw.json.gz');
 if(sha(summary)!==r.result_sha256||sha(raw)!==r.raw_sha256)throw Error('Closed DEV bytes changed');
 files.push(summary,raw,path.join(out,r.label+'.prepared.json.gz'));
 const frames=path.join(out,r.label+'.frames.pt.gz');if(fs.existsSync(frames))files.push(frames);
}
const at=rows.findLastIndex(r=>r.event==='COMPLETE'&&r.kind==='DEV');
const prefix=path.join(out,'SAVED_DEV_PREFIX.jsonl');fs.writeFileSync(prefix,lines.slice(0,at+1).join('\n')+'\n',{flag:'wx'});files.push(prefix);
const proof=path.join(out,'DEV_STAGE_PROOF.json');
fs.writeFileSync(proof,JSON.stringify({schema:'A24-coupled345-closed-dev-selection-proof-v1',utc:new Date().toISOString(),
 selected:selection.selected,qualification_is_not_assumed:true,all_42_DEV_runs_preserved:true,
 frozen_before_first_fresh_START:rows.findIndex(r=>r.event==='START'&&r.kind==='FRESH')>at,
 publication_is_during_fresh_stage:true,no_new_winner_selected:true,new_environment_START:0,
 files:files.map(p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size}))},null,2)+'\n',{flag:'wx'});files.push(proof);
const listing=path.join(__dirname,'DEV_FILES.txt');fs.writeFileSync(listing,files.map(p=>path.relative(repo,p).replaceAll('\\','/')).join('\n')+'\n',{flag:'wx'});
const cont=path.join(root,'CONTINUE.json'),state=read(cont);
state.coupled_345_development.status='FRESH_AND_ABLATION_RUNNING';state.coupled_345_development.frozen_selection=selection.selected;
state.coupled_345_development.DEV_proof='results/COUPLED_345_20261017_01/DEV_STAGE_PROOF.json';
fs.writeFileSync(cont,JSON.stringify(state,null,2)+'\n');
console.log(JSON.stringify({files:files.length,selected:selection.selected,no_new_environment:true}));
