'use strict';
// Consolidation copies exact immutable bytes; performs no native execution.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const pin=p=>({path:p,sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),bytes:fs.statSync(p).size});
const op=read(path.join(__dirname,'OPERATION.json')),cont=read(path.join(__dirname,'CONTINUATION_OPERATION.json'));
const old=path.join(root,op.output_dir),fresh=path.join(root,cont.output_dir),next=read(path.join(fresh,'RESULT.json'));
const terminal=read(path.join(fresh,'COMPLETE.json'));
if(terminal.result_sha256!==pin(path.join(fresh,'RESULT.json')).sha256||terminal.new_START!==2||terminal.new_COMPLETE!==2)throw Error('Continuation terminal binding');
for(const p of [...cont.sources,...cont.input_pins])if(pin(p.path).sha256!==p.sha256)throw Error('Continuation immutable source/input');
const folders=[old,fresh],all=[],receipts=[],pins=[];
for(const folder of folders){
 const p=path.join(folder,'receipts.jsonl'),events=fs.readFileSync(p,'utf8').trim().split('\n').map(JSON.parse);
 if(events.some(e=>e.event==='FAIL'))throw Error('Native FAIL present');receipts.push(...events);pins.push(pin(p));
 const started=new Map(events.filter(e=>e.event==='START').map(e=>[e.label,e.identity]));
 if(started.size!==events.filter(e=>e.event==='COMPLETE').length)throw Error('Open native START');
 for(const event of events.filter(e=>e.event==='COMPLETE')){
  const file=path.join(folder,event.label+'.json'),r=read(file),raw=path.join(folder,event.label+'.raw.json.gz');
  if(started.get(event.label)!==event.identity)throw Error('Native lifecycle identity mismatch');
  if(pin(file).sha256!==event.result_sha256||pin(raw).sha256!==r.raw_sha256)throw Error('Native row/raw binding');
  all.push({folder,row:r});pins.push(pin(file),pin(raw));
  if(r.frames_sha256){const frames=path.join(folder,r.label+'.frames.pt.gz');if(pin(frames).sha256!==r.frames_sha256)throw Error('Frame pin');pins.push(pin(frames));}
 }
}
if(all.length!==20||new Set(all.map(x=>x.row.label)).size!==20||next.new_START!==2||read(path.join(old,'FAILURE.json')).new_START!==18)throw Error('18plus2 only');
const out=path.join(root,'results/SUSTAINED_LOAD_REPORT_20261017_01');fs.mkdirSync(out);
fs.writeFileSync(path.join(out,'START.json'),JSON.stringify({utc:new Date().toISOString(),saved_merge_only:true,new_environment_START:0,command:process.argv,HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim()},null,2)+'\n',{flag:'wx'});
for(const {folder,row:r} of all){
 for(const suffix of ['.json','.raw.json.gz',...(r.frames_sha256?['.frames.pt.gz']:[])])fs.copyFileSync(path.join(folder,r.label+suffix),path.join(out,r.label+suffix),fs.constants.COPYFILE_EXCL);
}
fs.copyFileSync(path.join(old,'P0.json'),path.join(out,'P0.json'),fs.constants.COPYFILE_EXCL);
fs.writeFileSync(path.join(out,'receipts.jsonl'),receipts.map(x=>JSON.stringify(x)).join('\n')+'\n',{flag:'wx'});
const result={status:'COMPLETED20_NATIVE_ACROSS18_PLUS2_WITH_PRESERVED_GUARD_INTERRUPTION',rows:all.map(x=>x.row),
 new_START:20,new_COMPLETE:20,new_FAIL:0,new_environment_START_in_this_saved_merge:0,
 original_operation:pin(path.join(__dirname,'OPERATION.json')),continuation_operation:pin(path.join(__dirname,'CONTINUATION_OPERATION.json')),
 original_orchestration_failure:pin(path.join(old,'FAILURE.json')),original_native_START:18,continuation_native_START:2,
 network_sha256:next.network_sha256,counters:next.counters,continuation_network_and_training_RNG_unchanged:next.network_and_training_RNG_unchanged,
 original_final_runtime_RNG_counter_attestation_available:false,original_network_evidence:'Saved every neural frame digest/collect=false plus independent CP action replay; immutable argmax/no update source',
 frozen_bank_restores_total:2,new_training:0,new_physical_fit:0,measured_J:null};
fs.writeFileSync(path.join(out,'RESULT.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
fs.writeFileSync(path.join(out,'MERGE_MANIFEST.json'),JSON.stringify({utc:new Date().toISOString(),sources:pins,
 source_sha256:pin(__filename).sha256,source_outputs:folders,saved_only_new_START:0,all_copies_byte_identical:true,
 original_failure_preserved:pin(path.join(old,'FAILURE.json')),new20_native_identity_count:20},null,2)+'\n',{flag:'wx'});
fs.writeFileSync(path.join(out,'COMPLETE.json'),JSON.stringify({utc:new Date().toISOString(),result_sha256:pin(path.join(out,'RESULT.json')).sha256,
 referenced_native_START:20,referenced_native_COMPLETE:20,new_environment_START:0},null,2)+'\n',{flag:'wx'});
console.log('Saved-only assembly18plus2; no original namespace modified.');
