'use strict';
// Saved-only independent verification of the finite-class certificate.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),r=read(path.join(out,'RESULT.json'));
let checks=0,eligible=0,ineligible=0;const need=(b,s)=>{checks++;if(!b)throw Error(s);};
const classes={};
for(const row of r.rows.filter(x=>x.kind==='MICRO_LIST')){
 const p=path.join(out,row.label+'.raw.json.gz');need(sha(p)===row.raw_sha256,'Raw SHA');
 const raw=JSON.parse(zlib.gunzipSync(fs.readFileSync(p))),jobs=raw.result.requests,plan=row.extra.plan;
 const target=jobs.map(x=>x.request_id).sort();
 const permute=a=>a.length===0?[[]]:a.flatMap((x,i)=>permute(a.filter((_,j)=>j!==i)).map(z=>[x,...z]));
 if(!classes[row.case]){
  const expected=new Set();for(let mask=0;mask<16;mask++){
   const cpu=target.filter((_,i)=>(mask>>i)&1),gpu=target.filter((_,i)=>!((mask>>i)&1));
   for(const a of permute(cpu))for(const b of permute(gpu))expected.add(JSON.stringify([a,b]));
  }
  classes[row.case]={expected,seen:new Set()};
 }
 const key=JSON.stringify([plan.CPU,plan.GPU]),c=classes[row.case];
 need(c.expected.has(key)&&!c.seen.has(key),'Exact list-class coverage without duplicates');c.seen.add(key);
 if(row.list_plan_eligible){
  eligible++;need(!row.list_violations.length,'No hidden list violation');
  for(const lane of ['CPU','GPU']){
   const actual=jobs.filter(x=>x.route===lane).sort((a,b)=>a.dispatch_ns-b.dispatch_ns).map(x=>x.request_id);
   need(JSON.stringify(actual)===JSON.stringify(plan[lane]),'Eligible native dispatch follows full assigned lane list');
  }
 }else{ineligible++;need(row.list_violations.length>0,'Ineligibility must have a recorded violation');}
}
need(Object.keys(classes).length===2&&Object.values(classes).every(c=>c.expected.size===120&&c.seen.size===120),'All120 plans in each preselected mixed4 case');
const value={status:'PASS_INDEPENDENT_FINITE_LIST_CLASS_AUDIT',utc:new Date().toISOString(),command:process.argv,HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:true,checks,eligible,ineligible,result_sha256:sha(path.join(out,'RESULT.json')),source_sha256:sha(__filename),new_environment_START:0,new_fit:0,scope:'Exact enumerated class coverage and native dispatch list adherence for every marked eligible plan; no continuous-time/global optimum claim'};
fs.writeFileSync(path.join(out,'MICRO_AUDIT.json'),JSON.stringify(value,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(value,null,2));
