'use strict';
const fs=require('fs'),path=require('path'),zlib=require('zlib'),readline=require('readline');
const O=path.resolve(__dirname,'../../results/A24_NN_MARGIN_EXACT_20261021_01'),R=path.resolve(__dirname,'../../..');
const source=fs.readFileSync(path.join(__dirname,'audit.cjs'),'utf8'),prefix=source.slice(0,source.indexOf('const result=read('));
const checker=new Function('require','__dirname',prefix+'\nreturn {auditBank,stats:()=>({checks,maxerr})};')(require,__dirname),cache=new Map();
(async()=>{let labels=0;
 const lines=readline.createInterface({input:fs.createReadStream(path.join(O,'REPLAYED_TRAIN_LABELS.jsonl.gz')).pipe(zlib.createGunzip()),crlfDelay:Infinity});
 for await(const line of lines){const d=JSON.parse(line),p=d.bank_source.path;if(!cache.has(p)){const b=fs.readFileSync(path.join(R,p));cache.set(p,JSON.parse(p.endsWith('.gz')?zlib.gunzipSync(b):b));}checker.auditBank(d.public_state,d.call,cache.get(p),d.config,null,'SAVED_TRAIN_LABEL');labels++;}
 fs.writeFileSync(path.join(O,'AUDIT_LABELS_JS.json'),JSON.stringify({status:'PASS',...checker.stats(),labels,scope:'Independent public normalization/features/service mask/teacher targets on saved TRAIN states',new_environment:0,new_fit:0},null,2)+'\n',{flag:'wx'});console.log('SAVED_LABEL_AUDIT_PASS',labels,checker.stats());
})().catch(e=>{console.error(e);process.exitCode=1;});
