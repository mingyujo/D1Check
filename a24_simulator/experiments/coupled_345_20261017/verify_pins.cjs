'use strict';
// Hash checks only: no environment, model fitting, or neural update.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root);
const read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir);
if(!fs.existsSync(path.join(out,'COMPLETE.json')))throw Error('Completed operation required');
const checks=[];
function visit(value){
 if(!value||typeof value!=='object')return;
 if(typeof value.path==='string'&&typeof value.sha256==='string'&&typeof value.bytes==='number'){
  const p=path.isAbsolute(value.path)?value.path:path.join(repo,value.path);
  if(sha(p)!==value.sha256||fs.statSync(p).size!==value.bytes)throw Error('Pinned bytes changed: '+value.path);
  checks.push({path:value.path,sha256:value.sha256,bytes:value.bytes});
 }
 for(const child of Object.values(value))if(child&&typeof child==='object')visit(child);
}
if(process.argv.includes('--proof')){
 const proof=path.join(out,'FINAL_HANDOFF_PROOF.json');visit(read(proof));
 console.log(JSON.stringify({status:'PASS_FINAL_PROOF_BYTES',checks:checks.length,proof_sha256:sha(proof)}));
}else{
 const definitions=fs.readdirSync(__dirname).filter(f=>/OPERATION.*\.json$/.test(f));
 for(const file of definitions)visit(read(path.join(__dirname,file)));
 const value={status:'PASS_ALL_OPERATION_SOURCE_AND_INPUT_PINS',definitions,checks,
  new_environment_START:0,new_training:0,new_fit:0};
 fs.writeFileSync(path.join(out,'SOURCE_PIN_VERIFICATION.json'),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({status:value.status,definitions:definitions.length,checks:checks.length}));
}
