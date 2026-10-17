'use strict';
// Copy only closed immutable files; never stage a live receipt or open result.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),seed=Number(process.argv[2]);
if(![3701,3702,3703].includes(seed))throw Error('Registered seed');
const read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),training=read(path.join(out,'TRAINING_S'+seed+'.json'));
if(training.episodes!==128||training.updates!==64)throw Error('Seed not complete');
const text=fs.readFileSync(path.join(out,'receipts.jsonl'),'utf8'),lines=text.trim().split(/\r?\n/),receipts=lines.map(JSON.parse);
const final='TRAIN_S'+seed+'_EP128',at=receipts.findIndex(r=>r.event==='COMPLETE'&&r.label===final);
if(at<0)throw Error('Exact completed frontier required');
const completed=receipts.slice(0,at+1).filter(r=>r.event==='COMPLETE'&&r.label.startsWith('TRAIN_S'+seed+'_'));
if(completed.length!==128)throw Error('Closed seed denominator');
const files=[];
for(const r of completed){
 const summary=path.join(out,r.label+'.json'),raw=path.join(out,r.label+'.raw.json.gz');
 if(sha(summary)!==r.result_sha256||sha(raw)!==r.raw_sha256)throw Error('Closed file changed');
 files.push(summary,raw,path.join(out,r.label+'.prepared.json.gz'),path.join(out,r.label+'.frames.pt.gz'));
}
files.push(...fs.readdirSync(out).filter(f=>f.startsWith('UPDATE_S'+seed+'_')||f.startsWith('SEED_'+seed+'_')||f==='TRAINING_S'+seed+'.json').map(f=>path.join(out,f)));
if(seed===3701)files.push(...['START.json','NOMINAL_PREFLIGHT.json','P0.json','P0_0_OLD.json.gz','P0_0_NEW.json.gz','P0_1_OLD.json.gz','P0_1_NEW.json.gz'].map(f=>path.join(out,f)));
const prefix=path.join(out,'SAVED_PREFIX_S'+seed+'.jsonl');fs.writeFileSync(prefix,lines.slice(0,at+1).join('\n')+'\n',{flag:'wx'});files.push(prefix);
const proof=path.join(out,'PROGRESS_S'+seed+'.json');
fs.writeFileSync(proof,JSON.stringify({schema:'A24-coupled345-completed-seed-milestone-v1',seed,episodes:128,updates:64,Adam_steps:training.Adam_steps,
 source_operation_sha256:sha(path.join(__dirname,'OPERATION.json')),generation_complete:false,DEV_selection_done:false,
 files:files.map(p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size})),
 live_receipt_not_staged:true,new_environment_START:0,new_fit:0,new_NN_updates:0},null,2)+'\n',{flag:'wx'});
files.push(proof);const listing=path.join(__dirname,'PROGRESS_FILES_S'+seed+'.txt');
fs.writeFileSync(listing,files.map(p=>path.relative(repo,p).replaceAll('\\','/')).join('\n')+'\n',{flag:'wx'});
console.log(JSON.stringify({seed,files:files.length,episodes:128,updates:64,Adam_steps:training.Adam_steps,pathspec:path.relative(repo,listing).replaceAll('\\','/')}));
