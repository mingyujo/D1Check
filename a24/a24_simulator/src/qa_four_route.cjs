'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const {chromium}=require('C:/Users/chomg/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const O=path.resolve(__dirname,'../../outputs',path.basename(__dirname)),dir=path.join(O,'UI_ACTUAL_01');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8')),hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const used=()=>{const p=path.join(O,'receipts.jsonl');return fs.existsSync(p)?fs.readFileSync(p,'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse).filter(x=>x.event==='START').length:0;};
(async()=>{fs.mkdirSync(dir);let browser;const checks=[],errors=[],remote=[];const check=(s,b)=>{assert(b,s);checks.push(s);};const before=used();
try{
 const cfg=await(await fetch('http://127.0.0.1:8766/api/config')).json();assert(!cfg.job?.running);assert.equal(before,0);
 browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});const context=await browser.newContext({viewport:{width:1280,height:950}}),page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:8766/'))remote.push(r.url());});
 await page.goto('http://127.0.0.1:8766/');await page.waitForFunction(()=>document.getElementById('bulkStatus').textContent.includes('남은 계산'));
 check('Four-route scope visible',(await page.locator('#routeScope').innerText()).includes('탐지 D → CPU / GPU'));
 await page.locator('details.advanced').first().locator('summary').click();
 for(const [id,v] of Object.entries({bulkCounts:'8',bulkMixes:'0, 50',bulkSlacks:'1.5',bulkSeeds:'20261026'})){await page.fill('#'+id,v);await page.locator('#'+id).dispatchEvent('change');}
 await page.selectOption('#bulkPattern','burst');await page.locator('#bulkPattern').dispatchEvent('change');
 check('Predeclared D-only and mixed cases',(await page.locator('#bulkPreview').innerText()).includes('2조건 × 7정책'));
 await page.click('#bulkRun');await page.waitForFunction(()=>document.getElementById('bulkStatus').textContent.includes('계산·저장·집계 완료'),null,{timeout:600000});
 const status=await(await fetch('http://127.0.0.1:8766/api/status')).json(),suite=await(await fetch('http://127.0.0.1:8766/api/suite?id='+status.job.id)).json();
 check('All 14 environments complete',suite.aggregate.complete_conditions===2&&suite.aggregate.failed_conditions===0&&used()-before===14);
 for(const c of suite.cases){const r=c.result;check('Four-route result scope '+c.index,JSON.stringify(r.bindings.legal_route_scope)===JSON.stringify({C:['CPU','GPU'],D:['CPU','GPU']}));
  const fifo=r.rows.find(r=>r.policy==='FIFO_FREE');check('D_GPU actually dispatched by free FIFO '+c.index,fifo.route_counts.D_GPU>0);check('D_CPU remains selectable '+c.index,fifo.route_counts.D_CPU>0);
  for(const p of ['ROLLING_ATC_RL','ROLLING_ATC_RL_NO_WAIT']){const row=r.rows.find(r=>r.policy===p);check('Actor D_GPU physical/action mask legal '+c.index+p,row.D_GPU_legal_action_slots>0);check('Old checkpoint remains frozen '+c.index+p,/^[a-f0-9]{64}$/.test(row.network_sha256)&&row.actor_decisions>0);}
  for(const row of r.rows){const counts=row.route_counts;check('No missing route count '+c.index+row.policy,Object.values(counts).reduce((a,b)=>a+b,0)===row.metrics.planned);check('Conditional model J/AP finite '+c.index+row.policy,Number.isFinite(row.J_proxy)&&Number.isFinite(row.AP_mean_c));check('No measured J claim '+c.index+row.policy,row.measured_J===null);}
  check('Common four-route timing '+c.index,r.bindings.timing_model_digest===read(path.join(O,'REGISTRATION.json')).expected_four_route_timing_digest);
 }
 check('No old three-route cache used',suite.cases.every(c=>!c.reused));
 await page.click('[data-open-case="0"]');check('Seven route census display rows',await page.locator('#routeCounts tr').count()===7);check('D_GPU display matches raw',await page.locator('#routeCounts tr').filter({hasText:'FIFO · CPU/GPU 자유배정'}).locator('td').nth(4).innerText()===String(suite.cases[0].result.rows.find(r=>r.policy==='FIFO_FREE').route_counts.D_GPU));
 for(const theme of ['light','dark'])for(const width of [360,736,1280]){await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme:theme});await page.locator('#routeScope').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,`${theme}_${width}.png`)});check('No body overflow '+theme+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
 await page.setViewportSize({width:1280,height:950});await page.locator('#routeCounts').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,'route_counts.png')});
 const downloadPromise=page.waitForEvent('download');await page.click('#bulkExport');const download=await downloadPromise;await download.saveAs(path.join(dir,'exported_suite.json'));check('Export exact suite',read(path.join(dir,'exported_suite.json')).id===suite.id);
 await page.click('#bulkRun');await page.waitForFunction(()=>document.getElementById('bulkStatus').textContent.includes('계산·저장·집계 완료'),null,{timeout:60000});const status2=await(await fetch('http://127.0.0.1:8766/api/status')).json(),saved=await(await fetch('http://127.0.0.1:8766/api/suite?id='+status2.job.id)).json();check('Exact four-route cache no additional START',saved.cases.every(c=>c.reused)&&used()-before===14);assert.deepEqual(saved.aggregate,suite.aggregate);checks.push('Cached aggregate byte-equivalent values');
 check('No JS/console errors',errors.length===0);check('No remote requests',remote.length===0);
 const result={status:'PASS',utc:new Date().toISOString(),checks,check_count:checks.length,new_START:14,actual_suite:suite.id,cached_suite:saved.id,route_usage:suite.cases.map(c=>({condition:c.condition,rows:c.result.rows.map(r=>({policy:r.policy,route_counts:r.route_counts,D_GPU_legal_action_slots:r.D_GPU_legal_action_slots}))})),new_training:0,measured_J:null,physical_goal_verified:false,source_sha256:hash(__filename)};
 fs.writeFileSync(path.join(dir,'RESULT.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});fs.writeFileSync(path.join(dir,'COMPLETE.json'),JSON.stringify({result_sha256:hash(path.join(dir,'RESULT.json'))})+'\n',{flag:'wx'});console.log(JSON.stringify({status:'PASS',checks:checks.length,new_START:14,actual_suite:suite.id}));
}catch(e){fs.writeFileSync(path.join(dir,'FAILURE.json'),JSON.stringify({error:e.stack,checks,errors,remote,START:used()})+'\n',{flag:'wx'});throw e;}finally{if(browser)await browser.close();}})().catch(e=>{console.error(e.stack);process.exitCode=1;});
