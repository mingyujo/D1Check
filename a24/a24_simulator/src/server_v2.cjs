'use strict';
// Explicit one-shot jobs only. No timer launches a simulation or remote query.
const http=require('http'),fs=require('fs'),path=require('path'),crypto=require('crypto');
const {spawn,execFile}=require('child_process'),bulk=require('./bulk_design.cjs');
const W=__dirname,B=path.resolve(W,'..'),O=path.join(B,'runtime');
const REG=path.join(B,'runtime/registration.json'),PORT=Number(process.env.PORT||8766),HOST='127.0.0.1',ORIGIN=`http://${HOST}:${PORT}`;
const PY=process.env.A24_PYTHON||(process.platform==='win32'?'python':'python3'),token=crypto.randomBytes(24).toString('hex');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const json=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,''));
const stable=x=>Array.isArray(x)?'['+x.map(stable).join(',')+']':x&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+stable(x[k])).join(',')+'}':JSON.stringify(x);
const digest=x=>crypto.createHash('sha256').update(stable(x)).digest('hex');
const idOK=id=>typeof id==='string'&&/^[a-f0-9-]{1,64}$/.test(id);
const normalize=x=>({requests:x.requests.map((q,i)=>({ordinal:i,profile:q.profile,priority:q.priority||'N',arrival_s:q.arrival_s,deadline_s:q.deadline_s})),seed:x.seed??20261016,rl_seed:x.rl_seed??46201,initial_context:x.initial_context??'M128',alpha:x.alpha??.95});
function writeNew(p,x){fs.mkdirSync(path.dirname(p),{recursive:true});const fd=fs.openSync(p,'wx');try{fs.writeFileSync(fd,JSON.stringify(x,null,2)+'\n','utf8');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}}
function progress(p,x){const tmp=p+'.tmp';fs.writeFileSync(tmp,JSON.stringify(x,null,2)+'\n');fs.renameSync(tmp,p);}
const pathMap=json(path.join(B,'data/PATH_MAP.json'));function resolvePin(p){const v=pathMap[p.replace(/\\/g,'/').toLowerCase()];return v?path.join(B,'.cache',v.sha256):p;}
function registration(){const r=json(REG);for(const p of [...r.source_pins,...r.input_pins])if(hash(resolvePin(p.path))!==p.sha256)throw Error('등록 SHA 불일치: '+path.basename(p.path));return r;}
function used(){const p=path.join(O,'receipts.jsonl');if(!fs.existsSync(p))return 0;const a=fs.readFileSync(p,'utf8').split(/\r?\n/);a.pop();return a.filter(Boolean).map(JSON.parse).filter(x=>x.event==='START').length;}
const remaining=()=>json(REG).environment_cap-used();
function allBatches(){return [O,...(json(REG).cache_roots||[])].flatMap(root=>{const p=path.join(root,'batches');return fs.existsSync(p)?fs.readdirSync(p).filter(idOK).map(id=>({id,dir:path.join(p,id),time:fs.statSync(path.join(p,id)).birthtimeMs})):[];}).sort((a,b)=>b.time-a.time);}
function readResult(dir){const p=path.join(dir,'RESULT.json'),done=path.join(dir,'COMPLETE.json');if(!fs.existsSync(p)||!fs.existsSync(done))return null;if(hash(p)!==json(done).result_sha256)throw Error('저장 결과 SHA 불일치');return json(p);}
function result(id){if(!idOK(id))throw Error('실행 식별자 오류');const b=allBatches().find(b=>b.id===id);return b?readResult(b.dir):null;}
function prior(input){const key=stable(normalize(input));for(const b of allBatches()){const p=path.join(b.dir,'BATCH_REGISTERED.json');if(fs.existsSync(p)&&stable(json(p).input)===key){const r=readResult(b.dir);if(!r)throw Error('동일 입력·seed의 미종결/실패 기록이 있어 재계산을 막았습니다: '+b.id);return {id:b.id,dir:b.dir,result:r};}}return null;}
function guard(){return new Promise((resolve,reject)=>execFile(PY,['-B',path.join(B,'tools/guard.py')],{windowsHide:true,encoding:'utf8',timeout:20000},(e,o)=>{if(e)return reject(e);try{resolve(JSON.parse(o.replace(/^\uFEFF/,'')));}catch(x){reject(x);}}));}
async function canRun(){const g=await guard();if(!g.ok)throw Error('다른 계산이 진행 중이거나 디스크 여유 조건이 맞지 않습니다. 자동 재시작하지 않습니다.');return g;}
let job=null,launching=false;
function launch(input,id,onPolicy){
 const requestPath=path.join(O,'requests',id+'.json');writeNew(requestPath,input);
 writeNew(path.join(O,'launches',id+'.json'),{id,requestPath,source_registration_sha256:hash(REG),utc:new Date().toISOString(),automatic_retry:false});
 return new Promise((resolve,reject)=>{
  const child=spawn(PY,['-B',path.join(W,'shared_A24-MODEL-INTEGRATION-20261016_interactive_entry.py'),'--registration',REG,'--request',requestPath,'--batch',id],{windowsHide:true,env:{...process.env,OMP_NUM_THREADS:'1',MKL_NUM_THREADS:'1',PYTHONIOENCODING:'utf-8'}});
  job.pid=child.pid;const out=fs.createWriteStream(path.join(O,'launches',id+'.stdout.log'),{flags:'wx'}),err=fs.createWriteStream(path.join(O,'launches',id+'.stderr.log'),{flags:'wx'});let pending='';
  child.stdout.on('data',b=>{out.write(b);pending+=b.toString();const lines=pending.split(/\r?\n/);pending=lines.pop();for(const s of lines)try{onPolicy(JSON.parse(s));}catch{}});child.stderr.on('data',b=>err.write(b));
  child.on('error',e=>{job.error=e.message;});
  child.on('close',code=>{out.end();err.end();const terminal={id,pid:child.pid,exitCode:code,utc:new Date().toISOString(),automatic_retry:false};writeNew(path.join(O,'launches',id+'.terminal.json'),terminal);if(code!==0)return reject(Error('계산 실패 기록을 보존했습니다. 자동 재실행하지 않습니다.'));try{const r=result(id);if(!r)throw Error('완료 결과가 없어 미종결로 보존했습니다.');resolve(r);}catch(e){reject(e);}});
 });
}
function suiteDir(id){if(!idOK(id))throw Error('묶음 식별자 오류');return path.join(O,'suites',id);}
function suiteState(id){const dir=suiteDir(id);if(!fs.existsSync(path.join(dir,'PLAN.json')))return null;const plan=json(path.join(dir,'PLAN.json'));const p=path.join(dir,'RESULT.json');if(fs.existsSync(path.join(dir,'COMPLETE.json'))){if(hash(p)!==json(path.join(dir,'COMPLETE.json')).result_sha256)throw Error('묶음 결과 SHA 불일치');return {...json(p),finished:true};}return {id,plan,progress:fs.existsSync(path.join(dir,'PROGRESS.json'))?json(path.join(dir,'PROGRESS.json')):null,failed:fs.existsSync(path.join(dir,'FAILURE.json'))?json(path.join(dir,'FAILURE.json')):null,started:fs.existsSync(path.join(dir,'STARTED.json')),finished:false};}
function latestSuite(){const p=path.join(O,'suites');return fs.existsSync(p)?fs.readdirSync(p).filter(idOK).filter(id=>fs.existsSync(path.join(p,id,'PLAN.json'))).sort((a,b)=>fs.statSync(path.join(p,b)).birthtimeMs-fs.statSync(path.join(p,a)).birthtimeMs)[0]||null:null;}
async function runSuite(plan){
 const dir=suiteDir(plan.id),cases=plan.cases.map(c=>({...c,status:'NOT_STARTED',result:null}));
 let done=0;const record=()=>progress(path.join(dir,'PROGRESS.json'),{id:plan.id,completed:done,total:cases.length,cases:cases.map(({result,...c})=>c),utc:new Date().toISOString()});record();
 try{
  for(const c of cases){
   registration();const old=prior(c.input);job.case_index=c.index;job.case_label=c.label;job.message=c.label;
   if(old){c.result=old.result;c.batch_id=old.id;c.reused=true;}else{
    if(remaining()<7)throw Error('남은 등록 계산량이 부족합니다.');await canRun();c.status='RUNNING';record();
    c.result=await launch(c.input,c.batch_id,p=>{job.completed=done*7+p.completed;job.message=`조건 ${done+1}/${cases.length} · ${p.policy} 저장`;});c.reused=false;
   }
   c.status='COMPLETE';done++;job.completed=done*7;record();
  }
 }catch(e){const c=cases.find(c=>c.status==='RUNNING')||cases.find(c=>c.status==='NOT_STARTED');if(c){c.status='FAIL';c.error=e.message;}writeNew(path.join(dir,'FAILURE.json'),{error:e.message,utc:new Date().toISOString(),automatic_retry:false});job.error=e.message;record();}
 const final={id:plan.id,plan_sha256:hash(path.join(dir,'PLAN.json')),design:plan.design,planned_utc:plan.utc,cases,aggregate:bulk.aggregate(cases),utc:new Date().toISOString(),new_START_max:plan.new_START_max,automatic_retry:false,source_registration_sha256:hash(REG)};
 writeNew(path.join(dir,'RESULT.json'),final);writeNew(path.join(dir,'COMPLETE.json'),{result_sha256:hash(path.join(dir,'RESULT.json')),status:job.error?'PARTIAL_WITH_FAILURE':'COMPLETE',utc:new Date().toISOString()});
 job.running=false;job.exitCode=job.error?1:0;job.finished=new Date().toISOString();job.message=job.error||'모든 조건과 정책의 계산·저장·집계 완료';
}
const send=(res,status,x)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(x));};
async function body(req){let s='';for await(const b of req){s+=b;if(s.length>512000)throw Error('입력이 너무 큽니다.');}return JSON.parse(s);}
const server=http.createServer(async(req,res)=>{try{
 if(req.headers.host!==`${HOST}:${PORT}`)return send(res,403,{error:'로컬 주소만 허용합니다.'});const u=new URL(req.url,ORIGIN);
 if(req.method==='GET'&&u.pathname==='/favicon.ico'){res.writeHead(204);return res.end();}
 if(req.method==='GET'&&u.pathname==='/api/config'){const r=json(REG);return send(res,200,{token,catalog:json(resolvePin(r.catalog_pin.path)),remaining:remaining(),cap:r.environment_cap,parent_used:r.parent_START,shared_cap:512,job,latest:allBatches().find(b=>readResult(b.dir))?.id,latest_suite:latestSuite(),policies:r.policies});}
 if(req.method==='GET'&&u.pathname==='/api/status')return send(res,200,{job,remaining:remaining()});
 if(req.method==='GET'&&u.pathname==='/api/result')return send(res,200,result(u.searchParams.get('id'))||{pending:true});
 if(req.method==='GET'&&u.pathname==='/api/suite')return send(res,200,suiteState(u.searchParams.get('id'))||{pending:true});
 if(req.method==='GET'&&u.pathname==='/api/guard')return send(res,200,await guard());
 if(req.method==='POST'){
  if(req.headers['x-a24-token']!==token||req.headers.origin!==ORIGIN)return send(res,403,{error:'화면을 새로 열어 실행해 주세요.'});
  if(launching||job?.running)return send(res,409,{error:'기존 비교가 실행 중입니다.',job});launching=true;
  try{
   const data=await body(req),r=registration();
   if(u.pathname==='/api/suite-plan'){
    const planned=bulk.generate(data);const cases=planned.map(c=>{const old=prior(c.input);return {...c,batch_id:old?.id||crypto.randomUUID(),reuse:!!old,input_digest:digest(c.input)};});
    const cost=cases.filter(c=>!c.reuse).length*7;if(cost>remaining())throw Error(`필요 ${cost}회 / 남은 ${remaining()}회입니다. 조건 수를 줄여 주세요.`);
    const id=crypto.randomUUID(),plan={schema:'A24-one-shot-suite-plan-v1',id,utc:new Date().toISOString(),design:data,cases,new_START_max:cost,reused_conditions:cases.filter(c=>c.reuse).length,policies:r.policies,source_registration_sha256:hash(REG),sampling:'Fixed Cartesian grid, no outcome-adaptive selection',automatic_retry:false,periodic:false};
    writeNew(path.join(suiteDir(id),'PLAN.json'),plan);return send(res,200,{plan,plan_sha256:hash(path.join(suiteDir(id),'PLAN.json')),remaining:remaining()});
   }
   if(u.pathname==='/api/suite-run'){
    const dir=suiteDir(data.id),p=path.join(dir,'PLAN.json');if(hash(p)!==data.plan_sha256)throw Error('조건 봉인 SHA 불일치');const plan=json(p);if(plan.source_registration_sha256!==hash(REG))throw Error('등록 변경');
    if(fs.existsSync(path.join(dir,'COMPLETE.json')))return send(res,200,{cached:true,suite:suiteState(data.id)});
    if(fs.existsSync(path.join(dir,'STARTED.json')))throw Error('이미 시작된 묶음입니다. 자동 재실행하지 않습니다. 저장 상태를 확인하세요.');
    if(plan.new_START_max>remaining())throw Error('남은 계산량이 바뀌었습니다. 조건을 다시 확인하세요.');if(plan.new_START_max)await canRun();
    writeNew(path.join(dir,'STARTED.json'),{utc:new Date().toISOString(),plan_sha256:data.plan_sha256,source_registration_sha256:hash(REG)});job={id:plan.id,kind:'suite',running:true,completed:0,total:plan.cases.length*7,started:new Date().toISOString(),message:'조건 묶음을 계산합니다.'};
    runSuite(plan).catch(e=>{job.running=false;job.error=e.message;job.exitCode=1;job.message='묶음 저장 오류. 자동 재실행하지 않습니다: '+e.message;const fail=path.join(dir,'OPERATOR_FAILURE.json');if(!fs.existsSync(fail))writeNew(fail,{error:e.message,utc:new Date().toISOString()});});return send(res,202,{job});
   }
   if(u.pathname==='/api/run'){
    if(!Array.isArray(data.requests)||data.requests.length<1||data.requests.length>256)throw Error('요청은 1~256개입니다.');const old=prior(data);if(old)return send(res,200,{cached:true,result:old.result});
    if(remaining()<7)throw Error('남은 등록 계산량이 부족합니다.');await canRun();const id=crypto.randomUUID();job={id,kind:'single',running:true,completed:0,total:7,started:new Date().toISOString(),message:'7개 정책 계산 중'};
    launch(data,id,p=>{job.completed=p.completed;job.message=p.policy+' 저장·검산 완료';}).then(()=>{job.running=false;job.exitCode=0;job.message='모든 정책 계산·저장 완료';}).catch(e=>{job.running=false;job.exitCode=1;job.message=e.message;job.error=e.message;});return send(res,202,{job});
   }
  }finally{launching=false;}
 }
 if(req.method==='GET'){
  const allowed={'/':'index_v2.html','/index.html':'index_v2.html','/app.js':'app.js','/bulk.js':'bulk.js','/bulk_design.cjs':'bulk_design.cjs','/style.css':'style.css','/routes.js':'routes.js'};const name=allowed[u.pathname];if(name){res.writeHead(200,{'Content-Type':/\.c?js$/.test(name)?'text/javascript; charset=utf-8':name.endsWith('.css')?'text/css; charset=utf-8':'text/html; charset=utf-8','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"});return res.end(fs.readFileSync(path.join(W,name)));}
 }
 return send(res,404,{error:'없는 경로입니다.'});
}catch(e){return send(res,400,{error:e.message});}});
server.on('error',e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});fs.mkdirSync(path.join(O,'launches'),{recursive:true});
server.listen(PORT,HOST,()=>{writeNew(path.join(O,'SERVER_OWNER_'+process.pid+'.json'),{pid:process.pid,created_utc:new Date().toISOString(),command:process.argv,url:ORIGIN,periodic:false});process.stdout.write(ORIGIN+'\n');});
